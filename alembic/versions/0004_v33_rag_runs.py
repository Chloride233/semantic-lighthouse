"""v3.3 rag run audit records

Revision ID: 0004_v33_rag_runs
Revises: 0003_v21_embeddings
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_v33_rag_runs"
down_revision = "0003_v21_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("retrieval_method", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("knowledge_gaps", sa.JSON(), nullable=False),
        sa.Column("next_steps", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rag_runs_group_id", "rag_runs", ["group_id"])
    op.create_index("ix_rag_runs_user_id", "rag_runs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_runs_user_id", table_name="rag_runs")
    op.drop_index("ix_rag_runs_group_id", table_name="rag_runs")
    op.drop_table("rag_runs")
