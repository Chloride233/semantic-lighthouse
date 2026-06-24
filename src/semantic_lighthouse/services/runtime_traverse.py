"""Runtime relationship traversal core: hash join over CSV/XLSX.

R2C-R2F: service-level traversal supporting 1-2 hops (path length 2 or 3).
Uses compiled link_map from _build_contract_context for FK/PK resolution.
Multi-hop chains hash joins: each hop builds a PK index on the target dataset,
then joins source rows via FK -> PK lookup. Flat output with {ot}__{field} prefix.

No SQL, no DSL, no AST, no LLM, no Graph RAG, no writes.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import get_settings
from semantic_lighthouse.models import DatasetAsset, OntologyDatasetBinding
from semantic_lighthouse.services.runtime_audit import _record_audit, _sanitized_code
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


_MAX_PATH_LENGTH = 3


def execute_traversal(
    db: Session,
    group_id: str,
    project_id: str,
    path: list[str],
    user_id: str,
    fields: dict[str, list[str]] | None = None,
    filters: dict[str, dict[str, str | int | float | bool | None]] | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
    explain_only: bool = False,
    response_shape: str = "flat",
    direction: str = "forward",
) -> dict:
    """Execute a 1-2 hop relationship traversal over bound datasets.

    direction: "forward" follows link_type source→target (default);
               "reverse" traverses the same link_type target→source.
    """
    if direction not in ("forward", "reverse"):
        raise ValueError(
            f"direction must be 'forward' or 'reverse', got '{direction}'"
        )

    path_len = len(path)
    if path_len < 2 or path_len > _MAX_PATH_LENGTH:
        summary = (
            f"Traversal path must have 2-{_MAX_PATH_LENGTH} "
            f"object_types, got {path_len}"
        )
        _record_audit(
            db,
            user_id=user_id,
            group_id=group_id,
            project_id=project_id,
            operation="traverse",
            limit_val=max(1, min(limit, _MAX_LIMIT)),
            offset_val=max(0, min(offset, _MAX_OFFSET)),
            outcome="failure",
            error_code=_sanitized_code("max_path_length_exceeded"),
            error_summary=summary,
            path=path,
            hop_count=max(0, path_len - 1),
        )
        db.commit()
        raise ValueError(summary)

    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, min(offset, _MAX_OFFSET))

    # Audit base.
    audit_base: dict = {
        "user_id": user_id,
        "group_id": group_id,
        "project_id": project_id,
        "operation": "traverse",
        "limit_val": limit,
        "offset_val": offset,
        "path": path,
        "hop_count": len(path) - 1,
    }
    # Collected as we resolve (may be partial on failure)
    audit_link_type_api_names: list[str] = []
    audit_binding_ids: list[str] = []
    audit_dataset_ids: list[str] = []

    def _fail(code: str, summary: str) -> dict:
        _record_audit(
            db,
            **audit_base,
            outcome="failure",
            error_code=_sanitized_code(code),
            error_summary=summary,
            link_type_api_names=audit_link_type_api_names or None,
            binding_ids=audit_binding_ids or None,
            dataset_ids=audit_dataset_ids or None,
        )
        db.commit()
        raise ValueError(summary)

    # Shared: package + contract context (used by both paths).
    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        return _fail("no_package",
                      "No project package found for this project")

    try:
        ctx = _build_contract_context(pkg)
    except Exception:
        return _fail("contract_compilation",
                      "Business contract compilation failed")

    fields_by_ot = ctx.get("fields_by_ot", {})
    prop_map = ctx.get("prop_map", {})

    if path_len == 2:
        # Single-hop path (R2C-R2E).


        source_ot, target_ot = path

        # Link resolution.
        try:
            link = _resolve_link(ctx, source_ot, target_ot, direction)
        except ValueError as exc:
            msg = str(exc)
            code = (
                "ambiguous_link_type"
                if "ambiguous" in msg.lower()
                else "no_link_type"
            )
            return _fail(code, msg)

        audit_link_type_api_names.append(link.get("api_name", ""))

        if direction == "forward":
            source_fk = link.get("source_fk_property", "")
            target_pk = link.get("target_pk_property", "")
        else:
            source_fk = link.get("target_pk_property", "")
            target_pk = link.get("source_fk_property", "")
        if not source_fk:
            return _fail(
                "fk_property_not_in_contract",
                f"Link type '{link.get('api_name', '?')}' has no "
                "source_fk_property; cannot resolve FK column",
            )
        if not target_pk:
            return _fail(
                "fk_property_not_in_contract",
                f"Link type '{link.get('api_name', '?')}' has no "
                "target_pk_property and target OT has no primary_key",
            )

        # Bindings.
        try:
            source_binding = _resolve_binding(db, pkg.id, group_id, project_id, source_ot)
        except ValueError as exc:
            return _fail("no_binding_for_hop", str(exc))
        try:
            target_binding = _resolve_binding(db, pkg.id, group_id, project_id, target_ot)
        except ValueError as exc:
            return _fail("no_binding_for_hop", str(exc))

        audit_binding_ids.extend([source_binding.id, target_binding.id])

        # Field validation.
        try:
            source_fields = _validate_ot_fields(
                source_ot,
                fields.get(source_ot) if fields else None,
                source_binding,
                fields_by_ot,
            )
        except ValueError as exc:
            return _fail("invalid_fields", str(exc))
        try:
            target_fields = _validate_ot_fields(
                target_ot,
                fields.get(target_ot) if fields else None,
                target_binding,
                fields_by_ot,
            )
        except ValueError as exc:
            return _fail("invalid_fields", str(exc))

        # Filter validation — per-OT (R3C pushdown).
        all_filter_names: dict[str, list[str]] = {}
        all_converted_filters: dict[str, dict[str, Any]] = {}
        if filters:
            for ot_name in path:
                ot_filters = filters.get(ot_name)
                if not ot_filters:
                    continue
                ot_binding = source_binding if ot_name == source_ot else target_binding
                try:
                    fnames, fconverted = _prepare_ot_filters(
                        ot_name, ot_filters, ot_binding, fields_by_ot, prop_map,
                    )
                except ValueError as exc:
                    code = "type_conversion" if "cannot be converted" in str(exc).lower() else "invalid_filter"
                    return _fail(code, str(exc))
                if fnames:
                    all_filter_names[ot_name] = fnames
                    all_converted_filters[ot_name] = fconverted
        root_converted = all_converted_filters.get(source_ot, {})
        root_filter_names = all_filter_names.get(source_ot, [])

        # Column resolution.
        source_fk_col = source_binding.property_mappings.get(source_fk)
        if source_fk_col is None:
            return _fail(
                "fk_property_not_in_contract",
                f"source_fk_property '{source_fk}' is not in binding "
                f"property_mappings for '{source_ot}'",
            )
        target_pk_col = target_binding.property_mappings.get(target_pk)
        if target_pk_col is None:
            return _fail(
                "fk_property_not_in_contract",
                f"target_pk_property '{target_pk}' is not in binding "
                f"property_mappings for '{target_ot}'",
            )

        # Dataset resolution.
        try:
            source_dataset, source_file = _resolve_dataset_and_path(
                db, source_binding, group_id, project_id, source_ot,
            )
        except ValueError as exc:
            code = "cross_package_traversal" if "does not belong" in str(exc).lower() else "dataset_not_ready"
            return _fail(code, str(exc))
        try:
            target_dataset, target_file = _resolve_dataset_and_path(
                db, target_binding, group_id, project_id, target_ot,
            )
        except ValueError as exc:
            code = "cross_package_traversal" if "does not belong" in str(exc).lower() else "dataset_not_ready"
            return _fail(code, str(exc))

        audit_dataset_ids.extend([source_dataset.id, target_dataset.id])

        # Build explain metadata. No data values, no paths.
        audit_field_names = [
            f"{source_ot}__{f}" for f in source_fields
        ] + [
            f"{target_ot}__{f}" for f in target_fields
        ]
        audit_filter_names: list[str] = []
        for ot_name, fnames in all_filter_names.items():
            audit_filter_names.extend(f"{ot_name}__{f}" for f in fnames)

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
            "filter_field_names_by_ot": all_filter_names,
            "limit": limit,
            "offset": offset,
            "response_shape": response_shape,
            "direction": direction,
        }

        if explain_only:
            _record_audit(
                db,
                **audit_base,
                field_names=audit_field_names,
                filter_field_names=audit_filter_names,
                link_type_api_names=audit_link_type_api_names,
                binding_ids=audit_binding_ids,
                dataset_ids=audit_dataset_ids,
                outcome="success",
                row_count=0,
            )
            db.commit()
            return {"rows": [], "row_count": None, "explain": explain}

        # Read datasets.
        settings = get_settings()
        scan_limit = settings.dataset_max_scan_rows

        try:
            source_header, source_rows, source_scanned, source_truncated = (
                _read_dataset_rows(
                    source_file, source_dataset.file_format, max_rows=scan_limit,
                )
            )
        except Exception:
            return _fail("read_error",
                          f"Failed to read source dataset for '{source_ot}'")
        try:
            target_header, target_rows, target_scanned, target_truncated = (
                _read_dataset_rows(
                    target_file, target_dataset.file_format, max_rows=scan_limit,
                )
            )
        except Exception:
            return _fail("read_error",
                          f"Failed to read target dataset for '{target_ot}'")

        source_col_idx = {name: i for i, name in enumerate(source_header)}
        target_col_idx = {name: i for i, name in enumerate(target_header)}
        if source_fk_col not in source_col_idx:
            return _fail(
                "no_matching_column",
                f"FK column '{source_fk_col}' not found in source dataset "
                f"'{source_ot}'",
            )
        if target_pk_col not in target_col_idx:
            return _fail(
                "no_matching_column",
                f"PK column '{target_pk_col}' not found in target dataset "
                f"'{target_ot}'",
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
            root_converted,
            root_filter_names,
            prop_map,
        )

        # Apply target-OT filters (R3C pushdown).
        target_converted = all_converted_filters.get(target_ot, {})
        if target_converted:
            matched = _apply_flat_filters(matched, target_ot, target_converted)

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

        # Grouped response shape: nest children under root OT.
        rows: list[dict] = paged
        audit_row_count = len(paged)
        if response_shape == "grouped" and paged:
            child_cardinality = link.get("cardinality", "one_to_many")
            if direction == "reverse":
                child_cardinality = _reverse_cardinality(child_cardinality)
            rows = _group_flat_rows(
                paged, path,
                [source_fields, target_fields],
                [child_cardinality],
            )
            audit_row_count = len(rows)

        response: dict[str, Any] = {
            "rows": rows,
            "row_count": audit_row_count,
            "explain": explain,
        }

        type_errors = source_type_errors + target_type_errors
        if type_errors:
            response["type_errors"] = type_errors
            response["row_count"] = None

        # Audit must succeed before returning.
        final_outcome = (
            "failure" if type_errors
            else "empty" if audit_row_count == 0
            else "success"
        )
        _record_audit(
            db,
            **audit_base,
            field_names=audit_field_names,
            filter_field_names=audit_filter_names,
            link_type_api_names=audit_link_type_api_names,
            binding_ids=audit_binding_ids,
            dataset_ids=audit_dataset_ids,
            outcome=final_outcome,
            row_count=audit_row_count if not type_errors else None,
            error_code=_sanitized_code("type_conversion") if type_errors else None,
            error_summary=(
                f"{len(type_errors)} type conversion error(s)"
                if type_errors else None
            ),
        )
        db.commit()

        return response

    # Two-hop path (R2F): chain OT0 -> OT1 -> OT2.


    ots = path  # [ot0, ot1, ot2]
    hops_pairs = [(ots[0], ots[1]), (ots[1], ots[2])]

    # Resolve links for both hops.
    links: list[dict] = []
    for src_ot, tgt_ot in hops_pairs:
        try:
            lk = _resolve_link(ctx, src_ot, tgt_ot, direction)
        except ValueError as exc:
            msg = str(exc)
            code = "ambiguous_link_type" if "ambiguous" in msg.lower() else "no_link_type"
            return _fail(code, msg)
        if direction == "forward":
            if not lk.get("source_fk_property"):
                return _fail("fk_property_not_in_contract",
                             f"Link '{lk.get('api_name', '?')}' has no source_fk_property")
            if not lk.get("target_pk_property"):
                return _fail("fk_property_not_in_contract",
                             f"Link '{lk.get('api_name', '?')}' has no target_pk_property")
        else:
            if not lk.get("target_pk_property"):
                return _fail("fk_property_not_in_contract",
                             f"Link '{lk.get('api_name', '?')}' has no target_pk_property "
                             "(needed as FK in reverse)")
            if not lk.get("source_fk_property"):
                return _fail("fk_property_not_in_contract",
                             f"Link '{lk.get('api_name', '?')}' has no source_fk_property "
                             "(needed as PK in reverse)")
        links.append(lk)

    audit_link_type_api_names.extend(lk.get("api_name", "") for lk in links)

    # Resolve bindings for all 3 OTs.
    bindings: list[OntologyDatasetBinding] = []
    for ot in ots:
        try:
            b = _resolve_binding(db, pkg.id, group_id, project_id, ot)
        except ValueError as exc:
            return _fail("no_binding_for_hop", str(exc))
        bindings.append(b)

    audit_binding_ids.extend(b.id for b in bindings)

    # Validate fields per OT.  For intermediate OT (ots[1]) we must include
    # the FK property of the *second* hop so it is available during the
    # flat-dict join.
    per_ot_fields: list[list[str]] = []
    for i, ot in enumerate(ots):
        requested = fields.get(ot) if fields else None
        index_fields = list(requested) if requested else None
        # Ensure the second-hop FK property is present in OT1's index fields
        if i == 1:
            fk2 = (
                links[1].get("source_fk_property", "")
                if direction == "forward"
                else links[1].get("target_pk_property", "")
            )
            if fk2 and (index_fields is None or fk2 not in index_fields):
                if index_fields is None:
                    # Compute all valid fields, then ensure FK is included
                    all_valid = _validate_ot_fields(ot, None, bindings[i], fields_by_ot)
                    index_fields = list(dict.fromkeys(all_valid + [fk2]))
                else:
                    index_fields = list(dict.fromkeys(index_fields + [fk2]))
        try:
            ot_fields = _validate_ot_fields(ot, index_fields, bindings[i], fields_by_ot)
        except ValueError as exc:
            return _fail("invalid_fields", str(exc))
        per_ot_fields.append(ot_fields)

    # The *output* fields strip the join-only FK from OT1 (if user didn't request it).
    output_fields: list[list[str]] = []
    for i, ot in enumerate(ots):
        requested = fields.get(ot) if fields else None
        if requested:
            output_fields.append([f for f in per_ot_fields[i] if f in requested])
        else:
            output_fields.append(list(per_ot_fields[i]))

    # Filters — validate for all OTs that have them (R3C pushdown).
    all_filter_names: dict[str, list[str]] = {}
    all_converted_filters: dict[str, dict[str, Any]] = {}
    if filters:
        for i, ot_name in enumerate(ots):
            ot_filters = filters.get(ot_name)
            if not ot_filters:
                continue
            try:
                fnames, fconverted = _prepare_ot_filters(
                    ot_name, ot_filters, bindings[i], fields_by_ot, prop_map,
                )
            except ValueError as exc:
                code = "type_conversion" if "cannot be converted" in str(exc).lower() else "invalid_filter"
                return _fail(code, str(exc))
            if fnames:
                all_filter_names[ot_name] = fnames
                all_converted_filters[ot_name] = fconverted
    root_converted = all_converted_filters.get(ots[0], {})
    root_filter_names = all_filter_names.get(ots[0], [])

    # FK/PK column resolution per hop.
    hop_fk_props: list[str] = []
    hop_pk_props: list[str] = []
    hop_fk_cols: list[str] = []
    hop_pk_cols: list[str] = []
    for i, lk in enumerate(links):
        if direction == "forward":
            src_fk = lk["source_fk_property"]
            tgt_pk = lk["target_pk_property"]
        else:
            src_fk = lk["target_pk_property"]
            tgt_pk = lk["source_fk_property"]
        fk_col = bindings[i].property_mappings.get(src_fk)
        pk_col = bindings[i + 1].property_mappings.get(tgt_pk)
        if fk_col is None:
            return _fail("fk_property_not_in_contract",
                         f"FK property '{src_fk}' not in binding for '{ots[i]}'")
        if pk_col is None:
            return _fail("fk_property_not_in_contract",
                         f"PK property '{tgt_pk}' not in binding for '{ots[i + 1]}'")
        hop_fk_props.append(src_fk)
        hop_pk_props.append(tgt_pk)
        hop_fk_cols.append(fk_col)
        hop_pk_cols.append(pk_col)

    # Resolve datasets for all 3 OTs.
    datasets: list[DatasetAsset] = []
    files: list[str] = []
    for i, ot in enumerate(ots):
        try:
            ds, fp = _resolve_dataset_and_path(db, bindings[i], group_id, project_id, ot)
        except ValueError as exc:
            code = "cross_package_traversal" if "does not belong" in str(exc).lower() else "dataset_not_ready"
            return _fail(code, str(exc))
        datasets.append(ds)
        files.append(fp)

    audit_dataset_ids.extend(d.id for d in datasets)

    # Build explain.
    explain_hops: list[dict] = []
    for i, lk in enumerate(links):
        explain_hops.append({
            "hop_index": i,
            "link_type_api_name": lk.get("api_name", ""),
            "source_object_type": ots[i],
            "target_object_type": ots[i + 1],
            "cardinality": lk.get("cardinality", ""),
            "source_binding_id": bindings[i].id,
            "target_binding_id": bindings[i + 1].id,
            "source_dataset_id": datasets[i].id,
            "target_dataset_id": datasets[i + 1].id,
            "source_fk_property": hop_fk_props[i],
            "target_pk_property": hop_pk_props[i],
            "source_fk_column": hop_fk_cols[i],
            "target_pk_column": hop_pk_cols[i],
        })

    # Flat prefixed audit field/filter names.
    audit_field_names = []
    for i, ot in enumerate(ots):
        audit_field_names.extend(f"{ot}__{f}" for f in output_fields[i])
    audit_filter_names: list[str] = []
    for ot_name, fnames in all_filter_names.items():
        audit_filter_names.extend(f"{ot_name}__{f}" for f in fnames)

    explain: dict[str, Any] = {
        "package_id": pkg.id,
        "package_version": pkg.version,
        "package_semantic_hash": ctx["semantic_hash"],
        "path": path,
        "hops": explain_hops,
        "selected_fields_by_ot": {
            ot: output_fields[i] for i, ot in enumerate(ots)
        },
        "filter_field_names_by_ot": all_filter_names,
        "limit": limit,
        "offset": offset,
        "response_shape": response_shape,
        "direction": direction,
    }

    if explain_only:
        _record_audit(
            db,
            **audit_base,
            field_names=audit_field_names,
            filter_field_names=audit_filter_names,
            link_type_api_names=audit_link_type_api_names,
            binding_ids=audit_binding_ids,
            dataset_ids=audit_dataset_ids,
            outcome="success",
            row_count=0,
        )
        db.commit()
        return {"rows": [], "row_count": None, "explain": explain}

    # Read all datasets.
    settings = get_settings()
    scan_limit = settings.dataset_max_scan_rows

    all_headers: list[list[str]] = []
    all_rows_raw: list[list[list[str | None]]] = []
    all_scanned: list[int] = []
    all_truncated: list[bool] = []
    all_type_errors: list[dict] = []

    for i, ot in enumerate(ots):
        try:
            hdr, rows, sc, tr = _read_dataset_rows(
                files[i], datasets[i].file_format, max_rows=scan_limit,
            )
        except Exception:
            return _fail("read_error",
                          f"Failed to read dataset for '{ot}'")
        all_headers.append(hdr)
        all_rows_raw.append(rows)
        all_scanned.append(sc)
        all_truncated.append(tr)

    # Column index helpers.
    col_indices = [{name: i for i, name in enumerate(hdr)} for hdr in all_headers]

    for i, (fk_col, ot) in enumerate(zip(hop_fk_cols, ots)):
        if fk_col not in col_indices[i]:
            return _fail("no_matching_column",
                         f"FK column '{fk_col}' not found in dataset for '{ot}'")
    for i, (pk_col, ot) in enumerate(zip(hop_pk_cols, ots[1:])):
        if pk_col not in col_indices[i + 1]:
            return _fail("no_matching_column",
                         f"PK column '{pk_col}' not found in dataset for '{ot}'")

    # Hop 0: build target index on OT1, join OT0 -> OT1 (raw rows).
    idx1, te1 = _build_target_index(
        all_rows_raw[1], col_indices[1],
        hop_pk_cols[0], hop_pk_props[0],
        per_ot_fields[1], bindings[1], ots[1], prop_map,
    )
    all_type_errors.extend(te1)

    intermediate, te0 = _join_source_rows(
        all_rows_raw[0], col_indices[0],
        hop_fk_cols[0], hop_fk_props[0],
        per_ot_fields[0], bindings[0], ots[0], ots[1],
        idx1, root_converted, root_filter_names, prop_map,
    )
    all_type_errors.extend(te0)

    # Apply OT1 filters (R3C pushdown) before hop 1.
    ot1_converted = all_converted_filters.get(ots[1], {})
    if ot1_converted:
        intermediate = _apply_flat_filters(intermediate, ots[1], ot1_converted)

    # Hop 1: build target index on OT2, join intermediate -> OT2.
    idx2, te2 = _build_target_index(
        all_rows_raw[2], col_indices[2],
        hop_pk_cols[1], hop_pk_props[1],
        per_ot_fields[2], bindings[2], ots[2], prop_map,
    )
    all_type_errors.extend(te2)

    final_rows = _join_flat_rows(
        intermediate, ots[1], hop_fk_props[1],
        idx2, ots[2],
    )

    # Apply OT2 filters (R3C pushdown).
    ot2_converted = all_converted_filters.get(ots[2], {})
    if ot2_converted:
        final_rows = _apply_flat_filters(final_rows, ots[2], ot2_converted)

    # Strip join-only fields: only keep output_fields for each OT.
    keep_keys: set[str] = set()
    for i, ot in enumerate(ots):
        keep_keys.update(f"{ot}__{f}" for f in output_fields[i])
    final_rows = [
        {k: v for k, v in row.items() if k in keep_keys}
        for row in final_rows
    ]

    paged = final_rows[offset : offset + limit]
    explain["scanned_rows"] = {ot: all_scanned[i] for i, ot in enumerate(ots)}
    explain["scan_limit"] = scan_limit
    explain["scan_truncated"] = {ot: all_truncated[i] for i, ot in enumerate(ots)}
    explain["matched_before_paging"] = len(final_rows)

    # Grouped response shape: two-level nesting following cardinalities.
    rows: list[dict] = paged
    audit_row_count = len(paged)
    if response_shape == "grouped" and paged:
        cardinalities = [lk.get("cardinality", "one_to_many") for lk in links]
        if direction == "reverse":
            cardinalities = [_reverse_cardinality(card) for card in cardinalities]
        rows = _group_flat_rows(paged, path, output_fields, cardinalities)
        audit_row_count = len(rows)

    response: dict[str, Any] = {
        "rows": rows,
        "row_count": audit_row_count,
        "explain": explain,
    }

    if all_type_errors:
        response["type_errors"] = all_type_errors
        response["row_count"] = None

    final_outcome = (
        "failure" if all_type_errors
        else "empty" if audit_row_count == 0
        else "success"
    )
    _record_audit(
        db,
        **audit_base,
        field_names=audit_field_names,
        filter_field_names=audit_filter_names,
        link_type_api_names=audit_link_type_api_names,
        binding_ids=audit_binding_ids,
        dataset_ids=audit_dataset_ids,
        outcome=final_outcome,
        row_count=audit_row_count if not all_type_errors else None,
        error_code=_sanitized_code("type_conversion") if all_type_errors else None,
        error_summary=(
            f"{len(all_type_errors)} type conversion error(s)"
            if all_type_errors else None
        ),
    )
    db.commit()

    return response


def _resolve_link(ctx: dict, source_ot: str, target_ot: str,
                   direction: str = "forward") -> dict:
    link_map = ctx.get("link_map", {})
    if not link_map:
        raise ValueError("Package has no link_types in compiled contract")

    matching_links = [
        link
        for link in link_map.values()
        if (
            (
                direction == "forward"
                and link.get("source_object_type") == source_ot
                and link.get("target_object_type") == target_ot
            )
            or (
                direction == "reverse"
                and link.get("target_object_type") == source_ot
                and link.get("source_object_type") == target_ot
            )
        )
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


def _join_flat_rows(
    source_dicts: list[dict[str, Any]],
    source_ot: str,
    source_fk_property: str,
    target_index: dict[Any, list[dict[str, Any]]],
    target_ot: str,
) -> list[dict[str, Any]]:
    """Join pre-joined flat dicts against a target PK index (hop N > 0).

    Each source dict already contains {source_ot}__{prop} and earlier-OT
    prefixed keys.  The FK value is extracted from the source-OT prefixed
    key matching source_fk_property.
    """
    matched: list[dict[str, Any]] = []
    fk_key = f"{source_ot}__{source_fk_property}"

    for row in source_dicts:
        fk_value = row.get(fk_key)
        if fk_value is None:
            continue
        for target_row in target_index.get(fk_value, []):
            merged = dict(row)
            merged.update(
                {f"{target_ot}__{f}": v for f, v in target_row.items()}
            )
            matched.append(merged)

    return matched


def _group_flat_rows(
    flat_rows: list[dict[str, Any]],
    path: list[str],
    output_fields: list[list[str]],
    cardinalities: list[str],
) -> list[dict[str, Any]]:
    """Group flat {ot}__{field} rows into nested tree following path.

    Root OT fields form unique groups.  Child OTs are nested following
    hop cardinality: one_to_one/many_to_one → single object,
    one_to_many/many_to_many → array of objects.
    Empty children are [] (array card) or {} (single card).
    """
    if not flat_rows:
        return []

    root_ot = path[0]
    root_fields_list = output_fields[0]
    prefix = f"{root_ot}__"

    # Bucket by root-OT field values.
    buckets: dict[tuple, list[dict]] = {}
    for row in flat_rows:
        key = tuple(row.get(f"{prefix}{f}") for f in root_fields_list)
        buckets.setdefault(key, []).append(row)

    result: list[dict[str, Any]] = []
    for _key, bucket in buckets.items():
        entry: dict[str, Any] = {
            root_ot: {
                f: bucket[0].get(f"{prefix}{f}") for f in root_fields_list
            },
        }

        if len(path) >= 2:
            child_ot = path[1]
            child_fields = output_fields[1]
            child_card = cardinalities[0]
            child_prefix = f"{child_ot}__"

            if len(path) == 2:
                # Single-hop: children are leaf rows.
                seen: set[tuple] = set()
                child_rows: list[dict] = []
                for row in bucket:
                    ck = tuple(row.get(f"{child_prefix}{f}") for f in child_fields)
                    if ck not in seen:
                        seen.add(ck)
                        child_rows.append(
                            {f: row.get(f"{child_prefix}{f}") for f in child_fields}
                        )
                entry[child_ot] = child_rows if child_card in (
                    "one_to_many", "many_to_many",
                ) else (child_rows[0] if child_rows else {})
            else:
                # Two-hop: group by OT1, then nest OT2.
                sub_buckets: dict[tuple, list[dict]] = {}
                for row in bucket:
                    sk = tuple(row.get(f"{child_prefix}{f}") for f in child_fields)
                    sub_buckets.setdefault(sk, []).append(row)

                child_items: list[dict] = []
                for _sk, sub in sub_buckets.items():
                    sub_entry: dict[str, Any] = {
                        f: sub[0].get(f"{child_prefix}{f}") for f in child_fields
                    }
                    grand_ot = path[2]
                    grand_fields = output_fields[2]
                    grand_card = cardinalities[1]
                    grand_prefix = f"{grand_ot}__"

                    gseen: set[tuple] = set()
                    grands: list[dict] = []
                    for row in sub:
                        gk = tuple(row.get(f"{grand_prefix}{f}") for f in grand_fields)
                        if gk not in gseen:
                            gseen.add(gk)
                            grands.append(
                                {f: row.get(f"{grand_prefix}{f}") for f in grand_fields}
                            )
                    sub_entry[grand_ot] = grands if grand_card in (
                        "one_to_many", "many_to_many",
                    ) else (grands[0] if grands else {})

                    child_items.append(sub_entry)

                entry[child_ot] = child_items if child_card in (
                    "one_to_many", "many_to_many",
                ) else (child_items[0] if child_items else {})

        result.append(entry)

    return result


def _reverse_cardinality(cardinality: str) -> str:
    """Return the effective cardinality when traversing a link in reverse."""
    reverse_map = {
        "one_to_many": "many_to_one",
        "many_to_one": "one_to_many",
        "one_to_one": "one_to_one",
        "many_to_many": "many_to_many",
    }
    return reverse_map.get(cardinality, cardinality)


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


def _prepare_ot_filters(
    ot: str,
    ot_filters: dict[str, str | int | float | bool | None] | None,
    binding: OntologyDatasetBinding,
    fields_by_ot: dict,
    prop_map: dict,
) -> tuple[list[str], dict[str, Any]]:
    """Validate and type-convert filters for one OT. Returns (names, converted)."""
    if not ot_filters:
        return [], {}
    valid_fields = set(fields_by_ot.get(ot, [])) & set(binding.property_mappings.keys())
    filter_names: list[str] = []
    converted: dict[str, Any] = {}
    for field_name, raw_value in ot_filters.items():
        if field_name not in valid_fields:
            raise ValueError(
                f"Filter field '{field_name}' is not a bound property of '{ot}'"
            )
        value_type = prop_map.get(field_name, {}).get("value_type", "string")
        try:
            converted[field_name] = _convert_filter_value(raw_value, value_type, field_name)
        except ValueError:
            raise ValueError(
                f"Filter value for '{field_name}' cannot be converted to {value_type}"
            ) from None
        filter_names.append(field_name)
    return filter_names, converted


def _apply_flat_filters(
    rows: list[dict[str, Any]],
    ot: str,
    converted_filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Filter flat rows by checking {ot}__{field} keys."""
    if not converted_filters:
        return rows
    return [
        row for row in rows
        if all(row.get(f"{ot}__{f}") == v for f, v in converted_filters.items())
    ]


def _type_error(object_type: str, field: str, prop_map: dict) -> dict:
    return {
        "object_type": object_type,
        "field": field,
        "value_type": prop_map.get(field, {}).get("value_type", "string"),
    }
