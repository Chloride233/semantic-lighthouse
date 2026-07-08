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
    project_id: str | None = None
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
    project_id: str | None = None
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
    governance_layer: str
    governance_label: str
    review_required: bool
    hard_reasoning_allowed: bool
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


class TaskEvidenceSource(BaseModel):
    source_type: str
    source_id: str
    source_status: str
    question: str | None = None
    confidence: str | None = None
    retrieval_method: str | None = None
    citation_count: int | None = None
    project_evidence_link: dict | None = None


class TaskProposedAction(BaseModel):
    title: str
    description: str
    current_status: str


class TaskAffectedScope(BaseModel):
    group_id: str
    project_id: str | None = None
    source_type: str
    source_id: str


class TaskRisk(BaseModel):
    level: str = Field(pattern="^(low|medium|high)$")
    reasons: list[str]


class TaskReviewRequirements(BaseModel):
    requires_human_review: bool
    required_checks: list[str]


class TaskEvidenceAnchor(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    file_name: str
    chunk_index: int
    heading_path: str | None = None
    retrieval_method: str
    match_reason: str = ""


class TaskEvidencePacket(BaseModel):
    packet_version: str = "1.0"
    source: TaskEvidenceSource
    proposed_action: TaskProposedAction
    affected_scope: TaskAffectedScope
    risk: TaskRisk
    rollback_note: str
    review_requirements: TaskReviewRequirements
    evidence_anchors: list[TaskEvidenceAnchor] = Field(default_factory=list)


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
    evidence_packet: TaskEvidencePacket | None = None


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


# ── Phase 15.3 Evidence-Backed Draft Candidate ──────────────────────────────

MAX_EVIDENCE_LINKS_PER_DRAFT = 20


class EvidenceDraftCreateRequest(BaseModel):
    """Create a proposed modeling draft from one or more project evidence links.

    Evidence link IDs must be active, belong to the same group/project,
    and reference valid evidence sources. Server derives source_rag_run_id
    and evidence_refs from the evidence links; user authors name/description/type.
    """

    draft_type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=240)
    description: str = ""
    evidence_link_ids: list[str] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_LINKS_PER_DRAFT,
        description="Non-empty list of active ProjectEvidenceLink IDs.",
    )
    source_entity_id: str | None = None
    source_issue_id: str | None = None


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


# ── Phase 16.1: Pilot Outcome Records ────────────────────────────────────

# Forbidden keys in query_refs — never allow raw data, secrets, or paths
_FORBIDDEN_QUERY_REF_KEYS = frozenset({
    "raw_content", "raw_answer", "raw_prompt", "raw", "raw_csv", "csv_rows",
    "answer", "prompt",
    "source_path", "storage_path", "path",
    "secret", "token", "password", "key", "api_key",
    "stack_trace", "traceback",
})


