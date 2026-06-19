"""v17 ontology model packages

Revision ID: 0017_v17_ontology_model_packages
Revises: 0016_v16_ontology_modeling_drafts
Create Date: 2026-06-19

Phase 12.3a — Ontology Model Packages v1 schema foundation.
Immutable, versioned, content-hashed JSON contract snapshots.
No UPDATE path. source_draft_ids is audit trail only.
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_v17_ontology_model_packages"
down_revision = "0016_v16_ontology_modeling_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ontology_model_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"),
                  index=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(10), nullable=False,
                  server_default="1.0"),
        sa.Column("content_hash", sa.String(64), index=True, nullable=False),
        sa.Column("contract_json", sa.JSON(), nullable=False,
                  server_default="{}"),
        sa.Column("source_draft_ids", sa.JSON(), nullable=False,
                  server_default="[]"),
        sa.Column("draft_count", sa.Integer(), nullable=False),
        sa.Column("quality_status", sa.String(10), nullable=False),
        sa.Column("quality_summary", sa.JSON(), nullable=False,
                  server_default="{}"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "version",
                            name="uq_onto_pkg_group_version"),
        sa.UniqueConstraint("group_id", "content_hash",
                            name="uq_onto_pkg_group_hash"),
    )


def downgrade() -> None:
    op.drop_table("ontology_model_packages")
