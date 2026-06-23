"""Phase 14.5 — Pilot Read Runtime service.

Deterministic binding generation from compiled business_v1 contract
to DatasetAssets. Limited, explainable, permission-isolated
read-only query execution over CSV/XLSX with contract type conversion.

Review C hardened: audit, filter-before-offset/limit, compiled contract
as truth, no PK guessing, full smoke on activation.

No SQL, no DSL, no AST, no LLM, no MCP, no Graph RAG, no writes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    BusinessProject,
    DatasetAsset,
    OntologyDatasetBinding,
    OntologyModelingDraft,
    OntologyRuntimeAudit,  # noqa: F401 — re-exported for test backward compat
)
from semantic_lighthouse.services.runtime_audit import (
    _record_audit,
    _sanitized_code,
)
from semantic_lighthouse.services.runtime_contract import (
    _build_contract_context,
    _get_latest_project_package,
)
from semantic_lighthouse.services.runtime_dataset_io import (
    _read_dataset_rows,  # noqa: F401 — re-exported for backward compat
    _stream_csv_rows,  # noqa: F401 — re-exported for backward compat
    _stream_xlsx_rows,  # noqa: F401 — re-exported for backward compat
    _validate_dataset_path,  # noqa: F401 — re-exported for backward compat
)
from semantic_lighthouse.services.runtime_query import (
    _convert_filter_value,  # noqa: F401 — re-exported for backward compat
    _convert_value,  # noqa: F401 — re-exported for backward compat
    _DEFAULT_LIMIT,  # noqa: F401 — re-exported for backward compat
    _MAX_LIMIT,  # noqa: F401 — re-exported for backward compat
    _MAX_OFFSET,  # noqa: F401 — re-exported for backward compat
    execute_query,
)

# ═══════════════════════════════════════════════════════════════════════════
#  audit — re-exported from runtime_audit
# ═══════════════════════════════════════════════════════════════════════════


#  value / filter conversion — re-exported from runtime_query


# ═══════════════════════════════════════════════════════════════════════════
#  sanitized error codes — re-exported from runtime_audit


# ═══════════════════════════════════════════════════════════════════════════
#  compiled contract context — re-exported from runtime_contract


#  dataset IO — re-exported from runtime_dataset_io


# ═══════════════════════════════════════════════════════════════════════════
#  _get_latest_project_package — re-exported from runtime_contract


# ═══════════════════════════════════════════════════════════════════════════
#  binding generation — strict, no guessing
# ═══════════════════════════════════════════════════════════════════════════


def generate_bindings(
    db: Session,
    group_id: str,
    project_id: str,
    created_by: str,
) -> dict:
    """Deterministically generate OntologyDatasetBindings from the latest
    project-scoped package's compiled business_v1 contract.

    PK must resolve through: Object Type primary_key → Property draft → column.
    No fallback to dataset profile PK candidates.
    Property mapping must exist in: compiled contract + draft evidence + dataset columns.
    Empty property_mappings → error, not warning.

    Returns dict with created_count, existing_count, issues.
    """
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        return {
            "created_count": 0, "existing_count": 0,
            "issues": [{
                "code": "no_project_package",
                "severity": "error",
                "message": "No project-scoped package found. Build a package first.",
            }],
        }

    # ── Compile contract as single source of truth ──────────────────────────
    try:
        ctx = _build_contract_context(pkg)
    except Exception:
        return {
            "created_count": 0, "existing_count": 0,
            "issues": [{
                "code": "contract_compilation_failed",
                "severity": "error",
                "message": "Business contract compilation failed.",
            }],
        }

    source_ids = pkg.source_draft_ids or []
    if not source_ids:
        return {
            "created_count": 0, "existing_count": 0,
            "issues": [{
                "code": "no_source_drafts",
                "severity": "error",
                "message": "Package has no source draft references.",
            }],
        }

    accepted_drafts = db.scalars(
        select(OntologyModelingDraft).where(
            OntologyModelingDraft.id.in_(source_ids),
            OntologyModelingDraft.status == "accepted",
            OntologyModelingDraft.group_id == group_id,
            OntologyModelingDraft.project_id == project_id,
        )
    ).all()

    ot_drafts = [d for d in accepted_drafts if d.draft_type == "object_type"]
    prop_drafts = [d for d in accepted_drafts if d.draft_type == "property"]

    if not ot_drafts:
        return {
            "created_count": 0, "existing_count": 0,
            "issues": [{
                "code": "no_accepted_object_types",
                "severity": "error",
                "message": "No accepted Object Type drafts in the package.",
            }],
        }

    issues: list[dict] = []
    created = 0
    existing = 0

    for ot in ot_drafts:
        ot_payload = ot.payload or {}
        api_name = ot_payload.get("api_name")
        ds_id = ot.source_dataset_id

        if not api_name or not ds_id:
            issues.append({
                "code": "incomplete_object_type",
                "severity": "error",
                "draft_id": ot.id,
                "message": (
                    "Object Type draft missing api_name or source_dataset_id."
                ),
            })
            continue

        # Verify Object Type exists in compiled contract
        ot_ctx = ctx["ot_map"].get(api_name)
        if not ot_ctx:
            issues.append({
                "code": "object_type_not_in_compiled_contract",
                "severity": "error",
                "draft_id": ot.id,
                "object_type": api_name,
                "message": (
                    f"Object Type '{api_name}' not found in compiled "
                    f"business contract."
                ),
            })
            continue

        # ── Validate dataset ──────────────────────────────────────────────
        dataset = db.get(DatasetAsset, ds_id)
        if dataset is None or dataset.group_id != group_id or dataset.project_id != project_id:
            issues.append({
                "code": "dataset_not_found",
                "severity": "error",
                "draft_id": ot.id,
                "dataset_id": ds_id,
                "message": "Dataset not found or not in this project.",
            })
            continue

        if dataset.status not in ("ready",):
            issues.append({
                "code": "dataset_not_ready",
                "severity": "error",
                "draft_id": ot.id,
                "dataset_id": ds_id,
                "dataset_status": dataset.status,
                "message": (
                    f"Dataset status is '{dataset.status}', not 'ready'."
                ),
            })
            continue

        # ── Resolve PK through contract → draft → column ──────────────────
        contract_pk_api_name = ot_ctx.get("primary_key", "")
        if not contract_pk_api_name:
            issues.append({
                "code": "no_primary_key_in_contract",
                "severity": "error",
                "draft_id": ot.id,
                "object_type": api_name,
                "message": (
                    f"Object Type '{api_name}' has no primary_key "
                    f"in the compiled contract."
                ),
            })
            continue

        # Find the Property draft matching the contract PK
        pk_column: str | None = None
        for prop in prop_drafts:
            prop_payload = prop.payload or {}
            if prop_payload.get("api_name") == contract_pk_api_name:
                pk_column = (
                    prop_payload.get("property_name")
                    or (
                        (prop.evidence_refs or [{}])[0].get("column")
                        if prop.evidence_refs else None
                    )
                )
                break

        if not pk_column:
            issues.append({
                "code": "pk_column_not_resolved",
                "severity": "error",
                "draft_id": ot.id,
                "object_type": api_name,
                "primary_key": contract_pk_api_name,
                "message": (
                    f"Primary key '{contract_pk_api_name}' cannot be "
                    f"resolved to a dataset column through property evidence."
                ),
            })
            continue

        # ── Build property mappings, cross-validated ─────────────────────
        # contract_fields: property api_names from compiled contract for this OT
        contract_fields = set(ctx["fields_by_ot"].get(api_name, []))
        profile_columns = {
            c.get("name") for c in (dataset.profile_json or {}).get("columns", [])
        }

        property_mappings: dict[str, str] = {}
        mapping_issues: list[dict] = []

        for prop in prop_drafts:
            prop_payload = prop.payload or {}
            prop_ot = prop_payload.get("object_type")
            if prop_ot != api_name:
                continue
            prop_api_name = prop_payload.get("api_name")
            if not prop_api_name:
                continue

            # Must be in compiled contract
            if prop_api_name not in contract_fields:
                mapping_issues.append({
                    "code": "property_not_in_compiled_contract",
                    "severity": "error",
                    "property": prop_api_name,
                    "message": (
                        f"Property '{prop_api_name}' not in compiled contract."
                    ),
                })
                continue

            col_name = (
                prop_payload.get("property_name")
                or (
                    (prop.evidence_refs or [{}])[0].get("column")
                    if prop.evidence_refs else None
                )
            )
            if not col_name:
                mapping_issues.append({
                    "code": "column_not_in_evidence",
                    "severity": "error",
                    "property": prop_api_name,
                    "message": (
                        f"Property '{prop_api_name}' has no column evidence."
                    ),
                })
                continue

            # Must exist in dataset profile columns
            if col_name not in profile_columns:
                mapping_issues.append({
                    "code": "column_not_in_dataset",
                    "severity": "error",
                    "property": prop_api_name,
                    "column": col_name,
                    "message": (
                        f"Column '{col_name}' for property '{prop_api_name}' "
                        f"not found in dataset profile."
                    ),
                })
                continue

            property_mappings[prop_api_name] = col_name

        if mapping_issues:
            issues.extend(mapping_issues)

        if not property_mappings:
            issues.append({
                "code": "no_valid_property_mappings",
                "severity": "error",
                "draft_id": ot.id,
                "object_type": api_name,
                "message": (
                    f"No valid property mappings for Object Type "
                    f"'{api_name}'. All properties failed cross-validation."
                ),
            })
            continue

        # ── Check idempotency ────────────────────────────────────────────
        existing_binding = db.scalar(
            select(OntologyDatasetBinding).where(
                OntologyDatasetBinding.package_id == pkg.id,
                OntologyDatasetBinding.object_type_api_name == api_name,
            )
        )
        if existing_binding is not None:
            existing += 1
            continue

        # ── Verify binding.dataset_id equals Object Type source_dataset_id ─
        if ds_id != ot.source_dataset_id:
            issues.append({
                "code": "dataset_id_mismatch",
                "severity": "error",
                "draft_id": ot.id,
                "message": "Binding dataset_id does not match Object Type source_dataset_id.",
            })
            continue

        binding = OntologyDatasetBinding(
            group_id=group_id,
            project_id=project_id,
            package_id=pkg.id,
            dataset_id=ds_id,
            object_type_api_name=api_name,
            primary_key_column=pk_column,
            property_mappings=property_mappings,
            status="active",
            created_by=created_by,
        )
        db.add(binding)
        created += 1

    # ── Determine outcome from issues accumulated during iteration ────────
    has_errors = any(i.get("severity") == "error" for i in issues)

    # ── Commit or rollback with proper audit ordering ────────────────────
    try:
        if created and not has_errors:
            db.flush()
    except IntegrityError:
        # Concurrent duplicate — rollback, then record failure audit
        db.rollback()
        _record_audit(
            db, created_by, group_id, project_id, "generate_bindings",
            outcome="failure",
            error_code="concurrent_generation_conflict",
            error_summary="Concurrent binding generation conflict",
        )
        db.commit()
        return {
            "created_count": 0, "existing_count": existing,
            "issues": [{
                "code": "concurrent_generation_conflict",
                "severity": "error",
                "message": (
                    "Concurrent binding generation conflict. "
                    "Re-run to recover."
                ),
            }],
        }

    if has_errors:
        # Business failure: rollback binding additions, then record failure audit
        db.rollback()
        _record_audit(
            db, created_by, group_id, project_id, "generate_bindings",
            outcome="failure",
            row_count=0,
            error_code=issues[0]["code"] if issues else None,
            error_summary=(
                f"{len(issues)} issue(s)" if issues else None
            ),
        )
        db.commit()
        return {
            "created_count": 0, "existing_count": existing,
            "issues": issues,
        }

    # Success: bindings + audit in same transaction
    _record_audit(
        db, created_by, group_id, project_id, "generate_bindings",
        outcome="success",
        row_count=created,
    )
    db.commit()

    return {
        "created_count": created,
        "existing_count": existing,
        "issues": issues,
    }


#  query execution — re-exported from runtime_query


# ═══════════════════════════════════════════════════════════════════════════
#  pilot activation — full smoke query per binding
# ═══════════════════════════════════════════════════════════════════════════


def activate_pilot(
    db: Session,
    group_id: str,
    project_id: str,
    user_id: str,
) -> dict:
    """Activate the pilot stage for a project.

    Uses the full query execution path for smoke (not just _read_rows).
    Smoke verifies: binding completeness, PK resolution, all contract
    property mappings, type conversion.

    On failure: rolls back all state changes, records audit.
    Idempotent on already-pilot.
    """
    from semantic_lighthouse.services.projects import advance_stage

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="failure", error_code="project_not_found",
            error_summary="Project not found",
        )
        db.commit()
        raise ValueError("Project not found")

    if project.status != "active":
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="failure", error_code="archive",
            error_summary="Project is archived",
        )
        db.commit()
        raise ValueError("Project is archived")

    if project.stage not in ("validate", "pilot"):
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="failure", error_code="stage",
            error_summary=f"Stage is {project.stage}, not validate/pilot",
        )
        db.commit()
        raise ValueError(
            f"Project must be at validate or pilot stage, "
            f"currently: {project.stage}"
        )

    # Already pilot → idempotent with audit
    if project.stage == "pilot":
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="success", row_count=0,
        )
        db.commit()
        return {
            "activated": False,
            "already_pilot": True,
            "stage": "pilot",
            "issues": [],
        }

    # ── Get latest package and compiled contract ────────────────────────────
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="failure", error_code="no_package",
            error_summary="No project package found",
        )
        db.commit()
        raise ValueError("No project package found")

    try:
        _build_contract_context(pkg)  # verify compilation works
    except Exception:
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="failure", error_code="contract_compilation",
            error_summary="Business contract compilation failed",
        )
        db.commit()
        raise ValueError("Business contract compilation failed")

    source_ids = pkg.source_draft_ids or []
    accepted_ots = db.scalars(
        select(OntologyModelingDraft).where(
            OntologyModelingDraft.id.in_(source_ids),
            OntologyModelingDraft.status == "accepted",
            OntologyModelingDraft.draft_type == "object_type",
            OntologyModelingDraft.group_id == group_id,
        )
    ).all()

    issues: list[dict] = []

    # Only Object Types from datasets
    dataset_ots = [ot for ot in accepted_ots if ot.source_dataset_id]
    if not dataset_ots:
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="failure",
            error_code="no_dataset_ots",
            error_summary="No dataset-grounded Object Types in the package",
        )
        db.commit()
        raise ValueError(
            "No dataset-grounded Object Types found in the package."
        )

    # ── Full smoke for each binding ─────────────────────────────────────────
    for ot in dataset_ots:
        api_name = (ot.payload or {}).get("api_name")
        ds_id = ot.source_dataset_id

        binding = db.scalar(
            select(OntologyDatasetBinding).where(
                OntologyDatasetBinding.package_id == pkg.id,
                OntologyDatasetBinding.object_type_api_name == api_name,
                OntologyDatasetBinding.status == "active",
            )
        )
        if binding is None:
            issues.append({
                "code": "missing_binding",
                "severity": "error",
                "object_type": api_name,
                "message": f"No active binding for Object Type '{api_name}'.",
            })
            continue

        # Verify binding.dataset_id equals OT source_dataset_id
        if binding.dataset_id != ds_id:
            issues.append({
                "code": "binding_dataset_mismatch",
                "severity": "error",
                "object_type": api_name,
                "message": "Binding dataset_id does not match Object Type source_dataset_id.",
            })
            continue

        dataset = db.get(DatasetAsset, ds_id)
        if dataset is None or dataset.status != "ready":
            issues.append({
                "code": "dataset_not_ready",
                "severity": "error",
                "object_type": api_name,
                "message": f"Dataset not ready for Object Type '{api_name}'.",
            })
            continue

        if dataset.row_count < 1:
            issues.append({
                "code": "empty_dataset",
                "severity": "error",
                "object_type": api_name,
                "message": f"Dataset for '{api_name}' has zero rows.",
            })
            continue

        # ── Smoke: use full query with limit=1 ──────────────────────────
        try:
            result = execute_query(
                db, group_id, project_id, api_name,
                user_id=user_id,
                limit=1, offset=0,
                explain_only=False,
            )
            if result.get("type_errors"):
                issues.append({
                    "code": "smoke_type_conversion_error",
                    "severity": "error",
                    "object_type": api_name,
                    "message": (
                        f"Smoke query failed with {len(result['type_errors'])} "
                        f"type conversion error(s)."
                    ),
                })
                continue

            if result.get("row_count", 0) == 0:
                issues.append({
                    "code": "smoke_no_rows",
                    "severity": "error",
                    "object_type": api_name,
                    "message": "Smoke query returned no rows.",
                })
                continue

        except ValueError:
            issues.append({
                "code": "smoke_query_failed",
                "severity": "error",
                "object_type": api_name,
                "message": _sanitized_code("smoke_failed"),
            })
            continue

    if issues:
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="failure",
            error_code=issues[0]["code"],
            error_summary=f"{len(issues)} issue(s)",
        )
        db.commit()
        return {
            "activated": False,
            "already_pilot": False,
            "stage": "validate",
            "issues": issues,
        }

    # ── All gates passed: advance to pilot ──────────────────────────────────
    advance_stage("validate", "pilot")
    project.stage = "pilot"

    # Audit in same transaction as state change.
    # If audit write or commit fails, roll back stage change.
    try:
        _record_audit(
            db, user_id, group_id, project_id, "activate",
            outcome="success", row_count=len(dataset_ots),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "activated": True,
        "already_pilot": False,
        "stage": "pilot",
        "issues": [],
    }