def _validate_query_refs_safe(refs: list[dict]) -> None:
    """Reject query_ref objects that contain forbidden keys (recursive check)."""
    def _check(obj, path: str = "$") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _FORBIDDEN_QUERY_REF_KEYS:
                    raise ValueError(
                        f"Forbidden key '{k}' in query_refs at {path}"
                    )
                _check(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _check(item, f"{path}[{i}]")
    _check(refs)


class PilotOutcomeCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    selected_evidence_link_ids: list[str] = Field(
        default_factory=list, max_length=50,
    )
    package_ids: list[str] = Field(
        default_factory=list, max_length=20,
    )
    query_refs: list[dict] = Field(
        default_factory=list, max_length=100,
    )
    decision_summary: str = Field(default="", max_length=5000)
    risks: list[str] = Field(default_factory=list, max_length=50)
    next_actions: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("title")
    @classmethod
    def _trim_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty after trimming")
        return v

    @model_validator(mode="after")
    def _validate_query_refs(self) -> "PilotOutcomeCreateRequest":
        try:
            _validate_query_refs_safe(self.query_refs)
        except ValueError as e:
            raise ValueError(str(e)) from e
        return self


class PilotOutcomeResponse(BaseModel):
    id: str
    group_id: str
    project_id: str
    title: str
    business_goal_snapshot: str
    selected_evidence_refs: list = Field(default_factory=list)
    package_refs: list = Field(default_factory=list)
    query_refs: list = Field(default_factory=list)
    decision_summary: str
    risks: list = Field(default_factory=list)
    next_actions: list = Field(default_factory=list)
    created_by: str
    created_at: datetime


class PilotOutcomeListResponse(BaseModel):
    outcomes: list[PilotOutcomeResponse]
    total: int


# ── Phase 16.2: Pilot Outcome Summary (read-only aggregation) ────────────


class OutcomeEvidenceCounts(BaseModel):
    total_active: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_role: dict[str, int] = Field(default_factory=dict)


class OutcomePackageInfo(BaseModel):
    package_id: str
    version: int
    content_hash: str
    quality_status: str
    draft_count: int
    created_at: datetime | None = None


class OutcomePackageSummary(BaseModel):
    count: int = 0
    latest: OutcomePackageInfo | None = None


class OutcomeRuntimeSummary(BaseModel):
    total_operations: int = 0
    last_operation: dict | None = None
    note: str = (
        "v1: operation counts only from OntologyRuntimeAudit; "
        "detailed query result aggregation deferred."
    )


class OutcomeLatestInfo(BaseModel):
    id: str
    title: str
    created_at: datetime | None = None
    decision_summary: str = ""
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class PilotOutcomeSummaryResponse(BaseModel):
    project: dict
    latest_outcome: OutcomeLatestInfo | None = None
    evidence_summary: OutcomeEvidenceCounts
    package_summary: OutcomePackageSummary
    runtime_summary: OutcomeRuntimeSummary
    decision_summary: str = ""
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


# R2D: runtime relationship traversal.


class OrderByClause(BaseModel):
    """R3E1 — sort key on a selected joined field.

    No expression strings, no cross-OT computation, no aggregate references.
    """

    field: str = Field(..., min_length=1)
    direction: str = Field(default="asc", pattern="^(asc|desc)$")


class RuntimeTraverseRequest(BaseModel):
    """Declarative path traversal over bound dataset Object Types.

    Supports 1-2 hops (path of 2 or 3 OTs). Filters are per-OT.
    order_by sorts joined rows by selected {ot}__{prop} fields before
    offset/limit. No SQL, no DSL, no expression strings.
    """

    path: list[str] = Field(..., min_length=2, max_length=3)
    fields: dict[str, list[str]] | None = Field(default=None)
    filters: dict[str, dict[str, str | int | float | bool | None]] | None = Field(
        default=None,
    )
    order_by: list[OrderByClause] | None = Field(default=None)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    explain_only: bool = Field(default=False)
    response_shape: str = Field(default="flat", pattern="^(flat|grouped)$")
    direction: str = Field(default="forward", pattern="^(forward|reverse)$")


class HopExplain(BaseModel):
    """Per-hop explain detail: metadata only, never data values."""

    hop_index: int
    link_type_api_name: str
    source_object_type: str
    target_object_type: str
    cardinality: str
    source_binding_id: str
    target_binding_id: str
    source_dataset_id: str
    target_dataset_id: str
    source_fk_property: str
    target_pk_property: str
    source_fk_column: str = ""
    target_pk_column: str = ""


class TraverseExplain(BaseModel):
    """Traversal explain block: metadata only, never data values or paths."""

    package_id: str
    package_version: int
    package_semantic_hash: str
    path: list[str]
    hops: list[HopExplain]
    selected_fields_by_ot: dict[str, list[str]]
    filter_field_names_by_ot: dict[str, list[str]]
    limit: int
    offset: int
    response_shape: str = "flat"
    direction: str = "forward"
    order_by: list[dict] | None = None
    scanned_rows: dict[str, int] | None = None
    scan_limit: int | None = None
    scan_truncated: dict[str, bool] | None = None
    matched_before_paging: int | None = None


class RuntimeTraverseResponse(BaseModel):
    """Traversal response rows — flat prefixed or grouped nested, per response_shape."""

    rows: list[dict]
    row_count: int | None
    explain: TraverseExplain
    type_errors: list[dict] | None = None
