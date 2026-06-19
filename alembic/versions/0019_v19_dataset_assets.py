"""v19 project dataset assets and profiling

Revision ID: 0019_v19_dataset_assets
Revises: 0018_v18_business_pilot_projects
Create Date: 2026-06-19

Phase 14.2 — Dataset Asset storage and profiling.
Each business pilot project can contain multiple dataset assets.
Metadata-first: profile_json stores column statistics, not raw rows.
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_v19_dataset_assets"
down_revision = "0018_v18_business_pilot_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"),
                  index=True, nullable=False),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("business_projects.id"),
                  index=True, nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("file_format", sa.String(10), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="ready"),
        sa.Column("row_count", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("column_count", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("profile_json", sa.JSON(), nullable=False,
                  server_default="{}"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "content_hash",
                            name="uq_dataset_assets_project_hash"),
    )


def downgrade() -> None:
    op.drop_table("dataset_assets")
