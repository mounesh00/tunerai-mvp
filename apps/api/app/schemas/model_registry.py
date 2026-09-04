"""Model registry schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ModelCreate(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    domain: Optional[str] = None


class ModelVersionRead(BaseModel):
    id: UUID
    model_id: UUID
    version: str
    base_model: str
    training_method: str
    dataset_version_id: Optional[UUID] = None
    training_run_id: Optional[UUID] = None
    training_config: Optional[Dict[str, Any]] = None
    evaluation_results: Optional[Dict[str, Any]] = None
    domain_score: Optional[float] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    versions: List[ModelVersionRead] = []

    model_config = {"from_attributes": True}
