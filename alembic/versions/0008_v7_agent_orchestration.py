"""v7 agent orchestration

Revision ID: 0008_v7_agent_orchestration
Revises: 0007_v4_conversations
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_v7_agent_orchestration"
down_revision = "0007_v4_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_phase", sa.String(length=20), nullable=True),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_group_id", "agent_runs", ["group_id"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("thought", sa.Text(), nullable=False),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("action_detail", sa.JSON(), nullable=False),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key", sa.String(length=240), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("ttl_days", sa.Integer(), nullable=True),
        sa.Column("source_run_id", sa.String(length=36), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_memories_group_id", "agent_memories", ["group_id"])
    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_memories_user_id", table_name="agent_memories")
    op.drop_index("ix_agent_memories_group_id", table_name="agent_memories")
    op.drop_table("agent_memories")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_group_id", table_name="agent_runs")
    op.drop_table("agent_runs")
