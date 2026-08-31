"""Evaluation models."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, OrganizationScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Evaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrganizationScopedMixin):
    __tablename__ = "evaluations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    benchmark_type: Mapped[str] = mapped_column(String(100), default="custom", nullable=False)
    # custom | cybersec | instruction | safety


class EvaluationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_runs"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False
    )
    base_model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # null when comparing against original base HF model
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    results: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    # {
    #   "domain_accuracy": {"base": 0.62, "tuned": 0.81, "delta": 0.19},
    #   "instruction_following": {...},
    #   "factuality": {...},
    #   "safety": {...},
    #   "latency_ms": {...},
    #   "improvement": true,
    #   "regression_detected": false,
    #   "summary": "..."
    # }
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
