"""v22 ontology dataset bindings

Revision ID: 0022_v22_ontology_dataset_bindings
Revises: 0021_v21_package_project_scope
Create Date: 2026-06-20

Phase 14.5 — Ontology Dataset Bindings.
- Adds ontology_dataset_bindings table.
- Binds business_v1 Object Types from project packages to DatasetAssets.
- property_mappings: {property_api_name: column_name}.
- Unique: (package_id, object_type_api_name).
- Never stores sample_values, raw rows, or storage_path.
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_v22_ontology_dataset_bindings"
down_revision = "0021_v21_package_project_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ontology_dataset_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), index=True, nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("business_projects.id"), index=True, nullable=False),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("ontology_model_packages.id"), index=True, nullable=False),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("dataset_assets.id"), index=True, nullable=False),
        sa.Column("object_type_api_name", sa.String(240), nullable=False),
        sa.Column("primary_key_column", sa.String(240), nullable=False),
        sa.Column("property_mappings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("package_id", "object_type_api_name", name="uq_dataset_binding_package_object_type"),
    )


def downgrade() -> None:
    op.drop_table("ontology_dataset_bindings")
