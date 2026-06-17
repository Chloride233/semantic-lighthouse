"""v10 lightweight task board (product alignment A.3)

Revision ID: 0010_v10_tasks
Revises: 0009_v9_rag_audit
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_v10_tasks"
down_revision = "0009_v9_rag_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_tasks_group_id", "tasks", ["group_id"])
    op.create_index("ix_tasks_source_id", "tasks", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_source_id", table_name="tasks")
    op.drop_index("ix_tasks_group_id", table_name="tasks")
    op.drop_table("tasks")
