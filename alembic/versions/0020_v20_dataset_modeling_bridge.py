"""v20 dataset-to-modeling bridge

Revision ID: 0020_v20_dataset_modeling_bridge
Revises: 0019_v19_dataset_assets
Create Date: 2026-06-19

Phase 14.3 — Data-to-Model Bridge.
Adds project_id and source_dataset_id to ontology_modeling_drafts.
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_v20_dataset_modeling_bridge"
down_revision = "0019_v19_dataset_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ontology_modeling_drafts") as batch_op:
        batch_op.add_column(sa.Column(
            "project_id", sa.String(36),
            nullable=True,
        ))
        batch_op.create_index(
            "ix_ontology_modeling_drafts_project_id",
            ["project_id"],
        )
        batch_op.create_foreign_key(
            "fk_ontology_modeling_drafts_project_id",
            "business_projects", ["project_id"], ["id"],
        )
        batch_op.add_column(sa.Column(
            "source_dataset_id", sa.String(36),
            nullable=True,
        ))
        batch_op.create_index(
            "ix_ontology_modeling_drafts_source_dataset_id",
            ["source_dataset_id"],
        )
        batch_op.create_foreign_key(
            "fk_ontology_modeling_drafts_source_dataset_id",
            "dataset_assets", ["source_dataset_id"], ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ontology_modeling_drafts") as batch_op:
        batch_op.drop_constraint(
            "fk_ontology_modeling_drafts_source_dataset_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_ontology_modeling_drafts_source_dataset_id")
        batch_op.drop_column("source_dataset_id")
        batch_op.drop_constraint(
            "fk_ontology_modeling_drafts_project_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_ontology_modeling_drafts_project_id")
        batch_op.drop_column("project_id")
