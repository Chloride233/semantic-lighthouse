"""v11 document archive audit fields

Revision ID: 0011_v11_document_archive_audit
Revises: 0010_v10_tasks
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_v11_document_archive_audit"
down_revision = "0010_v10_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("archived_by", sa.String(length=36), nullable=True))
    op.add_column("documents", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("archive_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "archive_reason")
    op.drop_column("documents", "archived_at")
    op.drop_column("documents", "archived_by")
