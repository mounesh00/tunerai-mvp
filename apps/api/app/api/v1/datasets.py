"""Dataset endpoints: create, list, upload, validate, quality report."""

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.dataset import (
    DatasetCreate,
    DatasetRead,
    DatasetVersionRead,
    DatasetWithVersions,
    QualityReportResponse,
)
from app.services import dataset as dataset_service

router = APIRouter()


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    data: DatasetCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> DatasetRead:
    try:
        dataset = await dataset_service.create_dataset(db, current_user.id, data)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return DatasetRead.model_validate(dataset)


@router.get("/project/{project_id}", response_model=list[DatasetWithVersions])
async def list_datasets(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[DatasetWithVersions]:
    datasets = await dataset_service.list_datasets_for_project(
        db, current_user.id, project_id
    )
    return [DatasetWithVersions.model_validate(d) for d in datasets]


@router.get("/{dataset_id}", response_model=DatasetWithVersions)
async def get_dataset(
    dataset_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DatasetWithVersions:
    dataset = await dataset_service.get_dataset_for_user(db, current_user.id, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return DatasetWithVersions.model_validate(dataset)


@router.post(
    "/{dataset_id}/upload",
    response_model=DatasetVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    dataset_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> DatasetVersionRead:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds max size of {settings.max_upload_size_mb} MB",
        )

    try:
        version = await dataset_service.upload_and_validate(
            db, current_user.id, dataset_id, file.filename, content
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        if "already been uploaded" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except dataset_service.StorageError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except dataset_service.StoragePersistenceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return DatasetVersionRead.model_validate(version)


@router.get("/{dataset_id}/versions/{version_id}/report", response_model=QualityReportResponse)
async def get_quality_report(
    dataset_id: UUID,
    version_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> QualityReportResponse:
    version = await dataset_service.get_version_for_user(db, current_user.id, version_id)
    if version is None or version.dataset_id != dataset_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return QualityReportResponse(
        dataset_id=dataset_id,
        version_id=version_id,
        status=version.status,
        report=version.quality_report or {},
    )


@router.get("/{dataset_id}/versions/{version_id}/download")
async def get_dataset_download_url(
    dataset_id: UUID,
    version_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, str]:
    try:
        download_url = await dataset_service.get_download_url_for_user(
            db, current_user.id, dataset_id, version_id
        )
    except dataset_service.StorageError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    if download_url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return {"url": download_url}
