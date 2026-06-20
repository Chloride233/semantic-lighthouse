"""Phase 14.5 — Pilot Read Runtime service.

Deterministic binding generation from accepted business_v1 contract
drafts to DatasetAssets. Limited, explainable, permission-isolated
read-only query execution over CSV/XLSX with contract type conversion.

No SQL, no DSL, no AST, no LLM, no MCP, no Graph RAG, no writes.
"""

from __future__ import annotations

import csv
import io
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
)

# ═══════════════════════════════════════════════════════════════════════════
#  contract value_type → deterministic Python converter
# ═══════════════════════════════════════════════════════════════════════════


def _convert_value(raw: str | None, value_type: str, field_name: str) -> Any:
    """Convert a raw string cell value to the contract's declared type.

    Returns the converted Python value or raises ValueError with a
    field-specific message. Never silently coerces or forges data.
    """
    if raw is None or raw.strip() == "":
        return None

    stripped = raw.strip()

    if value_type == "string":
        return stripped
    if value_type in ("integer", "number"):
        try:
            return int(stripped) if value_type == "integer" else float(stripped)
        except (ValueError, OverflowError) as exc:
            raise ValueError(
                f"Cannot convert field '{field_name}' value "
                f"to {value_type}: {stripped!r}"
            ) from exc
    if value_type == "boolean":
        lower = stripped.lower()
        if lower in ("true", "1", "yes"):
            return True
        if lower in ("false", "0", "no"):
            return False
        raise ValueError(
            f"Cannot convert field '{field_name}' to boolean: {stripped!r}"
        )
    if value_type in ("date", "datetime"):
        # Return as string; no datetime parsing needed for read contract
        return stripped
    return stripped


# ═══════════════════════════════════════════════════════════════════════════
#  CSV / XLSX row reader (minimal, shared — no profiling duplication)
# ═══════════════════════════════════════════════════════════════════════════


def _read_rows(
    file_path: str,
    file_format: str,
    column_indices: dict[str, int] | None = None,
    max_rows: int = 100,
    offset: int = 0,
) -> tuple[list[str], list[list[str | None]]]:
    """Read rows from a CSV or XLSX file.

    Returns (header_names, data_rows) where data_rows are lists of
    string-or-None values indexed by column position.

    Args:
        file_path: Absolute path to the dataset file.
        file_format: "csv" or "xlsx".
        column_indices: Optional pre-computed header→index map (for XLSX reuse).
        max_rows: Maximum data rows to return.
        offset: Number of data rows to skip.

    Raises:
        ValueError: On unsupported format, encoding, or parse errors.
    """
    if file_format == "csv":
        return _read_csv_rows(file_path, max_rows, offset)
    if file_format == "xlsx":
        return _read_xlsx_rows(file_path, max_rows, offset)
    raise ValueError(f"Unsupported file format: {file_format}")


def _read_csv_rows(
    file_path: str, max_rows: int, offset: int,
) -> tuple[list[str], list[list[str | None]]]:
    """Read rows from a UTF-8 CSV file."""
    raw_bytes = Path(file_path).read_bytes()
    if not raw_bytes.strip():
        raise ValueError("Empty CSV file")

    text: str
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"CSV encoding not supported: {e}") from e

    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("CSV file has no rows")
    except csv.Error as e:
        raise ValueError(f"CSV parse error: {e}") from e

    if not header or all(h == "" for h in header):
        raise ValueError("CSV file has no valid header row")

    header = [h.strip() for h in header]

    # Skip offset rows
    skipped = 0
    rows: list[list[str | None]] = []
    for row in reader:
        if skipped < offset:
            skipped += 1
            continue
        if len(rows) >= max_rows:
            break
        parsed: list[str | None] = []
        for i in range(len(header)):
            if i >= len(row) or row[i].strip() == "":
                parsed.append(None)
            else:
                parsed.append(row[i].strip())
        rows.append(parsed)

    return header, rows


