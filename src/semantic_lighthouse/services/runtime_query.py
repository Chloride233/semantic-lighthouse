"""Runtime query core — value/filter conversion and read-only query execution.

Extracted from services/runtime.py per R1D.
No API, permission, migration, or query semantic changes.

Query semantics: single object_type, field whitelist, equality filters,
typed conversion, filter-before-offset-before-limit.
No SQL, no DSL, no AST, no LLM, no Graph RAG, no writes.
"""

from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime as dt_datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import get_settings
from semantic_lighthouse.models import (
    DatasetAsset,
    OntologyDatasetBinding,
)
from semantic_lighthouse.services.runtime_audit import _record_audit
from semantic_lighthouse.services.runtime_contract import (
    _build_contract_context,
    _get_latest_project_package,
)
from semantic_lighthouse.services.runtime_dataset_io import (
    _read_dataset_rows,
    _validate_dataset_path,
)

# ═══════════════════════════════════════════════════════════════════════════
#  query constants
# ═══════════════════════════════════════════════════════════════════════════

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_MAX_OFFSET = 10000


# ═══════════════════════════════════════════════════════════════════════════
#  contract value_type → deterministic Python converter
# ═══════════════════════════════════════════════════════════════════════════


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
        try:
            d = dt_date.fromisoformat(stripped)
        except (ValueError, TypeError):
            raise ValueError(
                f"Field '{field_name}': value is not a valid date (YYYY-MM-DD)"
            )
        return d.isoformat()
    if value_type == "datetime":
        try:
            d = dt_datetime.fromisoformat(stripped)
        except (ValueError, TypeError):
            raise ValueError(
                f"Field '{field_name}': value is not a valid ISO datetime"
            )
        return d.isoformat()
    return stripped


def _convert_filter_value(
    raw: str | int | float | bool | None,
    value_type: str,
    field_name: str,
) -> Any:
    """Convert a JSON scalar filter value for deterministic comparison.

    Accepts string, integer, number, boolean, null from the JSON body.
    Integer type rejects bool subtypes. Arrays and objects rejected by Pydantic.
    """
    # Reject arrays / objects (defense in depth)
    if isinstance(raw, (list, dict)):
        raise ValueError(
            f"Field '{field_name}': filter value must be a scalar"
        )

    # None matches empty cells
    if raw is None:
        return None

    # Already a Python scalar — validate against contract type
    if value_type == "integer":
        if isinstance(raw, bool):
            raise ValueError(
                f"Field '{field_name}': boolean not accepted for integer filter"
            )
        if isinstance(raw, str):
            return _convert_value(raw, "integer", field_name)
        if isinstance(raw, (int, float)):
            if isinstance(raw, float) and raw != int(raw):
                raise ValueError(
                    f"Field '{field_name}': float with fractional part "
                    f"not accepted for integer filter"
                )
            return int(raw)
        raise ValueError(
            f"Field '{field_name}': cannot convert filter value to integer"
        )

    if value_type == "number":
        if isinstance(raw, bool):
            raise ValueError(
                f"Field '{field_name}': boolean not accepted for number filter"
            )
        if isinstance(raw, str):
            return _convert_value(raw, "number", field_name)
        if isinstance(raw, (int, float)):
            return float(raw)
        raise ValueError(
            f"Field '{field_name}': cannot convert filter value to number"
        )

    if value_type == "boolean":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return _convert_value(raw, "boolean", field_name)
        raise ValueError(
            f"Field '{field_name}': filter value must be boolean or string"
        )

    if value_type == "date":
        if isinstance(raw, str):
            return _convert_value(raw, "date", field_name)
        raise ValueError(
            f"Field '{field_name}': date filter must be a string (YYYY-MM-DD)"
        )

    if value_type == "datetime":
        if isinstance(raw, str):
            return _convert_value(raw, "datetime", field_name)
        raise ValueError(
            f"Field '{field_name}': datetime filter must be an ISO string"
        )

    # string — convert anything to string for comparison
    if value_type == "string":
        if raw is None:
            return None
        return str(raw)

    raise ValueError(f"Unknown value_type: {value_type}")


# ═══════════════════════════════════════════════════════════════════════════
#  query execution — compiled contract, filter-before-offset/limit, streaming
# ═══════════════════════════════════════════════════════════════════════════


def execute_query(
    db: Session,
    group_id: str,
    project_id: str,
    object_type: str,
    user_id: str,
    fields: list[str] | None = None,
    filters: dict[str, str | int | float | bool | None] | None = None,
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
        for fname, fval in filters.items():
            if fname not in valid_fields:
                return _fail("invalid_filter",
                              f"Filter field '{fname}' is not a bound property")
            # Type-convert filter value (handles str/int/float/bool/None)
            vt = ctx["prop_map"].get(fname, {}).get("value_type", "string")
            try:
                converted_filters[fname] = _convert_filter_value(
                    fval, vt, fname,
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
    # Compute internal conversion set: selected_fields ∪ filter_field_names.
    # This ensures filter field values are available for comparison even when
    # the caller did not request them in the output.
    internal_fields = set(selected_fields) | set(filter_field_names)

    matched: list[dict] = []
    type_errors: list[dict] = []
    scan_row_index = 0

    for row in data_rows:
        mapped: dict[str, Any] = {}
        row_ok = True

        for prop_api_name in internal_fields:
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

        # Only return requested fields (strip filter-only fields)
        result_row = {k: v for k, v in mapped.items() if k in selected_fields}
        matched.append(result_row)
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
