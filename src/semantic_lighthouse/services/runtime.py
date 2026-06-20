"""Phase 14.5 — Pilot Read Runtime service.

Deterministic binding generation from compiled business_v1 contract
to DatasetAssets. Limited, explainable, permission-isolated
read-only query execution over CSV/XLSX with contract type conversion.

Review C hardened: audit, filter-before-offset/limit, compiled contract
as truth, no PK guessing, full smoke on activation.

No SQL, no DSL, no AST, no LLM, no MCP, no Graph RAG, no writes.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import get_settings
from semantic_lighthouse.models import (
    BusinessProject,
    DatasetAsset,
    OntologyDatasetBinding,
    OntologyModelingDraft,
    OntologyModelPackage,
    OntologyRuntimeAudit,
)
from semantic_lighthouse.services.business_contract_compiler import (
    compile_business_contract,
)

# ═══════════════════════════════════════════════════════════════════════════
#  audit
# ═══════════════════════════════════════════════════════════════════════════


def _record_audit(
    db: Session,
    user_id: str,
    group_id: str,
    project_id: str,
    operation: str,
    *,
    object_type: str | None = None,
    field_names: list[str] | None = None,
    filter_field_names: list[str] | None = None,
    limit_val: int | None = None,
    offset_val: int | None = None,
    outcome: str,
    row_count: int | None = None,
    error_code: str | None = None,
    error_summary: str | None = None,
) -> OntologyRuntimeAudit:
    """Write an immutable runtime audit record.

    Never records filter values, raw data, storage_path, PII, or secrets.
    """
    record = OntologyRuntimeAudit(
        user_id=user_id,
        group_id=group_id,
        project_id=project_id,
        operation=operation,
        object_type=object_type,
        field_names=field_names,
        filter_field_names=filter_field_names,
        limit_val=limit_val,
        offset_val=offset_val,
        outcome=outcome,
        row_count=row_count,
        error_code=error_code,
        error_summary=error_summary,
    )
    db.add(record)
    return record


# ═══════════════════════════════════════════════════════════════════════════
#  contract value_type → deterministic Python converter
# ═══════════════════════════════════════════════════════════════════════════

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def _convert_value(
    raw: str | None, value_type: str, field_name: str,
) -> Any:
    """Convert a raw string cell value to the contract's declared type.

    Never includes the raw value in error messages.
    """
    if raw is None or raw.strip() == "":
        return None

    stripped = raw.strip()

    if value_type == "string":
        return stripped
    if value_type == "integer":
        try:
            return int(stripped)
        except (ValueError, OverflowError):
            raise ValueError(
                f"Field '{field_name}': value is not a valid integer"
            )
    if value_type == "number":
        try:
            return float(stripped)
        except (ValueError, OverflowError):
            raise ValueError(
                f"Field '{field_name}': value is not a valid number"
            )
    if value_type == "boolean":
        lower = stripped.lower()
        if lower in ("true", "1", "yes"):
            return True
        if lower in ("false", "0", "no"):
            return False
        raise ValueError(
            f"Field '{field_name}': value is not a valid boolean"
        )
    if value_type == "date":
        if not _DATE_RE.match(stripped):
            raise ValueError(
                f"Field '{field_name}': value is not a valid ISO date (YYYY-MM-DD)"
            )
        return stripped
    if value_type == "datetime":
        if not _DATETIME_RE.match(stripped):
            raise ValueError(
                f"Field '{field_name}': value is not a valid ISO datetime"
            )
        return stripped
    return stripped


def _convert_filter_value(
    raw: str, value_type: str, field_name: str,
) -> Any:
    """Convert a filter value for comparison. Rejects arrays/objects."""
    converted = _convert_value(raw, value_type, field_name)
    if isinstance(converted, (list, dict)):
        raise ValueError(
            f"Field '{field_name}': filter value must be a scalar"
        )
    return converted


# ═══════════════════════════════════════════════════════════════════════════
#  sanitized error helpers
# ═══════════════════════════════════════════════════════════════════════════

_SANITIZED_ERROR_CODES = {
    "path_outside_root": "dataset_path_outside_root",
    "path_outside_project": "dataset_path_outside_project",
    "file_not_found": "dataset_file_not_found",
    "no_package": "no_project_package",
    "no_binding": "no_active_binding",
    "dataset_not_ready": "dataset_not_ready",
    "read_error": "file_read_error",
    "type_conversion": "type_conversion_error",
    "binding_missing": "missing_binding",
    "smoke_failed": "smoke_query_failed",
    "archive": "project_archived",
    "stage": "stage_not_allowed",
}


def _sanitized_code(error_type: str) -> str:
    """Map internal error type to stable, non-leaking error code."""
    return _SANITIZED_ERROR_CODES.get(error_type, "internal_error")


# ═══════════════════════════════════════════════════════════════════════════
#  compiled contract context — single source of truth for runtime
# ═══════════════════════════════════════════════════════════════════════════


def _build_contract_context(pkg: OntologyModelPackage) -> dict:
    """Compile the package into a runtime-ready context.

    Returns dict with:
      - manifest: the compiled business manifest
      - semantic_hash: from manifest
      - ot_map: {api_name: {primary_key, ...}}
      - prop_map: {api_name: {object_type, value_type, required}}
      - fields_by_ot: {object_type_api_name: [prop_api_names]}
    """
    compiled = compile_business_contract(pkg)
    manifest = compiled["manifest"]

    ot_map: dict[str, dict] = {}
    for ot in compiled.get("object_types", []):
        an = ot.get("api_name")
        if an:
            ot_map[an] = {
                "primary_key": ot.get("primary_key", ""),
                "display_name": ot.get("display_name", ""),
            }

    prop_map: dict[str, dict] = {}
    fields_by_ot: dict[str, list[str]] = {}
    for prop in compiled.get("properties", []):
        an = prop.get("api_name")
        ot = prop.get("object_type", "")
        vt = prop.get("value_type", "string")
        if an:
            prop_map[an] = {
                "object_type": ot,
                "value_type": vt,
                "required": prop.get("required", False),
            }
            fields_by_ot.setdefault(ot, []).append(an)

    return {
        "manifest": manifest,
        "semantic_hash": manifest.get("semantic_hash", ""),
        "ot_map": ot_map,
        "prop_map": prop_map,
        "fields_by_ot": fields_by_ot,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  CSV / XLSX row reader (streaming for CSV, read_only for XLSX)
# ═══════════════════════════════════════════════════════════════════════════


def _stream_csv_rows(
    file_path: str,
    max_rows: int,
) -> tuple[list[str], list[list[str | None]], int, bool]:
    """Stream rows from a CSV file. Never loads entire file into memory.

    Returns (header, data_rows, scanned_count, truncated).
    """
    scanned = 0
    rows: list[list[str | None]] = []

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.reader(fh, strict=True)
        try:
            header_row = next(reader)
        except StopIteration:
            raise ValueError("CSV file has no rows")
        except csv.Error as e:
            raise ValueError(f"CSV parse error: {e}") from e

        header = [h.strip() for h in header_row]
        if not header or all(h == "" for h in header):
            raise ValueError("CSV file has no valid header row")

        # Deduplicate check
        seen: set[str] = set()
        for h in header:
            if not h:
                raise ValueError("CSV header contains empty column name")
            if h in seen:
                raise ValueError(f"Duplicate column name: {h!r}")
            seen.add(h)

        for row in reader:
            scanned += 1
            if len(rows) >= max_rows:
                return header, rows, scanned, True

            parsed: list[str | None] = []
            for i in range(len(header)):
                if i >= len(row) or row[i].strip() == "":
                    parsed.append(None)
                else:
                    parsed.append(row[i].strip())
            rows.append(parsed)

    return header, rows, scanned, scanned > 0 and len(rows) >= max_rows


def _stream_xlsx_rows(
    file_path: str,
    max_rows: int,
) -> tuple[list[str], list[list[str | None]], int, bool]:
    """Read rows from an XLSX file (first visible sheet, read_only)."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ImportError("openpyxl is required for XLSX reading") from None

    try:
        wb = load_workbook(file_path, read_only=True, data_only=True, keep_links=False)
    except Exception as e:
        raise ValueError(f"Cannot open XLSX file: {e}") from e

    try:
        ws = None
        for name in wb.sheetnames:
            candidate = wb[name]
            if candidate and candidate.sheet_state == "visible":
                ws = candidate
                break
        if ws is None:
            raise ValueError("XLSX file has no visible worksheets")

        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if header_row is None or all(v is None or str(v).strip() == "" for v in header_row):
            raise ValueError("XLSX file has no valid header row")

        header = [str(v).strip() if v is not None else "" for v in header_row]
        while header and header[-1] == "":
            header.pop()
        if not header:
            raise ValueError("XLSX file has no valid header row")

        scanned = 0
        rows: list[list[str | None]] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if all(v is None or str(v).strip() == "" for v in row):
                continue
            scanned += 1
            if len(rows) >= max_rows:
                return header, rows, scanned, True

            parsed: list[str | None] = []
            for i in range(len(header)):
                if i >= len(row) or row[i] is None or str(row[i]).strip() == "":
                    parsed.append(None)
                else:
                    parsed.append(str(row[i]).strip())
            rows.append(parsed)

        return header, rows, scanned, False
    finally:
        wb.close()


