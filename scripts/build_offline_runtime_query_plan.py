"""Build an offline runtime query dry-run plan from dataset bindings.

This script turns offline_dataset_binding.json into explain-only query plans.
It does not execute runtime queries, read dataset rows, write audit records,
activate runtime, or publish model packages.

Usage:
  .venv/Scripts/python scripts/build_offline_runtime_query_plan.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


QUERY_PLAN_VERSION = "1.0"
DEFAULT_LIMIT = 20


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _artifact(path: Path) -> dict[str, str | None]:
    return {
        "path": str(path),
        "sha256": _sha256(path),
    }


def _data_pack_summary(
    data_dir: Path,
    manifest: dict[str, Any],
    binding_artifact: dict[str, Any],
) -> dict[str, Any]:
    if binding_artifact.get("data_pack"):
        return binding_artifact["data_pack"]
    tables = manifest.get("tables", [])
    return {
        "path": str(data_dir),
        "preset": manifest.get("preset"),
        "seed": manifest.get("seed"),
        "table_count": manifest.get("table_count", len(tables)),
        "total_rows": manifest.get(
            "total_rows",
            sum(table.get("row_count", 0) for table in tables),
        ),
    }


def _mapping_index(
    mapping_contract: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        str(mapping.get("source_table")): mapping
        for mapping in mapping_contract.get("object_type_mappings", [])
        if mapping.get("source_table")
    }


def _selected_fields(mapping: dict[str, Any]) -> list[str]:
    fields = []
    for column in mapping.get("column_mappings", []):
        target = column.get("target_property") or column.get("source_column")
        if target:
            fields.append(str(target))
    return sorted(dict.fromkeys(fields))


def _readiness_issues(binding_artifact: dict[str, Any]) -> list[dict[str, str]]:
    summary = binding_artifact.get("summary", {})
    if summary.get("runtime_query_ready") and binding_artifact.get("bindings"):
        return []
    return [
        {
            "code": "dataset_binding_not_ready",
            "severity": "info",
            "message": (
                "offline_dataset_binding.json is not runtime-query-ready."
            ),
        }
    ]


def _query_plan(
    binding: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    selected_fields = _selected_fields(mapping)
    object_type = binding.get("object_type")
    table = binding.get("table", {})
    return {
        "plan_id": f"offline-query-{binding.get('binding_id')}",
        "binding_id": binding.get("binding_id"),
        "object_type": object_type,
        "source_table": binding.get("source_table"),
        "derived_class": binding.get("derived_class"),
        "query_request": {
            "object_type": object_type,
            "fields": selected_fields,
            "filters": {},
            "limit": DEFAULT_LIMIT,
            "offset": 0,
            "explain_only": True,
        },
        "explain": {
            "package_semantic_hash": binding.get("package_semantic_hash"),
            "selected_fields": selected_fields,
            "filter_field_names": [],
            "table_name": table.get("table_name"),
            "csv_file": table.get("csv_file"),
            "row_count": table.get("row_count"),
            "primary_key": table.get("primary_key", []),
        },
        "execution": {
            "mode": "dry_run_only",
            "returns_rows": False,
            "reason": (
                "Requires DB-backed accepted package, active dataset "
                "binding, and runtime audit before execution."
            ),
        },
    }


def _query_plans(
    binding_artifact: dict[str, Any],
    mapping_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    mappings = _mapping_index(mapping_contract)
    plans = []
    for binding in binding_artifact.get("bindings", []):
        source_table = str(binding.get("source_table"))
        mapping = mappings.get(source_table)
        if mapping is None:
            raise ValueError(
                f"source table {source_table} not found in mapping_contract"
            )
        plans.append(_query_plan(binding, mapping))
    plans.sort(key=lambda item: (str(item["source_table"]), str(item["binding_id"])))
    return plans


def build_offline_runtime_query_plan(data_dir: Path) -> dict[str, Any]:
    manifest = _read_json(data_dir / "manifest.json", "manifest.json")
    mapping_contract = _read_json(
        data_dir / "mapping_contract.json",
        "mapping_contract.json",
    )
    binding_artifact = _read_json(
        data_dir / "offline_dataset_binding.json",
        "offline_dataset_binding.json",
    )

    issues = _readiness_issues(binding_artifact)
    plans = [] if issues else _query_plans(binding_artifact, mapping_contract)
    summary = binding_artifact.get("summary", {})
    query_status = "QUERY_PLANNED" if plans else "NO_RUNTIME_QUERY_READY"

    return {
        "query_plan_version": QUERY_PLAN_VERSION,
        "pipeline": "offline_runtime_query_dry_run",
        "generated_at": _utc_now(),
        "data_pack": _data_pack_summary(data_dir, manifest, binding_artifact),
        "source_artifacts": {
            "manifest": _artifact(data_dir / "manifest.json"),
            "mapping_contract": _artifact(data_dir / "mapping_contract.json"),
            "offline_dataset_binding": _artifact(
                data_dir / "offline_dataset_binding.json"
            ),
        },
        "summary": {
            "query_status": query_status,
            "binding_status": summary.get("binding_status"),
            "binding_count": int(summary.get("binding_count", 0) or 0),
            "query_plan_count": len(plans),
            "runtime_query_ready": bool(summary.get("runtime_query_ready", False)),
            "executes_runtime_query": False,
            "reads_dataset_rows": False,
            "writes_to_database": False,
        },
        "readiness_issues": issues,
        "query_plans": plans,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "reads_dataset_rows": False,
            "executes_runtime_query": False,
            "creates_audit_records": False,
            "activates_runtime": False,
            "hard_reasoning_allowed": False,
            "requires_db_backed_package": True,
            "requires_active_dataset_binding": True,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Offline Runtime Query Dry Run",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Query status: `{summary['query_status']}`",
        f"- Binding status: `{summary['binding_status']}`",
        f"- Query plans: `{summary['query_plan_count']}`",
        f"- Runtime query ready: `{str(summary['runtime_query_ready']).lower()}`",
        "- Executes runtime query: `false`",
        "- Reads dataset rows: `false`",
        "",
        "## Query Plans",
        "",
        "| Plan | Object type | Source table | Fields |",
        "|---|---|---|---|",
    ]
    for plan in result["query_plans"]:
        fields = ", ".join(plan.get("query_request", {}).get("fields", []))
        lines.append(
            "| "
            f"{plan.get('plan_id')} | "
            f"{plan.get('object_type')} | "
            f"{plan.get('source_table')} | "
            f"{fields} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Executes runtime query: `false`",
            "- Creates audit records: `false`",
            "- DB-backed package publication and active runtime bindings remain out of scope.",
            "",
        ]
    )
    return "\n".join(lines)


def write_offline_runtime_query_plan(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_offline_runtime_query_plan(data_dir)
    _write_json(output_path, result)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(
            render_markdown(result),
            encoding="utf-8",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline runtime query dry-run plan",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help=(
            "Data pack directory containing manifest.json, mapping_contract.json, "
            "and offline_dataset_binding.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/offline_runtime_query_plan.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/offline_runtime_query_plan.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "offline_runtime_query_plan.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "offline_runtime_query_plan.md"
    )

    try:
        result = write_offline_runtime_query_plan(
            args.data_pack,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Offline Runtime Query Dry Run ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Query status: {summary['query_status']}")
    print(f"Binding status: {summary['binding_status']}")
    print(f"Query plans: {summary['query_plan_count']}")
    print(f"Executes runtime query: {summary['executes_runtime_query']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
