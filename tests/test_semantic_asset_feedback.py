"""Tests for offline semantic asset feedback loop generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_semantic_asset_feedback.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_semantic_asset_feedback", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_runtime_query_plan(
    data_dir: Path,
    query_status: str = "NO_RUNTIME_QUERY_READY",
) -> None:
    query_ready = query_status == "QUERY_PLANNED"
    _write_json(
        data_dir / "offline_runtime_query_plan.json",
        {
            "query_plan_version": "1.0",
            "pipeline": "offline_runtime_query_dry_run",
            "data_pack": {
                "path": str(data_dir),
                "preset": "tiny",
                "seed": 42,
                "table_count": 1,
                "total_rows": 3,
            },
            "summary": {
                "query_status": query_status,
                "binding_status": "BOUND" if query_ready else "NO_BINDABLE_PACKAGE",
                "binding_count": 1 if query_ready else 0,
                "query_plan_count": 1 if query_ready else 0,
                "runtime_query_ready": query_ready,
                "executes_runtime_query": False,
                "reads_dataset_rows": False,
                "writes_to_database": False,
            },
            "readiness_issues": (
                []
                if query_ready
                else [
                    {
                        "code": "dataset_binding_not_ready",
                        "severity": "info",
                        "message": (
                            "offline_dataset_binding.json is not "
                            "runtime-query-ready."
                        ),
                    }
                ]
            ),
            "query_plans": [
                {
                    "plan_id": "offline-query-binding-1",
                    "binding_id": "binding-1",
                    "object_type": "equipment",
                    "source_table": "equipment",
                    "derived_class": "at_risk_equipment",
                }
            ] if query_ready else [],
            "boundaries": {
                "offline_only": True,
                "writes_to_database": False,
                "executes_runtime_query": False,
                "creates_audit_records": False,
                "activates_runtime": False,
            },
        },
    )


def _write_accepted_changes(data_dir: Path, undecided_items: int = 48) -> None:
    _write_json(
        data_dir / "accepted_governance_changes.json",
        {
            "change_version": "1.0",
            "pipeline": "governance_review_decisions",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "workspace_items": undecided_items,
                "submitted_decisions": 0,
                "accepted_decisions": 0,
                "accepted_change_count": 0,
                "undecided_items": undecided_items,
            },
            "accepted_changes": [],
            "boundaries": {
                "offline_only": True,
                "writes_to_database": False,
                "creates_real_governance_issues": False,
                "applies_model_changes": False,
                "publishes_model_package": False,
                "hard_reasoning_allowed": False,
                "requires_human_review": True,
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
                "hard_reasoning_allowed": False,
                "publishes_model_package": False,
            },
            "drafts": [],
        },
    )


def _write_model_package(data_dir: Path, status: str = "NO_ACCEPTED_DRAFTS") -> None:
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
                "hard_reasoning_allowed": False,
                "writes_to_database": False,
            },
            "model_package": None,
        },
    )


def _write_dataset_binding(
    data_dir: Path,
    status: str = "NO_BINDABLE_PACKAGE",
) -> None:
    _write_json(
        data_dir / "offline_dataset_binding.json",
        {
            "binding_artifact_version": "1.0",
            "pipeline": "offline_dataset_binding_bridge",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "binding_status": status,
                "package_status": "BUILT" if status == "BOUND" else "NO_ACCEPTED_DRAFTS",
                "semantic_hash": "sha256:" + "a" * 64 if status == "BOUND" else None,
                "table_count": 1,
                "total_rows": 3,
                "binding_count": 1 if status == "BOUND" else 0,
                "runtime_query_ready": status == "BOUND",
                "hard_reasoning_allowed": False,
                "writes_to_database": False,
            },
            "bindings": [],
        },
    )


def _write_not_ready_chain(data_dir: Path) -> None:
    _write_runtime_query_plan(data_dir, "NO_RUNTIME_QUERY_READY")
    _write_accepted_changes(data_dir, undecided_items=48)
    _write_drafts(data_dir, draft_count=0)
    _write_model_package(data_dir, "NO_ACCEPTED_DRAFTS")
    _write_dataset_binding(data_dir, "NO_BINDABLE_PACKAGE")


def test_not_ready_chain_outputs_semantic_asset_backlog(tmp_path):
    mod = _load_module()
    _write_not_ready_chain(tmp_path)

    result = mod.build_semantic_asset_feedback(tmp_path)

    assert result["feedback_version"] == "1.0"
    assert result["pipeline"] == "semantic_asset_feedback_loop"
    assert result["summary"] == {
        "feedback_status": "BACKLOG_OPEN",
        "runtime_query_ready": False,
        "total_feedback_items": 4,
        "requires_human_review": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "by_severity": {"high": 1, "medium": 3},
    }
    assert [item["feedback_id"] for item in result["feedback_items"]] == [
        "semantic-feedback-human-review-pending",
        "semantic-feedback-no-accepted-drafts",
        "semantic-feedback-no-bindable-package",
        "semantic-feedback-runtime-query-not-ready",
    ]
    first = result["feedback_items"][0]
    assert first == {
        "feedback_id": "semantic-feedback-human-review-pending",
        "target_asset_type": "governance_review_workspace",
        "status": "open",
        "severity": "high",
        "source_artifact": "accepted_governance_changes.json",
        "message": "48 governance review item(s) remain undecided.",
        "recommended_action": (
            "Record human review decisions before building accepted ontology "
            "drafts."
        ),
        "evidence": {
            "undecided_items": 48,
            "accepted_change_count": 0,
        },
    }
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "activates_runtime": False,
        "executes_runtime_query": False,
        "requires_human_review": True,
    }
    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "storage_path" not in serialized


def test_query_planned_still_feedbacks_db_backed_activation_gap(tmp_path):
    mod = _load_module()
    _write_runtime_query_plan(tmp_path, "QUERY_PLANNED")
    _write_accepted_changes(tmp_path, undecided_items=0)
    _write_drafts(tmp_path, draft_count=1)
    _write_model_package(tmp_path, "BUILT")
    _write_dataset_binding(tmp_path, "BOUND")

    result = mod.build_semantic_asset_feedback(tmp_path)

    assert result["summary"]["feedback_status"] == "BACKLOG_OPEN"
    assert result["summary"]["runtime_query_ready"] is True
    assert result["summary"]["total_feedback_items"] == 1
    assert result["feedback_items"] == [
        {
            "feedback_id": "semantic-feedback-db-backed-runtime-required",
            "target_asset_type": "runtime_activation",
            "status": "open",
            "severity": "medium",
            "source_artifact": "offline_runtime_query_plan.json",
            "message": (
                "Offline query plans exist, but no DB-backed runtime query "
                "was executed."
            ),
            "recommended_action": (
                "Promote reviewed package and dataset binding through the "
                "Safety Lane before runtime execution."
            ),
            "evidence": {
                "query_status": "QUERY_PLANNED",
                "query_plan_count": 1,
                "executes_runtime_query": False,
            },
        }
    ]


def test_missing_runtime_query_plan_fails_clearly(tmp_path):
    mod = _load_module()

    try:
        mod.build_semantic_asset_feedback(tmp_path)
    except FileNotFoundError as exc:
        assert "offline_runtime_query_plan.json not found" in str(exc)
    else:
        raise AssertionError("expected missing runtime query plan to fail")


def test_write_semantic_asset_feedback_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_not_ready_chain(tmp_path)
    json_path = tmp_path / "feedback.json"
    markdown_path = tmp_path / "feedback.md"

    result = mod.write_semantic_asset_feedback(
        tmp_path,
        json_path,
        markdown_path,
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Semantic Asset Feedback Loop" in markdown
    assert "Feedback status: `BACKLOG_OPEN`" in markdown
    assert "semantic-feedback-runtime-query-not-ready" in markdown
    assert "Writes to database: `false`" in markdown
