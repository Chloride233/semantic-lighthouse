"""Tests for AdventureWorks offline ontology seed generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_adventureworks_ontology_seed.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_adventureworks_ontology_seed", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_tiny_artifacts(data_dir: Path) -> None:
    _write_json(
        data_dir / "manifest.json",
        {
            "manifest_version": "1.0",
            "data_pack": "manufacturing",
            "preset": "adventureworks_semantic_v1",
            "seed": None,
            "table_count": 2,
            "total_rows": 3,
            "tables": [
                {"table_name": "materials", "row_count": 2},
                {"table_name": "suppliers", "row_count": 1},
            ],
        },
    )
    _write_json(
        data_dir / "mapping_contract.json",
        {
            "contract_version": "1.0",
            "object_type_mappings": [
                {
                    "object_type": "material",
                    "source_table": "materials",
                    "description": "Raw material",
                    "core_pilot": True,
                    "primary_key": ["material_id"],
                    "column_mappings": [
                        {
                            "source_column": "material_id",
                            "target_property": "material_id",
                            "value_type": "string",
                            "semantic_role": "primary_key",
                            "null_strategy": "forbid",
                        },
                        {
                            "source_column": "abc_class",
                            "target_property": "abc_class",
                            "value_type": "enum",
                            "semantic_role": "category",
                            "null_strategy": "forbid",
                        },
                    ],
                },
                {
                    "object_type": "supplier",
                    "source_table": "suppliers",
                    "description": "Supplier",
                    "core_pilot": True,
                    "primary_key": ["supplier_id"],
                    "column_mappings": [],
                },
            ],
            "relationship_mappings": [
                {
                    "relationship_name": "material_to_supplier",
                    "source_table": "materials",
                    "source_columns": ["supplier_id"],
                    "target_table": "suppliers",
                    "target_columns": ["supplier_id"],
                    "cardinality": "many_to_one",
                    "core_pilot": True,
                    "evidence_source": "manifest foreign_keys",
                }
            ],
        },
    )
    _write_json(
        data_dir / "governance_review_packet.json",
        {
            "packet_version": "1.0",
            "summary": {
                "total_review_items": 1,
                "requires_human_review": True,
            },
            "review_items": [
                {
                    "candidate_id": "gov-0001",
                    "review_owner_role": "ontology_steward",
                    "required_checks": [
                        "confirm_business_meaning",
                        "confirm_not_hard_relation",
                    ],
                    "evidence_anchor": {
                        "source": "rule_validation_report.json",
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
                        "table": "materials",
                        "row": "2",
                        "column": None,
                        "derived_class": "high_value_material",
                    },
                }
            ],
        },
    )
    _write_json(
        data_dir / "semantic_ci_report.json",
        {
            "report_version": "1.0",
            "summary": {
                "gate_status": "WARN",
                "hard_failures": 0,
                "warnings": 1,
                "total_candidates": 1,
                "critical_candidates": 0,
            },
        },
    )


def test_build_ontology_seed_preserves_review_boundaries(tmp_path):
    mod = _load_module()
    _write_tiny_artifacts(tmp_path)

    seed = mod.build_ontology_seed(tmp_path)

    assert seed["seed_version"] == "1.0"
    assert seed["pipeline"] == "adventureworks_ontology_seed"
    assert seed["data_pack"] == {
        "path": str(tmp_path),
        "preset": "adventureworks_semantic_v1",
        "seed": None,
        "table_count": 2,
        "total_rows": 3,
    }
    assert seed["summary"] == {
        "object_type_count": 2,
        "relationship_count": 1,
        "derived_class_count": 1,
        "review_candidate_count": 1,
        "requires_human_review": True,
    }

    material = seed["object_types"][0]
    assert material["object_type"] == "material"
    assert material["governance_status"] == "seed_candidate"
    assert material["properties"][1] == {
        "source_column": "abc_class",
        "target_property": "abc_class",
        "value_type": "enum",
        "semantic_role": "category",
        "null_strategy": "forbid",
    }

    relationship = seed["relationships"][0]
    assert relationship["relationship_name"] == "material_to_supplier"
    assert relationship["governance_layer"] == "contract_fk_candidate"
    assert relationship["hard_reasoning_allowed"] is False
    assert relationship["review_required"] is True

    derived_class = seed["derived_classes"][0]
    assert derived_class["derived_class"] == "high_value_material"
    assert derived_class["source_table"] == "materials"
    assert derived_class["candidate_ids"] == ["gov-0001"]
    assert derived_class["evidence_anchors"] == [
        {
            "source": "rule_validation_report.json",
            "finding_id": "derived_class-0001",
            "rule_id": "derived_class",
            "table": "materials",
            "row": "2",
            "column": None,
            "derived_class": "high_value_material",
        }
    ]

    assert seed["review_requirements"] == {
        "requires_human_review": True,
        "required_roles": ["ontology_steward"],
        "candidate_count": 1,
        "required_checks": [
            "confirm_business_meaning",
            "confirm_not_hard_relation",
        ],
    }
    assert seed["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "publishes_model_package": False,
        "hard_reasoning_allowed": False,
    }


def test_write_ontology_seed_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_tiny_artifacts(tmp_path)
    json_path = tmp_path / "seed.json"
    markdown_path = tmp_path / "seed.md"

    seed = mod.write_ontology_seed(tmp_path, json_path, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8")) == seed
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# AdventureWorks Ontology Seed" in markdown
    assert "material_to_supplier" in markdown
    assert "high_value_material" in markdown
    assert "Hard reasoning allowed: `false`" in markdown
