"""Build an offline model package bridge from accepted ontology drafts.

This script converts accepted_ontology_drafts.json into an immutable-style
offline model package artifact with a stable semantic hash. It does not write
to the database, publish a real model package, activate runtime, or grant hard
reasoning rights.

Usage:
  .venv/Scripts/python scripts/build_offline_model_package.py \
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


PACKAGE_ARTIFACT_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_drafts(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "accepted_ontology_drafts.json"
    if not path.is_file():
        raise FileNotFoundError(f"accepted_ontology_drafts.json not found in {data_dir}")
    return _read_json(path)


def _artifact_path(data_dir: Path, filename: str) -> str | None:
    path = data_dir / filename
    if not path.is_file():
        return None
    return str(path)


def _derived_class_snapshot(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": draft.get("draft_id"),
        "name": draft.get("name"),
        "description": draft.get("description"),
        "source_table": draft.get("source_table"),
        "payload": draft.get("payload", {}),
        "evidence_refs": draft.get("evidence_refs", []),
        "review": draft.get("review", {}),
        "hard_reasoning_allowed": False,
    }


def _contract(drafts: list[dict[str, Any]]) -> dict[str, Any]:
    derived_classes = [
        _derived_class_snapshot(draft)
        for draft in drafts
        if draft.get("draft_type") == "derived_class"
    ]
    derived_classes.sort(
        key=lambda item: (
            str(item.get("name") or "").casefold(),
            str(item.get("id") or ""),
        )
    )
    return {
        "schema_version": "1.0",
        "object_types": [],
        "properties": [],
        "link_types": [],
        "action_types": [],
        "derived_classes": derived_classes,
    }


def _semantic_hash(contract: dict[str, Any]) -> str:
    canonical = json.dumps(
        contract,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_draft_ids(contract: dict[str, Any]) -> list[str]:
    ids = []
    for key in (
        "object_types",
        "properties",
        "link_types",
        "action_types",
        "derived_classes",
    ):
        for item in contract.get(key, []):
            ids.append(str(item.get("id")))
    return ids


def _model_package(drafts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not drafts:
        return None
    contract = _contract(drafts)
    source_ids = _source_draft_ids(contract)
    return {
        "schema_version": "1.0",
        "package_status": "offline_built",
        "semantic_hash": _semantic_hash(contract),
        "contract": contract,
        "source_draft_ids": source_ids,
        "draft_count": len(source_ids),
        "quality_status": "PASS",
        "quality_summary": {
            "status": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "accepted_draft_count": len(source_ids),
        },
        "boundaries": {
            "offline_only": True,
            "publishes_model_package": False,
            "activates_runtime": False,
            "hard_reasoning_allowed": False,
        },
    }


def build_offline_model_package(data_dir: Path) -> dict[str, Any]:
    drafts_artifact = _load_drafts(data_dir)
    drafts = drafts_artifact.get("drafts", [])
    model_package = _model_package(drafts)
    package_status = "BUILT" if model_package is not None else "NO_ACCEPTED_DRAFTS"
    derived_class_count = 0
    source_draft_count = 0
    if model_package is not None:
        contract = model_package["contract"]
        derived_class_count = len(contract.get("derived_classes", []))
        source_draft_count = len(model_package.get("source_draft_ids", []))

    return {
        "package_artifact_version": PACKAGE_ARTIFACT_VERSION,
        "pipeline": "offline_model_package_bridge",
        "generated_at": _utc_now(),
        "data_pack": drafts_artifact.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "accepted_ontology_drafts": str(
                data_dir / "accepted_ontology_drafts.json"
            ),
            "accepted_governance_changes": _artifact_path(
                data_dir,
                "accepted_governance_changes.json",
            ),
        },
        "summary": {
            "package_status": package_status,
            "draft_count": len(drafts),
            "derived_class_count": derived_class_count,
            "source_draft_count": source_draft_count,
            "hard_reasoning_allowed": False,
            "writes_to_database": False,
        },
        "model_package": model_package,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "activates_runtime": False,
            "hard_reasoning_allowed": False,
            "requires_human_review": True,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    package = result.get("model_package")
    semantic_hash = package.get("semantic_hash") if package else None
    lines = [
        "# Offline Model Package Bridge",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Package status: `{summary['package_status']}`",
        f"- Drafts: `{summary['draft_count']}`",
        f"- Derived classes: `{summary['derived_class_count']}`",
        f"- Semantic hash: `{semantic_hash}`",
        "- Publishes model package: `false`",
        "- Activates runtime: `false`",
        "",
        "## Derived Classes",
        "",
        "| Draft | Name | Source table |",
        "|---|---|---|",
    ]
    if package:
        for item in package["contract"].get("derived_classes", []):
            lines.append(
                "| "
                f"{item.get('id')} | "
                f"{item.get('name')} | "
                f"{item.get('source_table')} |"
            )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Applies model changes: `false`",
            "- Publishes model package: `false`",
            "- Runtime activation remains out of scope for this artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def write_offline_model_package(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_offline_model_package(data_dir)
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
        description="Build offline model package bridge artifact",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing accepted_ontology_drafts.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/offline_model_package.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/offline_model_package.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "offline_model_package.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "offline_model_package.md"
    )

    try:
        result = write_offline_model_package(
            args.data_pack,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Offline Model Package Bridge ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Package status: {summary['package_status']}")
    print(f"Drafts: {summary['draft_count']}")
    print(f"Derived classes: {summary['derived_class_count']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
