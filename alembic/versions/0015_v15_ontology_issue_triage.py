"""v15 ontology validation issue triage fields

Revision ID: 0015_v15_ontology_issue_triage
Revises: 0014_v14_ontology_issue_nullable_doc
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_v15_ontology_issue_triage"
down_revision = "0014_v14_ontology_issue_nullable_doc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ontology_validation_issues") as batch:
        batch.add_column(sa.Column("issue_key", sa.String(400), nullable=True))
        batch.create_index("ix_onto_issues_issue_key", ["issue_key"])
        batch.add_column(sa.Column("triage_status", sa.String(20), nullable=False, server_default="pending"))
        batch.create_index("ix_onto_issues_triage_status", ["triage_status"])
        batch.add_column(sa.Column("triaged_by", sa.String(36), nullable=True))
        batch.add_column(sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("triage_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ontology_validation_issues") as batch:
        batch.drop_column("triage_note")
        batch.drop_column("triaged_at")
        batch.drop_column("triaged_by")
        batch.drop_column("triage_status")
        batch.drop_column("issue_key")
