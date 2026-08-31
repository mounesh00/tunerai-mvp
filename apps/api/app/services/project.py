"""Project service with tenant isolation."""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import OrganizationMember
from app.schemas.project import ProjectCreate, ProjectUpdate


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80] or "project"


async def user_belongs_to_org(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_user_default_org_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(OrganizationMember.organization_id)
        .where(OrganizationMember.user_id == user_id)
        .order_by(OrganizationMember.created_at.asc())
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def create_project(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: ProjectCreate,
    organization_id: Optional[uuid.UUID] = None,
) -> Project:
    if organization_id is None:
        organization_id = await get_user_default_org_id(db, user_id)
        if organization_id is None:
            raise ValueError("User has no organization")

    if not await user_belongs_to_org(db, user_id, organization_id):
        raise PermissionError("Not a member of this organization")

    base_slug = slugify(data.name)
    slug = base_slug
    counter = 1
    while True:
        result = await db.execute(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.slug == slug,
            )
        )
        if result.scalar_one_or_none() is None:
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    project = Project(
        organization_id=organization_id,
        name=data.name,
        slug=slug,
        description=data.description,
        domain=data.domain,
        status="active",
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


async def list_projects_for_user(
    db: AsyncSession, user_id: uuid.UUID, organization_id: Optional[uuid.UUID] = None
) -> list[Project]:
    # Get orgs the user belongs to
    org_result = await db.execute(
        select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user_id)
    )
    org_ids = [row[0] for row in org_result.all()]
    if not org_ids:
        return []

    query = select(Project).where(Project.organization_id.in_(org_ids))
    if organization_id is not None:
        if organization_id not in org_ids:
            return []
        query = query.where(Project.organization_id == organization_id)

    query = query.order_by(Project.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_project_for_user(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> Optional[Project]:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        return None
    if not await user_belongs_to_org(db, user_id, project.organization_id):
        return None
    return project


async def update_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, data: ProjectUpdate
) -> Optional[Project]:
    project = await get_project_for_user(db, user_id, project_id)
    if project is None:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    return project