def _read_xlsx_rows(
    file_path: str, max_rows: int, offset: int,
) -> tuple[list[str], list[list[str | None]]]:
    """Read rows from an XLSX file (first visible sheet)."""
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

        skipped = 0
        rows: list[list[str | None]] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if all(v is None or str(v).strip() == "" for v in row):
                continue
            if skipped < offset:
                skipped += 1
                continue
            if len(rows) >= max_rows:
                break
            parsed: list[str | None] = []
            for i in range(len(header)):
                if i >= len(row) or row[i] is None or str(row[i]).strip() == "":
                    parsed.append(None)
                else:
                    parsed.append(str(row[i]).strip())
            rows.append(parsed)

        return header, rows
    finally:
        wb.close()


# ═══════════════════════════════════════════════════════════════════════════
#  path safety
# ═══════════════════════════════════════════════════════════════════════════


def _validate_dataset_path(
    storage_path: str, group_id: str, project_id: str,
) -> Path:
    """Resolve storage_path and verify it stays within the dataset storage tree.

    Path must resolve to: dataset_storage_path / group_id / project_id / ...
    """
    settings = get_settings()
    root = Path(settings.dataset_storage_path).resolve()
    target = Path(storage_path).resolve()

    # Must be under the storage root
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Dataset path is outside the storage root")

    # Must be under the group/project subdirectory
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
#  binding generation
# ═══════════════════════════════════════════════════════════════════════════


