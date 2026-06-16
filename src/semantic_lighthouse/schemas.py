from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: datetime


class MembershipResponse(BaseModel):
    group_id: str
    group_name: str
    user_id: str
    role: str


class MeResponse(UserResponse):
    groups: list[MembershipResponse] = Field(default_factory=list)


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class GroupResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_by: str
    created_at: datetime
    role: str | None = None


class InviteResponse(BaseModel):
    group_id: str
    invite_code: str
    expires_at: datetime


class JoinByInviteRequest(BaseModel):
    invite_code: str = Field(min_length=16, max_length=256)


class JoinRequestResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    status: str
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class RoleUpdateRequest(BaseModel):
    role: str = Field(pattern="^(owner|admin|member)$")


class MessageResponse(BaseModel):
    message: str


class DocumentResponse(BaseModel):
    id: str
    group_id: str
    title: str
    file_name: str
    source_path: str
    content_hash: str
    file_hash: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    original_storage_path: str | None = None
    parser: str | None = None
    frontmatter: dict
    status: str
    ingestion_error: str | None = None
    processed_at: datetime | None = None
    created_by: str
    created_at: datetime


class DocumentChunkResponse(BaseModel):
    id: str
    document_id: str
    group_id: str
    chunk_index: int
    heading_path: str | None
    content: str
    content_hash: str


class DocumentDetailResponse(DocumentResponse):
    chunks: list[DocumentChunkResponse]


class LocalImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    documents: list[DocumentResponse]


class DocumentSearchResult(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    source_path: str
    file_name: str
    chunk_index: int
    heading_path: str | None
    snippet: str
    entity_type: str | None = None
    document_type: str | None = None
    source: str | None = None
    status: str | None = None


class EmbeddingRebuildResponse(BaseModel):
    processed_count: int
    skipped_count: int
    failed_count: int
    embedding_model: str


class SemanticSearchResult(DocumentSearchResult):
    score: float
    retrieval_method: str = "semantic"


class UploadInitRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    file_size: int = Field(ge=1)
    file_hash: str = Field(pattern="^[a-fA-F0-9]{64}$")
    chunk_size: int | None = Field(default=None, ge=1)


class UploadInitResponse(BaseModel):
    type: str
    document_id: str | None = None
    upload_id: str | None = None
    chunk_size: int | None = None
    total_chunks: int | None = None
    uploaded_chunks: list[int] = Field(default_factory=list)
    expires_at: datetime | None = None


class UploadSessionResponse(BaseModel):
    upload_id: str
    group_id: str
    file_name: str
    file_size: int
    file_hash: str
    chunk_size: int
    total_chunks: int
    uploaded_chunks: list[int]
    uploaded_count: int
    status: str
    expires_at: datetime


class UploadChunkResponse(BaseModel):
    upload_id: str
    uploaded_count: int
    total_count: int
    uploaded_chunks: list[int]


class RagAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    retrieval_method: str = Field(default="hybrid", pattern="^(hybrid|auto|keyword|semantic)$")
    limit: int | None = Field(default=None, ge=1, le=10)


class EvidenceQuality(BaseModel):
    retrieval_coverage: str = "none"  # full | partial | weak | none
    source_maturity: str = "unknown"  # strong | medium | weak | unknown
    citation_diversity: str = "none"  # high | medium | low | none
    score_distribution: str = "unknown"  # strong | medium | weak | unknown
    summary: str = ""


class RagCitation(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    source_path: str
    file_name: str
    chunk_index: int
    heading_path: str | None
    snippet: str
    entity_type: str | None = None
    document_type: str | None = None
    source: str | None = None
    status: str | None = None
    score: float | None = None
    retrieval_method: str
    match_reason: str = ""


class RagAnswerResponse(BaseModel):
    run_id: str
    question: str
    answer: str
    confidence: str
    confidence_reason: str = ""
    evidence_quality: EvidenceQuality | None = None
    knowledge_gaps: list[str]
    next_steps: list[str]
    citations: list[RagCitation]
    retrieval_method: str
    model: str


class RagRunSummary(BaseModel):
    id: str
    group_id: str
    user_id: str
    question: str
    confidence: str
    retrieval_method: str
    model: str
    citation_count: int
    status: str
    duration_ms: int | None = None
    created_at: datetime


class RagRunDetail(BaseModel):
    id: str
    group_id: str
    user_id: str
    question: str
    answer: str
    confidence: str
    confidence_reason: str = ""
    evidence_quality: EvidenceQuality | None = None
    knowledge_gaps: list[str]
    next_steps: list[str]
    citations: list[RagCitation]
    retrieval_method: str
    model: str
    status: str
    error_message: str | None = None
    duration_ms: int | None = None
    retrieved_count: int | None = None
    created_at: datetime


class IngestionJobResponse(BaseModel):
    id: str
    group_id: str
    document_id: str
    upload_session_id: str | None = None
    status: str
    current_step: str | None = None
    attempt_count: int
    max_attempts: int
    error_message: str | None = None
    created_by: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class IngestionJobDetailResponse(IngestionJobResponse):
    step_log: dict = Field(default_factory=dict)


# ── v4 conversations ──────────────────────────────────────────────────────


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: list[RagCitation] = Field(default_factory=list)
    retrieval_method: str | None = None
    model: str | None = None
    confidence: str | None = None
    knowledge_gaps: list[str] = Field(default_factory=list)
    tool_calls: list[dict] | None = None
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class ConversationMessageRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    retrieval_method: str = Field(default="hybrid", pattern="^(hybrid|auto|keyword|semantic)$")
    limit: int | None = Field(default=None, ge=1, le=10)


# ── v7 agent orchestration ──────────────────────────────────────────────


class AgentRunResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    conversation_id: str | None = None
    goal: str
    status: str
    current_phase: str | None = None
    step_count: int = 0
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None


class AgentStepResponse(BaseModel):
    id: str
    run_id: str
    phase: str
    step_index: int
    thought: str
    action_type: str
    action_detail: dict
    observation: str | None = None
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentRunDetailResponse(AgentRunResponse):
    final_answer: str | None = None
    citations: list[RagCitation] = Field(default_factory=list)
    steps: list[AgentStepResponse] = Field(default_factory=list)
    plan_json: list = Field(default_factory=list)


class AgentRunCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


class AgentRunRespondRequest(BaseModel):
    response: str = Field(min_length=1, max_length=2000)


class AgentMemoryResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    key: str
    value: str
    scope: str
    ttl_days: int | None = None
    source_run_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentMemoryUpsertRequest(BaseModel):
    key: str = Field(min_length=1, max_length=240)
    value: str = Field(min_length=1)
    scope: str = Field(pattern="^(user|group)$")
    ttl_days: int | None = None
