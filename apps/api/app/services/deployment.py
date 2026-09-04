"""Deployment and API key service."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import APIKey, Deployment
from app.schemas.deployment import DeploymentCreate
from app.services.model_registry import get_model_version_for_user
from app.services.project import get_project_for_user, require_org_role, user_belongs_to_org
from ml.inference.openai_api import global_inference


def _slug() -> str:
    return secrets.token_hex(6)


async def create_deployment(
    db: AsyncSession, user_id: uuid.UUID, data: DeploymentCreate
) -> Deployment:
    project = await get_project_for_user(db, user_id, data.project_id)
    if project is None:
        raise PermissionError("Project not found")
    await require_org_role(db, user_id, project.organization_id)
    version = await get_model_version_for_user(db, user_id, data.model_version_id)
    if version is None:
        raise PermissionError("Model version not found")
    if version.status != "READY":
        raise ValueError("Model version is not READY")

    dep = Deployment(
        organization_id=project.organization_id,
        project_id=project.id,
        model_version_id=version.id,
        name=data.name,
        endpoint_slug=f"tunerai-{_slug()}",
        status="RUNNING",
        inference_engine="mock",  # v0.1; swap to vllm when GPU available
        is_public=False,
    )
    db.add(dep)
    await db.flush()
    await db.refresh(dep)

    # Register in process inference router
    model_id = f"tunerai/{dep.endpoint_slug}"
    global_inference.register_mock(model_id, domain_hint=version.base_model)
    return dep


async def list_deployments(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> list[Deployment]:
    project = await get_project_for_user(db, user_id, project_id)
    if project is None:
        return []
    result = await db.execute(
        select(Deployment)
        .where(Deployment.project_id == project_id)
        .order_by(Deployment.created_at.desc())
    )
    return list(result.scalars().all())


async def get_deployment_by_slug(
    db: AsyncSession, organization_id: uuid.UUID, slug: str
) -> Optional[Deployment]:
    result = await db.execute(
        select(Deployment).where(
            Deployment.endpoint_slug == slug,
            Deployment.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def create_api_key(
    db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID, name: str, rpm: Optional[int]
) -> tuple[APIKey, str]:
    await require_org_role(db, user_id, organization_id)
    raw = f"tai_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    row = APIKey(
        organization_id=organization_id,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        is_active=True,
        rate_limit_rpm=rpm,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row, raw


async def verify_api_key(db: AsyncSession, raw_key: str) -> Optional[APIKey]:
    if not raw_key or not raw_key.startswith("tai_"):
        return None
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(
        select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active.is_(True))
    )
    return result.scalar_one_or_none()
