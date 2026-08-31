"""Training run endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.training import (
    TrainingEstimateRequest,
    TrainingEstimateResponse,
    TrainingRunCreate,
    TrainingRunRead,
)
from app.services import training as training_service
from ml.training.config import SUPPORTED_BASE_MODELS

router = APIRouter()


@router.get("/base-models")
async def list_base_models() -> dict:
    return {"models": SUPPORTED_BASE_MODELS}


@router.post("/estimate", response_model=TrainingEstimateResponse)
async def estimate_training(
    data: TrainingEstimateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> TrainingEstimateResponse:
    try:
        est = await training_service.estimate(
            db,
            current_user.id,
            data.base_model,
            data.dataset_version_id,
            data.preset,
            data.strategy,
            data.overrides,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return TrainingEstimateResponse(**est)


@router.post("/runs", response_model=TrainingRunRead, status_code=status.HTTP_201_CREATED)
async def create_run(
    data: TrainingRunCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TrainingRunRead:
    try:
        run = await training_service.create_training_run(db, current_user.id, data)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TrainingRunRead.model_validate(run)


@router.get("/runs/project/{project_id}", response_model=list[TrainingRunRead])
async def list_runs(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[TrainingRunRead]:
    runs = await training_service.list_runs_for_project(db, current_user.id, project_id)
    return [TrainingRunRead.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=TrainingRunRead)
async def get_run(
    run_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TrainingRunRead:
    run = await training_service.get_run_for_user(db, current_user.id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Training run not found")
    return TrainingRunRead.model_validate(run)


@router.post("/runs/{run_id}/cancel", response_model=TrainingRunRead)
async def cancel_run(
    run_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TrainingRunRead:
    run = await training_service.cancel_run(db, current_user.id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Training run not found")
    return TrainingRunRead.model_validate(run)
