"""Deployment endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.deployment import DeploymentCreate, DeploymentRead
from app.services import deployment as deployment_service

router = APIRouter()


@router.post("", response_model=DeploymentRead, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    data: DeploymentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> DeploymentRead:
    try:
        dep = await deployment_service.create_deployment(db, current_user.id, data)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return DeploymentRead.model_validate(dep)


@router.get("/project/{project_id}", response_model=list[DeploymentRead])
async def list_deployments(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[DeploymentRead]:
    deps = await deployment_service.list_deployments(db, current_user.id, project_id)
    return [DeploymentRead.model_validate(d) for d in deps]
