from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from semantic_lighthouse.vector_types import VectorType


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    memberships: Mapped[list[GroupMembership]] = relationship(back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=new_id)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    memberships: Mapped[list[GroupMembership]] = relationship(back_populates="group")


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_memberships_group_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    group: Mapped[Group] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class GroupInvite(Base):
    __tablename__ = "group_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    invite_code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class GroupJoinRequest(Base):
    __tablename__ = "group_join_requests"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "status", name="uq_join_requests_group_user_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("group_id", "content_hash", name="uq_documents_group_content_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    original_storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    parser: Mapped[str | None] = mapped_column(String(80), nullable=True)
    frontmatter: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    heading_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(VectorType(1024), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")


class DocumentUploadSession(Base):
    __tablename__ = "document_upload_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chunk_size: Mapped[int] = mapped_column(nullable=False)
    total_chunks: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploading")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list[DocumentUploadChunk]] = relationship(
        back_populates="upload_session",
        cascade="all, delete-orphan",
    )


class DocumentUploadChunk(Base):
    __tablename__ = "document_upload_chunks"
    __table_args__ = (UniqueConstraint("upload_id", "chunk_index", name="uq_upload_chunks_upload_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    upload_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_upload_sessions.id"),
        index=True,
        nullable=False,
    )
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    chunk_size: Mapped[int] = mapped_column(nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    upload_session: Mapped[DocumentUploadSession] = relationship(back_populates="chunks")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True, nullable=False)
    upload_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_upload_sessions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    current_step: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_log: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RagRun(Base):
    __tablename__ = "rag_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    retrieval_method: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    citations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    knowledge_gaps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    next_steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    retrieval_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    knowledge_gaps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tool_calls: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=True
    )
    conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    plan_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list[AgentStep]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id"), index=True, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    step_index: Mapped[int] = mapped_column(nullable=False)
    thought: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    action_detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[AgentRun] = relationship(back_populates="steps")


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(240), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    ttl_days: Mapped[int | None] = mapped_column(nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OntologyEntity(Base):
    """Phase 9 read model — extracted from document frontmatter."""

    __tablename__ = "ontology_entities"
    __table_args__ = (
        UniqueConstraint("group_id", "document_id", name="uq_onto_entity_group_doc"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OntologyValidationIssue(Base):
    """Phase 9 read model — governance issues from frontmatter validation."""

    __tablename__ = "ontology_validation_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), index=True, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ontology_entities.id"), index=True, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    field: Mapped[str | None] = mapped_column(String(80), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    issue_key: Mapped[str | None] = mapped_column(String(400), index=True, nullable=True)
    triage_status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="pending")
    triaged_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triage_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class OntologyRelation(Base):
    """Phase 9.3 read model — wikilink relations extracted from documents.

    Status: resolved (target entity found in same group) or unresolved.
    """

    __tablename__ = "ontology_relations"
    __table_args__ = (
        UniqueConstraint(
            "group_id", "source_entity_id", "target_path", "target_label",
            name="uq_onto_relation",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), index=True, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("ontology_entities.id"), index=True, nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True, nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ontology_entities.id"), index=True, nullable=True)
    target_path: Mapped[str] = mapped_column(String(1024), index=True, nullable=False)
    target_label: Mapped[str | None] = mapped_column(String(240), nullable=True)
    relation_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False, default="wikilink")
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="unresolved")
    evidence_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OntologyModelingDraft(Base):
    """Phase 11 read model — human-reviewable Object Type / Property / Link Type / Action Type proposals.

    Drafts are app-internal, group-scoped, audit-trailed proposals (proposed / accepted / rejected).
    They are NOT production schema and are NOT written back to the external KB.
    Agent may read but never auto-create/accept/publish.
    """

    __tablename__ = "ontology_modeling_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    draft_type: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False
    )  # object_type | property | link_type | action_type
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False, default="proposed"
    )  # proposed | accepted | rejected
    source_entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ontology_entities.id"), index=True, nullable=True
    )
    source_relation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ontology_relations.id"), index=True, nullable=True
    )
    source_issue_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ontology_validation_issues.id"), index=True, nullable=True
    )
    source_rag_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rag_runs.id"), index=True, nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=True
    )
    source_dataset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dataset_assets.id"), index=True, nullable=True
    )
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class OntologyModelPackage(Base):
    """Phase 12.3+14.4 — immutable snapshot of accepted modeling drafts.

    Versioned, content-hashed JSON contract. Immutable after creation
    (no UPDATE path). source_draft_ids is audit trail only, not a
    mutable FK relationship.

    Phase 14.4: project_id and scope_key enable project-scoped packages.
    scope_key = "group" for legacy group-wide packages.
    scope_key = "project:{project_id}" for project-scoped packages.
    """

    __tablename__ = "ontology_model_packages"
    __table_args__ = (
        UniqueConstraint("group_id", "scope_key", "version",
                         name="uq_onto_pkg_scope_version"),
        UniqueConstraint("group_id", "scope_key", "content_hash",
                         name="uq_onto_pkg_scope_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=True
    )
    scope_key: Mapped[str] = mapped_column(
        String(80), nullable=False, default="group"
    )
    version: Mapped[int] = mapped_column(nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(10), nullable=False, default="1.0"
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    contract_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_draft_ids: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )
    draft_count: Mapped[int] = mapped_column(nullable=False)
    quality_status: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    quality_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Task(Base):
    """Lightweight user-confirmed task from RAG next_steps.

    Product alignment §7 — tasks are traceable work items, not a full PM system.
    source_type: rag_run | conversation | agent_run | manual.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | in_progress | done | cancelled
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # rag_run | conversation | agent_run | manual
    source_id: Mapped[str] = mapped_column(
        String(36), index=True, nullable=False
    )  # informational FK — no DB cascade
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DatasetAsset(Base):
    """Phase 14.2 — uploaded dataset within a business pilot project.

    Metadata-first: profile_json stores column statistics, not raw rows.
    Binary data lives on disk under dataset-storage/, never in the DB.
    """

    __tablename__ = "dataset_assets"
    __table_args__ = (
        UniqueConstraint("project_id", "content_hash", name="uq_dataset_assets_project_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_format: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # csv | xlsx
    file_size: Mapped[int] = mapped_column(nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ready"
    )  # ready | failed | archived
    row_count: Mapped[int] = mapped_column(nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(nullable=False, default=0)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class OntologyDatasetBinding(Base):
    """Phase 14.5 — explicit binding between a business_v1 Object Type and a DatasetAsset.

    Each package + object_type_api_name can have only one active binding.
    property_mappings maps property api_name → dataset column name.
    Never stores sample_values, raw rows, or storage_path.
    """

    __tablename__ = "ontology_dataset_bindings"
    __table_args__ = (
        UniqueConstraint(
            "package_id", "object_type_api_name",
            name="uq_dataset_binding_package_object_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=False
    )
    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ontology_model_packages.id"), index=True, nullable=False
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_assets.id"), index=True, nullable=False
    )
    object_type_api_name: Mapped[str] = mapped_column(
        String(240), nullable=False
    )
    primary_key_column: Mapped[str] = mapped_column(String(240), nullable=False)
    property_mappings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | stale
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class OntologyRuntimeAudit(Base):
    """Phase 14.5 — immutable audit record for runtime operations.

    Records generate_bindings, query, and activate events.
    Never stores filter values, raw data, storage_path, PII,
    stack traces, or secrets.
    """

    __tablename__ = "ontology_runtime_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=False
    )
    operation: Mapped[str] = mapped_column(
        String(30), index=True, nullable=False
    )  # generate_bindings | query | activate
    object_type: Mapped[str | None] = mapped_column(String(240), nullable=True)
    field_names: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    filter_field_names: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    limit_val: Mapped[int | None] = mapped_column(nullable=True)
    offset_val: Mapped[int | None] = mapped_column(nullable=True)
    outcome: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # success | failure | empty
    row_count: Mapped[int | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # R2E — traverse-specific fields (nullable, query/activate records have NULL)
    path: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    hop_count: Mapped[int | None] = mapped_column(nullable=True)
    link_type_api_names: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    binding_ids: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    dataset_ids: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class BusinessProject(Base):
    """Phase 14.1 — business pilot project within a group workspace.

    A group can contain multiple projects. Each project follows the
    goal → data → model → validate → pilot progression.
    Stage is backend-controlled; clients cannot set it arbitrarily.
    """

    __tablename__ = "business_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    business_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    entry_mode: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # problem_first | data_first
    industry_template: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )  # e.g. ecommerce / manufacturing
    stage: Mapped[str] = mapped_column(
        String(20), nullable=False, default="goal"
    )  # goal | data | model | validate | pilot
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | archived
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

class PilotOutcomeRecord(Base):
    """Phase 16.1 — immutable FDE delivery snapshot for a business pilot project.

    Multiple records per project are allowed. Latest determined by created_at desc.
    No PATCH/DELETE in v1. Never stores raw prompts, answers, secrets, or paths.

    selected_evidence_refs: bounded provenance per evidence link (no raw content/paths).
    package_refs: id/version/hash/quality_status/draft_count per package (no contract_json).
    query_refs: client-provided objects validated for forbidden keys (no secrets/paths/raw data).
    """

    __tablename__ = "pilot_outcome_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    business_goal_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selected_evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    package_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    query_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    decision_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    next_actions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ProjectEvidenceLink(Base):
    """S2.2 — explicit user-created link between a Pilot project and group evidence.

    Supports document and rag_run evidence types via polymorphic evidence_id.
    Server-side validation ensures evidence belongs to the same group as the project.
    No DB-level foreign keys to evidence sources — type-specific queries enforce integrity.

    Lifecycle: active → removed (user unlink only). Source evidence deletion does NOT
    auto-set removed — GET derives evidence_status gone dynamically.
    """

    __tablename__ = "project_evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "evidence_type", "evidence_id",
            name="uq_project_evidence_link",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("business_projects.id"), index=True, nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # document | rag_run
    evidence_id: Mapped[str] = mapped_column(
        String(36), nullable=False
    )  # polymorphic — validated server-side
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # context | requirement | decision | validation
    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # trimmed, blank→null
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | removed
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    removed_by: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
