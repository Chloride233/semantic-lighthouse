"""v14 make ontology_validation_issues.document_id nullable

Revision ID: 0014_v14_ontology_issue_nullable_doc
Revises: 0013_v13_ontology_relations
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_v14_ontology_issue_nullable_doc"
down_revision = "0013_v13_ontology_relations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ontology_validation_issues") as batch:
        batch.alter_column("document_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("ontology_validation_issues") as batch:
        batch.alter_column("document_id", existing_type=sa.String(36), nullable=False)
