"""Model registry service."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.model_registry import Model, ModelVersion
from app.schemas.model_registry import ModelCreate
from app.services.project import get_project_for_user, user_belongs_to_org


async def create_model(db: AsyncSession, user_id: uuid.UUID, data: ModelCreate) -> Model:
    project = await get_project_for_user(db, user_id, data.project_id)
    if project is None:
        raise PermissionError("Project not found")
    model = Model(
        organization_id=project.organization_id,
        project_id=project.id,
        name=data.name,
        description=data.description,
        domain=data.domain,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return model


async def list_models_for_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> list[Model]:
    project = await get_project_for_user(db, user_id, project_id)
    if project is None:
        return []
    result = await db.execute(
        select(Model)
        .where(Model.project_id == project_id)
        .options(selectinload(Model.versions))
        .order_by(Model.created_at.desc())
    )
    return list(result.scalars().all())


async def get_model_for_user(
    db: AsyncSession, user_id: uuid.UUID, model_id: uuid.UUID
) -> Optional[Model]:
    result = await db.execute(
        select(Model).where(Model.id == model_id).options(selectinload(Model.versions))
    )
    model = result.scalar_one_or_none()
    if model is None:
        return None
    if not await user_belongs_to_org(db, user_id, model.organization_id):
        return None
    return model


async def get_model_version_for_user(
    db: AsyncSession, user_id: uuid.UUID, version_id: uuid.UUID
) -> Optional[ModelVersion]:
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
    version = result.scalar_one_or_none()
    if version is None:
        return None
    model = await get_model_for_user(db, user_id, version.model_id)
    if model is None:
        return None
    return version
