"""v27 pilot outcome records - Phase 16.1.

Add pilot_outcome_records table for immutable FDE delivery snapshots.
Each record snapshots a business pilot project's goal, evidence refs,
package refs, query refs, decision, risks, and next actions.

Revision ID: 0027_v27_pilot_outcome_records
Revises: 0026_v26_rag_run_project_scope
Create Date: 2026-06-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0027_v27_pilot_outcome_records"
down_revision: Union[str, None] = "0026_v26_rag_run_project_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pilot_outcome_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), index=True, nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("business_projects.id"), index=True, nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("business_goal_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("selected_evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("package_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("query_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("decision_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("risks", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("next_actions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pilot_outcome_records")
