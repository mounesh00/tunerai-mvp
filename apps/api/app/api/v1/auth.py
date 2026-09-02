"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.auth import (
    Token,
    UserCreate,
    UserLogin,
    UserRead,
    RefreshTokenRequest,
    ChangePasswordRequest,
)
from app.services import auth as auth_service

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: DbSession) -> UserRead:
    settings = get_settings()
    if not settings.enable_registration:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")
    try:
        user = await auth_service.create_user(db, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: DbSession) -> Token:
    user = await auth_service.authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return auth_service.create_tokens_for_user(user)


@router.post("/refresh", response_model=Token)
async def refresh(
    data: RefreshTokenRequest,
    db: DbSession,
) -> Token:
    """
    Refresh access token using a refresh token.
    """
    new_access_token = await auth_service.refresh_access_token(db, data.refresh_token)
    if new_access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Return new access token with same refresh token
    return Token(access_token=new_access_token, refresh_token=data.refresh_token)


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    data: ChangePasswordRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """
    Change password for authenticated user.
    """
    try:
        success = await auth_service.change_password(
            db, current_user, data.current_password, data.new_password
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
