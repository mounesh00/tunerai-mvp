"""Celery tasks: training + evaluation jobs."""

from __future__ import annotations

import json
import logging
import os
import traceback
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)
STORAGE_ROOT = Path(os.environ.get("TUNERAI_STORAGE", "/tmp/tunerai/storage"))


def _sync_db_session():
    """Sync-style session for Celery workers (simpler than async in workers)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://tunerai:tunerai_dev_password@localhost:5432/tunerai",
    )
    # Workers use sync driver
    sync_url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )
    if sync_url.startswith("postgresql+asyncpg"):
        sync_url = sync_url.replace("+asyncpg", "")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def _download_dataset_from_r2(storage_path: str) -> bytes:
    """Fetch dataset bytes from Cloudflare R2 using a sync boto3 client.

    Celery tasks run synchronously, so this uses boto3 (not aioboto3, which
    the async FastAPI app uses) with the same S3-compatible configuration.
    """
    import boto3

    from app.core.config import get_settings

    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
    )
    response = client.get_object(Bucket=settings.s3_bucket_name, Key=storage_path)
    return response["Body"].read()


@celery_app.task(bind=True, name="workers.tasks.run_training_job")
def run_training_job(self, training_run_id: str) -> Dict[str, Any]:
    """Execute a training run: PREPARING → TRAINING → EVALUATING → PACKAGING → COMPLETED."""
    from datetime import datetime, timezone

    session = _sync_db_session()
    try:
        from app.models.training import TrainingRun
        from app.models.dataset import DatasetVersion

        run = session.get(TrainingRun, UUID(training_run_id))
        if run is None:
            return {"error": "training_run_not_found"}

        def set_status(status: str, **kwargs: Any) -> None:
            run.status = status
            for k, v in kwargs.items():
                if hasattr(run, k):
                    setattr(run, k, v)
            session.commit()

        if run.status == "CANCELLED":
            return {"status": "CANCELLED"}

        set_status("PREPARING", progress=0.02, started_at=datetime.now(timezone.utc).isoformat())

        dv = session.get(DatasetVersion, run.dataset_version_id)
        if dv is None:
            set_status("FAILED", error_message="Dataset version not found")
            return {"status": "FAILED"}

        # Fetch dataset content from R2 (dv.storage_path is an R2 object key,
        # not a local filesystem path — datasets are stored in Cloudflare R2
        # since the Phase 3 storage migration)
        try:
            from botocore.exceptions import BotoCoreError, ClientError

            content_bytes = _download_dataset_from_r2(dv.storage_path)
        except (BotoCoreError, ClientError) as e:
            set_status("FAILED", error_message=f"Unable to fetch dataset from object storage: {e}")
            return {"status": "FAILED"}

        text = content_bytes.decode("utf-8")
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        from ml.data.validator import DatasetValidator

        validator = DatasetValidator()
        # Re-validate in-memory for train/val split
        validation = validator.validate_text(text)
        train_records = validation.train_records or records
        eval_records = validation.validation_records or []

        from app.models.training import TrainingConfig

        tcfg = session.get(TrainingConfig, run.training_config_id)
        config = dict(tcfg.config) if tcfg else {}

        out_dir = STORAGE_ROOT / str(run.organization_id) / "runs" / str(run.id)
        out_dir.mkdir(parents=True, exist_ok=True)

        set_status("TRAINING", progress=0.1)

        def progress_cb(p: float, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
            run.progress = min(0.85, 0.1 + p * 0.7)
            run.logs = (run.logs or "") + f"\n{msg}"
            if extra and "train_loss" in extra:
                run.train_loss = extra["train_loss"]
            if extra and "epoch" in extra:
                run.current_epoch = extra["epoch"]
            session.commit()

        from ml.training.pipeline import run_training

        dry = os.environ.get("TUNERAI_DRY_RUN", "true").lower() in ("1", "true", "yes")
        result = run_training(
            base_model=run.base_model,
            train_records=train_records,
            eval_records=eval_records,
            config=config,
            output_dir=str(out_dir),
            dry_run=dry,
            progress_cb=progress_cb,
        )

        set_status(
            "EVALUATING",
            progress=0.88,
            train_loss=result.get("train_loss"),
            eval_loss=result.get("eval_loss"),
            artifact_path=result.get("adapter_path"),
            metrics=result.get("metrics"),
        )

        # Evaluation: base vs tuned (mock generators in dry-run)
        from ml.evaluation.engine import compare_base_vs_tuned, mock_generate_factory

        comparison = compare_base_vs_tuned(
            mock_generate_factory("base"),
            mock_generate_factory("tuned"),
        )

        set_status("PACKAGING", progress=0.95, metrics={**(run.metrics or {}), "evaluation": comparison})

        # Register model version
        from app.models.model_registry import Model, ModelVersion

        model_name = f"{run.base_model.split('/')[-1]}-tuned"
        model = (
            session.query(Model)
            .filter(Model.project_id == run.project_id, Model.name == model_name)
            .first()
        )
        if model is None:
            model = Model(
                organization_id=run.organization_id,
                project_id=run.project_id,
                name=model_name,
                domain="cybersecurity",
            )
            session.add(model)
            session.flush()

        version_label = f"v{len(model.versions) + 1}.0" if model.versions else "v1.0"
        mv = ModelVersion(
            model_id=model.id,
            version=version_label,
            base_model=run.base_model,
            training_method=config.get("strategy", "qlora"),
            dataset_version_id=run.dataset_version_id,
            training_run_id=run.id,
            training_config=config,
            evaluation_results=comparison,
            domain_score=float(comparison.get("tuned", {}).get("overall", 0)) * 100.0,
            storage_path=result.get("adapter_path") or str(out_dir),
            status="READY",
        )
        session.add(mv)
        session.commit()

        set_status(
            "COMPLETED",
            progress=1.0,
            completed_at=datetime.now(timezone.utc).isoformat(),
            artifact_path=result.get("adapter_path"),
        )
        return {
            "status": "COMPLETED",
            "model_version_id": str(mv.id),
            "dry_run": result.get("dry_run", True),
            "evaluation_summary": comparison.get("summary"),
        }
    except Exception as e:
        logger.exception("training_job_failed")
        try:
            run = session.get(TrainingRun, UUID(training_run_id))
            if run:
                run.status = "FAILED"
                run.error_message = f"{e}\n{traceback.format_exc()[-2000:]}"
                session.commit()
        except Exception:
            pass
        return {"status": "FAILED", "error": str(e)}
    finally:
        session.close()
