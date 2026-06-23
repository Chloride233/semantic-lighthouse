"""Runtime relationship traversal core: single-hop hash join over CSV/XLSX.

R2C: service-level only. No router, no endpoint, no audit, no migration.
Uses compiled link_map from _build_contract_context for FK/PK resolution.
Single-hop only: path must contain exactly 2 object_types.

Query semantics: stream source -> filter -> for each matching row, look up
FK value in an in-memory target index -> produce flat joined rows with the
{object_type}__{field} prefix.

No SQL, no DSL, no AST, no LLM, no Graph RAG, no writes.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import get_settings
from semantic_lighthouse.models import DatasetAsset, OntologyDatasetBinding
from semantic_lighthouse.services.runtime_contract import (
    _build_contract_context,
    _get_latest_project_package,
)
from semantic_lighthouse.services.runtime_dataset_io import (
    _read_dataset_rows,
    _validate_dataset_path,
)
from semantic_lighthouse.services.runtime_query import (
    _convert_filter_value,
    _convert_value,
    _DEFAULT_LIMIT,
    _MAX_LIMIT,
    _MAX_OFFSET,
)


_MAX_PATH_LENGTH = 2


def execute_traversal(
    db: Session,
    group_id: str,
    project_id: str,
    path: list[str],
    user_id: str,
    fields: dict[str, list[str]] | None = None,
    filters: dict[str, str | int | float | bool | None] | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
    explain_only: bool = False,
) -> dict:
    """Execute a single-hop relationship traversal over two bound datasets."""
    if len(path) != _MAX_PATH_LENGTH:
        raise ValueError(
            f"Traversal path must have exactly {_MAX_PATH_LENGTH} "
            f"object_types, got {len(path)}"
        )

    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, min(offset, _MAX_OFFSET))

    source_ot, target_ot = path
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        raise ValueError("No project package found for this project")

    try:
        ctx = _build_contract_context(pkg)
    except Exception:
        raise ValueError("Business contract compilation failed") from None

    link = _resolve_link(ctx, source_ot, target_ot)
    source_fk = link.get("source_fk_property", "")
    target_pk = link.get("target_pk_property", "")
    if not source_fk:
        raise ValueError(
            f"Link type '{link.get('api_name', '?')}' has no "
            "source_fk_property; cannot resolve FK column"
        )
    if not target_pk:
        raise ValueError(
            f"Link type '{link.get('api_name', '?')}' has no "
            "target_pk_property and target OT has no primary_key"
        )

    source_binding = _resolve_binding(db, pkg.id, group_id, project_id, source_ot)
    target_binding = _resolve_binding(db, pkg.id, group_id, project_id, target_ot)

    fields_by_ot = ctx.get("fields_by_ot", {})
    prop_map = ctx.get("prop_map", {})
    source_fields = _validate_ot_fields(
        source_ot,
        fields.get(source_ot) if fields else None,
        source_binding,
        fields_by_ot,
    )
    target_fields = _validate_ot_fields(
        target_ot,
        fields.get(target_ot) if fields else None,
        target_binding,
        fields_by_ot,
    )

    filter_field_names, converted_filters = _validate_root_filters(
        filters,
        source_ot,
        source_binding,
        fields_by_ot,
        prop_map,
    )

    source_fk_col = source_binding.property_mappings.get(source_fk)
    if source_fk_col is None:
        raise ValueError(
            f"source_fk_property '{source_fk}' is not in binding "
            f"property_mappings for '{source_ot}'"
        )
    target_pk_col = target_binding.property_mappings.get(target_pk)
    if target_pk_col is None:
        raise ValueError(
            f"target_pk_property '{target_pk}' is not in binding "
            f"property_mappings for '{target_ot}'"
        )

    source_dataset, source_file = _resolve_dataset_and_path(
        db, source_binding, group_id, project_id, source_ot
    )
    target_dataset, target_file = _resolve_dataset_and_path(
        db, target_binding, group_id, project_id, target_ot
    )

    explain: dict[str, Any] = {
        "package_id": pkg.id,
        "package_version": pkg.version,
        "package_semantic_hash": ctx["semantic_hash"],
        "path": path,
        "hops": [
            {
                "hop_index": 0,
                "link_type_api_name": link.get("api_name", ""),
                "source_object_type": source_ot,
                "target_object_type": target_ot,
                "cardinality": link.get("cardinality", ""),
                "source_binding_id": source_binding.id,
                "target_binding_id": target_binding.id,
                "source_dataset_id": source_dataset.id,
                "target_dataset_id": target_dataset.id,
                "source_fk_property": source_fk,
                "target_pk_property": target_pk,
                "source_fk_column": source_fk_col,
                "target_pk_column": target_pk_col,
            }
        ],
        "selected_fields_by_ot": {
            source_ot: source_fields,
            target_ot: target_fields,
        },
        "filter_field_names_by_ot": {source_ot: filter_field_names},
        "limit": limit,
        "offset": offset,
    }

    if explain_only:
        return {"rows": [], "row_count": None, "explain": explain}

    settings = get_settings()
    scan_limit = settings.dataset_max_scan_rows

    try:
        source_header, source_rows, source_scanned, source_truncated = (
            _read_dataset_rows(
                source_file, source_dataset.file_format, max_rows=scan_limit
            )
        )
    except Exception:
        raise ValueError(f"Failed to read source dataset for '{source_ot}'") from None

    try:
        target_header, target_rows, target_scanned, target_truncated = (
            _read_dataset_rows(
                target_file, target_dataset.file_format, max_rows=scan_limit
            )
        )
    except Exception:
        raise ValueError(f"Failed to read target dataset for '{target_ot}'") from None

    source_col_idx = {name: i for i, name in enumerate(source_header)}
    target_col_idx = {name: i for i, name in enumerate(target_header)}
    if source_fk_col not in source_col_idx:
        raise ValueError(
            f"FK column '{source_fk_col}' not found in source dataset "
            f"'{source_ot}'"
        )
    if target_pk_col not in target_col_idx:
        raise ValueError(
            f"PK column '{target_pk_col}' not found in target dataset "
            f"'{target_ot}'"
        )

    target_index, target_type_errors = _build_target_index(
        target_rows,
        target_col_idx,
        target_pk_col,
        target_pk,
        target_fields,
        target_binding,
        target_ot,
        prop_map,
    )
    matched, source_type_errors = _join_source_rows(
        source_rows,
        source_col_idx,
        source_fk_col,
        source_fk,
        source_fields,
        source_binding,
        source_ot,
        target_ot,
        target_index,
        converted_filters,
        filter_field_names,
        prop_map,
    )

    paged = matched[offset : offset + limit]
    explain["scanned_rows"] = {
        source_ot: source_scanned,
        target_ot: target_scanned,
    }
    explain["scan_limit"] = scan_limit
    explain["scan_truncated"] = {
        source_ot: source_truncated,
        target_ot: target_truncated,
    }
    explain["matched_before_paging"] = len(matched)

    response: dict[str, Any] = {
        "rows": paged,
        "row_count": len(paged),
        "explain": explain,
    }

    type_errors = source_type_errors + target_type_errors
    if type_errors:
        response["type_errors"] = type_errors
        response["row_count"] = None

    return response


def _resolve_link(ctx: dict, source_ot: str, target_ot: str) -> dict:
    link_map = ctx.get("link_map", {})
    if not link_map:
        raise ValueError("Package has no link_types in compiled contract")

    matching_links = [
        link
        for link in link_map.values()
        if link.get("source_object_type") == source_ot
        and link.get("target_object_type") == target_ot
    ]
    if not matching_links:
        raise ValueError(f"No link_type connects '{source_ot}' -> '{target_ot}'")
    if len(matching_links) > 1:
        raise ValueError(
            "Ambiguous: multiple link_types connect "
            f"'{source_ot}' -> '{target_ot}'"
        )
    return matching_links[0]


def _resolve_binding(
    db: Session,
    package_id: str,
    group_id: str,
    project_id: str,
    object_type: str,
) -> OntologyDatasetBinding:
    binding = db.scalar(
        select(OntologyDatasetBinding).where(
            OntologyDatasetBinding.package_id == package_id,
            OntologyDatasetBinding.object_type_api_name == object_type,
            OntologyDatasetBinding.status == "active",
            OntologyDatasetBinding.group_id == group_id,
            OntologyDatasetBinding.project_id == project_id,
        )
    )
    if binding is None:
        raise ValueError(f"No active binding for Object Type '{object_type}'")
    return binding


def _validate_ot_fields(
    object_type: str,
    requested: list[str] | None,
    binding: OntologyDatasetBinding,
    fields_by_ot: dict,
) -> list[str]:
    contract_fields = set(fields_by_ot.get(object_type, []))
    bound_fields = set(binding.property_mappings.keys())
    valid_fields = contract_fields & bound_fields
    if not valid_fields:
        raise ValueError(f"No valid fields for Object Type '{object_type}'")
    if requested:
        invalid = [field for field in requested if field not in valid_fields]
        if invalid:
            raise ValueError(
                f"Fields not in contract for '{object_type}': "
                f"{', '.join(invalid)}"
            )
        return requested
    return sorted(valid_fields)


def _validate_root_filters(
    filters: dict[str, str | int | float | bool | None] | None,
    source_ot: str,
    source_binding: OntologyDatasetBinding,
    fields_by_ot: dict,
    prop_map: dict,
) -> tuple[list[str], dict[str, Any]]:
    filter_field_names: list[str] = []
    converted_filters: dict[str, Any] = {}
    if not filters:
        return filter_field_names, converted_filters

    valid_fields = set(fields_by_ot.get(source_ot, [])) & set(
        source_binding.property_mappings.keys()
    )
    for field_name, raw_value in filters.items():
        if field_name not in valid_fields:
            raise ValueError(
                f"Filter field '{field_name}' is not a bound property "
                f"of '{source_ot}'"
            )
        value_type = prop_map.get(field_name, {}).get("value_type", "string")
        try:
            converted_filters[field_name] = _convert_filter_value(
                raw_value, value_type, field_name
            )
        except ValueError:
            raise ValueError(
                f"Filter value for '{field_name}' cannot be converted "
                f"to {value_type}"
            ) from None
        filter_field_names.append(field_name)

    return filter_field_names, converted_filters


def _resolve_dataset_and_path(
    db: Session,
    binding: OntologyDatasetBinding,
    group_id: str,
    project_id: str,
    object_type: str,
) -> tuple[DatasetAsset, str]:
    dataset = db.get(DatasetAsset, binding.dataset_id)
    if dataset is None or dataset.status != "ready":
        raise ValueError(f"Dataset for '{object_type}' not found or not ready")
    if dataset.group_id != group_id or dataset.project_id != project_id:
        raise ValueError(f"Dataset for '{object_type}' does not belong to this project")
    try:
        file_path = str(_validate_dataset_path(dataset.storage_path, group_id, project_id))
    except ValueError:
        raise ValueError(f"Dataset path validation failed for '{object_type}'") from None
    return dataset, file_path


def _build_target_index(
    target_rows: list[list[str | None]],
    target_col_idx: dict[str, int],
    target_pk_col: str,
    target_pk: str,
    target_fields: list[str],
    target_binding: OntologyDatasetBinding,
    target_ot: str,
    prop_map: dict,
) -> tuple[dict[Any, list[dict[str, Any]]], list[dict]]:
    target_index: dict[Any, list[dict[str, Any]]] = {}
    type_errors: list[dict] = []
    pk_col_idx = target_col_idx[target_pk_col]
    pk_value_type = prop_map.get(target_pk, {}).get("value_type", "string")

    for row in target_rows:
        try:
            pk_value = _convert_value(row[pk_col_idx], pk_value_type, target_pk)
        except ValueError:
            continue

        converted, row_ok = _convert_row_fields(
            row, target_col_idx, target_fields, target_binding, target_ot, prop_map
        )
        if not row_ok:
            type_errors.extend(
                _type_error(target_ot, field, prop_map)
                for field, value in converted.items()
                if value is None
            )
            continue
        target_index.setdefault(pk_value, []).append(converted)

    return target_index, type_errors


def _join_source_rows(
    source_rows: list[list[str | None]],
    source_col_idx: dict[str, int],
    source_fk_col: str,
    source_fk: str,
    source_fields: list[str],
    source_binding: OntologyDatasetBinding,
    source_ot: str,
    target_ot: str,
    target_index: dict[Any, list[dict[str, Any]]],
    converted_filters: dict[str, Any],
    filter_field_names: list[str],
    prop_map: dict,
) -> tuple[list[dict[str, Any]], list[dict]]:
    matched: list[dict[str, Any]] = []
    type_errors: list[dict] = []
    fk_col_idx = source_col_idx[source_fk_col]
    fk_value_type = prop_map.get(source_fk, {}).get("value_type", "string")
    internal_fields = sorted(set(source_fields) | set(filter_field_names))

    for row in source_rows:
        converted, row_ok = _convert_row_fields(
            row, source_col_idx, internal_fields, source_binding, source_ot, prop_map
        )
        if not row_ok:
            type_errors.extend(
                _type_error(source_ot, field, prop_map)
                for field, value in converted.items()
                if value is None
            )
            continue

        if any(converted.get(field) != value for field, value in converted_filters.items()):
            continue

        try:
            fk_value = _convert_value(row[fk_col_idx], fk_value_type, source_fk)
        except ValueError:
            continue

        for target_row in target_index.get(fk_value, []):
            flat: dict[str, Any] = {
                f"{source_ot}__{field}": converted[field]
                for field in source_fields
                if field in converted
            }
            flat.update(
                {
                    f"{target_ot}__{field}": value
                    for field, value in target_row.items()
                }
            )
            matched.append(flat)

    return matched, type_errors


def _convert_row_fields(
    row: list[str | None],
    col_idx: dict[str, int],
    fields: list[str],
    binding: OntologyDatasetBinding,
    object_type: str,
    prop_map: dict,
) -> tuple[dict[str, Any], bool]:
    converted: dict[str, Any] = {}
    row_ok = True
    for field in fields:
        col = binding.property_mappings.get(field)
        if col is None or col not in col_idx:
            converted[field] = None
            continue
        value_type = prop_map.get(field, {}).get("value_type", "string")
        try:
            converted[field] = _convert_value(row[col_idx[col]], value_type, field)
        except ValueError:
            converted[field] = None
            row_ok = False
    return converted, row_ok


def _type_error(object_type: str, field: str, prop_map: dict) -> dict:
    return {
        "object_type": object_type,
        "field": field,
        "value_type": prop_map.get(field, {}).get("value_type", "string"),
    }
