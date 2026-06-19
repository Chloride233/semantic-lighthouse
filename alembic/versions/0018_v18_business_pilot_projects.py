"""v18 business pilot projects

Revision ID: 0018_v18_business_pilot_projects
Revises: 0017_v17_ontology_model_packages
Create Date: 2026-06-19

Phase 14.1 — Business Pilot Project Foundation.
Each group can contain multiple business pilot projects.
Stage is backend-controlled (goal → data → model → validate → pilot).
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_v18_business_pilot_projects"
down_revision = "0017_v17_ontology_model_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"),
                  index=True, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("business_goal", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("entry_mode", sa.String(20), nullable=False),
        sa.Column("industry_template", sa.String(80), nullable=True),
        sa.Column("stage", sa.String(20), nullable=False,
                  server_default="goal"),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="active"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("business_projects")
