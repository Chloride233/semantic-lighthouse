"""Tests for offline runtime query dry-run plan generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_offline_runtime_query_plan.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_offline_runtime_query_plan", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_manifest(data_dir: Path) -> None:
    _write_json(
        data_dir / "manifest.json",
        {
            "manifest_version": "1.0",
            "data_pack": "manufacturing",
            "preset": "tiny",
            "seed": 42,
            "table_count": 1,
            "total_rows": 3,
            "tables": [
                {
                    "table_name": "equipment",
                    "csv_file": "equipment.csv",
                    "row_count": 3,
                    "primary_key": ["equipment_id"],
                    "foreign_keys": [],
                    "core_pilot": True,
                    "business_meaning": "Physical equipment asset.",
                },
            ],
        },
    )


def _write_mapping_contract(data_dir: Path) -> None:
    _write_json(
        data_dir / "mapping_contract.json",
        {
            "contract_version": "1.0",
            "object_type_mappings": [
                {
                    "object_type": "equipment",
                    "source_table": "equipment",
                    "primary_key": ["equipment_id"],
                    "column_mappings": [
                        {
                            "source_column": "equipment_id",
                            "target_property": "equipment_id",
                        },
                        {
                            "source_column": "status",
                            "target_property": "status",
                        },
                    ],
                },
            ],
            "relationship_mappings": [],
        },
    )


def _write_dataset_binding(
    data_dir: Path,
    runtime_query_ready: bool = True,
) -> None:
    binding = {
        "binding_id": "dataset-binding-offline-draft-accepted-gov-0001",
        "draft_id": "offline-draft-accepted-gov-0001",
        "derived_class": "at_risk_equipment",
        "source_table": "equipment",
        "object_type": "equipment",
        "package_semantic_hash": "sha256:" + "a" * 64,
        "table": {
            "table_name": "equipment",
            "csv_file": "equipment.csv",
            "row_count": 3,
            "primary_key": ["equipment_id"],
            "core_pilot": True,
            "business_meaning": "Physical equipment asset.",
        },
        "mapping": {
            "object_type": "equipment",
            "primary_key": ["equipment_id"],
            "column_count": 2,
        },
    }
    bindings = [binding] if runtime_query_ready else []
    status = "BOUND" if runtime_query_ready else "NO_BINDABLE_PACKAGE"
    _write_json(
        data_dir / "offline_dataset_binding.json",
        {
            "binding_artifact_version": "1.0",
            "pipeline": "offline_dataset_binding_bridge",
            "data_pack": {
                "path": str(data_dir),
                "preset": "tiny",
                "seed": 42,
                "table_count": 1,
                "total_rows": 3,
            },
            "summary": {
                "binding_status": status,
                "package_status": "BUILT" if runtime_query_ready else "NO_ACCEPTED_DRAFTS",
                "semantic_hash": (
                    "sha256:" + "a" * 64 if runtime_query_ready else None
                ),
                "table_count": 1,
                "total_rows": 3,
                "binding_count": len(bindings),
                "runtime_query_ready": runtime_query_ready,
                "hard_reasoning_allowed": False,
                "writes_to_database": False,
            },
            "package_ref": {
                "package_status": "BUILT" if runtime_query_ready else "NO_ACCEPTED_DRAFTS",
                "semantic_hash": (
                    "sha256:" + "a" * 64 if runtime_query_ready else None
                ),
                "source_draft_count": len(bindings),
            },
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
        },
    )


def _write_required_inputs(
    data_dir: Path,
    runtime_query_ready: bool = True,
) -> None:
    _write_manifest(data_dir)
    _write_mapping_contract(data_dir)
    _write_dataset_binding(data_dir, runtime_query_ready=runtime_query_ready)


def test_ready_binding_outputs_explain_only_query_plan(tmp_path):
    mod = _load_module()
    _write_required_inputs(tmp_path)

    result = mod.build_offline_runtime_query_plan(tmp_path)

    assert result["query_plan_version"] == "1.0"
    assert result["pipeline"] == "offline_runtime_query_dry_run"
    assert result["summary"] == {
        "query_status": "QUERY_PLANNED",
        "binding_status": "BOUND",
        "binding_count": 1,
        "query_plan_count": 1,
        "runtime_query_ready": True,
        "executes_runtime_query": False,
        "reads_dataset_rows": False,
        "writes_to_database": False,
    }
    assert result["query_plans"] == [
        {
            "plan_id": "offline-query-dataset-binding-offline-draft-accepted-gov-0001",
            "binding_id": "dataset-binding-offline-draft-accepted-gov-0001",
            "object_type": "equipment",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
            "query_request": {
                "object_type": "equipment",
                "fields": ["equipment_id", "status"],
                "filters": {},
                "limit": 20,
                "offset": 0,
                "explain_only": True,
            },
            "explain": {
                "package_semantic_hash": "sha256:" + "a" * 64,
                "selected_fields": ["equipment_id", "status"],
                "filter_field_names": [],
                "table_name": "equipment",
                "csv_file": "equipment.csv",
                "row_count": 3,
                "primary_key": ["equipment_id"],
            },
            "execution": {
                "mode": "dry_run_only",
                "returns_rows": False,
                "reason": (
                    "Requires DB-backed accepted package, active dataset "
                    "binding, and runtime audit before execution."
                ),
            },
        }
    ]
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "reads_dataset_rows": False,
        "executes_runtime_query": False,
        "creates_audit_records": False,
        "activates_runtime": False,
        "hard_reasoning_allowed": False,
        "requires_db_backed_package": True,
        "requires_active_dataset_binding": True,
    }
    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "storage_path" not in serialized


def test_not_ready_binding_outputs_no_query_ready_report(tmp_path):
    mod = _load_module()
    _write_required_inputs(tmp_path, runtime_query_ready=False)

    result = mod.build_offline_runtime_query_plan(tmp_path)

    assert result["summary"]["query_status"] == "NO_RUNTIME_QUERY_READY"
    assert result["summary"]["binding_status"] == "NO_BINDABLE_PACKAGE"
    assert result["summary"]["query_plan_count"] == 0
    assert result["summary"]["runtime_query_ready"] is False
    assert result["query_plans"] == []
    assert result["readiness_issues"] == [
        {
            "code": "dataset_binding_not_ready",
            "severity": "info",
            "message": (
                "offline_dataset_binding.json is not runtime-query-ready."
            ),
        }
    ]


def test_missing_dataset_binding_fails_clearly(tmp_path):
    mod = _load_module()
    _write_manifest(tmp_path)
    _write_mapping_contract(tmp_path)

    try:
        mod.build_offline_runtime_query_plan(tmp_path)
    except FileNotFoundError as exc:
        assert "offline_dataset_binding.json not found" in str(exc)
    else:
        raise AssertionError("expected missing dataset binding to fail")


def test_write_offline_runtime_query_plan_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_required_inputs(tmp_path)
    json_path = tmp_path / "runtime_query_plan.json"
    markdown_path = tmp_path / "runtime_query_plan.md"

    result = mod.write_offline_runtime_query_plan(
        tmp_path,
        json_path,
        markdown_path,
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Offline Runtime Query Dry Run" in markdown
    assert "Query status: `QUERY_PLANNED`" in markdown
    assert "equipment" in markdown
    assert "Executes runtime query: `false`" in markdown
