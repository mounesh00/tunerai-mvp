"""Pytest configuration and shared fixtures for API tests."""

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.models.user import Organization, OrganizationMember, User


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create in-memory SQLite engine for testing Phase 2 only (no JSONB columns)."""
    # Use SQLite for testing with in-memory database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    # Manually create only the Phase 2 tables (avoiding JSONB-dependent tables)
    async with engine.begin() as conn:
        # Create organizations table
        await conn.exec_driver_sql("""
            CREATE TABLE organizations (
                id TEXT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create users table
        await conn.exec_driver_sql("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                email VARCHAR(320) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                is_active BOOLEAN DEFAULT 1,
                is_superuser BOOLEAN DEFAULT 0,
                is_verified BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create organization_members table
        await conn.exec_driver_sql("""
            CREATE TABLE organization_members (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role VARCHAR(50) DEFAULT 'member',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (organization_id, user_id)
            )
        """)
        
        # Create projects table
        await conn.exec_driver_sql("""
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(100) NOT NULL,
                description TEXT,
                domain VARCHAR(100),
                status VARCHAR(50) DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
            )
        """)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP TABLE IF EXISTS projects")
        await conn.exec_driver_sql("DROP TABLE IF EXISTS organization_members")
        await conn.exec_driver_sql("DROP TABLE IF EXISTS users")
        await conn.exec_driver_sql("DROP TABLE IF EXISTS organizations")
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async_session = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        hashed_password=get_password_hash("TestPassword123"),
        full_name="Test User",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_organization(db_session: AsyncSession, test_user: User) -> Organization:
    """Create a test organization and add test_user as owner."""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug="test-org",
        description="Organization for testing",
        is_active=True,
    )
    db_session.add(org)
    await db_session.flush()
    
    membership = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=test_user.id,
        role="owner",
    )
    db_session.add(membership)
    await db_session.flush()
    
    return org


@pytest.fixture
async def test_user_access_token(test_user: User) -> str:
    """Create an access token for test_user."""
    return create_access_token(subject=str(test_user.id))


@pytest.fixture
async def test_user_refresh_token(test_user: User) -> str:
    """Create a refresh token for test_user."""
    return create_refresh_token(subject=str(test_user.id))


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user in a different organization."""
    user = User(
        id=uuid.uuid4(),
        email="otheruser@example.com",
        hashed_password=get_password_hash("OtherPassword123"),
        full_name="Other User",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.flush()
    
    # Create separate org for other_user
    org = Organization(
        id=uuid.uuid4(),
        name="Other Organization",
        slug="other-org",
        is_active=True,
    )
    db_session.add(org)
    await db_session.flush()
    
    membership = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db_session.add(membership)
    await db_session.flush()
    
    return user


@pytest.fixture
async def other_user_access_token(other_user: User) -> str:
    """Create an access token for other_user."""
    return create_access_token(subject=str(other_user.id))


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create an inactive test user."""
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        hashed_password=get_password_hash("InactivePassword123"),
        full_name="Inactive User",
        is_active=False,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user
