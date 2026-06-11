"""v2.2 chunked document uploads

Revision ID: 0005_v22_chunked_uploads
Revises: 0004_v33_rag_runs
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_v22_chunked_uploads"
down_revision = "0004_v33_rag_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("file_hash", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("mime_type", sa.String(length=120), nullable=True))
    op.add_column("documents", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("original_storage_path", sa.String(length=1024), nullable=True))
    op.add_column("documents", sa.Column("parser", sa.String(length=80), nullable=True))
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"])

    op.execute("UPDATE documents SET file_hash = content_hash WHERE file_hash IS NULL")
    op.execute("UPDATE documents SET mime_type = 'text/markdown' WHERE mime_type IS NULL")
    op.execute("UPDATE documents SET parser = 'markdown' WHERE parser IS NULL")

    op.create_table(
        "document_upload_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_upload_sessions_group_id", "document_upload_sessions", ["group_id"])
    op.create_index("ix_document_upload_sessions_file_hash", "document_upload_sessions", ["file_hash"])

    op.create_table(
        "document_upload_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("upload_id", sa.String(length=36), sa.ForeignKey("document_upload_sessions.id"), nullable=False),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("upload_id", "chunk_index", name="uq_upload_chunks_upload_index"),
    )
    op.create_index("ix_document_upload_chunks_upload_id", "document_upload_chunks", ["upload_id"])
    op.create_index("ix_document_upload_chunks_group_id", "document_upload_chunks", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_document_upload_chunks_group_id", table_name="document_upload_chunks")
    op.drop_index("ix_document_upload_chunks_upload_id", table_name="document_upload_chunks")
    op.drop_table("document_upload_chunks")
    op.drop_index("ix_document_upload_sessions_file_hash", table_name="document_upload_sessions")
    op.drop_index("ix_document_upload_sessions_group_id", table_name="document_upload_sessions")
    op.drop_table("document_upload_sessions")
    op.drop_index("ix_documents_file_hash", table_name="documents")
    op.drop_column("documents", "parser")
    op.drop_column("documents", "original_storage_path")
    op.drop_column("documents", "file_size")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "file_hash")
