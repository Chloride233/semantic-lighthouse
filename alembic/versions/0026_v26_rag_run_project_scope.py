"""v26 rag run project scope - S2.4C.

Add nullable project_id FK to rag_runs for project-bounded RAG answers.
No backfill; existing group-scoped runs remain NULL.

Revision ID: 0026_v26_rag_run_project_scope
Revises: 0025_v25_project_work_context
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0026_v26_rag_run_project_scope"
down_revision: Union[str, None] = "0025_v25_project_work_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("rag_runs") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.String(36), nullable=True))
        batch_op.create_index("ix_rag_runs_project_id", ["project_id"])
        batch_op.create_foreign_key(
            "fk_rag_runs_project_id",
            "business_projects",
            ["project_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("rag_runs") as batch_op:
        batch_op.drop_constraint("fk_rag_runs_project_id", type_="foreignkey")
        batch_op.drop_index("ix_rag_runs_project_id")
        batch_op.drop_column("project_id")
