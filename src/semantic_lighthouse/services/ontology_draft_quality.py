"""Ontology draft quality validator — deterministic rules, read-only.

Phase 12.2a: validates modeling drafts for structural integrity,
evidence completeness, and cross-reference consistency.
Never modifies drafts, commits, or calls external systems.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    DatasetAsset,
    OntologyEntity,
    OntologyModelingDraft,
    OntologyRelation,
    OntologyValidationIssue,
    RagRun,
)

REQUIRED_PAYLOAD_FIELDS: dict[str, set[str]] = {
    "object_type": {"source_entity_type", "entity_count"},
    "property": {
        "object_type", "property_name", "observed_value_types",
        "observed_count", "entity_count",
    },
    "link_type": {
        "source_object_type", "target_object_type", "relation_type", "relation_count",
    },
    "action_type": {"scope", "issue_count", "issue_codes"},
}

DATASET_REQUIRED_PAYLOAD_FIELDS: dict[str, set[str]] = {
    "object_type": {"api_name", "display_name", "primary_key"},
    "property": {"object_type", "property_name", "value_type"},
    "link_type": {"source_object_type", "target_object_type", "source_property",
                  "target_property", "cardinality"},
}

VALID_DRAFT_TYPES = {"object_type", "property", "link_type", "action_type"}
VALID_STATUSES = {"proposed", "accepted", "rejected"}


def validate_modeling_drafts(
    db: Session, group_id: str, project_id: str | None = None,
) -> dict:
    """Validate modeling drafts. Read-only — no mutations.

    If project_id is provided, validates only that project's drafts.
    Otherwise validates all group drafts (legacy behavior).

    Returns: {status, draft_count, error_count, warning_count, issues}
    """
    base = select(OntologyModelingDraft).where(
        OntologyModelingDraft.group_id == group_id,
    )
    if project_id is not None:
        base = base.where(OntologyModelingDraft.project_id == project_id)

    drafts = list(db.scalars(base).all())

    # Build lookup sets for cross-reference validation
    entity_ids: set[str] = set()
    relation_ids: set[str] = set()
    issue_ids: set[str] = set()
    rag_run_ids: set[str] = set()
    dataset_ids: set[str] = set()
    project_ds_ids: set[str] = set()

    if drafts:
        eids = {d.source_entity_id for d in drafts if d.source_entity_id}
        rids = {d.source_relation_id for d in drafts if d.source_relation_id}
        iids = {d.source_issue_id for d in drafts if d.source_issue_id}
        ragids = {d.source_rag_run_id for d in drafts if d.source_rag_run_id}
        dsids = {d.source_dataset_id for d in drafts if d.source_dataset_id}

        if eids:
            entity_ids = set(
                db.scalars(
                    select(OntologyEntity.id).where(
                        OntologyEntity.id.in_(eids),
                        OntologyEntity.group_id == group_id,
                    )
                ).all()
            )
        if rids:
            relation_ids = set(
                db.scalars(
                    select(OntologyRelation.id).where(
                        OntologyRelation.id.in_(rids),
                        OntologyRelation.group_id == group_id,
                    )
                ).all()
            )
        if iids:
            issue_ids = set(
                db.scalars(
                    select(OntologyValidationIssue.id).where(
                        OntologyValidationIssue.id.in_(iids),
                        OntologyValidationIssue.group_id == group_id,
                    )
                ).all()
            )
        if ragids:
            rag_run_ids = set(
                db.scalars(
                    select(RagRun.id).where(
                        RagRun.id.in_(ragids),
                        RagRun.group_id == group_id,
                    )
                ).all()
            )
        if dsids:
            dataset_ids = set(
                db.scalars(
                    select(DatasetAsset.id).where(
                        DatasetAsset.id.in_(dsids),
                        DatasetAsset.group_id == group_id,
                    )
                ).all()
            )
            project_ds_ids = dataset_ids
            if project_id is not None:
                # Also verify datasets belong to the project
                project_ds_ids = set(
                    db.scalars(
                        select(DatasetAsset.id).where(
                            DatasetAsset.id.in_(dsids),
                            DatasetAsset.group_id == group_id,
                            DatasetAsset.project_id == project_id,
                        )
                    ).all()
                )

    # Collect object_type names from same-scope drafts for cross-reference.
    # For dataset_deterministic_v1, the cross-reference uses api_name from payload.
    # For legacy deterministic_v1 and manual drafts, the cross-reference uses d.name.
    object_type_names: set[str] = set()
    for d in drafts:
        if d.draft_type == "object_type":
            p = d.payload or {}
            if p.get("generator") == "dataset_deterministic_v1":
                api_name = p.get("api_name", "")
                if api_name:
                    object_type_names.add(api_name.strip().casefold())
            # Also add d.name for backward compatibility and manual drafts
            object_type_names.add(d.name.strip().casefold())

    issues: list[dict] = []

    ds_ids_context = project_ds_ids if project_id is not None else dataset_ids

    for d in drafts:
        _validate_draft(
            d, entity_ids, relation_ids, issue_ids, rag_run_ids,
            ds_ids_context, object_type_names, issues,
        )

    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")

    if error_count > 0:
        status = "FAIL"
    elif warning_count > 0:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "draft_count": len(drafts),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }


def _validate_draft(
    d: OntologyModelingDraft,
    entity_ids: set[str],
    relation_ids: set[str],
    issue_ids: set[str],
    rag_run_ids: set[str],
    dataset_ids: set[str],
    object_type_names: set[str],
    issues: list[dict],
) -> None:
    """Validate a single draft. Appends findings to issues list."""
    dt = d.draft_type
    payload = d.payload or {}
    generator = payload.get("generator", "")
    is_det = generator in ("deterministic_v1", "dataset_deterministic_v1")
    is_dataset = generator == "dataset_deterministic_v1"
    gen_key = payload.get("generation_key", "")

    # ── Errors: basic integrity (applies to all drafts) ──────────────
    if dt not in VALID_DRAFT_TYPES:
        issues.append(_issue("error", "invalid_draft_type", d, "draft_type",
                             f"Invalid draft_type: {dt}"))
        return

    if d.status not in VALID_STATUSES:
        issues.append(_issue("error", "invalid_status", d, "status",
                             f"Invalid status: {d.status}"))

    # Source pointer existence
    has_source = bool(
        d.source_entity_id or d.source_relation_id
        or d.source_issue_id or d.source_rag_run_id
        or d.source_dataset_id
    )
    if not has_source:
        issues.append(_issue("error", "missing_source_pointer", d, None,
                             "No source pointer set"))

    # Source pointer validity (must exist in same group/scope)
    if d.source_entity_id and d.source_entity_id not in entity_ids:
        issues.append(_issue(
            "error", "source_pointer_not_in_group", d, "source_entity_id",
            f"source_entity_id {d.source_entity_id} not found in group",
            details={"source_entity_id": d.source_entity_id},
        ))
    if d.source_relation_id and d.source_relation_id not in relation_ids:
        issues.append(_issue(
            "error", "source_pointer_not_in_group", d, "source_relation_id",
            f"source_relation_id {d.source_relation_id} not found in group",
            details={"source_relation_id": d.source_relation_id},
        ))
    if d.source_issue_id and d.source_issue_id not in issue_ids:
        issues.append(_issue(
            "error", "source_pointer_not_in_group", d, "source_issue_id",
            f"source_issue_id {d.source_issue_id} not found in group",
            details={"source_issue_id": d.source_issue_id},
        ))
    if d.source_rag_run_id and d.source_rag_run_id not in rag_run_ids:
        issues.append(_issue(
            "error", "source_pointer_not_in_group", d, "source_rag_run_id",
            f"source_rag_run_id {d.source_rag_run_id} not found in group",
            details={"source_rag_run_id": d.source_rag_run_id},
        ))
    if d.source_dataset_id and d.source_dataset_id not in dataset_ids:
        issues.append(_issue(
            "error", "source_dataset_not_in_scope", d, "source_dataset_id",
            f"source_dataset_id {d.source_dataset_id} not found in scope",
            details={"source_dataset_id": d.source_dataset_id},
        ))

    # Phase 14.3+14.4: project/dataset consistency
    p = d.payload or {}
    if d.project_id and p.get("project_id") and p["project_id"] != d.project_id:
        issues.append(_issue(
            "error", "payload_project_id_mismatch", d, "payload.project_id",
            f"payload.project_id {p['project_id']} != draft.project_id {d.project_id}",
        ))
    if d.source_dataset_id and p.get("source_dataset_id") and (
        p["source_dataset_id"] != d.source_dataset_id
    ):
        issues.append(_issue(
            "error", "payload_dataset_id_mismatch", d, "payload.source_dataset_id",
            f"payload.source_dataset_id {p['source_dataset_id']} != "
            f"draft.source_dataset_id {d.source_dataset_id}",
        ))

    # Evidence (all drafts)
    if not isinstance(d.evidence_refs, list):
        issues.append(_issue("error", "invalid_evidence_refs", d, "evidence_refs",
                             "evidence_refs is not a list"))
    elif len(d.evidence_refs) == 0:
        issues.append(_issue("error", "empty_evidence_refs", d, "evidence_refs",
                             "evidence_refs is empty"))

    # ── deterministic_v1 specific checks ─────────────────────────────
    if is_det:
        # generation_key must be present and non-empty
        if not gen_key:
            issues.append(_issue(
                "error", "missing_generation_key", d, "payload.generation_key",
                "Deterministic draft missing generation_key",
            ))

        # Required payload fields — use correct set per generator
        if is_dataset and dt in DATASET_REQUIRED_PAYLOAD_FIELDS:
            required = DATASET_REQUIRED_PAYLOAD_FIELDS[dt]
            missing = [f for f in required if f not in payload]
            if missing:
                issues.append(_issue(
                    "error", "missing_required_payload_fields", d, "payload",
                    f"Missing required payload fields: {', '.join(sorted(missing))}",
                    details={"missing_fields": sorted(missing),
                             "required": sorted(required)},
                ))
        elif not is_dataset and dt in REQUIRED_PAYLOAD_FIELDS:
            required = REQUIRED_PAYLOAD_FIELDS[dt]
            missing = [f for f in required if f not in payload]
            if missing:
                issues.append(_issue(
                    "error", "missing_required_payload_fields", d, "payload",
                    f"Missing required payload fields: {', '.join(sorted(missing))}",
                    details={"missing_fields": sorted(missing),
                             "required": sorted(required)},
                ))

        # Cross-reference consistency (all deterministic — manual
        # drafts may not have standard payload shapes)
        if dt == "property":
            ot = payload.get("object_type", "")
            if ot and ot.strip().casefold() not in object_type_names:
                issues.append(_issue(
                    "error", "property_object_type_not_found", d,
                    "payload.object_type",
                    f"Property object_type '{ot}' not found",
                    details={"object_type": ot},
                ))

        if dt == "link_type":
            src_ot = payload.get("source_object_type", "")
            tgt_ot = payload.get("target_object_type", "")
            if src_ot and src_ot.strip().casefold() not in object_type_names:
                issues.append(_issue(
                    "error", "link_source_object_type_not_found", d,
                    "payload.source_object_type",
                    f"Link source_object_type '{src_ot}' not found",
                    details={"source_object_type": src_ot},
                ))
            if tgt_ot and tgt_ot.strip().casefold() not in object_type_names:
                issues.append(_issue(
                    "error", "link_target_object_type_not_found", d,
                    "payload.target_object_type",
                    f"Link target_object_type '{tgt_ot}' not found",
                    details={"target_object_type": tgt_ot},
                ))

    # ── Warnings: legacy deterministic_v1 only (skip for dataset drafts) ─
    if is_det and not is_dataset:
        if dt == "property":
            oc = payload.get("observed_count")
            if isinstance(oc, (int, float)) and oc <= 1:
                issues.append(_issue(
                    "warning", "weak_property_evidence", d,
                    "payload.observed_count",
                    f"Property observed_count={oc} — weak evidence",
                    details={"observed_count": oc},
                ))
            ovt = payload.get("observed_value_types")
            if isinstance(ovt, list) and len(ovt) > 1:
                issues.append(_issue(
                    "warning", "mixed_property_value_types", d,
                    "payload.observed_value_types",
                    f"Property has {len(ovt)} value types: {ovt}",
                    details={"observed_value_types": ovt},
                ))

        if dt == "link_type":
            rc = payload.get("relation_count")
            if isinstance(rc, (int, float)) and rc <= 1:
                issues.append(_issue(
                    "warning", "weak_link_evidence", d,
                    "payload.relation_count",
                    f"Link relation_count={rc} — weak evidence",
                    details={"relation_count": rc},
                ))
            rt = payload.get("relation_type", "")
            if rt == "wikilink":
                issues.append(_issue(
                    "warning", "untyped_wikilink_candidate", d,
                    "payload.relation_type",
                    "Link based on wikilink — not a typed business relation",
                    details={"relation_type": rt},
                ))

        if dt == "action_type":
            ic = payload.get("issue_count")
            if isinstance(ic, (int, float)) and ic <= 1:
                issues.append(_issue(
                    "warning", "weak_action_evidence", d,
                    "payload.issue_count",
                    f"Action issue_count={ic} — weak evidence",
                    details={"issue_count": ic},
                ))
            scope = payload.get("scope", "")
            if scope == "ontology_governance":
                issues.append(_issue(
                    "warning", "governance_action_candidate", d,
                    "payload.scope",
                    "Action scope=ontology_governance — not a business action",
                    details={"scope": scope},
                ))

        if dt == "object_type" and payload.get("source_entity_type"):
            issues.append(_issue(
                "warning", "knowledge_meta_model_candidate", d,
                "payload.source_entity_type",
                "Object type from deterministic generation "
                "— may not be a business object type",
                details={"source_entity_type": payload["source_entity_type"]},
            ))


def _issue(
    severity: str,
    code: str,
    draft: OntologyModelingDraft,
    field: str | None,
    message: str,
    details: dict | None = None,
) -> dict:
    return {
        "severity": severity,
        "code": code,
        "draft_id": draft.id,
        "draft_type": draft.draft_type,
        "field": field,
        "message": message,
        "details": details or {},
    }
