"""Build an offline AdventureWorks ontology seed from Semantic CI artifacts.

The seed is a reviewer-facing bridge from mapping_contract.json and
governance_review_packet.json into object types, relationship candidates, and
derived-class candidates. It does not write to the database, publish a model
package, or make any candidate available for hard runtime reasoning.

Usage:
  .venv/Scripts/python scripts/build_adventureworks_ontology_seed.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SEED_VERSION = "1.0"


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


def _artifact_path(data_dir: Path, filename: str) -> str | None:
    path = data_dir / filename
    if not path.is_file():
        return None
    return str(path)


def _require_artifact(data_dir: Path, filename: str) -> Path:
    path = data_dir / filename
    if not path.is_file():
        raise FileNotFoundError(f"{filename} not found in {data_dir}")
    return path


def _object_types(contract: dict[str, Any]) -> list[dict[str, Any]]:
    object_types = []
    for mapping in contract.get("object_type_mappings", []):
        properties = [
            {
                "source_column": column.get("source_column"),
                "target_property": column.get("target_property"),
                "value_type": column.get("value_type"),
                "semantic_role": column.get("semantic_role"),
                "null_strategy": column.get("null_strategy"),
            }
            for column in mapping.get("column_mappings", [])
        ]
        object_types.append(
            {
                "object_type": mapping.get("object_type"),
                "source_table": mapping.get("source_table"),
                "description": mapping.get("description"),
                "core_pilot": mapping.get("core_pilot", False),
                "primary_key": mapping.get("primary_key", []),
                "governance_status": "seed_candidate",
                "properties": properties,
            }
        )
    return object_types


def _relationships(contract: dict[str, Any]) -> list[dict[str, Any]]:
    relationships = []
    for mapping in contract.get("relationship_mappings", []):
        relationships.append(
            {
                "relationship_name": mapping.get("relationship_name"),
                "source_table": mapping.get("source_table"),
                "source_columns": mapping.get("source_columns", []),
                "target_table": mapping.get("target_table"),
                "target_columns": mapping.get("target_columns", []),
                "cardinality": mapping.get("cardinality"),
                "core_pilot": mapping.get("core_pilot", False),
                "evidence_source": mapping.get("evidence_source"),
                "governance_layer": "contract_fk_candidate",
                "governance_label": "Contract FK candidate",
                "review_required": True,
                "hard_reasoning_allowed": False,
            }
        )
    return relationships


def _safe_anchor(anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": anchor.get("source"),
        "finding_id": anchor.get("finding_id"),
        "rule_id": anchor.get("rule_id"),
        "table": anchor.get("table"),
        "row": anchor.get("row"),
        "column": anchor.get("column"),
        "derived_class": anchor.get("derived_class"),
    }


def _derived_classes(packet: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in packet.get("review_items", []):
        anchor = _safe_anchor(item.get("evidence_anchor", {}) or {})
        derived_class = anchor.get("derived_class")
        source_table = anchor.get("table")
        if not derived_class or not source_table:
            continue

        key = (str(derived_class), str(source_table))
        group = grouped.setdefault(
            key,
            {
                "derived_class": derived_class,
                "source_table": source_table,
                "governance_layer": "weak_candidate",
                "governance_label": "Weak derived-class candidate",
                "review_required": True,
                "hard_reasoning_allowed": False,
                "review_owner_role": item.get("review_owner_role"),
                "candidate_ids": [],
                "evidence_anchors": [],
            },
        )
        candidate_id = item.get("candidate_id")
        if candidate_id is not None:
            group["candidate_ids"].append(candidate_id)
        group["evidence_anchors"].append(anchor)

    return [grouped[key] for key in sorted(grouped)]


def _review_requirements(packet: dict[str, Any]) -> dict[str, Any]:
    roles = set()
    checks = set()
    for item in packet.get("review_items", []):
        role = item.get("review_owner_role")
        if role:
            roles.add(str(role))
        checks.update(str(check) for check in item.get("required_checks", []))

    summary = packet.get("summary", {}) or {}
    candidate_count = summary.get(
        "total_review_items",
        len(packet.get("review_items", [])),
    )
    return {
        "requires_human_review": bool(
            summary.get("requires_human_review", candidate_count > 0)
        ),
        "required_roles": sorted(roles),
        "candidate_count": candidate_count,
        "required_checks": sorted(checks),
    }


def _data_pack_summary(data_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(data_dir),
        "preset": manifest.get("preset"),
        "seed": manifest.get("seed"),
        "table_count": manifest.get(
            "table_count",
            len(manifest.get("tables", [])),
        ),
        "total_rows": manifest.get(
            "total_rows",
            sum(t.get("row_count", 0) for t in manifest.get("tables", [])),
        ),
    }


def build_ontology_seed(data_dir: Path) -> dict[str, Any]:
    manifest = _read_json(_require_artifact(data_dir, "manifest.json"))
    contract = _read_json(_require_artifact(data_dir, "mapping_contract.json"))
    review_packet = _read_json(
        _require_artifact(data_dir, "governance_review_packet.json")
    )

    object_types = _object_types(contract)
    relationships = _relationships(contract)
    derived_classes = _derived_classes(review_packet)
    review_requirements = _review_requirements(review_packet)

    return {
        "seed_version": SEED_VERSION,
        "pipeline": "adventureworks_ontology_seed",
        "generated_at": _utc_now(),
        "data_pack": _data_pack_summary(data_dir, manifest),
        "source_artifacts": {
            "manifest": str(data_dir / "manifest.json"),
            "mapping_contract": str(data_dir / "mapping_contract.json"),
            "governance_review_packet": str(
                data_dir / "governance_review_packet.json"
            ),
            "semantic_ci_report": _artifact_path(
                data_dir,
                "semantic_ci_report.json",
            ),
        },
        "summary": {
            "object_type_count": len(object_types),
            "relationship_count": len(relationships),
            "derived_class_count": len(derived_classes),
            "review_candidate_count": review_requirements["candidate_count"],
            "requires_human_review": review_requirements[
                "requires_human_review"
            ],
        },
        "object_types": object_types,
        "relationships": relationships,
        "derived_classes": derived_classes,
        "review_requirements": review_requirements,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "publishes_model_package": False,
            "hard_reasoning_allowed": False,
        },
    }


def _markdown_table_rows(items: list[dict[str, Any]], fields: list[str]) -> list[str]:
    rows = []
    for item in items:
        values = [str(item.get(field, "")).replace("|", "\\|") for field in fields]
        rows.append("| " + " | ".join(values) + " |")
    return rows


def render_markdown(seed: dict[str, Any]) -> str:
    summary = seed["summary"]
    lines = [
        "# AdventureWorks Ontology Seed",
        "",
        f"- Generated at: `{seed['generated_at']}`",
        f"- Data pack: `{seed['data_pack']['path']}`",
        f"- Object types: `{summary['object_type_count']}`",
        f"- Relationships: `{summary['relationship_count']}`",
        f"- Derived classes: `{summary['derived_class_count']}`",
        f"- Requires human review: `{summary['requires_human_review']}`",
        "- Hard reasoning allowed: `false`",
        "",
        "## Object Types",
        "",
        "| Object type | Source table | Properties | Governance |",
        "|---|---|---:|---|",
    ]
    for item in seed["object_types"]:
        lines.append(
            "| "
            f"{item.get('object_type')} | "
            f"{item.get('source_table')} | "
            f"{len(item.get('properties', []))} | "
            f"{item.get('governance_status')} |"
        )

    lines.extend(
        [
            "",
            "## Relationships",
            "",
            "| Relationship | Source | Target | Layer | Review |",
            "|---|---|---|---|---|",
        ]
    )
    lines.extend(
        _markdown_table_rows(
            seed["relationships"],
            [
                "relationship_name",
                "source_table",
                "target_table",
                "governance_layer",
                "review_required",
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Derived Classes",
            "",
            "| Derived class | Source table | Candidates | Layer | Review |",
            "|---|---|---:|---|---|",
        ]
    )
    for item in seed["derived_classes"]:
        lines.append(
            "| "
            f"{item.get('derived_class')} | "
            f"{item.get('source_table')} | "
            f"{len(item.get('candidate_ids', []))} | "
            f"{item.get('governance_layer')} | "
            f"{item.get('review_required')} |"
        )

    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Creates real governance issues: `false`",
            "- Publishes model package: `false`",
            "- Human review is required before modeling or runtime use.",
            "",
        ]
    )
    return "\n".join(lines)


def write_ontology_seed(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    seed = build_ontology_seed(data_dir)
    _write_json(output_path, seed)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(
            render_markdown(seed),
            encoding="utf-8",
        )
    return seed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline AdventureWorks ontology seed artifacts",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing Semantic CI artifacts",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/adventureworks_ontology_seed.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/adventureworks_ontology_seed.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "adventureworks_ontology_seed.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "adventureworks_ontology_seed.md"
    )

    try:
        seed = write_ontology_seed(args.data_pack, output, markdown_output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = seed["summary"]
    print("=== AdventureWorks Ontology Seed ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Object types: {summary['object_type_count']}")
    print(f"Relationships: {summary['relationship_count']}")
    print(f"Derived classes: {summary['derived_class_count']}")
    print(f"Requires human review: {summary['requires_human_review']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
