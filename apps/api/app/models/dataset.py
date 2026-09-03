"""Dataset and DatasetVersion models."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrganizationScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Dataset(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrganizationScopedMixin):
    __tablename__ = "datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    # uploaded | validating | ready | failed

    project: Mapped["Project"] = relationship("Project", back_populates="datasets")
    versions: Mapped[List["DatasetVersion"]] = relationship(
        "DatasetVersion", back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dataset_versions"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. v1, v1.1
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    format: Mapped[str] = mapped_column(String(50), default="jsonl", nullable=False)

    # Content integrity
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    content_hash_algorithm: Mapped[str] = mapped_column(
        String(20), default="sha256", nullable=False
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )

    # Quality metrics (populated after validation)
    total_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    valid_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    invalid_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duplicate_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duplicate_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_training_tokens: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    train_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validation_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    warnings: Mapped[Optional[List[Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="versions")
