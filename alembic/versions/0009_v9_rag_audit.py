"""v9 rag run audit fields

Revision ID: 0009_v9_rag_audit
Revises: 0008_v7_agent_orchestration
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_v9_rag_audit"
down_revision = "0008_v7_agent_orchestration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_runs", sa.Column("status", sa.String(length=20), nullable=False, server_default="success"))
    op.add_column("rag_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("rag_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("rag_runs", sa.Column("retrieved_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("rag_runs", "retrieved_count")
    op.drop_column("rag_runs", "duration_ms")
    op.drop_column("rag_runs", "error_message")
    op.drop_column("rag_runs", "status")
