"""Tests for public benchmark governance decision fixtures."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_public_benchmark_decisions.py"
PRECHECK_SCRIPT_PATH = REPO_ROOT / "scripts" / "precheck_governance_review_decisions.py"


def _load_module(name: str, path: Path):
    assert path.is_file(), f"missing script: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_workspace(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_workspace.json",
        {
            "workspace_version": "1.0",
            "pipeline": "governance_candidate_review_workspace",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "total_review_items": 3,
                "pending_review_items": 3,
                "requires_human_review": True,
            },
            "review_items": [
                {
                    "review_item_id": "gov-0001",
                    "candidate": {"recommended_decision": "consider_modeling"},
                    "finding": {
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
                        "table": "equipment",
                        "message": "Equipment classified as at_risk_equipment",
                    },
                    "affected_scope": {
                        "source_table": "equipment",
                        "derived_class": "at_risk_equipment",
                    },
                    "evidence_anchors": [
                        {
                            "source": "rule_validation_report.json",
                            "table": "equipment",
                            "row": "1",
                        }
                    ],
                },
                {
                    "review_item_id": "gov-0002",
                    "candidate": {"recommended_decision": "consider_modeling"},
                    "finding": {
                        "finding_id": "derived_class-0002",
                        "rule_id": "derived_class",
                        "table": "materials",
                        "message": "Material classified as high_value_material",
                    },
                    "affected_scope": {
                        "source_table": "materials",
                        "derived_class": "high_value_material",
                    },
                    "evidence_anchors": [
                        {
                            "source": "rule_validation_report.json",
                            "table": "materials",
                            "row": "210",
                        }
                    ],
                },
                {
                    "review_item_id": "gov-0003",
                    "candidate": {"recommended_decision": "fix_or_explain_data"},
                    "finding": {
                        "finding_id": "quality-0001",
                        "rule_id": "data_quality",
                        "table": "orders",
                        "message": "Missing value",
                    },
                    "affected_scope": {
                        "source_table": "orders",
                        "derived_class": None,
                    },
                    "evidence_anchors": [],
                },
            ],
        },
    )


def test_public_benchmark_decisions_are_explicit_fixture_not_human_review(tmp_path):
    mod = _load_module("build_public_benchmark_decisions", SCRIPT_PATH)
    _write_workspace(tmp_path)

    result = mod.build_public_benchmark_decisions(
        tmp_path,
        benchmark_name="AdventureWorks public benchmark",
    )

    assert result["decision_version"] == "1.0"
    assert result["pipeline"] == "public_benchmark_governance_decisions"
    assert result["review_batch"] == "public-benchmark-fixture"
    assert result["benchmark"] == {
        "name": "AdventureWorks public benchmark",
        "decision_mode": "public_benchmark_fixture",
        "evidence_basis": [
            "public_sample_schema",
            "data_pack_manifest",
            "mapping_contract",
            "rule_validation_report",
            "governance_review_workspace",
        ],
        "not_enterprise_human_review": True,
    }
    assert result["summary"] == {
        "workspace_items": 3,
        "submitted_decisions": 3,
        "accepted_decisions": 2,
        "deferred_decisions": 0,
        "needs_more_evidence_decisions": 1,
    }
    decisions = {item["review_item_id"]: item for item in result["decisions"]}
    assert decisions["gov-0001"]["decision"] == "accept"
    assert decisions["gov-0001"]["reviewer"] == "public_benchmark_fixture"
    assert "public benchmark fixture" in decisions["gov-0001"]["rationale"]
    assert "not a real enterprise human approval" in decisions["gov-0001"][
        "rationale"
    ]
    assert decisions["gov-0003"]["decision"] == "needs_more_evidence"
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "activates_runtime": False,
        "executes_runtime_query": False,
        "auto_accepts_candidates": False,
        "not_enterprise_human_review": True,
        "public_benchmark_fixture_only": True,
    }


def test_public_benchmark_decision_file_passes_existing_precheck(tmp_path):
    mod = _load_module("build_public_benchmark_decisions", SCRIPT_PATH)
    precheck_mod = _load_module(
        "precheck_governance_review_decisions",
        PRECHECK_SCRIPT_PATH,
    )
    _write_workspace(tmp_path)
    output = tmp_path / "governance_review_decisions.json"

    result = mod.write_public_benchmark_decisions(
        tmp_path,
        output,
        tmp_path / "governance_review_decisions.md",
        benchmark_name="AdventureWorks public benchmark",
    )
    precheck = precheck_mod.precheck_governance_review_decisions(tmp_path)

    assert json.loads(output.read_text(encoding="utf-8")) == result
    assert precheck["summary"]["precheck_status"] == "PASS"
    assert precheck["summary"]["ready_for_apply"] is True
    assert precheck["summary"]["submitted_decisions"] == 3
    assert precheck["summary"]["accepted_decisions"] == 2
    assert "source_path" not in json.dumps(result)
    assert "storage_path" not in json.dumps(result)

