"""Deployment and inference schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DeploymentCreate(BaseModel):
    project_id: UUID
    model_version_id: UUID
    name: str = Field(..., min_length=1, max_length=255)


class DeploymentRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    model_version_id: UUID
    name: str
    endpoint_slug: str
    status: str
    inference_engine: str
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.2


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    rate_limit_rpm: Optional[int] = 60


class APIKeyRead(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    rate_limit_rpm: Optional[int] = None
    created_at: datetime
    # raw key only returned once at creation
    key: Optional[str] = None

    model_config = {"from_attributes": True}
