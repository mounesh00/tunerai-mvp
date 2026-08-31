"""Dataset service: upload, validate, quality report with tenant isolation."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.dataset import Dataset, DatasetVersion
from app.models.project import Project
from app.models.user import OrganizationMember
from app.schemas.dataset import DatasetCreate
from app.services.project import get_project_for_user, user_belongs_to_org

# Local filesystem storage for v0.1 (S3 later)
STORAGE_ROOT = Path("/tmp/tunerai/storage")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80] or "dataset"


async def create_dataset(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: DatasetCreate,
) -> Dataset:
    project = await get_project_for_user(db, user_id, data.project_id)
    if project is None:
        raise PermissionError("Project not found or access denied")

    dataset = Dataset(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name,
        description=data.description,
        status="uploaded",
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)
    return dataset


async def list_datasets_for_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> list[Dataset]:
    project = await get_project_for_user(db, user_id, project_id)
    if project is None:
        return []
    result = await db.execute(
        select(Dataset)
        .where(Dataset.project_id == project_id)
        .options(selectinload(Dataset.versions))
        .order_by(Dataset.created_at.desc())
    )
    return list(result.scalars().all())


async def get_dataset_for_user(
    db: AsyncSession, user_id: uuid.UUID, dataset_id: uuid.UUID
) -> Optional[Dataset]:
    result = await db.execute(
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .options(selectinload(Dataset.versions))
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        return None
    if not await user_belongs_to_org(db, user_id, dataset.organization_id):
        return None
    return dataset


async def upload_and_validate(
    db: AsyncSession,
    user_id: uuid.UUID,
    dataset_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> DatasetVersion:
    """Store file, run validation pipeline, persist quality metrics."""
    settings = get_settings()
    dataset = await get_dataset_for_user(db, user_id, dataset_id)
    if dataset is None:
        raise PermissionError("Dataset not found or access denied")

    # Extension / size checks
    lower = filename.lower()
    if not any(lower.endswith(ext) for ext in settings.allowed_extensions_list):
        raise ValueError(
            f"Invalid file type. Allowed: {settings.allowed_upload_extensions}"
        )
    if len(content) > settings.max_upload_size_bytes:
        raise ValueError(
            f"File exceeds max size of {settings.max_upload_size_mb} MB"
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"File must be UTF-8 text: {e}") from e

    # Version number
    existing = dataset.versions or []
    version_num = len(existing) + 1
    version_label = f"v{version_num}"

    # Store locally (S3-compatible path abstraction for later)
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    org_dir = STORAGE_ROOT / str(dataset.organization_id) / str(dataset.id)
    org_dir.mkdir(parents=True, exist_ok=True)
    storage_path = str(org_dir / f"{version_label}_{filename}")
    Path(storage_path).write_bytes(content)

    # Run validation
    from ml.data.validator import DatasetValidator

    validator = DatasetValidator()
    validation = validator.validate_text(text, filename=filename)

    # Persist version with metrics
    version = DatasetVersion(
        dataset_id=dataset.id,
        version=version_label,
        storage_path=storage_path,
        original_filename=filename,
        format=validation.format_detected,
        total_records=validation.total_records,
        valid_records=validation.valid_records,
        invalid_records=validation.invalid_records,
        duplicate_count=validation.duplicate_count,
        duplicate_percentage=validation.duplicate_percentage,
        avg_tokens=validation.avg_tokens,
        max_tokens=validation.max_tokens,
        estimated_training_tokens=validation.estimated_training_tokens,
        train_size=validation.train_size,
        validation_size=validation.validation_size,
        quality_score=validation.quality_score,
        quality_report=validation.to_report_dict(),
        warnings=validation.warnings,
        status="ready" if validation.valid_records > 0 else "failed",
    )
    db.add(version)

    dataset.status = "ready" if version.status == "ready" else "failed"
    await db.flush()
    await db.refresh(version)
    return version


async def get_version_for_user(
    db: AsyncSession, user_id: uuid.UUID, version_id: uuid.UUID
) -> Optional[DatasetVersion]:
    result = await db.execute(
        select(DatasetVersion).where(DatasetVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        return None
    dataset = await get_dataset_for_user(db, user_id, version.dataset_id)
    if dataset is None:
        return None
    return version
