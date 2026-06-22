"""Generate Governance Feedback from a rule validation report.

Reads rule_validation_report.json produced by Phase 19.4 and produces
governance_feedback.json — an offline artifact that groups rule validation
findings into human-reviewable governance candidates.

This proves the closed loop: data anomaly → rule finding → governance
candidate. Does NOT write to the database, create real governance issues,
or create modeling drafts (those are 19.6+/future phases).

Usage:
  .venv/Scripts/python scripts/generate_governance_feedback.py \\
      --data-pack .tmp/phase19-manufacturing

  .venv/Scripts/python scripts/generate_governance_feedback.py \\
      --report .tmp/phase19-manufacturing/rule_validation_report.json \\
      --output .tmp/gov-feedback.json

  .venv/Scripts/python scripts/generate_governance_feedback.py \\
      --data-pack .tmp/phase19-manufacturing --fail-on-critical

Exit: 0 = no critical candidates (or only with default flags).
      1 = critical candidates found (with --fail-on-critical).
Dependencies: stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK_VERSION = "1.0"

# ── Candidate type definitions ───────────────────────────────────────────────

CANDIDATE_TYPES = {
    "data_quality_issue": {
        "description": (
            "A rule validation finding that indicates a data quality problem "
            "in the source CSV data. Should be reviewed and either corrected "
            "at source or acknowledged as expected."
        ),
        "triggers": {
            "required_field", "pk_unique", "fk_integrity",
            "enum_allowed", "numeric_range", "date_order",
            "row_count_range",
        },
    },
    "ontology_modeling_opportunity": {
        "description": (
            "A derived class or pattern identified in the data that may "
            "warrant explicit modeling as an Ontology object type, property, "
            "or link type."
        ),
        "triggers": {"derived_class"},
    },
    "mapping_review": {
        "description": (
            "A finding that suggests the mapping contract may need revision "
            "— e.g., an enum vocabulary is incomplete, a null_strategy is "
            "too strict, or a column semantic_role is incorrect."
        ),
        "triggers": {"enum_allowed", "required_field", "date_order"},
    },
}

# ── Severity assignment ──────────────────────────────────────────────────────

SEVERITY_MAP: dict[str, str] = {
    "pk_unique": "critical",
    "fk_integrity": "critical",
    "required_field": "high",
    "date_order": "high",
    "enum_allowed": "medium",
    "numeric_range": "medium",
    "row_count_range": "medium",
    "derived_class": "info",
}

# ── Suggested actions per rule ───────────────────────────────────────────────

SUGGESTED_ACTIONS: dict[str, str] = {
    "pk_unique": (
        "Review and deduplicate source data. If the apparent duplicate "
        "is legitimate, the primary key definition in the mapping contract "
        "may need to include additional columns to form a composite key."
    ),
    "fk_integrity": (
        "Review orphan records. Either correct the foreign key values to "
        "reference existing rows, or insert the missing referenced rows "
        "into the parent table."
    ),
    "required_field": (
        "Review null values in columns marked null_strategy=forbid. Either "
        "populate missing data at source, or update the null_strategy in "
        "the mapping contract to 'allow' or 'default' with a rationale."
    ),
    "date_order": (
        "Review date ordering: start dates should not exceed end dates. "
        "Either correct the dates in the source data, or update the mapping "
        "contract to document that date inversion is expected for this field."
    ),
    "enum_allowed": (
        "Review unknown enum values. Either correct the values in the source "
        "data, or extend the enum vocabulary in the mapping contract. "
        "New values should be reviewed by a domain expert before acceptance."
    ),
    "numeric_range": (
        "Review negative values in fields expected to be non-negative. "
        "Either correct the data at source, or document that negative "
        "values are meaningful (e.g., inventory adjustments)."
    ),
    "row_count_range": (
        "Table has zero rows. Either regenerate the data pack with the "
        "correct preset, or remove the empty table from the manifest "
        "and mapping contract."
    ),
    "derived_class": (
        "Consider creating an explicit derived class or object subtype in "
        "the Ontology model. Derived classes help downstream consumers "
        "filter and reason about important entity subsets."
    ),
}


# ── Generator ────────────────────────────────────────────────────────────────


def _candidate_type_for_rule(rule_id: str) -> list[str]:
    """Return all candidate types that a rule_id maps to."""
    types = []
    for ct_name, ct_def in CANDIDATE_TYPES.items():
        if rule_id in ct_def["triggers"]:
            types.append(ct_name)
    return types or ["data_quality_issue"]


def generate_governance_feedback(report: dict) -> dict:
    """Transform a rule_validation_report into governance feedback."""
    findings = report.get("findings", [])
    candidates = []
    stats_by_type: dict[str, int] = {}
    stats_by_severity: dict[str, int] = {}
    stats_by_table: dict[str, int] = {}

    for i, finding in enumerate(findings, 1):
        rule_id = finding.get("rule_id", "unknown")
        status = finding.get("status", "UNKNOWN")

        # Only FAIL and INFO findings become candidates
        # PASS findings are not governance-relevant
        if status not in ("FAIL", "INFO"):
            continue

        candidate_types = _candidate_type_for_rule(rule_id)
        severity = SEVERITY_MAP.get(rule_id, "medium")

        candidate_id = f"gov-{i:04d}"

        # Build bounded evidence — never include full row data
        evidence = {
            "source": "rule_validation_report.json",
            "finding_id": finding.get("finding_id"),
            "rule_id": rule_id,
            "table": finding.get("table"),
            "row": finding.get("row"),
            "column": finding.get("column"),
            "detail": finding.get("message"),
        }

        # For derived class, include derived class name
        derived_class = finding.get("evidence", {}).get("derived_class")
        if derived_class:
            evidence["derived_class"] = derived_class

        candidate = {
            "candidate_id": candidate_id,
            "finding_ref": {
                "finding_id": finding.get("finding_id"),
                "rule_id": rule_id,
                "table": finding.get("table"),
                "message": finding.get("message"),
            },
            "candidate_types": candidate_types,
            "severity": severity,
            "suggested_action": SUGGESTED_ACTIONS.get(
                rule_id, "Review this finding with a domain expert."
            ),
            "status": "open",
            "evidence": evidence,
        }

        candidates.append(candidate)

        # Stats
        for ct in candidate_types:
            stats_by_type[ct] = stats_by_type.get(ct, 0) + 1
        stats_by_severity[severity] = stats_by_severity.get(severity, 0) + 1
        tbl = finding.get("table", "unknown")
        stats_by_table[tbl] = stats_by_table.get(tbl, 0) + 1

    # Build summary
    critical_count = stats_by_severity.get("critical", 0)
    high_count = stats_by_severity.get("high", 0)
    medium_count = stats_by_severity.get("medium", 0)
    info_count = stats_by_severity.get("info", 0)

    return {
        "feedback_version": FEEDBACK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_report": "rule_validation_report.json",
        "data_pack": report.get("data_pack", "unknown"),
        "summary": {
            "total_findings_in_report": len(findings),
            "total_candidates": len(candidates),
            "by_type": stats_by_type,
            "by_severity": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "info": info_count,
            },
            "by_table": dict(
                sorted(stats_by_table.items(),
                       key=lambda x: x[1], reverse=True)
            ),
            "requires_human_review": len(candidates) > 0,
        },
        "candidates": candidates,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "replaces_human_review": False,
            "note": (
                "These are governance feedback candidates generated from "
                "offline rule validation. They have NOT been written to the "
                "database as governance_issues or modeling_drafts. Human "
                "review is required before any database-level action."
            ),
        },
    }


# ── Validator (minimal structural check) ─────────────────────────────────────


def validate_feedback(feedback: dict) -> tuple[bool, list[str]]:
    """Minimal structural validation of governance feedback."""
    issues = []
    required_top = [
        "feedback_version", "generated_at", "source_report",
        "data_pack", "summary", "candidates", "boundaries",
    ]
    for field in required_top:
        if field not in feedback:
            issues.append(f"Missing required field: {field}")

    if feedback.get("feedback_version") != FEEDBACK_VERSION:
        issues.append(
            f"Unsupported feedback_version: "
            f"{feedback.get('feedback_version')}"
        )

    s = feedback.get("summary", {})
    for key in ("total_candidates", "by_type", "by_severity",
                "requires_human_review"):
        if key not in s:
            issues.append(f"summary missing: {key}")

    b = feedback.get("boundaries", {})
    for key in ("offline_only", "writes_to_database",
                "creates_real_governance_issues", "replaces_human_review"):
        if key not in b:
            issues.append(f"boundaries missing: {key}")

    for c in feedback.get("candidates", []):
        for key in ("candidate_id", "finding_ref", "candidate_types",
                    "severity", "suggested_action", "status", "evidence"):
            if key not in c:
                issues.append(
                    f"Candidate {c.get('candidate_id', '?')} "
                    f"missing: {key}"
                )

    return len(issues) == 0, issues


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Governance Feedback from rule validation report",
    )
    parser.add_argument(
        "--data-pack", type=Path, default=None,
        help="Path to data pack directory (reads rule_validation_report.json "
             "from this directory)",
    )
    parser.add_argument(
        "--report", type=Path, default=None,
        help="Path to rule_validation_report.json (overrides --data-pack)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path for governance_feedback.json "
             "(default: <data-pack>/governance_feedback.json)",
    )
    parser.add_argument(
        "--fail-on-critical", action="store_true",
        help="Exit 1 if any critical-severity candidates exist",
    )
    args = parser.parse_args()

    # Resolve report path
    if args.report:
        report_path = args.report
        data_dir = args.data_pack  # may be None
    elif args.data_pack:
        report_path = args.data_pack / "rule_validation_report.json"
        data_dir = args.data_pack
    else:
        print(
            "ERROR: provide --data-pack or --report",
            file=sys.stderr,
        )
        return 2

    if not report_path.is_file():
        print(
            f"ERROR: rule_validation_report.json not found at {report_path}",
            file=sys.stderr,
        )
        print(
            "Run validate_business_rules.py first to generate the report.",
            file=sys.stderr,
        )
        return 1

    report = json.loads(report_path.read_text(encoding="utf-8"))

    print("=== Governance Feedback Generator (Phase 19.5) ===\n")
    print(f"Source report: {report_path}")
    print(f"Findings in report: {len(report.get('findings', []))}")

    feedback = generate_governance_feedback(report)

    # Validate
    valid, issues = validate_feedback(feedback)
    if not valid:
        for issue in issues:
            print(f"  [WARN] {issue}")

    # Print summary
    s = feedback["summary"]
    print(f"\nCandidates: {s['total_candidates']}")
    print(f"  by severity: critical={s['by_severity']['critical']}  "
          f"high={s['by_severity']['high']}  "
          f"medium={s['by_severity']['medium']}  "
          f"info={s['by_severity']['info']}")
    print(f"  by type: {s['by_type']}")

    top_tables = list(s["by_table"].items())[:5]
    if top_tables:
        print(f"  top tables: {', '.join(f'{t}({n})' for t, n in top_tables)}")

    if s["requires_human_review"]:
        print(f"\n  Human review required: YES "
              f"({s['total_candidates']} candidate(s))")

    # Write output
    output_path = args.output
    if output_path is None and data_dir is not None:
        output_path = data_dir / "governance_feedback.json"
    elif output_path is None:
        output_path = Path("governance_feedback.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(feedback, f, indent=2, ensure_ascii=False)
    print(f"\n  [OK] Governance feedback -> {output_path}")

    # Print boundaries
    b = feedback["boundaries"]
    print("\n  Boundaries:")
    print(f"    offline_only: {b['offline_only']}")
    print(f"    writes_to_database: {b['writes_to_database']}")
    print(f"    creates_real_governance_issues: {b['creates_real_governance_issues']}")
    print(f"    replaces_human_review: {b['replaces_human_review']}")

    # Determine exit code
    critical_count = s["by_severity"].get("critical", 0)
    if critical_count > 0 and args.fail_on_critical:
        print(f"\nResult: FAIL ({critical_count} critical candidate(s))")
        return 1
    elif critical_count > 0:
        print(f"\nResult: WARN ({critical_count} critical candidate(s) "
              f"— use --fail-on-critical to treat as failure)")
        return 0
    elif s["total_candidates"] > 0:
        print(f"\nResult: WARN ({s['total_candidates']} candidate(s) "
              f"require review)")
        return 0
    else:
        print("\nResult: PASS (no governance candidates)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
