"""v13 ontology wikilink relations

Revision ID: 0013_v13_ontology_relations
Revises: 0012_v12_ontology_read_model
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_v13_ontology_relations"
down_revision = "0012_v12_ontology_read_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ontology_relations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False, index=True),
        sa.Column("source_entity_id", sa.String(36), sa.ForeignKey("ontology_entities.id"), nullable=False, index=True),
        sa.Column("source_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("target_entity_id", sa.String(36), sa.ForeignKey("ontology_entities.id"), nullable=True, index=True),
        sa.Column("target_path", sa.String(1024), nullable=False, index=True),
        sa.Column("target_label", sa.String(240), nullable=True),
        sa.Column("relation_type", sa.String(80), nullable=False, index=True, server_default="wikilink"),
        sa.Column("status", sa.String(20), nullable=False, index=True, server_default="unresolved"),
        sa.Column("evidence_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("group_id", "source_entity_id", "target_path", "target_label", name="uq_onto_relation"),
    )


def downgrade() -> None:
    op.drop_table("ontology_relations")
