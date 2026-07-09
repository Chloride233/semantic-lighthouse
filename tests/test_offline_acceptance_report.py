"""Tests for offline semantic loop acceptance report generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_offline_acceptance_report.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_offline_acceptance_report", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_semantic_ci(data_dir: Path) -> None:
    _write_json(
        data_dir / "semantic_ci_report.json",
        {
            "report_version": "1.0",
            "pipeline": "semantic_ci",
            "data_pack": {
                "path": str(data_dir),
                "preset": "adventureworks_semantic_v1",
                "seed": None,
                "table_count": 13,
                "total_rows": 187508,
            },
            "summary": {
                "gate_status": "WARN",
                "hard_failures": 0,
                "warnings": 2,
                "total_candidates": 48,
                "critical_candidates": 0,
            },
        },
    )


def _write_review_workspace(data_dir: Path, pending: int = 48) -> None:
    _write_json(
        data_dir / "governance_review_workspace.json",
        {
            "workspace_version": "1.0",
            "pipeline": "governance_candidate_review_workspace",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "total_review_items": 48,
                "pending_review_items": pending,
                "requires_human_review": pending > 0,
            },
        },
    )


def _write_accepted_changes(data_dir: Path, undecided: int = 48) -> None:
    _write_json(
        data_dir / "accepted_governance_changes.json",
        {
            "change_version": "1.0",
            "pipeline": "governance_review_decisions",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "workspace_items": 48,
                "submitted_decisions": 0,
                "accepted_change_count": 0,
                "undecided_items": undecided,
            },
        },
    )


def _write_drafts(data_dir: Path, draft_count: int = 0) -> None:
    _write_json(
        data_dir / "accepted_ontology_drafts.json",
        {
            "draft_artifact_version": "1.0",
            "pipeline": "accepted_ontology_drafts",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "accepted_change_count": draft_count,
                "draft_count": draft_count,
                "derived_class_draft_count": draft_count,
            },
        },
    )


def _write_package(data_dir: Path, status: str = "NO_ACCEPTED_DRAFTS") -> None:
    _write_json(
        data_dir / "offline_model_package.json",
        {
            "package_artifact_version": "1.0",
            "pipeline": "offline_model_package_bridge",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "package_status": status,
                "draft_count": 0 if status != "BUILT" else 1,
                "derived_class_count": 0 if status != "BUILT" else 1,
                "source_draft_count": 0 if status != "BUILT" else 1,
            },
        },
    )


def _write_binding(data_dir: Path, status: str = "NO_BINDABLE_PACKAGE") -> None:
    _write_json(
        data_dir / "offline_dataset_binding.json",
        {
            "binding_artifact_version": "1.0",
            "pipeline": "offline_dataset_binding_bridge",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "binding_status": status,
                "package_status": "BUILT" if status == "BOUND" else "NO_ACCEPTED_DRAFTS",
                "binding_count": 1 if status == "BOUND" else 0,
                "runtime_query_ready": status == "BOUND",
            },
        },
    )


def _write_runtime_plan(
    data_dir: Path,
    status: str = "NO_RUNTIME_QUERY_READY",
) -> None:
    _write_json(
        data_dir / "offline_runtime_query_plan.json",
        {
            "query_plan_version": "1.0",
            "pipeline": "offline_runtime_query_dry_run",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "query_status": status,
                "binding_status": "BOUND" if status == "QUERY_PLANNED" else "NO_BINDABLE_PACKAGE",
                "binding_count": 1 if status == "QUERY_PLANNED" else 0,
                "query_plan_count": 1 if status == "QUERY_PLANNED" else 0,
                "runtime_query_ready": status == "QUERY_PLANNED",
                "executes_runtime_query": False,
            },
        },
    )


def _write_feedback(
    data_dir: Path,
    status: str = "BACKLOG_OPEN",
    item_count: int = 4,
) -> None:
    _write_json(
        data_dir / "semantic_asset_feedback.json",
        {
            "feedback_version": "1.0",
            "pipeline": "semantic_asset_feedback_loop",
            "data_pack": {
                "path": str(data_dir),
                "preset": "adventureworks_semantic_v1",
                "seed": None,
                "table_count": 13,
                "total_rows": 187508,
            },
            "summary": {
                "feedback_status": status,
                "runtime_query_ready": False,
                "total_feedback_items": item_count,
                "requires_human_review": item_count > 0,
            },
        },
    )


def _write_not_ready_chain(data_dir: Path) -> None:
    _write_semantic_ci(data_dir)
    _write_review_workspace(data_dir)
    _write_accepted_changes(data_dir)
    _write_drafts(data_dir)
    _write_package(data_dir)
    _write_binding(data_dir)
    _write_runtime_plan(data_dir)
    _write_feedback(data_dir)


def test_not_ready_chain_outputs_blocked_acceptance_report(tmp_path):
    mod = _load_module()
    _write_not_ready_chain(tmp_path)

    result = mod.build_offline_acceptance_report(tmp_path)

    assert result["acceptance_version"] == "1.0"
    assert result["pipeline"] == "offline_semantic_loop_acceptance"
    assert result["summary"] == {
        "chain_status": "BLOCKED_BY_HUMAN_REVIEW",
        "table_count": 13,
        "total_rows": 187508,
        "semantic_ci_status": "WARN",
        "governance_candidates": 48,
        "pending_review_items": 48,
        "accepted_change_count": 0,
        "draft_count": 0,
        "package_status": "NO_ACCEPTED_DRAFTS",
        "binding_status": "NO_BINDABLE_PACKAGE",
        "query_status": "NO_RUNTIME_QUERY_READY",
        "feedback_status": "BACKLOG_OPEN",
        "feedback_items": 4,
        "ready_for_db_backed_runtime": False,
        "requires_human_review": True,
    }
    assert result["stages"] == [
        {
            "stage": "semantic_ci",
            "status": "WARN",
            "evidence": {
                "hard_failures": 0,
                "total_candidates": 48,
                "critical_candidates": 0,
            },
        },
        {
            "stage": "governance_review",
            "status": "PENDING_REVIEW",
            "evidence": {
                "total_review_items": 48,
                "pending_review_items": 48,
            },
        },
        {
            "stage": "accepted_ontology",
            "status": "NO_ACCEPTED_CHANGES",
            "evidence": {
                "accepted_change_count": 0,
                "draft_count": 0,
                "undecided_items": 48,
            },
        },
        {
            "stage": "model_package",
            "status": "NO_ACCEPTED_DRAFTS",
            "evidence": {
                "source_draft_count": 0,
                "derived_class_count": 0,
            },
        },
        {
            "stage": "dataset_binding",
            "status": "NO_BINDABLE_PACKAGE",
            "evidence": {
                "binding_count": 0,
                "runtime_query_ready": False,
            },
        },
        {
            "stage": "runtime_query",
            "status": "NO_RUNTIME_QUERY_READY",
            "evidence": {
                "query_plan_count": 0,
                "executes_runtime_query": False,
            },
        },
        {
            "stage": "semantic_asset_feedback",
            "status": "BACKLOG_OPEN",
            "evidence": {
                "feedback_items": 4,
                "requires_human_review": True,
            },
        },
    ]
    assert result["acceptance_criteria"] == [
        {
            "criterion": "Semantic CI completed without hard failures",
            "status": "PASS",
        },
        {
            "criterion": "Governance candidates have human decisions",
            "status": "BLOCKED",
        },
        {
            "criterion": "Accepted ontology drafts exist",
            "status": "BLOCKED",
        },
        {
            "criterion": "Offline package and dataset binding are ready",
            "status": "BLOCKED",
        },
        {
            "criterion": "Runtime query is ready for Safety Lane promotion",
            "status": "BLOCKED",
        },
        {
            "criterion": "Semantic asset feedback backlog is generated",
            "status": "PASS",
        },
    ]
    assert result["boundaries"]["writes_to_database"] is False
    assert result["boundaries"]["executes_runtime_query"] is False


def test_query_planned_chain_remains_safety_lane_required(tmp_path):
    mod = _load_module()
    _write_semantic_ci(tmp_path)
    _write_review_workspace(tmp_path, pending=0)
    _write_accepted_changes(tmp_path, undecided=0)
    _write_drafts(tmp_path, draft_count=1)
    _write_package(tmp_path, "BUILT")
    _write_binding(tmp_path, "BOUND")
    _write_runtime_plan(tmp_path, "QUERY_PLANNED")
    _write_feedback(tmp_path, status="BACKLOG_OPEN", item_count=1)

    result = mod.build_offline_acceptance_report(tmp_path)

    assert result["summary"]["chain_status"] == "READY_FOR_SAFETY_LANE"
    assert result["summary"]["ready_for_db_backed_runtime"] is False
    assert result["summary"]["query_status"] == "QUERY_PLANNED"
    assert result["acceptance_criteria"][-2] == {
        "criterion": "Runtime query is ready for Safety Lane promotion",
        "status": "PASS",
    }


def test_missing_semantic_asset_feedback_fails_clearly(tmp_path):
    mod = _load_module()

    try:
        mod.build_offline_acceptance_report(tmp_path)
    except FileNotFoundError as exc:
        assert "semantic_asset_feedback.json not found" in str(exc)
    else:
        raise AssertionError("expected missing semantic asset feedback to fail")


def test_write_offline_acceptance_report_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_not_ready_chain(tmp_path)
    json_path = tmp_path / "acceptance.json"
    markdown_path = tmp_path / "acceptance.md"

    result = mod.write_offline_acceptance_report(
        tmp_path,
        json_path,
        markdown_path,
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Offline Semantic Loop Acceptance Report" in markdown
    assert "Chain status: `BLOCKED_BY_HUMAN_REVIEW`" in markdown
    assert "semantic_asset_feedback" in markdown
    assert "Writes to database: `false`" in markdown
