"""Model registry endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.model_registry import ModelCreate, ModelRead, ModelVersionRead
from app.services import model_registry as model_service

router = APIRouter()


@router.post("", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
async def create_model(
    data: ModelCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ModelRead:
    try:
        model = await model_service.create_model(db, current_user.id, data)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return ModelRead.model_validate(model)


@router.get("/project/{project_id}", response_model=list[ModelRead])
async def list_models(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ModelRead]:
    models = await model_service.list_models_for_project(db, current_user.id, project_id)
    return [ModelRead.model_validate(m) for m in models]


@router.get("/{model_id}", response_model=ModelRead)
async def get_model(
    model_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ModelRead:
    model = await model_service.get_model_for_user(db, current_user.id, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelRead.model_validate(model)


@router.get("/versions/{version_id}", response_model=ModelVersionRead)
async def get_version(
    version_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ModelVersionRead:
    version = await model_service.get_model_version_for_user(db, current_user.id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    return ModelVersionRead.model_validate(version)
