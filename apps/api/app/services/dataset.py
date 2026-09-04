"""Dataset service: upload, validate, quality report with tenant isolation."""

from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.dataset import Dataset, DatasetVersion
from app.schemas.dataset import DatasetCreate
from app.services.project import get_project_for_user, user_belongs_to_org
from app.utils.storage import calculate_content_hash, generate_safe_object_key


class StorageError(RuntimeError):
    """Raised when the configured S3-compatible object store cannot complete an operation."""


class StoragePersistenceError(RuntimeError):
    """Raised after an uploaded object cannot be recorded in the database."""


class DuplicateContentError(ValueError):
    """Raised when concurrent uploads persist identical dataset content."""


@asynccontextmanager
async def _storage_client() -> AsyncIterator:
    settings = get_settings()
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
    ) as client:
        yield client


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80] or "dataset"


async def _delete_uploaded_object(storage_path: str) -> None:
    settings = get_settings()
    try:
        async with _storage_client() as client:
            await client.delete_object(
                Bucket=settings.s3_bucket_name,
                Key=storage_path,
            )
    except (BotoCoreError, ClientError):
        pass


def _is_duplicate_content_constraint(error: IntegrityError) -> bool:
    current_error = error.orig
    while current_error is not None:
        constraint_name = getattr(
            getattr(current_error, "diag", None), "constraint_name", None
        ) or getattr(current_error, "constraint_name", None)
        if constraint_name == "uq_dataset_versions_dataset_content_hash":
            return True
        current_error = getattr(current_error, "__cause__", None)
    return False


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
    # Defense in depth: verify user belongs to project's organization
    if not await user_belongs_to_org(db, user_id, project.organization_id):
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
    """Upload a validated dataset version and persist its R2 object key.

    Re-uploading identical content to the same dataset is rejected with a
    ``ValueError`` so the caller can return HTTP 409 rather than silently
    discarding the upload. The existing byte-buffered request flow is retained
    because validation currently requires decoded full-text input.
    """
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

    content_hash = calculate_content_hash(content)
    existing_content = await db.execute(
        select(DatasetVersion.id).where(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.content_hash == content_hash,
        )
    )
    if existing_content.scalar_one_or_none() is not None:
        raise ValueError("This content has already been uploaded to this dataset")

    # Version number
    existing = dataset.versions or []
    version_num = len(existing) + 1
    version_label = f"v{version_num}"
    storage_path = generate_safe_object_key(
        str(dataset.organization_id),
        str(dataset.project_id),
        str(dataset.id),
        version_label,
        filename,
    )

    # Run validation
    from ml.data.validator import DatasetValidator

    validator = DatasetValidator()
    validation = validator.validate_text(text, filename=filename)

    try:
        async with _storage_client() as client:
            await client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=storage_path,
                Body=content,
            )
    except (BotoCoreError, ClientError) as e:
        raise StorageError("Unable to upload dataset to object storage") from e

    # Persist version with metrics
    version = DatasetVersion(
        dataset_id=dataset.id,
        version=version_label,
        storage_path=storage_path,
        original_filename=filename,
        format=validation.format_detected,
        content_hash=content_hash,
        content_hash_algorithm="sha256",
        file_size_bytes=len(content),
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
    try:
        await db.flush()
    except IntegrityError as persistence_error:
        await _delete_uploaded_object(storage_path)
        if _is_duplicate_content_constraint(persistence_error):
            raise DuplicateContentError(
                "This content has already been uploaded to this dataset"
            ) from persistence_error
        raise StoragePersistenceError(
            "Unable to save dataset metadata after object upload"
        ) from persistence_error
    except Exception as persistence_error:
        await _delete_uploaded_object(storage_path)
        raise StoragePersistenceError(
            "Unable to save dataset metadata after object upload"
        ) from persistence_error
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


async def get_download_url_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> Optional[str]:
    """Return a short-lived URL only after tenant access to the version is verified."""
    version = await get_version_for_user(db, user_id, version_id)
    if version is None or version.dataset_id != dataset_id:
        return None

    settings = get_settings()
    try:
        async with _storage_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket_name, "Key": version.storage_path},
                ExpiresIn=900,
            )
    except (BotoCoreError, ClientError) as e:
        raise StorageError("Unable to create dataset download URL") from e
