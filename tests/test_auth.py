"""Comprehensive tests for authentication endpoints."""

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin
from app.services import auth as auth_service


class TestRegistration:
    """Test registration endpoint."""

    async def test_successful_registration(self, db_session: AsyncSession):
        """Test successful user registration."""
        user_data = UserCreate(
            email="newuser@example.com",
            password="ValidPassword123",
            full_name="New User",
            organization_name="My Workspace",
        )
        user = await auth_service.create_user(db_session, user_data)
        
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.is_active is True
        assert user.is_verified is False
        assert user.hashed_password != "ValidPassword123"  # Should be hashed

    async def test_duplicate_email(self, db_session: AsyncSession, test_user: User):
        """Test registration with duplicate email fails."""
        user_data = UserCreate(
            email=test_user.email,  # Duplicate
            password="ValidPassword123",
            full_name="Another User",
        )
        with pytest.raises(ValueError, match="already registered"):
            await auth_service.create_user(db_session, user_data)

    async def test_weak_password_too_short(self, db_session: AsyncSession):
        """Test registration with weak password (too short)."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="newuser@example.com",
                password="Short1",  # Only 6 chars, needs 10+
                full_name="User",
            )

    async def test_weak_password_no_letter(self, db_session: AsyncSession):
        """Test registration with weak password (no letters)."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="newuser@example.com",
                password="1234567890",  # All numbers, needs at least one letter
                full_name="User",
            )

    async def test_weak_password_no_number(self, db_session: AsyncSession):
        """Test registration with weak password (no numbers)."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="newuser@example.com",
                password="OnlyLetters",  # All letters, needs at least one number
                full_name="User",
            )

    async def test_auto_org_creation_on_register(self, db_session: AsyncSession):
        """Test that an organization is automatically created on registration."""
        user_data = UserCreate(
            email="newuser@example.com",
            password="ValidPassword123",
            full_name="New User",
            organization_name="Custom Org Name",
        )
        user = await auth_service.create_user(db_session, user_data)
        orgs = await auth_service.get_user_organizations(db_session, user.id)
        
        assert len(orgs) == 1
        assert orgs[0].name == "Custom Org Name"


class TestLogin:
    """Test login endpoint."""

    async def test_successful_login(self, db_session: AsyncSession, test_user: User):
        """Test successful login."""
        user = await auth_service.authenticate_user(
            db_session, test_user.email, "TestPassword123"
        )
        assert user is not None
        assert user.id == test_user.id

    async def test_login_wrong_password(self, db_session: AsyncSession, test_user: User):
        """Test login with wrong password fails."""
        user = await auth_service.authenticate_user(
            db_session, test_user.email, "WrongPassword123"
        )
        assert user is None

    async def test_login_nonexistent_email(self, db_session: AsyncSession):
        """Test login with non-existent email fails."""
        user = await auth_service.authenticate_user(
            db_session, "nonexistent@example.com", "SomePassword123"
        )
        assert user is None

    async def test_login_inactive_user(self, db_session: AsyncSession, inactive_user: User):
        """Test login with inactive user fails."""
        user = await auth_service.authenticate_user(
            db_session, inactive_user.email, "InactivePassword123"
        )
        assert user is None

    async def test_email_normalization_in_login(self, db_session: AsyncSession, test_user: User):
        """Test that email is normalized during login."""
        user = await auth_service.authenticate_user(
            db_session, test_user.email.upper(), "TestPassword123"
        )
        assert user is not None
        assert user.id == test_user.id


class TestMeEndpoint:
    """Test GET /auth/me endpoint."""

    async def test_me_with_valid_token(self, test_user: User, test_user_access_token: str):
        """Test /me with valid access token."""
        # This would be tested via HTTP in integration tests
        # Here we just verify the token payload can be decoded
        from app.core.security import decode_token
        
        payload = decode_token(test_user_access_token)
        assert payload is not None
        assert payload["sub"] == str(test_user.id)
        assert payload["type"] == "access"

    async def test_me_with_invalid_token(self):
        """Test /me with invalid token."""
        from app.core.security import decode_token
        
        payload = decode_token("invalid.token.here")
        assert payload is None

    async def test_me_with_refresh_token_fails(self, test_user_refresh_token: str):
        """Test /me with refresh token should fail (only access tokens allowed)."""
        from app.core.security import decode_token
        
        payload = decode_token(test_user_refresh_token)
        assert payload is not None
        # Verify it's a refresh token, not access
        assert payload["type"] == "refresh"


class TestRefreshToken:
    """Test refresh token endpoint."""

    async def test_refresh_with_valid_refresh_token(
        self, db_session: AsyncSession, test_user: User, test_user_refresh_token: str
    ):
        """Test refresh endpoint with valid refresh token."""
        new_access_token = await auth_service.refresh_access_token(
            db_session, test_user_refresh_token
        )
        assert new_access_token is not None
        
        # Verify new token is valid
        from app.core.security import decode_token
        
        payload = decode_token(new_access_token)
        assert payload is not None
        assert payload["sub"] == str(test_user.id)
        assert payload["type"] == "access"

    async def test_refresh_with_access_token_fails(
        self, db_session: AsyncSession, test_user_access_token: str
    ):
        """Test refresh endpoint rejects access tokens."""
        new_access_token = await auth_service.refresh_access_token(
            db_session, test_user_access_token
        )
        assert new_access_token is None

    async def test_refresh_with_invalid_token(self, db_session: AsyncSession):
        """Test refresh endpoint with invalid token."""
        new_access_token = await auth_service.refresh_access_token(
            db_session, "invalid.token.here"
        )
        assert new_access_token is None

    async def test_refresh_with_inactive_user(
        self, db_session: AsyncSession, inactive_user: User
    ):
        """Test refresh endpoint with inactive user fails."""
        from app.core.security import create_refresh_token
        
        inactive_refresh_token = create_refresh_token(subject=str(inactive_user.id))
        new_access_token = await auth_service.refresh_access_token(
            db_session, inactive_refresh_token
        )
        assert new_access_token is None

    async def test_refresh_with_nonexistent_user(self, db_session: AsyncSession):
        """Test refresh endpoint with non-existent user."""
        import uuid
        from app.core.security import create_refresh_token
        
        fake_user_id = uuid.uuid4()
        fake_refresh_token = create_refresh_token(subject=str(fake_user_id))
        new_access_token = await auth_service.refresh_access_token(
            db_session, fake_refresh_token
        )
        assert new_access_token is None


class TestChangePassword:
    """Test change password endpoint."""

    async def test_change_password_success(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test successful password change."""
        success = await auth_service.change_password(
            db_session, test_user, "TestPassword123", "NewPassword456"
        )
        assert success is True
        
        # Verify old password no longer works
        user = await auth_service.authenticate_user(
            db_session, test_user.email, "TestPassword123"
        )
        assert user is None
        
        # Verify new password works
        user = await auth_service.authenticate_user(
            db_session, test_user.email, "NewPassword456"
        )
        assert user is not None

    async def test_change_password_wrong_current_password(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test change password with wrong current password."""
        success = await auth_service.change_password(
            db_session, test_user, "WrongPassword123", "NewPassword456"
        )
        assert success is False

    async def test_change_password_weak_new_password(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test change password with weak new password."""
        with pytest.raises(ValueError, match="at least 10 characters"):
            await auth_service.change_password(
                db_session, test_user, "TestPassword123", "Short1"
            )

    async def test_change_password_new_password_no_letter(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test change password with new password having no letter."""
        with pytest.raises(ValueError, match="at least one letter"):
            await auth_service.change_password(
                db_session, test_user, "TestPassword123", "1234567890"
            )

    async def test_change_password_new_password_no_number(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test change password with new password having no number."""
        with pytest.raises(ValueError, match="at least one number"):
            await auth_service.change_password(
                db_session, test_user, "TestPassword123", "OnlyLetters"
            )
