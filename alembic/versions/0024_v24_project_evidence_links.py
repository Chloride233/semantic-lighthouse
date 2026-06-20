"""0024_v24_project_evidence_links — S2.2 Project Evidence Links.

Create project_evidence_links table with unique constraint
on (project_id, evidence_type, evidence_id).

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0024_v24_project_evidence_links"
down_revision: Union[str, None] = "0023_v23_ontology_runtime_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_evidence_links",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), index=True, nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("business_projects.id"), index=True, nullable=False),
        sa.Column("evidence_type", sa.String(20), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("removed_by", sa.String(36), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "evidence_type", "evidence_id", name="uq_project_evidence_link"),
    )


def downgrade() -> None:
    op.drop_table("project_evidence_links")
