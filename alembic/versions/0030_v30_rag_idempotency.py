"""v30 RAG idempotency and terminal error metadata.

Revision ID: 0030_v30_rag_idempotency
Revises: 0029_v29_traverse_audit_columns
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0030_v30_rag_idempotency"
down_revision: Union[str, None] = "0029_v29_traverse_audit_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("rag_runs") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("idempotency_scope", sa.String(80), nullable=True))
        batch_op.add_column(
            sa.Column("idempotency_fingerprint", sa.String(64), nullable=True)
        )
        batch_op.add_column(sa.Column("error_kind", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("retry_after_seconds", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_rag_runs_idempotency_scope_key",
            ["group_id", "user_id", "idempotency_scope", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("rag_runs") as batch_op:
        batch_op.drop_constraint(
            "uq_rag_runs_idempotency_scope_key", type_="unique"
        )
        batch_op.drop_column("retry_after_seconds")
        batch_op.drop_column("error_kind")
        batch_op.drop_column("idempotency_fingerprint")
        batch_op.drop_column("idempotency_scope")
        batch_op.drop_column("idempotency_key")
