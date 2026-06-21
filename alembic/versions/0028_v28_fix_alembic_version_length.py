"""v28 fix alembic version table column width.

The default alembic_version.version_num column is VARCHAR(32), but this
project's revision IDs can exceed 32 characters (e.g., revision 0014 is
36 chars). SQLite ignores the length constraint, but PostgreSQL enforces
it strictly, causing DataError on upgrade past 0013.

Widen the column to VARCHAR(64) to support all current and future
revision IDs. env.py also sets version_num_length=64 for fresh databases.

Revision ID: 0028_v28_fix_alembic_version_length
Revises: 0027_v27_pilot_outcome_records
Create Date: 2026-06-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0028_v28_fix_alembic_version_length"
down_revision: Union[str, None] = "0027_v27_pilot_outcome_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("alembic_version") as batch_op:
        batch_op.alter_column(
            "version_num",
            existing_type=sa.String(32),
            type_=sa.String(64),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("alembic_version") as batch_op:
        batch_op.alter_column(
            "version_num",
            existing_type=sa.String(64),
            type_=sa.String(32),
            existing_nullable=False,
        )
