"""Tests for offline dataset binding bridge generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_offline_dataset_binding.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_offline_dataset_binding", SCRIPT_PATH
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
            "table_count": 2,
            "total_rows": 8,
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
                {
                    "table_name": "materials",
                    "csv_file": "materials.csv",
                    "row_count": 5,
                    "primary_key": ["material_id"],
                    "foreign_keys": [],
                    "core_pilot": True,
                    "business_meaning": "Raw material or component.",
                },
            ],
        },
    )


def _write_mapping_contract(data_dir: Path) -> None:
    _write_json(
        data_dir / "mapping_contract.json",
        {
            "contract_version": "1.0",
            "data_pack": "manufacturing",
            "object_type_count": 2,
            "relationship_count": 0,
            "object_type_mappings": [
                {
                    "object_type": "equipment",
                    "source_table": "equipment",
                    "description": "Physical equipment asset.",
                    "core_pilot": True,
                    "primary_key": ["equipment_id"],
                    "column_mappings": [
                        {"source_column": "equipment_id"},
                        {"source_column": "status"},
                    ],
                },
                {
                    "object_type": "material",
                    "source_table": "materials",
                    "description": "Raw material or component.",
                    "core_pilot": True,
                    "primary_key": ["material_id"],
                    "column_mappings": [
                        {"source_column": "material_id"},
                        {"source_column": "abc_class"},
                    ],
                },
            ],
            "relationship_mappings": [],
        },
    )


def _write_model_package(
    data_dir: Path,
    package_status: str = "BUILT",
    derived_classes: list[dict] | None = None,
) -> None:
    derived = derived_classes or [
        {
            "id": "offline-draft-accepted-gov-0001",
            "name": "at_risk_equipment",
            "description": "Accepted derived class candidate for equipment.",
            "source_table": "equipment",
            "payload": {"derived_class": "at_risk_equipment"},
            "evidence_refs": [],
            "review": {"decision": "accept"},
            "hard_reasoning_allowed": False,
        }
    ]
    model_package = None
    if package_status == "BUILT":
        model_package = {
            "schema_version": "1.0",
            "package_status": "offline_built",
            "semantic_hash": "sha256:" + "a" * 64,
            "contract": {
                "schema_version": "1.0",
                "object_types": [],
                "properties": [],
                "link_types": [],
                "action_types": [],
                "derived_classes": derived,
            },
            "source_draft_ids": [item["id"] for item in derived],
            "draft_count": len(derived),
            "quality_status": "PASS",
        }
    _write_json(
        data_dir / "offline_model_package.json",
        {
            "package_artifact_version": "1.0",
            "pipeline": "offline_model_package_bridge",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "package_status": package_status,
                "draft_count": len(derived) if package_status == "BUILT" else 0,
                "derived_class_count": len(derived) if package_status == "BUILT" else 0,
                "source_draft_count": len(derived) if package_status == "BUILT" else 0,
                "hard_reasoning_allowed": False,
                "writes_to_database": False,
            },
            "model_package": model_package,
            "boundaries": {
                "offline_only": True,
                "writes_to_database": False,
                "creates_real_governance_issues": False,
                "publishes_model_package": False,
                "activates_runtime": False,
                "hard_reasoning_allowed": False,
            },
        },
    )


def _write_required_inputs(data_dir: Path) -> None:
    _write_manifest(data_dir)
    _write_mapping_contract(data_dir)


def test_built_model_package_binds_derived_classes_to_manifest_tables(tmp_path):
    mod = _load_module()
    _write_required_inputs(tmp_path)
    _write_model_package(tmp_path)

    result = mod.build_offline_dataset_binding(tmp_path)

    assert result["binding_artifact_version"] == "1.0"
    assert result["pipeline"] == "offline_dataset_binding_bridge"
    assert result["data_pack"] == {
        "path": str(tmp_path),
        "preset": "tiny",
        "seed": 42,
        "table_count": 2,
        "total_rows": 8,
    }
    assert result["summary"] == {
        "binding_status": "BOUND",
        "package_status": "BUILT",
        "semantic_hash": "sha256:" + "a" * 64,
        "table_count": 2,
        "total_rows": 8,
        "binding_count": 1,
        "runtime_query_ready": True,
        "hard_reasoning_allowed": False,
        "writes_to_database": False,
    }
    assert result["package_ref"] == {
        "package_status": "BUILT",
        "semantic_hash": "sha256:" + "a" * 64,
        "source_draft_count": 1,
    }
    assert result["bindings"] == [
        {
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
    ]
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "publishes_model_package": False,
        "activates_runtime": False,
        "hard_reasoning_allowed": False,
        "runtime_query_ready": True,
    }
    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "storage_path" not in serialized


def test_no_built_package_outputs_no_bindable_package(tmp_path):
    mod = _load_module()
    _write_required_inputs(tmp_path)
    _write_model_package(tmp_path, package_status="NO_ACCEPTED_DRAFTS")

    result = mod.build_offline_dataset_binding(tmp_path)

    assert result["summary"]["binding_status"] == "NO_BINDABLE_PACKAGE"
    assert result["summary"]["package_status"] == "NO_ACCEPTED_DRAFTS"
    assert result["summary"]["binding_count"] == 0
    assert result["summary"]["runtime_query_ready"] is False
    assert result["package_ref"] == {
        "package_status": "NO_ACCEPTED_DRAFTS",
        "semantic_hash": None,
        "source_draft_count": 0,
    }
    assert result["bindings"] == []
    assert result["boundaries"]["runtime_query_ready"] is False


def test_missing_manifest_fails_clearly(tmp_path):
    mod = _load_module()
    _write_mapping_contract(tmp_path)
    _write_model_package(tmp_path)

    try:
        mod.build_offline_dataset_binding(tmp_path)
    except FileNotFoundError as exc:
        assert "manifest.json not found" in str(exc)
    else:
        raise AssertionError("expected missing manifest to fail")


def test_write_offline_dataset_binding_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_required_inputs(tmp_path)
    _write_model_package(tmp_path)
    json_path = tmp_path / "binding.json"
    markdown_path = tmp_path / "binding.md"

    result = mod.write_offline_dataset_binding(tmp_path, json_path, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Offline Dataset Binding Bridge" in markdown
    assert "Binding status: `BOUND`" in markdown
    assert "at_risk_equipment" in markdown
    assert "Runtime query ready: `true`" in markdown
