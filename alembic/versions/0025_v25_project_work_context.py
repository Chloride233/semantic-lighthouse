"""v25 project work context — S2.3A.

Add nullable project_id FK to conversations, tasks, and agent_runs.
No backfill; existing rows remain NULL. Indexed for list filtering.
Uses batch mode for SQLite compatibility.

Revision ID: 0025_v25_project_work_context
Revises: 0024_v24_project_evidence_links
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0025_v25_project_work_context"
down_revision: Union[str, None] = "0024_v24_project_evidence_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("conversations", "tasks", "agent_runs"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.String(36), nullable=True))
            batch_op.create_index(f"ix_{table}_project_id", ["project_id"])
            batch_op.create_foreign_key(
                f"fk_{table}_project_id",
                "business_projects", ["project_id"], ["id"],
            )


def downgrade() -> None:
    for table in ("agent_runs", "tasks", "conversations"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_project_id", type_="foreignkey")
            batch_op.drop_index(f"ix_{table}_project_id")
            batch_op.drop_column("project_id")
