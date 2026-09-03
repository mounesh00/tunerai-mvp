"""Add content_hash to dataset_versions for duplicate detection

Revision ID: 002
Revises: 001
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add content_hash (with index for duplicate detection)
    op.add_column(
        "dataset_versions",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_dataset_versions_content_hash",
        "dataset_versions",
        ["content_hash"],
    )

    # Add content_hash_algorithm for future algorithm migration support
    op.add_column(
        "dataset_versions",
        sa.Column(
            "content_hash_algorithm",
            sa.String(20),
            nullable=False,
            server_default="sha256",
        ),
    )

    # Add file_size_bytes for tracking and analytics
    op.add_column(
        "dataset_versions",
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_versions_content_hash", table_name="dataset_versions")
    op.drop_column("dataset_versions", "file_size_bytes")
    op.drop_column("dataset_versions", "content_hash_algorithm")
    op.drop_column("dataset_versions", "content_hash")
