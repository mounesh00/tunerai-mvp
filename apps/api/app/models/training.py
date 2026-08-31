"""TrainingRun and TrainingConfig models."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrganizationScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class TrainingConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_configs"

    # Hyperparameters stored as structured JSON for flexibility
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preset: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # fast | balanced | quality | custom
    strategy: Mapped[str] = mapped_column(String(50), default="qlora", nullable=False)  # qlora | lora | sft


class TrainingRun(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrganizationScopedMixin):
    __tablename__ = "training_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False
    )
    training_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_configs.id", ondelete="RESTRICT"), nullable=False
    )
    base_model: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. Qwen/Qwen2.5-7B-Instruct
    status: Mapped[str] = mapped_column(String(50), default="QUEUED", nullable=False, index=True)
    # QUEUED | PREPARING | TRAINING | EVALUATING | PACKAGING | COMPLETED | FAILED | CANCELLED

    progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.0 - 1.0
    current_epoch: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_epochs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    train_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eval_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    estimated_vram_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_time_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="training_runs")
    training_config: Mapped["TrainingConfig"] = relationship("TrainingConfig")
