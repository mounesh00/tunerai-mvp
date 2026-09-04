"""Enforce per-dataset content hash uniqueness.

Revision ID: 003
Revises: 002
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_dataset_versions_dataset_content_hash",
        "dataset_versions",
        ["dataset_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_dataset_versions_dataset_content_hash",
        "dataset_versions",
        type_="unique",
    )