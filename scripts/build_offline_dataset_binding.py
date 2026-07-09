"""Build an offline dataset binding bridge from a model package snapshot.

This script connects an offline_model_package.json to a data-pack manifest and
mapping_contract.json. It does not publish the package, activate runtime, write
to the database, or turn offline candidates into hard reasoning facts.

Usage:
  .venv/Scripts/python scripts/build_offline_dataset_binding.py \
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


BINDING_ARTIFACT_VERSION = "1.0"


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


def _data_pack_summary(data_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
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


def _table_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(table.get("table_name")): table
        for table in manifest.get("tables", [])
        if table.get("table_name")
    }


def _mapping_index(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(mapping.get("source_table")): mapping
        for mapping in contract.get("object_type_mappings", [])
        if mapping.get("source_table")
    }


def _package_ref(
    package_artifact: dict[str, Any],
    model_package: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = package_artifact.get("summary", {})
    return {
        "package_status": summary.get("package_status"),
        "semantic_hash": (
            model_package.get("semantic_hash") if model_package else None
        ),
        "source_draft_count": int(summary.get("source_draft_count", 0) or 0),
    }


def _table_snapshot(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "table_name": table.get("table_name"),
        "csv_file": table.get("csv_file"),
        "row_count": table.get("row_count"),
        "primary_key": table.get("primary_key", []),
        "core_pilot": bool(table.get("core_pilot", False)),
        "business_meaning": table.get("business_meaning"),
    }


def _mapping_snapshot(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        "object_type": mapping.get("object_type"),
        "primary_key": mapping.get("primary_key", []),
        "column_count": len(mapping.get("column_mappings", [])),
    }


def _binding(
    derived_class: dict[str, Any],
    table: dict[str, Any],
    mapping: dict[str, Any],
    semantic_hash: str,
) -> dict[str, Any]:
    draft_id = str(derived_class.get("id"))
    return {
        "binding_id": f"dataset-binding-{draft_id}",
        "draft_id": draft_id,
        "derived_class": derived_class.get("name"),
        "source_table": derived_class.get("source_table"),
        "object_type": mapping.get("object_type"),
        "package_semantic_hash": semantic_hash,
        "table": _table_snapshot(table),
        "mapping": _mapping_snapshot(mapping),
    }


def _build_bindings(
    model_package: dict[str, Any],
    manifest: dict[str, Any],
    mapping_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    tables = _table_index(manifest)
    mappings = _mapping_index(mapping_contract)
    semantic_hash = str(model_package.get("semantic_hash"))
    bindings = []

    for item in model_package.get("contract", {}).get("derived_classes", []):
        source_table = item.get("source_table")
        if not source_table:
            raise ValueError(f"derived class {item.get('id')} missing source_table")
        table = tables.get(str(source_table))
        if table is None:
            raise ValueError(f"source table {source_table} not found in manifest")
        mapping = mappings.get(str(source_table))
        if mapping is None:
            raise ValueError(
                f"source table {source_table} not found in mapping_contract"
            )
        bindings.append(_binding(item, table, mapping, semantic_hash))

    bindings.sort(key=lambda item: (str(item["source_table"]), str(item["draft_id"])))
    return bindings


def build_offline_dataset_binding(data_dir: Path) -> dict[str, Any]:
    manifest = _read_json(data_dir / "manifest.json", "manifest.json")
    mapping_contract = _read_json(
        data_dir / "mapping_contract.json",
        "mapping_contract.json",
    )
    package_artifact = _read_json(
        data_dir / "offline_model_package.json",
        "offline_model_package.json",
    )

    model_package = package_artifact.get("model_package")
    package_ref = _package_ref(package_artifact, model_package)
    package_status = package_ref["package_status"]
    bindings: list[dict[str, Any]] = []

    if package_status == "BUILT" and model_package:
        bindings = _build_bindings(model_package, manifest, mapping_contract)

    binding_status = "BOUND" if bindings else "NO_BINDABLE_PACKAGE"
    runtime_query_ready = bool(bindings)
    data_pack = _data_pack_summary(data_dir, manifest)

    return {
        "binding_artifact_version": BINDING_ARTIFACT_VERSION,
        "pipeline": "offline_dataset_binding_bridge",
        "generated_at": _utc_now(),
        "data_pack": data_pack,
        "source_artifacts": {
            "manifest": _artifact(data_dir / "manifest.json"),
            "mapping_contract": _artifact(data_dir / "mapping_contract.json"),
            "offline_model_package": _artifact(data_dir / "offline_model_package.json"),
        },
        "summary": {
            "binding_status": binding_status,
            "package_status": package_status,
            "semantic_hash": package_ref["semantic_hash"],
            "table_count": data_pack["table_count"],
            "total_rows": data_pack["total_rows"],
            "binding_count": len(bindings),
            "runtime_query_ready": runtime_query_ready,
            "hard_reasoning_allowed": False,
            "writes_to_database": False,
        },
        "package_ref": package_ref,
        "bindings": bindings,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "publishes_model_package": False,
            "activates_runtime": False,
            "hard_reasoning_allowed": False,
            "runtime_query_ready": runtime_query_ready,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Offline Dataset Binding Bridge",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Binding status: `{summary['binding_status']}`",
        f"- Package status: `{summary['package_status']}`",
        f"- Semantic hash: `{summary['semantic_hash']}`",
        f"- Bindings: `{summary['binding_count']}`",
        f"- Runtime query ready: `{str(summary['runtime_query_ready']).lower()}`",
        "- Writes to database: `false`",
        "- Activates runtime: `false`",
        "",
        "## Bindings",
        "",
        "| Binding | Derived class | Source table | Object type | Rows |",
        "|---|---|---|---|---|",
    ]
    for binding in result["bindings"]:
        lines.append(
            "| "
            f"{binding.get('binding_id')} | "
            f"{binding.get('derived_class')} | "
            f"{binding.get('source_table')} | "
            f"{binding.get('object_type')} | "
            f"{binding.get('table', {}).get('row_count')} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Publishes model package: `false`",
            "- Runtime activation remains out of scope for this artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def write_offline_dataset_binding(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_offline_dataset_binding(data_dir)
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
        description="Build offline dataset binding bridge artifact",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help=(
            "Data pack directory containing manifest.json, mapping_contract.json, "
            "and offline_model_package.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/offline_dataset_binding.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/offline_dataset_binding.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "offline_dataset_binding.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "offline_dataset_binding.md"
    )

    try:
        result = write_offline_dataset_binding(
            args.data_pack,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Offline Dataset Binding Bridge ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Binding status: {summary['binding_status']}")
    print(f"Package status: {summary['package_status']}")
    print(f"Bindings: {summary['binding_count']}")
    print(f"Runtime query ready: {summary['runtime_query_ready']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
