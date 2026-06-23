"""v29 traverse audit columns for R2E.

Add nullable traverse-specific columns to ontology_runtime_audit:
  - path (JSON): ordered OT api_names traversed
  - hop_count (Integer): number of hops = len(path) - 1
  - link_type_api_names (JSON): resolved link_type api_name per hop
  - binding_ids (JSON): binding IDs per OT in path
  - dataset_ids (JSON): dataset IDs per OT in path

All nullable; query/activate records will have NULL for these columns.
SQLite compatible via batch_alter_table.

Revision ID: 0029_v29_traverse_audit_columns
Revises: 0028_v28_fix_alembic_version_length
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0029_v29_traverse_audit_columns"
down_revision: Union[str, None] = "0028_v28_fix_alembic_version_length"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ontology_runtime_audit") as batch_op:
        batch_op.add_column(sa.Column("path", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("hop_count", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("link_type_api_names", sa.JSON(), nullable=True)
        )
        batch_op.add_column(sa.Column("binding_ids", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("dataset_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ontology_runtime_audit") as batch_op:
        batch_op.drop_column("dataset_ids")
        batch_op.drop_column("binding_ids")
        batch_op.drop_column("link_type_api_names")
        batch_op.drop_column("hop_count")
        batch_op.drop_column("path")
