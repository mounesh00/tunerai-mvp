"""Training schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TrainingRunCreate(BaseModel):
    project_id: UUID
    dataset_version_id: UUID
    base_model: str = Field(..., min_length=1, max_length=255)
    preset: str = Field(default="balanced", pattern="^(fast|balanced|quality|custom)$")
    strategy: str = Field(default="qlora", pattern="^(qlora|lora|sft)$")
    overrides: Optional[Dict[str, Any]] = None


class TrainingEstimateRequest(BaseModel):
    base_model: str
    dataset_version_id: UUID
    preset: str = "balanced"
    strategy: str = "qlora"
    overrides: Optional[Dict[str, Any]] = None


class TrainingEstimateResponse(BaseModel):
    estimated_vram_gb: float
    estimated_time_minutes: float
    estimated_cost_usd: float
    estimated_storage_gb: float
    total_steps: int
    note: str
    config: Dict[str, Any]
    supported_models: List[str]


class TrainingRunRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    dataset_version_id: UUID
    training_config_id: UUID
    base_model: str
    status: str
    progress: Optional[float] = None
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    train_loss: Optional[float] = None
    eval_loss: Optional[float] = None
    logs: Optional[str] = None
    error_message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    estimated_vram_gb: Optional[float] = None
    estimated_time_minutes: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
