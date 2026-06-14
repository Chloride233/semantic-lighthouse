"""v4 conversations and multi-turn dialogue

Revision ID: 0007_v4_conversations
Revises: 0006_v34_ingestion_jobs
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_v4_conversations"
down_revision = "0006_v34_ingestion_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_group_id", "conversations", ["group_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("retrieval_method", sa.String(length=20), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=True),
        sa.Column("knowledge_gaps", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_index("ix_conversations_group_id", table_name="conversations")
    op.drop_table("conversations")
