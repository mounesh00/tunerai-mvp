"""Authentication and user schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    organization_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets MVP security policy."""
        from app.core.password import validate_password
        
        is_valid, error_msg = validate_password(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets MVP security policy."""
        from app.core.password import validate_password
        
        is_valid, error_msg = validate_password(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=10, max_length=128)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)
