"""Add document content column.

Revision ID: 20260704_0002
Revises: 20260703_0001
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260704_0002"
down_revision: str | None = "20260703_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content", sa.Text(), server_default="", nullable=False))
    op.alter_column("documents", "content", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "content")
