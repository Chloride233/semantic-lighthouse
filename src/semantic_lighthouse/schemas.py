from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


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
    archived_by: str | None = None
    archived_at: datetime | None = None
    archive_reason: str | None = None
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
    project_id: str | None = None


class ConversationResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    project_id: str | None = None
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
    project_id: str | None = None
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
    project_id: str | None = None
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


# ── Product Alignment: Lightweight Tasks ──────────────────────────────────


# ── v9 ontology governance ──────────────────────────────────────────────


class OntologyScanResponse(BaseModel):
    scanned_count: int
    entity_count: int
    issue_count: int
    relation_count: int = 0


class OntologyEntityResponse(BaseModel):
    id: str
    group_id: str
    document_id: str
    title: str
    entity_type: str
    aliases: list = Field(default_factory=list)
    source_path: str
    source: str | None = None
    status: str | None = None
    tags: list = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class OntologyEntityListResponse(BaseModel):
    entities: list[OntologyEntityResponse]
    total: int


class OntologyValidationIssueResponse(BaseModel):
    id: str
    group_id: str
    document_id: str | None = None
    entity_id: str | None = None
    severity: str
    code: str
    field: str | None = None
    message: str
    source_path: str
    details: dict = Field(default_factory=dict)
    created_at: datetime
    issue_key: str | None = None
    triage_status: str = "pending"
    triaged_by: str | None = None
    triaged_at: datetime | None = None
    triage_note: str | None = None


class OntologyIssueTriageRequest(BaseModel):
    triage_status: str = Field(pattern="^(pending|confirmed|ignored)$")
    triage_note: str = Field(default="", max_length=1000)


class OntologyIssueListResponse(BaseModel):
    issues: list[OntologyValidationIssueResponse]
    total: int


class OntologyRelationResponse(BaseModel):
    id: str
    group_id: str
    source_entity_id: str
    source_document_id: str
    target_entity_id: str | None = None
    target_path: str
    target_label: str | None = None
    relation_type: str
    status: str
    evidence_document_id: str
    created_at: datetime


class OntologyRelationListResponse(BaseModel):
    relations: list[OntologyRelationResponse]
    total: int


# ── Product Alignment: Lightweight Tasks ──────────────────────────────────


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    source_type: str = Field(pattern="^(rag_run|conversation|agent_run|manual)$")
    source_id: str = Field(min_length=1, max_length=36)
    project_id: str | None = None


class TaskUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|in_progress|done|cancelled)$")
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None


class TaskResponse(BaseModel):
    id: str
    group_id: str
    project_id: str | None = None
    title: str
    description: str
    status: str
    source_type: str
    source_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


# ── Phase 11: Ontology Modeling Drafts ──────────────────────────────────

DRAFT_TYPES = {"object_type", "property", "link_type", "action_type"}


class OntologyModelingDraftCreateRequest(BaseModel):
    draft_type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=240)
    description: str = ""
    source_entity_id: str | None = None
    source_relation_id: str | None = None
    source_issue_id: str | None = None
    source_rag_run_id: str | None = None
    project_id: str | None = None
    source_dataset_id: str | None = None
    evidence_refs: list = Field(
        default_factory=list,
        description="Supplemental evidence snapshot — not a substitute for a proper source_*_id.",
    )
    payload: dict = Field(default_factory=dict)


class OntologyModelingDraftResponse(BaseModel):
    id: str
    group_id: str
    draft_type: str
    name: str
    description: str
    status: str
    source_entity_id: str | None = None
    source_relation_id: str | None = None
    source_issue_id: str | None = None
    source_rag_run_id: str | None = None
    project_id: str | None = None
    source_dataset_id: str | None = None
    evidence_refs: list = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)
    created_by: str
    created_at: datetime
    updated_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None


class OntologyModelingDraftListResponse(BaseModel):
    drafts: list[OntologyModelingDraftResponse]
    total: int


# ── Phase 11.3: draft generation ─────────────────────────────────────


class DraftGenerationCountsByType(BaseModel):
    object_type: int = 0
    property: int = 0
    link_type: int = 0
    action_type: int = 0


class DraftGenerationResponse(BaseModel):
    generated_count: int
    existing_count: int
    skipped_count: int
    counts_by_type: DraftGenerationCountsByType


# ── Phase 11.4: human review workflow ──────────────────────────────────


class OntologyModelingDraftReviewRequest(BaseModel):
    """Single draft review — accept or reject a proposed draft."""

    status: str = Field(pattern="^(accepted|rejected)$")
    review_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _require_note_for_rejected(self) -> "OntologyModelingDraftReviewRequest":
        if self.status == "rejected" and (
            not self.review_note or not self.review_note.strip()
        ):
            raise ValueError("review_note is required when rejecting a draft")
        return self


class OntologyModelingDraftBatchReviewRequest(BaseModel):
    """Batch review — atomically accept or reject up to 100 proposed drafts."""

    draft_ids: list[str] = Field(min_length=1, max_length=100)
    status: str = Field(pattern="^(accepted|rejected)$")
    review_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _require_note_for_rejected(self) -> "OntologyModelingDraftBatchReviewRequest":
        if self.status == "rejected" and (
            not self.review_note or not self.review_note.strip()
        ):
            raise ValueError("review_note is required when rejecting a draft")
        return self


class OntologyModelingDraftBatchReviewResponse(BaseModel):
    reviewed_count: int
    status: str
    draft_ids: list[str]
    reviewed_by: str
    reviewed_at: datetime


# ── Phase 14.3: Dataset Modeling Bridge ──────────────────────────────────


class DatasetModelingIssue(BaseModel):
    code: str
    severity: str  # error | warning
    dataset_id: str | None = None
    column: str | None = None
    message: str


