"""Authentication service."""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import Organization, OrganizationMember, User
from app.schemas.auth import Token, UserCreate, UserRead


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80] or "org"


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise ValueError("Email already registered")

    user = User(
        email=data.email.lower(),
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    # Create personal organization
    org_name = data.organization_name or f"{data.full_name or data.email.split('@')[0]}'s Workspace"
    base_slug = slugify(org_name)
    slug = base_slug
    # Ensure unique slug
    counter = 1
    while True:
        result = await db.execute(select(Organization).where(Organization.slug == slug))
        if result.scalar_one_or_none() is None:
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(name=org_name, slug=slug)
    db.add(org)
    await db.flush()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def create_tokens_for_user(user: User) -> Token:
    access = create_access_token(subject=str(user.id))
    refresh = create_refresh_token(subject=str(user.id))
    return Token(access_token=access, refresh_token=refresh)


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> Optional[str]:
    """
    Validate refresh token and return a new access token.
    
    Returns:
        New access token string if valid, None if invalid
    """
    payload = decode_token(refresh_token)
    
    # Validate token structure
    if payload is None:
        return None
    
    # Ensure it's a refresh token, not an access token
    if payload.get("type") != "refresh":
        return None
    
    # Extract and validate user ID
    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
    
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return None
    
    # Verify user exists and is active
    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        return None
    
    # Create and return new access token
    return create_access_token(subject=str(user.id))


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> bool:
    """
    Change password for authenticated user.
    
    Args:
        db: Database session
        user: Current user object
        current_password: User's current password (plaintext)
        new_password: New password (plaintext)
        
    Returns:
        True if successful, False if current password is wrong
        
    Raises:
        ValueError: If new password fails validation
    """
    # Verify current password
    if not verify_password(current_password, user.hashed_password):
        return False
    
    # Validate new password through password policy
    from app.core.password import validate_password
    
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Hash and update
    user.hashed_password = get_password_hash(new_password)
    await db.flush()
    
    return True


async def get_user_organizations(db: AsyncSession, user_id: uuid.UUID) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember)
        .where(OrganizationMember.user_id == user_id)
        .options(selectinload(Organization.members))
    )
    return list(result.scalars().all())
