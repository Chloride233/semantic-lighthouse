"""v21 package project scope

Revision ID: 0021_v21_package_project_scope
Revises: 0020_v20_dataset_modeling_bridge
Create Date: 2026-06-19

Phase 14.4 — Project-scoped packages.
- Adds project_id (nullable FK) and scope_key (non-null) to ontology_model_packages.
- Replaces old group-scoped unique constraints with (group_id, scope_key).
- Legacy packages: project_id=null, scope_key='group'.
- Project packages: project_id set, scope_key='project:{project_id}'.
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_v21_package_project_scope"
down_revision = "0020_v20_dataset_modeling_bridge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ontology_model_packages") as batch_op:
        # Add new columns
        batch_op.add_column(sa.Column(
            "project_id", sa.String(36),
            nullable=True,
        ))
        batch_op.add_column(sa.Column(
            "scope_key", sa.String(80),
            nullable=False, server_default="group",
        ))
        batch_op.create_index(
            "ix_ontology_model_packages_project_id",
            ["project_id"],
        )
        batch_op.create_foreign_key(
            "fk_ontology_model_packages_project_id",
            "business_projects", ["project_id"], ["id"],
        )

        # Drop old group-scoped unique constraints
        batch_op.drop_constraint(
            "uq_onto_pkg_group_version", type_="unique",
        )
        batch_op.drop_constraint(
            "uq_onto_pkg_group_hash", type_="unique",
        )

        # Create new scope-aware unique constraints
        batch_op.create_unique_constraint(
            "uq_onto_pkg_scope_version",
            ["group_id", "scope_key", "version"],
        )
        batch_op.create_unique_constraint(
            "uq_onto_pkg_scope_hash",
            ["group_id", "scope_key", "content_hash"],
        )


def downgrade() -> None:
    # Before downgrading: check if there are non-legacy packages (project_id not null)
    # that would collide under the old group-scoped unique constraints.
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM ontology_model_packages "
            "WHERE project_id IS NOT NULL"
        )
    ).scalar()
    if row and row > 0:
        raise RuntimeError(
            "Cannot downgrade: there are project-scoped packages in the database. "
            "The old group-scoped unique constraints would conflict. "
            "Remove project-scoped packages before downgrading."
        )

    with op.batch_alter_table("ontology_model_packages") as batch_op:
        # Drop scope-aware constraints
        batch_op.drop_constraint(
            "uq_onto_pkg_scope_hash", type_="unique",
        )
        batch_op.drop_constraint(
            "uq_onto_pkg_scope_version", type_="unique",
        )

        # Restore old group-scoped unique constraints
        batch_op.create_unique_constraint(
            "uq_onto_pkg_group_hash",
            ["group_id", "content_hash"],
        )
        batch_op.create_unique_constraint(
            "uq_onto_pkg_group_version",
            ["group_id", "version"],
        )

        # Drop new columns and indices
        batch_op.drop_constraint(
            "fk_ontology_model_packages_project_id", type_="foreignkey",
        )
        batch_op.drop_index("ix_ontology_model_packages_project_id")
        batch_op.drop_column("scope_key")
        batch_op.drop_column("project_id")
