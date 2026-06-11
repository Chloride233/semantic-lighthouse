"""v3.4 ingestion jobs and ETL pipeline

Revision ID: 0006_v34_ingestion_jobs
Revises: 0005_v22_chunked_uploads
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_v34_ingestion_jobs"
down_revision = "0005_v22_chunked_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ingestion_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("upload_session_id", sa.String(length=36), sa.ForeignKey("document_upload_sessions.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_step", sa.String(length=40), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("step_log", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_group_id", "ingestion_jobs", ["group_id"])
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])

    # HNSW index on document_chunks.embedding — PostgreSQL-only.
    # m=16, ef_construction=200 is the pgvector conservative default, suitable
    # for prototype-scale (< 1M vectors).  SQLite is skipped automatically
    # because it has no pgvector extension.
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
                "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 200)"
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw"))

    op.drop_index("ix_ingestion_jobs_document_id", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_group_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "ingestion_error")
