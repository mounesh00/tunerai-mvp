"""Enforce unique project slugs within an organization.

Revision ID: 004
Revises: 003
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_projects_org_slug",
        "projects",
        ["organization_id", "slug"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_projects_org_slug", "projects", type_="unique")