"""v23 ontology runtime audit

Revision ID: 0023_v23_ontology_runtime_audit
Revises: 0022_v22_ontology_dataset_bindings
Create Date: 2026-06-20

Phase 14.5 Review C — Ontology Runtime Audit.
- Adds ontology_runtime_audit table for immutable audit records.
- Records generate_bindings, query, activate operations.
- Never stores filter values, raw data, storage_path, PII, or secrets.
- Only field names, filter field names, row_count, error codes/summaries.
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_v23_ontology_runtime_audit"
down_revision = "0022_v22_ontology_dataset_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ontology_runtime_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), index=True, nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("business_projects.id"), index=True, nullable=False),
        sa.Column("operation", sa.String(30), index=True, nullable=False),
        sa.Column("object_type", sa.String(240), nullable=True),
        sa.Column("field_names", sa.JSON(), nullable=True),
        sa.Column("filter_field_names", sa.JSON(), nullable=True),
        sa.Column("limit_val", sa.Integer(), nullable=True),
        sa.Column("offset_val", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("ontology_runtime_audit")
