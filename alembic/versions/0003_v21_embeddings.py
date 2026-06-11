"""v2.1 document chunk embeddings

Revision ID: 0003_v21_embeddings
Revises: 0002_v2_documents
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

from pgvector.sqlalchemy import Vector

revision = "0003_v21_embeddings"
down_revision = "0002_v2_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        embedding_type = Vector(1024)
    else:
        embedding_type = sa.JSON()

    op.add_column("document_chunks", sa.Column("embedding", embedding_type, nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(length=120), nullable=True))
    op.add_column("document_chunks", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "embedded_at")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")
