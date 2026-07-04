"""Rename document chunk columns.

Revision ID: 20260704_0003
Revises: 20260704_0002
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260704_0003"
down_revision: str | None = "20260704_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("document_chunks", "content", new_column_name="chunk_text")
    op.alter_column("document_chunks", "chunk_metadata", new_column_name="metadata")


def downgrade() -> None:
    op.alter_column("document_chunks", "metadata", new_column_name="chunk_metadata")
    op.alter_column("document_chunks", "chunk_text", new_column_name="content")
