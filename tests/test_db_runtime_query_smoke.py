"""Tests for DB-backed runtime query smoke from offline artifacts."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_db_runtime_query_smoke.py"
FEEDBACK_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_semantic_asset_feedback.py"


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


def _write_data_pack(data_dir: Path) -> None:
    (data_dir / "equipment.csv").write_text(
        "equipment_id,status,risk_score\n"
        "EQ-1,active,0.91\n"
        "EQ-2,inactive,0.12\n",
        encoding="utf-8",
    )
    _write_json(
        data_dir / "manifest.json",
        {
            "manifest_version": "1.0",
            "preset": "tiny",
            "seed": 7,
            "table_count": 1,
            "total_rows": 2,
            "tables": [
                {
                    "table_name": "equipment",
                    "csv_file": "equipment.csv",
                    "row_count": 2,
                    "primary_key": ["equipment_id"],
                    "foreign_keys": [],
                    "core_pilot": True,
                    "business_meaning": "Equipment assets",
                }
            ],
        },
    )
    _write_json(
        data_dir / "mapping_contract.json",
        {
            "contract_version": "1.0",
            "object_type_mappings": [
                {
                    "object_type": "equipment",
                    "source_table": "equipment",
                    "description": "Equipment assets",
                    "primary_key": ["equipment_id"],
                    "column_mappings": [
                        {
                            "source_column": "equipment_id",
                            "target_property": "equipment_id",
                            "value_type": "string",
                        },
                        {
                            "source_column": "status",
                            "target_property": "status",
                            "value_type": "string",
                        },
                        {
                            "source_column": "risk_score",
                            "target_property": "risk_score",
                            "value_type": "float",
                        },
                    ],
                }
            ],
            "relationship_mappings": [],
        },
    )
    _write_json(
        data_dir / "offline_runtime_query_plan.json",
        {
            "query_plan_version": "1.0",
            "pipeline": "offline_runtime_query_dry_run",
            "data_pack": {
                "path": str(data_dir),
                "preset": "tiny",
                "seed": 7,
                "table_count": 1,
                "total_rows": 2,
            },
            "summary": {
                "query_status": "QUERY_PLANNED",
                "binding_status": "BOUND",
                "binding_count": 1,
                "query_plan_count": 1,
                "runtime_query_ready": True,
                "executes_runtime_query": False,
                "reads_dataset_rows": False,
                "writes_to_database": False,
            },
            "query_plans": [
                {
                    "plan_id": "offline-query-equipment",
                    "binding_id": "dataset-binding-equipment",
                    "object_type": "equipment",
                    "source_table": "equipment",
                    "query_request": {
                        "object_type": "equipment",
                        "fields": ["equipment_id", "status", "risk_score"],
                        "filters": {},
                        "limit": 20,
                        "offset": 0,
                        "explain_only": False,
                    },
                }
            ],
        },
    )


def test_db_runtime_smoke_executes_query_and_writes_audit(tmp_path):
    mod = _load_module("run_db_runtime_query_smoke", SCRIPT_PATH)
    _write_data_pack(tmp_path)

    result = mod.run_db_runtime_query_smoke(tmp_path, max_plans=1)

    assert result["pipeline"] == "db_runtime_query_smoke"
    assert result["summary"]["runtime_execution_status"] == "PASS"
    assert result["summary"]["executed_query_count"] == 1
    assert result["summary"]["returned_row_count"] == 2
    assert result["summary"]["audit_record_count"] == 1
    assert result["summary"]["executes_runtime_query"] is True
    assert result["summary"]["reads_dataset_rows"] is True
    assert result["summary"]["writes_to_application_database"] is False
    assert result["query_results"][0]["row_count"] == 2
    assert result["query_results"][0]["row_preview"][0] == {
        "equipment_id": "EQ-1",
        "risk_score": 0.91,
        "status": "active",
    }
    assert result["boundaries"] == {
        "temporary_sqlite_only": True,
        "writes_to_application_database": False,
        "creates_real_governance_issues": False,
        "publishes_model_package": False,
        "activates_runtime": False,
        "executes_runtime_query": True,
        "reads_dataset_rows": True,
        "creates_audit_records": True,
    }
    serialized = json.dumps(result)
    assert "storage_path" not in serialized
    assert "source_path" not in serialized
    assert str(tmp_path) not in serialized


def test_db_runtime_smoke_requires_query_planned(tmp_path):
    mod = _load_module("run_db_runtime_query_smoke", SCRIPT_PATH)
    _write_data_pack(tmp_path)
    plan = json.loads(
        (tmp_path / "offline_runtime_query_plan.json").read_text(encoding="utf-8")
    )
    plan["summary"]["query_status"] = "NO_RUNTIME_QUERY_READY"
    plan["query_plans"] = []
    _write_json(tmp_path / "offline_runtime_query_plan.json", plan)

    result = mod.run_db_runtime_query_smoke(tmp_path)

    assert result["summary"]["runtime_execution_status"] == "BLOCKED"
    assert result["summary"]["executed_query_count"] == 0
    assert result["readiness_issues"][0]["code"] == "offline_query_not_ready"


def test_semantic_feedback_closes_runtime_gap_after_db_smoke_pass(tmp_path):
    smoke_mod = _load_module("run_db_runtime_query_smoke", SCRIPT_PATH)
    feedback_mod = _load_module("build_semantic_asset_feedback", FEEDBACK_SCRIPT_PATH)
    _write_data_pack(tmp_path)
    smoke_mod.write_db_runtime_query_smoke(
        tmp_path,
        tmp_path / "db_runtime_query_smoke_report.json",
        tmp_path / "db_runtime_query_smoke_report.md",
        max_plans=1,
    )

    result = feedback_mod.build_semantic_asset_feedback(tmp_path)

    assert result["summary"]["feedback_status"] == "NO_OPEN_FEEDBACK"
    assert result["summary"]["runtime_execution_status"] == "PASS"
    assert result["summary"]["executes_runtime_query"] is True
    assert result["summary"]["creates_audit_records"] is True
    assert result["feedback_items"] == []
