"""Build an offline review packet for Semantic CI governance candidates.

The packet turns governance_feedback.json into a reviewer-facing artifact with
owner role, required checks, evidence anchors, and recommended review decisions.
It does not write to the database or create real governance issues.

Usage:
  .venv/Scripts/python scripts/build_governance_review_packet.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKET_VERSION = "1.0"


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


def _safe_evidence_anchor(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence", {}) or {}
    return {
        "source": evidence.get("source"),
        "finding_id": evidence.get("finding_id"),
        "rule_id": evidence.get("rule_id"),
        "table": evidence.get("table"),
        "row": evidence.get("row"),
        "column": evidence.get("column"),
        "derived_class": evidence.get("derived_class"),
    }


def _review_guidance(candidate: dict[str, Any]) -> dict[str, Any]:
    types = set(candidate.get("candidate_types", []))
    severity = candidate.get("severity", "info")

    if "data_quality_issue" in types or severity in {"critical", "high"}:
        return {
            "recommended_decision": "fix_or_explain_data",
            "review_owner_role": "data_steward",
            "required_checks": [
                "verify_source_record",
                "confirm_business_exception",
                "decide_fix_or_document_exception",
            ],
            "rollback_note": (
                "Do not apply modeling changes until the source record is fixed "
                "or the exception is explicitly documented."
            ),
        }

    if "mapping_review" in types:
        return {
            "recommended_decision": "review_mapping_contract",
            "review_owner_role": "semantic_modeler",
            "required_checks": [
                "confirm_source_column_semantics",
                "confirm_target_property",
                "rerun_semantic_ci",
            ],
            "rollback_note": (
                "Revert the mapping contract change and rerun Semantic CI if "
                "downstream rule results regress."
            ),
        }

    if "ontology_modeling_opportunity" in types:
        return {
            "recommended_decision": "consider_modeling",
            "review_owner_role": "ontology_steward",
            "required_checks": [
                "confirm_business_meaning",
                "confirm_not_hard_relation",
                "decide_modeling_action",
            ],
            "rollback_note": (
                "Keep as an offline candidate unless a human reviewer accepts "
                "the modeling change."
            ),
        }

    return {
        "recommended_decision": "review_manually",
        "review_owner_role": "governance_reviewer",
        "required_checks": [
            "inspect_candidate",
            "confirm_evidence",
            "decide_next_action",
        ],
        "rollback_note": (
            "No action should be applied without explicit human review."
        ),
    }


def _build_review_item(candidate: dict[str, Any]) -> dict[str, Any]:
    guidance = _review_guidance(candidate)
    finding = candidate.get("finding_ref", {}) or {}
    evidence = candidate.get("evidence", {}) or {}
    return {
        "candidate_id": candidate.get("candidate_id"),
        "status": candidate.get("status", "open"),
        "severity": candidate.get("severity", "info"),
        "candidate_types": candidate.get("candidate_types", []),
        "finding": {
            "finding_id": finding.get("finding_id") or evidence.get("finding_id"),
            "rule_id": finding.get("rule_id") or evidence.get("rule_id"),
            "table": finding.get("table") or evidence.get("table"),
            "message": finding.get("message") or evidence.get("detail"),
        },
        "suggested_action": candidate.get("suggested_action"),
        "recommended_decision": guidance["recommended_decision"],
        "review_owner_role": guidance["review_owner_role"],
        "required_checks": guidance["required_checks"],
        "rollback_note": guidance["rollback_note"],
        "evidence_anchor": _safe_evidence_anchor(candidate),
        "human_review": {
            "required": True,
            "decision_options": ["accept", "reject", "defer", "needs_more_evidence"],
            "decision": None,
            "reviewer": None,
            "reviewed_at": None,
            "notes": None,
        },
    }


def _count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(field) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_types(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for value in item.get("candidate_types", []):
            counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _semantic_ci_summary(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / "semantic_ci_report.json"
    if not path.is_file():
        return None
    report = _read_json(path)
    return report.get("summary", {})


def build_review_packet(data_dir: Path) -> dict[str, Any]:
    feedback_path = data_dir / "governance_feedback.json"
    if not feedback_path.is_file():
        raise FileNotFoundError(f"governance_feedback.json not found in {data_dir}")

    feedback = _read_json(feedback_path)
    review_items = [
        _build_review_item(candidate)
        for candidate in feedback.get("candidates", [])
    ]

    tables: dict[str, int] = {}
    for item in review_items:
        table = item["finding"].get("table") or "unknown"
        tables[table] = tables.get(table, 0) + 1

    requires_human_review = bool(
        feedback.get("summary", {}).get("requires_human_review", bool(review_items))
    )
    return {
        "packet_version": PACKET_VERSION,
        "pipeline": "governance_candidate_review",
        "generated_at": _utc_now(),
        "data_pack": {
            "path": str(data_dir),
        },
        "source_artifacts": {
            "semantic_ci_report": (
                str(data_dir / "semantic_ci_report.json")
                if (data_dir / "semantic_ci_report.json").is_file()
                else None
            ),
            "governance_feedback": str(feedback_path),
            "rule_validation_report": (
                str(data_dir / "rule_validation_report.json")
                if (data_dir / "rule_validation_report.json").is_file()
                else None
            ),
        },
        "semantic_ci_summary": _semantic_ci_summary(data_dir),
        "summary": {
            "total_review_items": len(review_items),
            "requires_human_review": requires_human_review,
            "by_severity": _count_by(review_items, "severity"),
            "by_type": _count_types(review_items),
            "by_table": dict(sorted(tables.items())),
            "by_recommended_decision": _count_by(
                review_items,
                "recommended_decision",
            ),
            "by_owner_role": _count_by(review_items, "review_owner_role"),
        },
        "review_items": review_items,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "requires_human_review": requires_human_review,
        },
    }


def _markdown_table_rows(counts: dict[str, int]) -> list[str]:
    return [f"| {key} | {value} |" for key, value in counts.items()]


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet["summary"]
    lines = [
        "# Governance Candidate Review Packet",
        "",
        f"- Generated at: `{packet['generated_at']}`",
        f"- Data pack: `{packet['data_pack']['path']}`",
        f"- Total review items: `{summary['total_review_items']}`",
        f"- Requires human review: `{summary['requires_human_review']}`",
        "",
        "## Recommended Decisions",
        "",
        "| Decision | Count |",
        "|---|---:|",
    ]
    lines.extend(_markdown_table_rows(summary["by_recommended_decision"]))
    lines.extend([
        "",
        "## Owner Roles",
        "",
        "| Role | Count |",
        "|---|---:|",
    ])
    lines.extend(_markdown_table_rows(summary["by_owner_role"]))
    lines.extend([
        "",
        "## Review Items",
        "",
        "| Candidate | Severity | Decision | Owner | Table | Finding |",
        "|---|---|---|---|---|---|",
    ])
    for item in packet["review_items"]:
        finding = item.get("finding", {})
        message = str(finding.get("message") or "").replace("|", "\\|")
        lines.append(
            "| "
            f"{item.get('candidate_id')} | "
            f"{item.get('severity')} | "
            f"{item.get('recommended_decision')} | "
            f"{item.get('review_owner_role')} | "
            f"{finding.get('table')} | "
            f"{message} |"
        )
    lines.extend([
        "",
        "## Boundaries",
        "",
        "- Offline only: `true`",
        "- Writes to database: `false`",
        "- Creates real governance issues: `false`",
        "- Human review remains required before any modeling or data change.",
        "",
    ])
    return "\n".join(lines)


def write_review_packet(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    packet = build_review_packet(data_dir)
    _write_json(output_path, packet)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(
            render_markdown(packet),
            encoding="utf-8",
        )
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline review packet from governance feedback",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_feedback.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/governance_review_packet.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/governance_review_packet.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "governance_review_packet.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "governance_review_packet.md"
    )

    try:
        packet = write_review_packet(args.data_pack, output, markdown_output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = packet["summary"]
    print("=== Governance Candidate Review Packet ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Review items: {summary['total_review_items']}")
    print(f"Requires human review: {summary['requires_human_review']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