def generate_bindings(
    db: Session,
    group_id: str,
    project_id: str,
    created_by: str,
) -> dict:
    """Deterministically generate OntologyDatasetBindings from the latest
    project-scoped package's accepted business_v1 drafts.

    Only Object Types with a source_dataset_id get bindings.
    Action Types never get bindings. Link Types not joined.

    Idempotent: re-running with the same package produces no duplicates.
    Never overwrites bindings that point to a different (older) package.

    Returns:
        dict with created_count, existing_count, issues list.
    """
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        return {
            "created_count": 0,
            "existing_count": 0,
            "issues": [{
                "code": "no_project_package",
                "severity": "error",
                "message": "No project-scoped package found. Build a package first.",
            }],
        }

    # Get accepted draft IDs from the package
    source_ids = pkg.source_draft_ids or []
    if not source_ids:
        return {
            "created_count": 0,
            "existing_count": 0,
            "issues": [{
                "code": "no_source_drafts",
                "severity": "error",
                "message": "Package has no source draft references.",
            }],
        }

    # Load accepted drafts that belong to this package
    accepted_drafts = db.scalars(
        select(OntologyModelingDraft).where(
            OntologyModelingDraft.id.in_(source_ids),
            OntologyModelingDraft.status == "accepted",
            OntologyModelingDraft.group_id == group_id,
            OntologyModelingDraft.project_id == project_id,
        )
    ).all()

    # Separate by type
    ot_drafts = [d for d in accepted_drafts if d.draft_type == "object_type"]
    prop_drafts = [d for d in accepted_drafts if d.draft_type == "property"]

    if not ot_drafts:
        return {
            "created_count": 0,
            "existing_count": 0,
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
        api_name = (ot.payload or {}).get("api_name")
        ds_id = ot.source_dataset_id
        pk_api_name = (ot.payload or {}).get("primary_key")

        if not api_name or not ds_id:
            issues.append({
                "code": "incomplete_object_type",
                "severity": "error",
                "draft_id": ot.id,
                "message": (
                    f"Object Type draft '{ot.name}' missing api_name "
                    f"or source_dataset_id."
                ),
            })
            continue

        # Validate dataset exists and is ready / belongs to this project
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
                "message": f"Dataset '{dataset.original_name}' status is "
                           f"'{dataset.status}', not 'ready'.",
            })
            continue

        # Find PK column
        pk_column: str | None = None
        if pk_api_name:
            for prop in prop_drafts:
                if (prop.payload or {}).get("api_name") == pk_api_name:
                    pk_column = (
                        (prop.payload or {}).get("property_name")
                        or (
                            (prop.evidence_refs or [{}])[0].get("column")
                            if prop.evidence_refs else None
                        )
                    )
                    break

        if not pk_column:
            # Fall back to dataset profile PK candidates
            pk_candidates = (dataset.profile_json or {}).get(
                "primary_key_candidates", []
            )
            if pk_candidates:
                best = sorted(
                    pk_candidates,
                    key=lambda p: {"high": 0, "medium": 1, "low": 2}.get(
                        p.get("confidence", "low"), 3
                    ),
                )[0]
                pk_column = best["column"]
            else:
                issues.append({
                    "code": "no_primary_key",
                    "severity": "error",
                    "draft_id": ot.id,
                    "object_type": api_name,
                    "message": f"Cannot determine primary key column for "
                               f"Object Type '{api_name}'.",
                })
                continue

        # Build property_mappings from accepted property drafts
        # that belong to this object type
        property_mappings: dict[str, str] = {}
        for prop in prop_drafts:
            prop_ot = (prop.payload or {}).get("object_type")
            if prop_ot != api_name:
                continue
            prop_api_name = (prop.payload or {}).get("api_name")
            col_name = (
                (prop.payload or {}).get("property_name")
                or (
                    (prop.evidence_refs or [{}])[0].get("column")
                    if prop.evidence_refs else None
                )
            )
            if prop_api_name and col_name:
                property_mappings[prop_api_name] = col_name

        if not property_mappings:
            issues.append({
                "code": "no_property_mappings",
                "severity": "warning",
                "draft_id": ot.id,
                "object_type": api_name,
                "message": f"No property mappings for Object Type '{api_name}'.",
            })

        # Check idempotency: already exists for this package + object_type?
        existing_binding = db.scalar(
            select(OntologyDatasetBinding).where(
                OntologyDatasetBinding.package_id == pkg.id,
                OntologyDatasetBinding.object_type_api_name == api_name,
            )
        )
        if existing_binding is not None:
            existing += 1
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

    if created:
        db.commit()

    return {
        "created_count": created,
        "existing_count": existing,
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  query execution
# ═══════════════════════════════════════════════════════════════════════════

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_MAX_OFFSET = 10000


def execute_query(
    db: Session,
    group_id: str,
    project_id: str,
    object_type: str,
    fields: list[str] | None = None,
    filters: dict[str, str] | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
    explain_only: bool = False,
) -> dict:
    """Execute a read-only query against a bound dataset Object Type.

    Args:
        db: Database session.
        group_id: Authorized group.
        project_id: Project within the group.
        object_type: The api_name of the Object Type to query.
        fields: Optional whitelist of property api_names to return.
        filters: Optional {property_api_name: value} for equality filtering.
        limit: Max rows to return (1–100, default 20).
        offset: Rows to skip (0–10000).
        explain_only: If True, return explain info without data rows.

    Returns:
        dict with rows, row_count, explain, and error fields.

    Raises:
        ValueError: On invalid parameters or execution errors.
    """
    # ── Validate parameters ───────────────────────────────────────────────
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, min(offset, _MAX_OFFSET))

    # ── Find the latest package and active binding ────────────────────────
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        raise ValueError("No project package found for this project")

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
        raise ValueError(
            f"No active binding for Object Type '{object_type}' "
            f"in the latest package"
        )

    # ── Validate dataset ──────────────────────────────────────────────────
    dataset = db.get(DatasetAsset, binding.dataset_id)
    if dataset is None or dataset.status not in ("ready",):
        raise ValueError(
            f"Bound dataset not found or not ready (status: "
            f"{getattr(dataset, 'status', 'unknown')})"
        )
    if dataset.group_id != group_id or dataset.project_id != project_id:
        raise ValueError("Bound dataset does not belong to this project")

    # Load accepted property drafts to get value_types
    source_ids = pkg.source_draft_ids or []
    accepted_props = db.scalars(
        select(OntologyModelingDraft).where(
            OntologyModelingDraft.id.in_(source_ids),
            OntologyModelingDraft.status == "accepted",
            OntologyModelingDraft.draft_type == "property",
            OntologyModelingDraft.group_id == group_id,
        )
    ).all()

    # Build api_name → value_type map from property drafts
    value_types: dict[str, str] = {}
    for prop in accepted_props:
        p_api = (prop.payload or {}).get("api_name")
        p_vt = (prop.payload or {}).get("value_type", "string")
        if p_api:
            value_types[p_api] = p_vt

    # ── Build field whitelist ─────────────────────────────────────────────
    # All bound property api_names
    all_bound_fields = set(binding.property_mappings.keys())
    if fields:
        # Validate all requested fields are bound
        invalid = [f for f in fields if f not in all_bound_fields]
        if invalid:
            raise ValueError(
                f"Fields not in contract binding: {', '.join(invalid)}"
            )
        selected_fields = fields
    else:
        selected_fields = sorted(all_bound_fields)

    # ── Validate filter fields ────────────────────────────────────────────
    if filters:
        for fname in filters:
            if fname not in all_bound_fields:
                raise ValueError(
                    f"Filter field '{fname}' is not a bound property"
                )

    # ── Resolve and validate file path ────────────────────────────────────
    file_path = _validate_dataset_path(
        dataset.storage_path, group_id, project_id,
    )

    if not file_path.exists():
        raise ValueError("Dataset file not found on disk")

    # ── Build explain/provenance info ─────────────────────────────────────
    contract_info = (pkg.contract_json or {}).get("object_types", [])
    semantic_hash = ""
    for ot in contract_info:
        if isinstance(ot, dict) and ot.get("api_name") == object_type:
            semantic_hash = ot.get("semantic_hash", "")
            break

    explain = {
        "package_id": pkg.id,
        "package_version": pkg.version,
        "package_semantic_hash": semantic_hash or pkg.content_hash,
        "binding_id": binding.id,
        "dataset_id": dataset.id,
        "dataset_content_hash": dataset.content_hash,
        "object_type": object_type,
        "selected_fields": selected_fields,
        "filter_fields": sorted(filters.keys()) if filters else [],
        "limit": limit,
        "offset": offset,
    }

    if explain_only:
        return {"rows": [], "row_count": None, "explain": explain}

    # ── Read data file ────────────────────────────────────────────────────
    header, data_rows = _read_rows(
        str(file_path), dataset.file_format,
        max_rows=limit, offset=offset,
    )

    # Build column name → position index
    col_index: dict[str, int] = {name: i for i, name in enumerate(header)}

    # ── Map rows through binding ──────────────────────────────────────────
    results: list[dict] = []
    type_errors: list[dict] = []
    row_index = offset

    for row in data_rows:
        mapped: dict[str, Any] = {}
        row_has_error = False

        for prop_api_name in selected_fields:
            col_name = binding.property_mappings.get(prop_api_name)
            if col_name is None or col_name not in col_index:
                mapped[prop_api_name] = None
                continue

            raw_val = row[col_index[col_name]]
            value_type = value_types.get(prop_api_name, "string")

            try:
                converted = _convert_value(raw_val, value_type, prop_api_name)
                mapped[prop_api_name] = converted
            except ValueError as exc:
                type_errors.append({
                    "row": row_index,
                    "field": prop_api_name,
                    "value_type": value_type,
                    "raw_value": raw_val,
                    "error": str(exc),
                })
                row_has_error = True
                mapped[prop_api_name] = None

        # ── Apply equality filters ────────────────────────────────────────
        if filters and not row_has_error:
            skip = False
            for fname, fval in filters.items():
                col_name = binding.property_mappings.get(fname)
                if col_name is None or col_name not in col_index:
                    skip = True
                    break
                raw_val = row[col_index[col_name]]
                if raw_val is None or raw_val.strip() != fval:
                    skip = True
                    break
            if skip:
                row_index += 1
                continue

        results.append(mapped)
        row_index += 1

    # ── Build response ────────────────────────────────────────────────────
    response: dict = {
        "rows": results,
        "row_count": len(results),
        "explain": explain,
    }

    if type_errors:
        # Fail fast: if any row had type conversion errors, report them
        response["type_errors"] = type_errors
        response["row_count"] = None  # Don't return partial data

    return response


