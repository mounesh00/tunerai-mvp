"""Training run service."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import DatasetVersion
from app.models.training import TrainingConfig, TrainingRun
from app.schemas.training import TrainingRunCreate
from app.services.dataset import get_version_for_user
from app.services.project import get_project_for_user, user_belongs_to_org
from ml.training.config import SUPPORTED_BASE_MODELS, estimate_resources, resolve_config

logger = logging.getLogger(__name__)


async def estimate(
    db: AsyncSession,
    user_id: uuid.UUID,
    base_model: str,
    dataset_version_id: uuid.UUID,
    preset: str = "balanced",
    strategy: str = "qlora",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    version = await get_version_for_user(db, user_id, dataset_version_id)
    if version is None:
        raise PermissionError("Dataset version not found")
    if base_model not in SUPPORTED_BASE_MODELS:
        # Allow but warn via note
        pass
    cfg = resolve_config(preset=preset, strategy=strategy, overrides=overrides)
    n = version.valid_records or version.total_records or 100
    est = estimate_resources(base_model, n, cfg)
    est["config"] = cfg
    est["supported_models"] = SUPPORTED_BASE_MODELS
    return est


async def create_training_run(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: TrainingRunCreate,
) -> TrainingRun:
    project = await get_project_for_user(db, user_id, data.project_id)
    if project is None:
        raise PermissionError("Project not found")

    version = await get_version_for_user(db, user_id, data.dataset_version_id)
    if version is None:
        raise PermissionError("Dataset version not found")
    if version.status != "ready":
        raise ValueError("Dataset version is not ready for training")

    cfg = resolve_config(
        preset=data.preset, strategy=data.strategy, overrides=data.overrides
    )
    n = version.valid_records or 100
    est = estimate_resources(data.base_model, n, cfg)

    tconfig = TrainingConfig(
        config=cfg,
        preset=data.preset,
        strategy=data.strategy,
    )
    db.add(tconfig)
    await db.flush()

    run = TrainingRun(
        organization_id=project.organization_id,
        project_id=project.id,
        dataset_version_id=version.id,
        training_config_id=tconfig.id,
        base_model=data.base_model,
        status="QUEUED",
        progress=0.0,
        total_epochs=int(cfg.get("epochs", 3)),
        estimated_vram_gb=est["estimated_vram_gb"],
        estimated_time_minutes=est["estimated_time_minutes"],
        estimated_cost_usd=est["estimated_cost_usd"],
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)

    # Enqueue Celery task (or run inline dry if no broker)
    try:
        from workers.tasks import run_training_job

        run_training_job.delay(str(run.id))
    except Exception as e:
        logger.warning("celery_enqueue_failed falling_back_inline: %s", e)
        # Inline dry-run fallback for local without Redis
        if os.environ.get("TUNERAI_INLINE_TRAINING", "true").lower() in ("1", "true", "yes"):
            try:
                from workers.tasks import run_training_job as _task

                _task(str(run.id))
                await db.refresh(run)
            except Exception as e2:
                logger.exception("inline_training_failed")
                run.status = "FAILED"
                run.error_message = str(e2)
                await db.flush()

    return run


async def list_runs_for_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> list[TrainingRun]:
    project = await get_project_for_user(db, user_id, project_id)
    if project is None:
        return []
    result = await db.execute(
        select(TrainingRun)
        .where(TrainingRun.project_id == project_id)
        .order_by(TrainingRun.created_at.desc())
    )
    return list(result.scalars().all())


async def get_run_for_user(
    db: AsyncSession, user_id: uuid.UUID, run_id: uuid.UUID
) -> Optional[TrainingRun]:
    result = await db.execute(select(TrainingRun).where(TrainingRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        return None
    if not await user_belongs_to_org(db, user_id, run.organization_id):
        return None
    return run


async def cancel_run(
    db: AsyncSession, user_id: uuid.UUID, run_id: uuid.UUID
) -> Optional[TrainingRun]:
    run = await get_run_for_user(db, user_id, run_id)
    if run is None:
        return None
    if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
        return run
    if run.status in ("QUEUED", "PREPARING"):
        run.status = "CANCELLED"
        await db.flush()
    # Running cancel is best-effort flag; worker checks status
    elif run.status in ("TRAINING", "EVALUATING"):
        run.status = "CANCELLED"
        await db.flush()
    return run
