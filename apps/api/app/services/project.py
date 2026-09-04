"""Project service with tenant isolation."""

from __future__ import annotations

import re
import uuid
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import OrganizationMember
from app.schemas.project import ProjectCreate, ProjectUpdate

ALLOWED_WRITE_ROLES = frozenset({"owner", "admin"})


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


async def get_membership(
    db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID
) -> Optional[OrganizationMember]:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    return result.scalar_one_or_none()


async def require_org_role(
    db: AsyncSession,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    allowed_roles: Iterable[str] = ALLOWED_WRITE_ROLES,
) -> OrganizationMember:
    membership = await get_membership(db, user_id, org_id)
    if membership is None:
        raise PermissionError("Not a member of this organization")
    if membership.role not in set(allowed_roles):
        raise PermissionError("Insufficient role for this action")
    return membership


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

    await require_org_role(db, user_id, organization_id)

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
    try:
        await db.flush()
    except IntegrityError as error:
        await db.rollback()
        raise ValueError("Project slug already exists in this organization") from error
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
    await require_org_role(db, user_id, project.organization_id)
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Handle slug regeneration if name is being updated
    if "name" in update_data and update_data["name"]:
        base_slug = slugify(update_data["name"])
        new_slug = base_slug
        counter = 1
        
        # Ensure uniqueness within the organization
        while True:
            result = await db.execute(
                select(Project).where(
                    Project.organization_id == project.organization_id,
                    Project.slug == new_slug,
                    Project.id != project.id,  # Exclude current project
                )
            )
            if result.scalar_one_or_none() is None:
                break
            new_slug = f"{base_slug}-{counter}"
            counter += 1
        
        update_data["slug"] = new_slug
    
    for field, value in update_data.items():
        setattr(project, field, value)
    
    try:
        await db.flush()
    except IntegrityError as error:
        await db.rollback()
        raise ValueError("Project slug already exists in this organization") from error
    await db.refresh(project)
    return project