class DatasetModelingCountsByType(BaseModel):
    object_type: int = 0
    property: int = 0
    link_type: int = 0
    action_type: int = 0


class DatasetModelingResponse(BaseModel):
    generated_count: int
    existing_count: int
    skipped_count: int
    counts_by_type: DatasetModelingCountsByType
    issues: list[DatasetModelingIssue] = Field(default_factory=list)


# ── Phase 14.4: Project Validation Gate ──────────────────────────────────


class ProjectPackageBuildRequest(BaseModel):
    allow_warnings: bool = False
    override_reason: str | None = Field(default=None, max_length=2000)


# ── Phase 12.2b: draft quality API ────────────────────────────────────


class OntologyDraftQualityIssueResponse(BaseModel):
    severity: str
    code: str
    draft_id: str
    draft_type: str
    field: str | None = None
    message: str
    details: dict = Field(default_factory=dict)


class OntologyDraftQualityResponse(BaseModel):
    status: str
    draft_count: int
    error_count: int
    warning_count: int
    issues: list[OntologyDraftQualityIssueResponse] = Field(default_factory=list)


# ── Phase 12.4: package API ───────────────────────────────────────────


class OntologyModelPackageSummaryResponse(BaseModel):
    id: str
    group_id: str
    version: int
    schema_version: str
    content_hash: str
    draft_count: int
    quality_status: str
    project_id: str | None = None
    created_by: str
    created_at: datetime


class OntologyModelPackageDetailResponse(OntologyModelPackageSummaryResponse):
    contract_json: dict = Field(default_factory=dict)
    source_draft_ids: list = Field(default_factory=list)
    quality_summary: dict = Field(default_factory=dict)


class OntologyModelPackageBuildResponse(BaseModel):
    id: str
    version: int
    content_hash: str
    draft_count: int
    quality_status: str
    project_id: str | None = None
    created: bool


class OntologyModelPackageListResponse(BaseModel):
    packages: list[OntologyModelPackageSummaryResponse]
    total: int


class OntologyModelPackageExportResponse(BaseModel):
    package_id: str
    version: int
    schema_version: str
    content_hash: str
    quality_status: str
    contract: dict


# ── Phase 13.4: business contract export ────────────────────────────────


class BusinessContractManifestMetadata(BaseModel):
    contract_profile: str
    schema_version: str
    semantic_hash: str


class BusinessContractProvenance(BaseModel):
    source_package_id: str
    source_package_version: int
    source_content_hash: str
    project_id: str | None = None


class BusinessContractManifestResponse(BaseModel):
    manifest: BusinessContractManifestMetadata
    provenance: BusinessContractProvenance
    object_types: list[dict] = Field(default_factory=list)
    properties: list[dict] = Field(default_factory=list)
    link_types: list[dict] = Field(default_factory=list)
    action_types: list[dict] = Field(default_factory=list)


# ── Phase 14.1: Business Pilot Projects ──────────────────────────────────


class BusinessProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    business_goal: str = Field(default="", max_length=2000)
    entry_mode: str = Field(pattern="^(problem_first|data_first)$")
    industry_template: str | None = Field(default=None, max_length=80)

    @field_validator("name")
    @classmethod
    def _trim_and_check_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty after trimming")
        return v


class BusinessProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    business_goal: str | None = Field(default=None, max_length=2000)
    entry_mode: str | None = Field(default=None, pattern="^(problem_first|data_first)$")
    industry_template: str | None = Field(default=None, max_length=80)

    @field_validator("name")
    @classmethod
    def _trim_and_check_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty after trimming")
        return v


class BusinessProjectResponse(BaseModel):
    id: str
    group_id: str
    name: str
    business_goal: str
    entry_mode: str
    industry_template: str | None = None
    stage: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class BusinessProjectListResponse(BaseModel):
    projects: list[BusinessProjectResponse]
    total: int


# ── S2.2 Project Evidence Links ────────────────────────────────────────────

EVIDENCE_TYPES = {"document", "rag_run"}
EVIDENCE_ROLES = {"context", "requirement", "decision", "validation"}


class EvidenceLinkCreateRequest(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=20)
    evidence_id: str = Field(min_length=1, max_length=36)
    role: str = Field(min_length=1, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class EvidenceProvenance(BaseModel):
    """Minimal provenance — never exposes paths, content, or secrets."""
    evidence_title: str | None = None
    evidence_status: str | None = None
    unavailable: bool = False
    # Document-only
    file_name: str | None = None
    source_label: str | None = None
    # RAGRun-only
    question: str | None = None  # truncated 120 chars
    confidence: str | None = None
    retrieval_method: str | None = None
    citation_count: int | None = None
    # Shared
    evidence_created_at: str | None = None


class EvidenceLinkResponse(BaseModel):
    id: str
    project_id: str
    evidence_type: str
    evidence_id: str
    role: str
    note: str | None = None
    status: str
    created_by: str
    created_at: str
    updated_at: str
    removed_by: str | None = None
    removed_at: str | None = None
    provenance: EvidenceProvenance | None = None


class EvidenceLinkListResponse(BaseModel):
    links: list[EvidenceLinkResponse]
    total: int
    limit: int
    offset: int


# ── S2.4B Project Summary ──────────────────────────────────────────────────

class TaskCountsByStatus(BaseModel):
    pending: int = 0
    in_progress: int = 0
    done: int = 0
    cancelled: int = 0


class ProjectSummaryResponse(BaseModel):
    project: dict
    evidence_count: int
    recent_evidence: list[dict]
    conversation_count: int
    task_count: TaskCountsByStatus
    agent_run_count: int
