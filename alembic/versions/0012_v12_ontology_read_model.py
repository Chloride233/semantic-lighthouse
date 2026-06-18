"""v12 ontology read model entities and validation issues

Revision ID: 0012_v12_ontology_read_model
Revises: 0011_v11_document_archive_audit
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_v12_ontology_read_model"
down_revision = "0011_v11_document_archive_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ontology_entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False, index=True),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_path", sa.String(1024), nullable=False),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("status", sa.String(80), nullable=True, index=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("group_id", "document_id", name="uq_onto_entity_group_doc"),
    )
    op.create_table(
        "ontology_validation_issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("ontology_entities.id"), nullable=True, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("code", sa.String(80), nullable=False, index=True),
        sa.Column("field", sa.String(80), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_path", sa.String(1024), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ontology_validation_issues")
    op.drop_table("ontology_entities")
