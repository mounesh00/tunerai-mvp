"""Dataset schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    project_id: UUID


class DatasetRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatasetVersionRead(BaseModel):
    id: UUID
    dataset_id: UUID
    version: str
    original_filename: str
    format: str
    total_records: Optional[int] = None
    valid_records: Optional[int] = None
    invalid_records: Optional[int] = None
    duplicate_count: Optional[int] = None
    duplicate_percentage: Optional[float] = None

    # Content integrity
    content_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None

    avg_tokens: Optional[float] = None
    max_tokens: Optional[int] = None
    estimated_training_tokens: Optional[int] = None
    train_size: Optional[int] = None
    validation_size: Optional[int] = None
    quality_score: Optional[float] = None
    quality_report: Optional[Dict[str, Any]] = None
    warnings: Optional[List[Any]] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatasetWithVersions(DatasetRead):
    versions: List[DatasetVersionRead] = []


class QualityReportResponse(BaseModel):
    dataset_id: UUID
    version_id: UUID
    status: str
    report: Dict[str, Any]
