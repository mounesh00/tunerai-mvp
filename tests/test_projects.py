"""Comprehensive tests for project endpoints and tenant isolation."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import OrganizationMember, User
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import project as project_service


class TestProjectCreation:
    """Test project creation."""

    async def test_create_project_success(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test successful project creation."""
        project_data = ProjectCreate(
            name="My First Project",
            description="A test project",
            domain="cybersecurity",
        )
        project = await project_service.create_project(
            db_session, test_user.id, project_data
        )
        
        assert project.name == "My First Project"
        assert project.slug == "my-first-project"
        assert project.organization_id == test_organization.id
        assert project.status == "active"

    async def test_create_project_unauthenticated_fails(self, db_session: AsyncSession):
        """Test project creation by user with no organization fails."""
        import uuid
        
        fake_user_id = uuid.uuid4()
        project_data = ProjectCreate(
            name="My First Project",
            description="A test project",
        )
        with pytest.raises(ValueError, match="no organization"):
            await project_service.create_project(db_session, fake_user_id, project_data)

    async def test_create_project_with_explicit_org(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test project creation with explicit organization."""
        project_data = ProjectCreate(
            name="My Project",
            description="Test",
        )
        project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        assert project.organization_id == test_organization.id

    async def test_create_project_not_member_of_org_fails(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test project creation by user not member of org fails."""
        import uuid
        from app.models.user import Organization
        
        # Create org user doesn't belong to
        other_org = Organization(
            id=uuid.uuid4(),
            name="Other Org",
            slug="other-org",
            is_active=True,
        )
        db_session.add(other_org)
        await db_session.flush()
        
        project_data = ProjectCreate(
            name="My Project",
            description="Test",
        )
        with pytest.raises(PermissionError, match="Not a member"):
            await project_service.create_project(
                db_session, test_user.id, project_data, organization_id=other_org.id
            )

    async def test_create_project_slug_uniqueness(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test project slug is unique within organization."""
        project_data1 = ProjectCreate(name="My Project")
        project1 = await project_service.create_project(
            db_session, test_user.id, project_data1, organization_id=test_organization.id
        )
        
        project_data2 = ProjectCreate(name="My Project")
        project2 = await project_service.create_project(
            db_session, test_user.id, project_data2, organization_id=test_organization.id
        )
        
        assert project1.slug == "my-project"
        assert project2.slug == "my-project-1"

    async def test_database_rejects_duplicate_slug_within_organization(
        self, db_session: AsyncSession, test_organization
    ):
        values = {
            "id": "duplicate-project-id",
            "organization_id": str(test_organization.id),
            "name": "First Project",
            "slug": "duplicate-slug",
        }
        await db_session.execute(
            text(
                "INSERT INTO projects (id, organization_id, name, slug) "
                "VALUES (:id, :organization_id, :name, :slug)"
            ),
            values,
        )

        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO projects (id, organization_id, name, slug) "
                    "VALUES (:id, :organization_id, :name, :slug)"
                ),
                {**values, "id": "second-duplicate-project-id", "name": "Second Project"},
            )


class TestProjectListing:
    """Test project listing."""

    async def test_list_projects_for_user(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test listing projects for authenticated user."""
        project_data = ProjectCreate(name="Test Project")
        await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        projects = await project_service.list_projects_for_user(db_session, test_user.id)
        assert len(projects) == 1
        assert projects[0].name == "Test Project"

    async def test_list_projects_empty_for_new_user(self, db_session: AsyncSession):
        """Test listing projects for user with no orgs returns empty."""
        import uuid
        
        fake_user_id = uuid.uuid4()
        projects = await project_service.list_projects_for_user(db_session, fake_user_id)
        assert projects == []


class TestProjectRetrieval:
    """Test project retrieval."""

    async def test_get_project_by_id(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test retrieving project by ID."""
        project_data = ProjectCreate(name="Test Project")
        created_project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        retrieved = await project_service.get_project_for_user(
            db_session, test_user.id, created_project.id
        )
        assert retrieved is not None
        assert retrieved.id == created_project.id

    async def test_get_nonexistent_project_returns_none(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test getting non-existent project returns None."""
        import uuid
        
        fake_project_id = uuid.uuid4()
        retrieved = await project_service.get_project_for_user(
            db_session, test_user.id, fake_project_id
        )
        assert retrieved is None


class TestProjectUpdate:
    """Test project updates."""

    async def test_update_project_name(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test updating project name."""
        project_data = ProjectCreate(name="Old Name")
        project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        update_data = ProjectUpdate(name="New Name")
        updated = await project_service.update_project(
            db_session, test_user.id, project.id, update_data
        )
        
        assert updated is not None
        assert updated.name == "New Name"

    async def test_update_project_slug_on_name_change(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test that slug is regenerated when name changes."""
        project_data = ProjectCreate(name="Old Name")
        project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        old_slug = project.slug
        update_data = ProjectUpdate(name="Completely Different Name")
        updated = await project_service.update_project(
            db_session, test_user.id, project.id, update_data
        )
        
        assert updated is not None
        assert updated.slug == "completely-different-name"
        assert updated.slug != old_slug

    async def test_update_project_slug_uniqueness_on_name_change(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test slug uniqueness is enforced on name change."""
        # Create first project
        project_data1 = ProjectCreate(name="Project A")
        project1 = await project_service.create_project(
            db_session, test_user.id, project_data1, organization_id=test_organization.id
        )
        
        # Create second project with different name
        project_data2 = ProjectCreate(name="Project B")
        project2 = await project_service.create_project(
            db_session, test_user.id, project_data2, organization_id=test_organization.id
        )
        
        # Update second project to have same name as first
        update_data = ProjectUpdate(name="Project A")
        updated = await project_service.update_project(
            db_session, test_user.id, project2.id, update_data
        )
        
        assert updated is not None
        assert updated.slug != project1.slug  # Should have counter suffix
        assert updated.slug == "project-a-1"

    async def test_update_project_description(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        """Test updating project description."""
        project_data = ProjectCreate(name="Project", description="Old description")
        project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        update_data = ProjectUpdate(description="New description")
        updated = await project_service.update_project(
            db_session, test_user.id, project.id, update_data
        )
        
        assert updated is not None
        assert updated.description == "New description"


class TestTenantIsolation:
    """Test tenant isolation - prevent IDOR/BOLA attacks."""

    async def test_user_cannot_access_other_org_project(
        self, db_session: AsyncSession, test_user: User, other_user: User, test_organization
    ):
        """Test user from org A cannot access org B's project."""
        # Create project in test_user's org
        project_data = ProjectCreate(name="Org A Project")
        project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        # Try to access with other_user (different org)
        retrieved = await project_service.get_project_for_user(
            db_session, other_user.id, project.id
        )
        assert retrieved is None

    async def test_user_cannot_update_other_org_project(
        self, db_session: AsyncSession, test_user: User, other_user: User, test_organization
    ):
        """Test user from org A cannot update org B's project."""
        # Create project in test_user's org
        project_data = ProjectCreate(name="Org A Project")
        project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        # Try to update with other_user (different org)
        update_data = ProjectUpdate(name="Updated Name")
        updated = await project_service.update_project(
            db_session, other_user.id, project.id, update_data
        )
        assert updated is None

    async def test_list_projects_only_returns_user_orgs(
        self, db_session: AsyncSession, test_user: User, other_user: User, test_organization
    ):
        """Test list_projects only returns projects from user's orgs."""
        # Create project in test_user's org
        project_data1 = ProjectCreate(name="Org A Project")
        await project_service.create_project(
            db_session, test_user.id, project_data1, organization_id=test_organization.id
        )
        
        # List projects for other_user (different org)
        projects = await project_service.list_projects_for_user(db_session, other_user.id)
        assert len(projects) == 0

    async def test_org_filtering_cannot_bypass_isolation(
        self, db_session: AsyncSession, test_user: User, other_user: User, test_organization
    ):
        """Test that explicit org_id filter cannot bypass tenant isolation."""
        # Create project in test_user's org
        project_data = ProjectCreate(name="Org A Project")
        project = await project_service.create_project(
            db_session, test_user.id, project_data, organization_id=test_organization.id
        )
        
        # Try to list projects from org A as other_user
        projects = await project_service.list_projects_for_user(
            db_session, other_user.id, organization_id=test_organization.id
        )
        assert len(projects) == 0


class TestProjectRoleAuthorization:
    async def test_member_can_read_but_cannot_write(
        self, db_session: AsyncSession, test_user: User, other_user: User, test_organization
    ):
        project = await project_service.create_project(
            db_session, test_user.id, ProjectCreate(name="Owner Project")
        )
        db_session.add(
            OrganizationMember(
                organization_id=test_organization.id,
                user_id=other_user.id,
                role="member",
            )
        )
        await db_session.flush()

        assert await project_service.get_project_for_user(
            db_session, other_user.id, project.id
        ) is not None
        assert len(
            await project_service.list_projects_for_user(
                db_session, other_user.id, test_organization.id
            )
        ) == 1

        with pytest.raises(PermissionError, match="Insufficient role"):
            await project_service.create_project(
                db_session,
                other_user.id,
                ProjectCreate(name="Member Project"),
                organization_id=test_organization.id,
            )
        with pytest.raises(PermissionError, match="Insufficient role"):
            await project_service.update_project(
                db_session, other_user.id, project.id, ProjectUpdate(name="Renamed")
            )

    async def test_admin_can_create_and_update_project(
        self, db_session: AsyncSession, other_user: User, test_organization
    ):
        db_session.add(
            OrganizationMember(
                organization_id=test_organization.id,
                user_id=other_user.id,
                role="admin",
            )
        )
        await db_session.flush()

        project = await project_service.create_project(
            db_session,
            other_user.id,
            ProjectCreate(name="Admin Project"),
            organization_id=test_organization.id,
        )
        updated = await project_service.update_project(
            db_session, other_user.id, project.id, ProjectUpdate(name="Updated Admin Project")
        )

        assert updated is not None
        assert updated.name == "Updated Admin Project"

    async def test_owner_can_create_and_update_project(
        self, db_session: AsyncSession, test_user: User, test_organization
    ):
        project = await project_service.create_project(
            db_session,
            test_user.id,
            ProjectCreate(name="Owner Project"),
            organization_id=test_organization.id,
        )
        updated = await project_service.update_project(
            db_session, test_user.id, project.id, ProjectUpdate(name="Updated Owner Project")
        )

        assert updated is not None
        assert updated.name == "Updated Owner Project"
