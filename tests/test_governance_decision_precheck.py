"""Tests for offline governance decision precheck."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "precheck_governance_review_decisions.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "precheck_governance_review_decisions", SCRIPT_PATH
    )
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
                "total_review_items": 2,
                "pending_review_items": 2,
                "requires_human_review": True,
            },
            "review_items": [
                {
                    "review_item_id": "gov-0001",
                    "affected_scope": {
                        "source_table": "equipment",
                        "derived_class": "at_risk_equipment",
                    },
                },
                {
                    "review_item_id": "gov-0002",
                    "affected_scope": {
                        "source_table": "materials",
                        "derived_class": "high_value_material",
                    },
                },
            ],
        },
    )


def _write_valid_decisions(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_decisions.json",
        {
            "decision_version": "1.0",
            "review_batch": "tiny-review",
            "decisions": [
                {
                    "review_item_id": "gov-0001",
                    "decision": "accept",
                    "reviewer": "alice",
                    "reviewed_at": "2026-07-09T08:00:00+00:00",
                    "rationale": "Useful pilot class.",
                },
                {
                    "review_item_id": "gov-0002",
                    "decision": "reject",
                    "reviewer": "alice",
                    "reviewed_at": "2026-07-09T08:05:00+00:00",
                    "rationale": "Insufficient evidence.",
                },
            ],
        },
    )


def test_valid_decisions_pass_precheck(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_valid_decisions(tmp_path)

    result = mod.precheck_governance_review_decisions(tmp_path)

    assert result["precheck_version"] == "1.0"
    assert result["pipeline"] == "governance_review_decision_precheck"
    assert result["summary"] == {
        "precheck_status": "PASS",
        "workspace_items": 2,
        "submitted_decisions": 2,
        "accepted_decisions": 1,
        "rejected_decisions": 1,
        "deferred_decisions": 0,
        "needs_more_evidence_decisions": 0,
        "undecided_items": 0,
        "error_count": 0,
        "warning_count": 0,
        "ready_for_apply": True,
        "writes_to_database": False,
    }
    assert result["findings"] == []
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "hard_reasoning_allowed": False,
        "precheck_only": True,
    }


def test_partial_valid_decisions_warn_but_are_applyable(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_json(
        tmp_path / "governance_review_decisions.json",
        {
            "decision_version": "1.0",
            "decisions": [
                {
                    "review_item_id": "gov-0001",
                    "decision": "defer",
                    "reviewer": "alice",
                    "reviewed_at": "2026-07-09T08:00:00+00:00",
                    "rationale": "Needs a manufacturing steward review.",
                }
            ],
        },
    )

    result = mod.precheck_governance_review_decisions(tmp_path)

    assert result["summary"]["precheck_status"] == "WARN"
    assert result["summary"]["submitted_decisions"] == 1
    assert result["summary"]["undecided_items"] == 1
    assert result["summary"]["ready_for_apply"] is True
    assert result["findings"] == [
        {
            "severity": "WARN",
            "code": "undecided_items",
            "message": "1 workspace item(s) have no submitted decision.",
        }
    ]


def test_invalid_decisions_fail_precheck(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_json(
        tmp_path / "governance_review_decisions.json",
        {
            "decision_version": "1.0",
            "decisions": [
                {
                    "review_item_id": "gov-9999",
                    "decision": "accept",
                    "reviewer": "alice",
                    "reviewed_at": "2026-07-09T08:00:00+00:00",
                    "rationale": "Unknown id.",
                },
                {
                    "review_item_id": "gov-0001",
                    "decision": "approve",
                    "reviewer": "alice",
                    "reviewed_at": "2026-07-09T08:05:00+00:00",
                    "rationale": "Invalid decision.",
                },
                {
                    "review_item_id": "gov-0002",
                    "decision": "accept",
                    "reviewer": None,
                    "reviewed_at": None,
                    "rationale": None,
                },
            ],
        },
    )

    result = mod.precheck_governance_review_decisions(tmp_path)

    assert result["summary"]["precheck_status"] == "FAIL"
    assert result["summary"]["error_count"] == 5
    assert result["summary"]["ready_for_apply"] is False
    assert result["findings"] == [
        {
            "severity": "ERROR",
            "code": "unknown_review_item_id",
            "review_item_id": "gov-9999",
            "message": "unknown review_item_id: gov-9999",
        },
        {
            "severity": "ERROR",
            "code": "invalid_decision",
            "review_item_id": "gov-0001",
            "message": "invalid decision for gov-0001: approve",
        },
        {
            "severity": "ERROR",
            "code": "accept_requires_rationale",
            "review_item_id": "gov-0002",
            "message": "accept decision requires rationale: gov-0002",
        },
        {
            "severity": "ERROR",
            "code": "missing_reviewer",
            "review_item_id": "gov-0002",
            "message": "decision requires reviewer: gov-0002",
        },
        {
            "severity": "ERROR",
            "code": "missing_reviewed_at",
            "review_item_id": "gov-0002",
            "message": "decision requires reviewed_at: gov-0002",
        },
    ]


def test_template_file_fails_precheck_until_filled(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_json(
        tmp_path / "governance_review_decisions_template.json",
        {
            "template_version": "1.0",
            "decisions": [
                {
                    "review_item_id": "gov-0001",
                    "decision": None,
                    "reviewer": None,
                    "reviewed_at": None,
                    "rationale": None,
                }
            ],
        },
    )

    result = mod.precheck_governance_review_decisions(
        tmp_path,
        tmp_path / "governance_review_decisions_template.json",
    )

    assert result["summary"]["precheck_status"] == "FAIL"
    assert result["summary"]["ready_for_apply"] is False
    assert result["findings"][0] == {
        "severity": "ERROR",
        "code": "invalid_decision",
        "review_item_id": "gov-0001",
        "message": "invalid decision for gov-0001: None",
    }


def test_write_precheck_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_valid_decisions(tmp_path)
    json_path = tmp_path / "precheck.json"
    markdown_path = tmp_path / "precheck.md"

    result = mod.write_decision_precheck(
        tmp_path,
        json_path,
        markdown_path,
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Governance Review Decision Precheck" in markdown
    assert "Precheck status: `PASS`" in markdown
    assert "Ready for apply: `true`" in markdown
    assert "Writes to database: `false`" in markdown
