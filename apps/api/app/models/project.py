"""Project model."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrganizationScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import Organization
    from app.models.dataset import Dataset
    from app.models.training import TrainingRun
    from app.models.model_registry import Model


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrganizationScopedMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_projects_org_slug"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. cybersecurity
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset", back_populates="project", cascade="all, delete-orphan"
    )
    training_runs: Mapped[List["TrainingRun"]] = relationship(
        "TrainingRun", back_populates="project", cascade="all, delete-orphan"
    )
    models: Mapped[List["Model"]] = relationship(
        "Model", back_populates="project", cascade="all, delete-orphan"
    )
