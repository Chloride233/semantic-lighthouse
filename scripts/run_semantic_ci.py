"""Run the offline Semantic CI/CD pipeline for a Phase 19 data pack.

This script productizes the existing offline chain:

manifest -> mapping_contract -> rule_validation_report
-> governance_feedback -> semantic_ci_report

It does not write to the database, call APIs, create real governance issues,
or invoke Agent/MCP behavior.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generate_governance_feedback import (
    generate_governance_feedback,
    validate_feedback,
)
from generate_mapping_contract import build_mapping_contract
from validate_business_rules import validate_business_rules
from validate_manufacturing_data_pack import validate_data_pack
from validate_mapping_contract import validate_contract

REPORT_VERSION = "1.0"


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


def _gate(status: str, message: str, findings: list[str] | None = None) -> dict:
    return {
        "status": status,
        "message": message,
        "findings": findings or [],
    }


def _validation_findings(result) -> list[str]:
    return [f"[{level}] {msg}" for level, msg in result.findings]


def _has_structural_data_pack_failure(result) -> bool:
    """Return True when data-pack validation cannot safely continue.

    The data-pack validator also reports data-quality failures such as broken
    FKs. Those should still flow into business_rules -> governance_feedback.
    Structural failures stop the pipeline immediately.
    """
    structural_markers = (
        "Data pack directory not found",
        "manifest.json not found",
        "not valid JSON",
        "missing required field",
        "Unsupported manifest_version",
        "manifest.tables is empty",
        "missing field",
        "Missing CSV",
        "manifest row_count",
    )
    return any(
        level == "FAIL" and any(marker in msg for marker in structural_markers)
        for level, msg in result.findings
    )


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        rows = []
        for i, row in enumerate(csv.DictReader(f), 1):
            row["__row__"] = str(i)
            rows.append(row)
        return rows


def _load_csv_data(data_dir: Path, manifest: dict) -> dict[str, list[dict[str, str]]]:
    data: dict[str, list[dict[str, str]]] = {}
    for table in manifest.get("tables", []):
        csv_path = data_dir / table["csv_file"]
        if csv_path.is_file():
            data[table["table_name"]] = _read_csv_rows(csv_path)
    return data


def _data_pack_summary(data_dir: Path, manifest: dict | None) -> dict:
    if not manifest:
        return {
            "path": str(data_dir),
            "preset": None,
            "seed": None,
            "table_count": 0,
            "total_rows": 0,
        }
    return {
        "path": str(data_dir),
        "preset": manifest.get("preset"),
        "seed": manifest.get("seed"),
        "table_count": manifest.get("table_count", len(manifest.get("tables", []))),
        "total_rows": manifest.get(
            "total_rows",
            sum(t.get("row_count", 0) for t in manifest.get("tables", [])),
        ),
    }


def _build_report(
    *,
    data_dir: Path,
    output_path: Path,
    gates: dict,
    manifest: dict | None = None,
) -> dict:
    artifacts = {
        "manifest": _artifact(data_dir / "manifest.json"),
        "mapping_contract": _artifact(data_dir / "mapping_contract.json"),
        "rule_validation_report": _artifact(data_dir / "rule_validation_report.json"),
        "governance_feedback": _artifact(data_dir / "governance_feedback.json"),
    }

    hard_failures = sum(
        1 for gate in gates.values()
        if gate["status"] == "FAIL" and gate.get("hard_failure", False)
    )
    warnings = sum(1 for gate in gates.values() if gate["status"] == "WARN")

    feedback_path = data_dir / "governance_feedback.json"
    feedback = _read_json(feedback_path) if feedback_path.is_file() else {}
    feedback_summary = feedback.get("summary", {})
    total_candidates = int(feedback_summary.get("total_candidates", 0) or 0)
    severity = feedback_summary.get("by_severity", {})
    critical_candidates = int(severity.get("critical", 0) or 0)
    requires_human_review = bool(
        feedback_summary.get("requires_human_review", total_candidates > 0)
    )

    if any(g["status"] == "FAIL" for g in gates.values()):
        gate_status = "FAIL"
    elif warnings:
        gate_status = "WARN"
    else:
        gate_status = "PASS"

    report = {
        "report_version": REPORT_VERSION,
        "pipeline": "semantic_ci",
        "generated_at": _utc_now(),
        "data_pack": _data_pack_summary(data_dir, manifest),
        "gates": {
            name: {
                "status": gate["status"],
                "message": gate["message"],
                "findings": gate.get("findings", []),
            }
            for name, gate in gates.items()
        },
        "artifacts": artifacts,
        "summary": {
            "gate_status": gate_status,
            "hard_failures": hard_failures,
            "warnings": warnings,
            "total_candidates": total_candidates,
            "critical_candidates": critical_candidates,
        },
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "requires_human_review": requires_human_review,
        },
    }
    _write_json(output_path, report)
    return report


def _print_summary(report: dict, output_path: Path) -> None:
    summary = report["summary"]
    print("=== Semantic CI Pipeline ===\n")
    print(f"Data pack: {report['data_pack']['path']}")
    print(f"Status: {summary['gate_status']}")
    print(f"Hard failures: {summary['hard_failures']}")
    print(f"Warnings: {summary['warnings']}")
    print(f"Governance candidates: {summary['total_candidates']}")
    print(f"Critical candidates: {summary['critical_candidates']}")
    print(f"Report: {output_path}")


def run_pipeline(
    *,
    data_dir: Path,
    output_path: Path,
    regenerate_mapping: bool,
    allow_critical: bool,
) -> tuple[int, dict]:
    gates: dict[str, dict] = {}
    manifest: dict | None = None

    # Gate 1: data-pack contract validation.
    data_result = validate_data_pack(data_dir)
    data_findings = _validation_findings(data_result)
    if _has_structural_data_pack_failure(data_result):
        first_fail = next(
            (msg for level, msg in data_result.findings if level == "FAIL"),
            "Data pack contract validation failed",
        )
        gates["data_pack_contract"] = {
            **_gate("FAIL", first_fail, data_findings),
            "hard_failure": True,
        }
        report = _build_report(
            data_dir=data_dir,
            output_path=output_path,
            gates=gates,
            manifest=manifest,
        )
        return 1, report

    manifest_path = data_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    if data_result.has_fail:
        gates["data_pack_contract"] = {
            **_gate(
                "WARN",
                "Data pack contract has data-quality findings; continuing to governance feedback",
                data_findings,
            ),
            "hard_failure": False,
        }
    else:
        gates["data_pack_contract"] = {
            **_gate("PASS", "Data pack contract validation passed", data_findings),
            "hard_failure": False,
        }

    # Gate 2: mapping contract generation/validation.
    contract_path = data_dir / "mapping_contract.json"
    if regenerate_mapping or not contract_path.is_file():
        contract = build_mapping_contract(manifest)
        _write_json(contract_path, contract)
    else:
        contract = _read_json(contract_path)

    mapping_result = validate_contract(contract, manifest, data_dir)
    mapping_findings = _validation_findings(mapping_result)
    if mapping_result.has_fail:
        gates["mapping_contract"] = {
            **_gate("FAIL", "Mapping contract validation failed", mapping_findings),
            "hard_failure": True,
        }
        report = _build_report(
            data_dir=data_dir,
            output_path=output_path,
            gates=gates,
            manifest=manifest,
        )
        return 1, report

    mapping_status = "WARN" if any(
        level == "WARN" for level, _ in mapping_result.findings
    ) else "PASS"
    gates["mapping_contract"] = {
        **_gate(mapping_status, "Mapping contract validation passed", mapping_findings),
        "hard_failure": False,
    }

    # Gate 3: deterministic business rules.
    data = _load_csv_data(data_dir, manifest)
    rule_report = validate_business_rules(data_dir, manifest, contract, data)
    rule_path = data_dir / "rule_validation_report.json"
    _write_json(rule_path, rule_report)
    rules_failed = int(rule_report["summary"].get("rules_failed", 0) or 0)
    business_status = "WARN" if rules_failed else "PASS"
    gates["business_rules"] = {
        **_gate(
            business_status,
            (
                f"Business rules produced {rules_failed} failed rule category(s)"
                if rules_failed
                else "Business rules completed without failed rule categories"
            ),
            [
                f"{r['rule_id']}={r['status']} "
                f"findings={len(r.get('findings', []))}"
                for r in rule_report.get("rule_results", [])
            ],
        ),
        "hard_failure": False,
    }

    # Gate 4: governance feedback.
    feedback = generate_governance_feedback(rule_report)
    valid_feedback, feedback_issues = validate_feedback(feedback)
    feedback_path = data_dir / "governance_feedback.json"
    _write_json(feedback_path, feedback)

    critical = int(
        feedback["summary"].get("by_severity", {}).get("critical", 0) or 0
    )
    total_candidates = int(feedback["summary"].get("total_candidates", 0) or 0)
    if not valid_feedback:
        gov_status = "FAIL"
        gov_message = "Governance feedback structure validation failed"
        hard_failure = True
    elif critical and not allow_critical:
        gov_status = "FAIL"
        gov_message = (
            f"Governance feedback has {critical} critical candidate(s)"
        )
        hard_failure = False
    elif critical and allow_critical:
        gov_status = "WARN"
        gov_message = (
            f"Governance feedback has {critical} critical candidate(s); allowed"
        )
        hard_failure = False
    elif total_candidates:
        gov_status = "WARN"
        gov_message = (
            f"Governance feedback has {total_candidates} candidate(s)"
        )
        hard_failure = False
    else:
        gov_status = "PASS"
        gov_message = "Governance feedback has no candidates"
        hard_failure = False

    gates["governance_feedback"] = {
        **_gate(gov_status, gov_message, feedback_issues),
        "hard_failure": hard_failure,
    }

    report = _build_report(
        data_dir=data_dir,
        output_path=output_path,
        gates=gates,
        manifest=manifest,
    )
    return (1 if report["summary"]["gate_status"] == "FAIL" else 0), report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run offline Semantic CI/CD gates for a data pack",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing manifest.json and CSV files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output path for semantic_ci_report.json "
            "(default: <data-pack>/semantic_ci_report.json)"
        ),
    )
    parser.add_argument(
        "--regenerate-mapping",
        action="store_true",
        help="Regenerate mapping_contract.json before validation",
    )
    parser.add_argument(
        "--allow-critical",
        action="store_true",
        help="Return exit 0 when critical governance candidates exist",
    )
    args = parser.parse_args()

    output_path = args.output or (args.data_pack / "semantic_ci_report.json")
    exit_code, report = run_pipeline(
        data_dir=args.data_pack,
        output_path=output_path,
        regenerate_mapping=args.regenerate_mapping,
        allow_critical=args.allow_critical,
    )
    _print_summary(report, output_path)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
