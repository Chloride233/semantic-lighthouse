"""v16 ontology modeling drafts

Revision ID: 0016_v16_ontology_modeling_drafts
Revises: 0015_v15_ontology_issue_triage
Create Date: 2026-06-19

Phase 11.1 — Ontology Modeling Drafts v1 read model.
App-internal, group-scoped, audit-trailed proposals.
Not production schema, not written back to external KB.
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_v16_ontology_modeling_drafts"
down_revision = "0015_v15_ontology_issue_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ontology_modeling_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), index=True, nullable=False),
        sa.Column("draft_type", sa.String(20), index=True, nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), index=True, nullable=False, server_default="proposed"),
        sa.Column("source_entity_id", sa.String(36), sa.ForeignKey("ontology_entities.id"), index=True, nullable=True),
        sa.Column("source_relation_id", sa.String(36), sa.ForeignKey("ontology_relations.id"), index=True, nullable=True),
        sa.Column("source_issue_id", sa.String(36), sa.ForeignKey("ontology_validation_issues.id"), index=True, nullable=True),
        sa.Column("source_rag_run_id", sa.String(36), sa.ForeignKey("rag_runs.id"), index=True, nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ontology_modeling_drafts")