def _read_dataset_rows(
    file_path: str,
    file_format: str,
    max_rows: int,
) -> tuple[list[str], list[list[str | None]], int, bool]:
    """Read rows from a dataset file.

    Returns (header, data_rows, scanned_count, truncated).
    CSV uses streaming; XLSX uses openpyxl read_only.
    """
    if file_format == "csv":
        return _stream_csv_rows(file_path, max_rows)
    if file_format == "xlsx":
        return _stream_xlsx_rows(file_path, max_rows)
    raise ValueError(f"Unsupported file format: {file_format}")


# ═══════════════════════════════════════════════════════════════════════════
#  path safety
# ═══════════════════════════════════════════════════════════════════════════


def _validate_dataset_path(
    storage_path: str, group_id: str, project_id: str,
) -> Path:
    """Resolve storage_path and verify it stays within the dataset storage tree."""
    settings = get_settings()
    root = Path(settings.dataset_storage_path).resolve()
    target = Path(storage_path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Dataset path is outside the storage root")

    expected_prefix = root / group_id / project_id
    try:
        target.relative_to(expected_prefix)
    except ValueError:
        raise ValueError("Dataset path is outside the project scope")

    return target


# ═══════════════════════════════════════════════════════════════════════════
#  latest project package helper
# ═══════════════════════════════════════════════════════════════════════════


def _get_latest_project_package(
    db: Session, group_id: str, project_id: str,
) -> OntologyModelPackage | None:
    """Return the latest (highest version) project-scoped package."""
    return db.scalar(
        select(OntologyModelPackage)
        .where(
            OntologyModelPackage.group_id == group_id,
            OntologyModelPackage.scope_key == f"project:{project_id}",
        )
        .order_by(OntologyModelPackage.version.desc())
        .limit(1)
    )


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

    # ── Commit with IntegrityError handling ─────────────────────────────
    try:
        if created:
            db.flush()
    except Exception:
        db.rollback()
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

    outcome = "success" if not issues or all(
        i.get("severity") != "error" for i in issues
    ) else "failure"

    _record_audit(
        db, created_by, group_id, project_id, "generate_bindings",
        object_type=None,
        outcome=outcome,
        row_count=created,
        error_code=(issues[0]["code"] if issues and outcome == "failure" else None),
        error_summary=(
            f"{len(issues)} issue(s)" if issues and outcome == "failure"
            else None
        ),
    )

    if outcome == "failure":
        db.rollback()
        return {
            "created_count": 0, "existing_count": existing,
            "issues": issues,
        }

    if created:
        db.commit()
    else:
        # Still commit the audit record even if nothing created
        db.commit()

    return {
        "created_count": created,
        "existing_count": existing,
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  query execution — compiled contract, filter-before-offset/limit, streaming
# ═══════════════════════════════════════════════════════════════════════════

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_MAX_OFFSET = 10000


def execute_query(
    db: Session,
    group_id: str,
    project_id: str,
    object_type: str,
    user_id: str,
    fields: list[str] | None = None,
    filters: dict[str, str] | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
    explain_only: bool = False,
) -> dict:
    """Execute a read-only query against a bound dataset Object Type.

    Uses compiled business contract as single source of truth for
    value_types, field whitelist, and semantic_hash.

    Correct semantics: stream → convert → filter → offset → limit.
    """
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, min(offset, _MAX_OFFSET))

    audit_kwargs: dict = {
        "user_id": user_id,
        "group_id": group_id,
        "project_id": project_id,
        "operation": "query",
        "object_type": object_type,
        "limit_val": limit,
        "offset_val": offset,
    }

    def _fail(code: str, summary: str) -> dict:
        _record_audit(
            db, **audit_kwargs, outcome="failure",
            error_code=code, error_summary=summary,
        )
        db.commit()
        raise ValueError(summary)  # router catches this

    # ── Latest package and binding ──────────────────────────────────────────
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        return _fail("no_package",
                      "No project package found for this project")

    binding = db.scalar(
        select(OntologyDatasetBinding).where(
            OntologyDatasetBinding.package_id == pkg.id,
            OntologyDatasetBinding.object_type_api_name == object_type,
            OntologyDatasetBinding.status == "active",
            OntologyDatasetBinding.group_id == group_id,
            OntologyDatasetBinding.project_id == project_id,
        )
    )
    if binding is None:
        return _fail("no_binding",
                      f"No active binding for Object Type '{object_type}'")

    # ── Validate dataset ────────────────────────────────────────────────────
    dataset = db.get(DatasetAsset, binding.dataset_id)
    if dataset is None or dataset.status not in ("ready",):
        return _fail("dataset_not_ready",
                      "Bound dataset not found or not ready")
    if dataset.group_id != group_id or dataset.project_id != project_id:
        return _fail("dataset_not_ready",
                      "Bound dataset does not belong to this project")

    # ── Compile contract — single source of truth ───────────────────────────
    try:
        ctx = _build_contract_context(pkg)
    except Exception:
        return _fail("contract_compilation",
                      "Business contract compilation failed")

    # ── Field whitelist from compiled contract ──────────────────────────────
    all_contract_fields = set(ctx["fields_by_ot"].get(object_type, []))
    # Cross with binding
    bound_fields = set(binding.property_mappings.keys())
    valid_fields = all_contract_fields & bound_fields

    if fields:
        invalid = [f for f in fields if f not in valid_fields]
        if invalid:
            return _fail("invalid_fields",
                          f"Fields not in contract: {', '.join(invalid)}")
        selected_fields = fields
    else:
        selected_fields = sorted(valid_fields)

    if not selected_fields:
        return _fail("no_fields",
                      "No valid fields for this Object Type")

    # ── Validate filter fields against compiled contract ────────────────────
    filter_field_names: list[str] = []
    converted_filters: dict[str, Any] = {}
    if filters:
        for fname, fval_str in filters.items():
            if fname not in valid_fields:
                return _fail("invalid_filter",
                              f"Filter field '{fname}' is not a bound property")
            # Type-convert filter value
            vt = ctx["prop_map"].get(fname, {}).get("value_type", "string")
            try:
                converted_filters[fname] = _convert_filter_value(
                    fval_str, vt, fname,
                )
            except ValueError:
                return _fail("type_conversion",
                              f"Filter value for '{fname}' cannot be "
                              f"converted to {vt}")
            filter_field_names.append(fname)

    # ── Resolve and validate file path ──────────────────────────────────────
    try:
        file_path = _validate_dataset_path(
            dataset.storage_path, group_id, project_id,
        )
    except ValueError:
        return _fail("path_outside_root",
                      "Dataset path validation failed")
    if not file_path.exists():
        return _fail("file_not_found",
                      "Dataset file not found on disk")

    # ── Build explain/provenance (no filter values, no paths, no raw data) ─
    explain = {
        "package_id": pkg.id,
        "package_version": pkg.version,
        "package_semantic_hash": ctx["semantic_hash"],
        "binding_id": binding.id,
        "dataset_id": dataset.id,
        "dataset_content_hash": dataset.content_hash,
        "object_type": object_type,
        "selected_fields": selected_fields,
        "filter_field_names": filter_field_names,
        "limit": limit,
        "offset": offset,
    }

    if explain_only:
        _record_audit(
            db, **audit_kwargs,
            field_names=selected_fields,
            filter_field_names=filter_field_names,
            outcome="success", row_count=0,
        )
        db.commit()
        return {"rows": [], "row_count": None, "explain": explain}

    # ── Read data: stream all rows up to scan limit ─────────────────────────
    settings = get_settings()
    scan_limit = settings.dataset_max_scan_rows
    try:
        header, data_rows, scanned_count, truncated = _read_dataset_rows(
            str(file_path), dataset.file_format, max_rows=scan_limit,
        )
    except Exception:
        return _fail("read_error",
                      "Failed to read dataset file")

    col_index: dict[str, int] = {name: i for i, name in enumerate(header)}

    # ── Map, type-convert, filter ───────────────────────────────────────────
    matched: list[dict] = []
    type_errors: list[dict] = []
    scan_row_index = 0

    for row in data_rows:
        mapped: dict[str, Any] = {}
        row_ok = True

        for prop_api_name in selected_fields:
            col_name = binding.property_mappings.get(prop_api_name)
            if col_name is None or col_name not in col_index:
                mapped[prop_api_name] = None
                continue

            raw_val = row[col_index[col_name]]
            vt = ctx["prop_map"].get(prop_api_name, {}).get("value_type", "string")

            try:
                converted = _convert_value(raw_val, vt, prop_api_name)
                mapped[prop_api_name] = converted
            except ValueError:
                type_errors.append({
                    "row": scan_row_index,
                    "field": prop_api_name,
                    "value_type": vt,
                })
                row_ok = False
                mapped[prop_api_name] = None

        if not row_ok:
            scan_row_index += 1
            continue

        # Apply type-converted equality filters
        if converted_filters:
            skip = False
            for fname, fval in converted_filters.items():
                row_val = mapped.get(fname)
                if row_val != fval:
                    skip = True
                    break
            if skip:
                scan_row_index += 1
                continue

        matched.append(mapped)
        scan_row_index += 1

    # ── Apply offset then limit ─────────────────────────────────────────────
    paged = matched[offset:offset + limit]
    out_row_count = len(paged)

    # ── Build response ──────────────────────────────────────────────────────
    explain["scanned_rows"] = scanned_count
    explain["scan_limit"] = scan_limit
    explain["scan_truncated"] = truncated
    explain["matched_before_paging"] = len(matched)

    response: dict = {
        "rows": paged,
        "row_count": out_row_count,
        "explain": explain,
    }

    if type_errors:
        response["type_errors"] = type_errors
        response["row_count"] = None

    # ── Audit (must succeed before returning) ───────────────────────────────
    final_outcome = (
        "failure" if type_errors
        else "empty" if out_row_count == 0
        else "success"
    )
    _record_audit(
        db, **audit_kwargs,
        field_names=selected_fields,
        filter_field_names=filter_field_names,
        outcome=final_outcome,
        row_count=out_row_count if not type_errors else None,
        error_code=(
            "type_conversion" if type_errors else None
        ),
        error_summary=(
            f"{len(type_errors)} type conversion error(s)"
            if type_errors else None
        ),
    )
    db.commit()

    return response


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

    # Audit in same transaction as state change
    _record_audit(
        db, user_id, group_id, project_id, "activate",
        outcome="success", row_count=len(dataset_ots),
    )
    db.commit()

    return {
        "activated": True,
        "already_pilot": False,
        "stage": "pilot",
        "issues": [],
    }