# ═══════════════════════════════════════════════════════════════════════════
#  pilot activation
# ═══════════════════════════════════════════════════════════════════════════


def activate_pilot(
    db: Session,
    group_id: str,
    project_id: str,
    user_id: str,
) -> dict:
    """Activate the pilot stage for a project.

    Requirements:
    - Project must be at validate or pilot stage.
    - Latest project package must exist.
    - All Object Types from datasets must have complete, valid bindings.
    - Datasets must be ready with at least one row.
    - Smoke query must succeed for each binding.

    Idempotent: calling on an already-pilot project succeeds with no change.
    """
    from semantic_lighthouse.services.projects import advance_stage

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise ValueError("Project not found")

    if project.status != "active":
        raise ValueError("Project is archived")

    if project.stage not in ("validate", "pilot"):
        raise ValueError(
            f"Project must be at validate or pilot stage, "
            f"currently: {project.stage}"
        )

    # Already pilot → idempotent
    if project.stage == "pilot":
        return {
            "activated": False,
            "already_pilot": True,
            "stage": "pilot",
            "issues": [],
        }

    # ── Get latest package ────────────────────────────────────────────────
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        raise ValueError("No project package found")

    # ── Get accepted object type drafts ───────────────────────────────────
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

    # Find Object Types that came from datasets (have source_dataset_id)
    dataset_ots = [ot for ot in accepted_ots if ot.source_dataset_id]
    if not dataset_ots:
        raise ValueError(
            "No dataset-grounded Object Types found in the package. "
            "Only dataset-grounded Object Types can have bindings."
        )

    # ── Verify each dataset Object Type has a binding ─────────────────────
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

        # Verify dataset is ready
        dataset = db.get(DatasetAsset, ds_id)
        if dataset is None or dataset.status != "ready":
            issues.append({
                "code": "dataset_not_ready",
                "severity": "error",
                "object_type": api_name,
                "dataset_id": ds_id,
                "message": f"Dataset not ready for Object Type '{api_name}'.",
            })
            continue

        if dataset.row_count < 1:
            issues.append({
                "code": "empty_dataset",
                "severity": "error",
                "object_type": api_name,
                "dataset_id": ds_id,
                "message": f"Dataset for '{api_name}' has zero rows.",
            })
            continue

        # ── Smoke query: read one row ─────────────────────────────────────
        try:
            file_path = _validate_dataset_path(
                dataset.storage_path, group_id, project_id,
            )
            if not file_path.exists():
                issues.append({
                    "code": "dataset_file_missing",
                    "severity": "error",
                    "object_type": api_name,
                    "message": "Dataset file not found on disk.",
                })
                continue

            header, data_rows = _read_rows(
                str(file_path), dataset.file_format,
                max_rows=1, offset=0,
            )
            if not data_rows:
                issues.append({
                    "code": "no_data_rows",
                    "severity": "error",
                    "object_type": api_name,
                    "message": "Dataset has header but no data rows.",
                })
                continue

            # Verify the PK column exists in the file header
            pk_col = binding.primary_key_column
            if pk_col not in header:
                issues.append({
                    "code": "pk_column_missing",
                    "severity": "error",
                    "object_type": api_name,
                    "column": pk_col,
                    "message": f"Primary key column '{pk_col}' not found "
                               f"in dataset file.",
                })
                continue

        except Exception as exc:
            issues.append({
                "code": "smoke_query_failed",
                "severity": "error",
                "object_type": api_name,
                "message": str(exc),
            })
            continue

    if issues:
        return {
            "activated": False,
            "already_pilot": False,
            "stage": "validate",
            "issues": issues,
        }

    # ── All gates passed: advance to pilot ────────────────────────────────
    advance_stage("validate", "pilot")
    project.stage = "pilot"
    db.commit()

    return {
        "activated": True,
        "already_pilot": False,
        "stage": "pilot",
        "issues": [],
    }
