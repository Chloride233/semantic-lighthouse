"""Tests for business_contract_compiler — Phase 13.3.

6-8 parametrized tests covering compilation, sorting, hash stability,
error handling, and immutability.
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock

import pytest

from semantic_lighthouse.services.business_contract_compiler import (
    BusinessContractCompilationError,
    compile_business_contract,
)


# ── helpers ──────────────────────────────────────────────────────────────

def _item(draft_type, name, description, **payload):
    """Build a minimal contract_json item."""
    return {
        "id": f"id-{name}",
        "draft_type": draft_type,
        "name": name,
        "description": description,
        "payload": {"contract_profile": "business_v1", **payload},
        "evidence_refs": ["doc-ref"],
        "reviewed_by": "u1",
        "reviewed_at": "2026-06-19T00:00:00Z",
        "review_note": "ok",
    }


def _contract(*items):
    """Build a contract_json from items."""
    result = {
        "schema_version": "1.0",
        "object_types": [],
        "properties": [],
        "link_types": [],
        "action_types": [],
    }
    for item in items:
        dt = item["draft_type"]
        if dt == "object_type":
            result["object_types"].append(item)
        elif dt == "property":
            result["properties"].append(item)
        elif dt == "link_type":
            result["link_types"].append(item)
        elif dt == "action_type":
            result["action_types"].append(item)
    return result


def _package(contract, pkg_id="pkg-1", version=1, content_hash="abc123"):
    """Build a mock OntologyModelPackage."""
    pkg = MagicMock()
    pkg.id = pkg_id
    pkg.version = version
    pkg.content_hash = content_hash
    pkg.contract_json = contract
    return pkg


def _valid_full_contract():
    """Return a complete, well-formed business_v1 contract."""
    return _contract(
        _item("object_type", "equipment", "Physical equipment",
              api_name="equipment", display_name="Equipment",
              primary_key="equipment_id"),
        _item("object_type", "work_order", "Maintenance work order",
              api_name="work_order", display_name="Work Order",
              primary_key="work_order_id"),
        _item("property", "equipment.equipment_id", "Unique equipment ID",
              api_name="equipment_id", display_name="Equipment ID",
              object_type="equipment", value_type="string", required=True),
        _item("property", "equipment.name", "Equipment name",
              api_name="name", display_name="Equipment Name",
              object_type="equipment", value_type="string", required=True),
        _item("property", "equipment.status", "Equipment status",
              api_name="status", display_name="Status",
              object_type="equipment", value_type="string", required=False),
        _item("property", "work_order.work_order_id", "Unique WO ID",
              api_name="work_order_id", display_name="Work Order ID",
              object_type="work_order", value_type="string", required=True),
        _item("property", "work_order.title", "WO title",
              api_name="title", display_name="Title",
              object_type="work_order", value_type="string", required=True),
        _item("property", "work_order.status", "WO status",
              api_name="status", display_name="Status",
              object_type="work_order", value_type="string", required=False),
        _item("link_type", "equipment_wo", "Equipment-WorkOrder link",
              api_name="equipment_work_orders",
              display_name="Equipment Work Orders",
              source_object_type="equipment",
              target_object_type="work_order",
              cardinality="one_to_many"),
        _item("link_type", "wo_equipment", "WorkOrder-Equipment link",
              api_name="work_order_equipment",
              display_name="Work Order Equipment",
              source_object_type="work_order",
              target_object_type="equipment",
              cardinality="many_to_one"),
        _item("action_type", "create_wo", "Create a work order",
              api_name="create_work_order", display_name="Create Work Order",
              target_object_type="work_order",
              parameters=[
                  {"name": "title", "value_type": "string", "required": True},
                  {"name": "equipment_id", "value_type": "string",
                   "required": True},
                  {"name": "priority", "value_type": "string",
                   "required": True},
                  {"name": "description", "value_type": "string",
                   "required": False},
              ],
              declared_effects=[
                  "Creates a new work order for the specified equipment",
                  "Links the work order to the equipment asset",
              ],
              action_contract={
                  "required_role": "admin",
                  "confirmation_requirement": "always",
                  "evidence_requirement": ["ontology_validation_issue"],
              },
              ),
    )


# ── test 1: valid package compiles with correct structure ─────────────────

def test_valid_package_compiles_with_structure():
    """A valid business_v1 package produces manifest, provenance, and
    whitelisted business entities."""
    contract = _valid_full_contract()
    # Top-level action_contract also set (as Phase 12 builder does)
    contract["action_types"][0]["action_contract"] = (
        contract["action_types"][0]["payload"]["action_contract"]
    )
    pkg = _package(contract)

    result = compile_business_contract(pkg)

    # Top-level structure
    assert result["manifest"]["contract_profile"] == "business_v1"
    assert result["manifest"]["schema_version"] == "1.0"
    assert result["manifest"]["semantic_hash"].startswith("sha256:")
    assert len(result["manifest"]["semantic_hash"]) == 71  # "sha256:" + 64
    assert "compiled_at" not in result["manifest"]

    # Provenance
    assert result["provenance"]["source_package_id"] == "pkg-1"
    assert result["provenance"]["source_package_version"] == 1
    assert result["provenance"]["source_content_hash"] == "abc123"

    # Business arrays
    assert len(result["object_types"]) == 2
    assert len(result["properties"]) == 6
    assert len(result["link_types"]) == 2
    assert len(result["action_types"]) == 1

    # Field whitelist: Object Type
    ot = result["object_types"][0]
    assert set(ot.keys()) == {
        "entity_type", "api_name", "display_name", "description", "primary_key",
    }
    assert ot["entity_type"] == "object_type"
    assert ot["api_name"] == "equipment"

    # Field whitelist: Property — no payload leakage
    prop = result["properties"][0]
    assert set(prop.keys()) == {
        "entity_type", "api_name", "display_name", "description",
        "object_type", "value_type", "required",
    }
    assert "observed_value_types" not in prop
    assert "generator" not in prop

    # Field whitelist: Link
    link = result["link_types"][0]
    assert set(link.keys()) == {
        "entity_type", "api_name", "display_name", "description",
        "source_object_type", "target_object_type", "cardinality",
    }

    # Field whitelist: Action
    act = result["action_types"][0]
    assert set(act.keys()) == {
        "entity_type", "api_name", "display_name", "description",
        "target_object_type", "parameters", "declared_effects",
        "action_contract",
    }
    assert act["action_contract"]["required_role"] == "admin"
    # Audit noise removed
    assert "id" not in act
    assert "reviewed_by" not in act
    assert "evidence_refs" not in act
    assert "payload" not in act
    # api_name from payload, not root name
    assert act["api_name"] == "create_work_order"
    # description from root
    assert act["description"] == "Create a work order"


# ── test 2: FAIL validation blocks compilation ────────────────────────────

def test_fail_validation_blocks_compilation():
    """BusinessContractCompilationError raised with full validation result."""
    contract = _contract(
        _item("object_type", "x", "desc",
              api_name="x", display_name="X", primary_key="xid"),
    )
    del contract["object_types"][0]["payload"]["contract_profile"]
    pkg = _package(contract)

    with pytest.raises(BusinessContractCompilationError) as exc_info:
        compile_business_contract(pkg)

    assert "1 validation error" in str(exc_info.value)
    vr = exc_info.value.validation_result
    assert vr["status"] == "FAIL"
    assert vr["error_count"] >= 1
    assert any(
        i["code"] == "contract_profile_mismatch" for i in vr["issues"]
    )


# ── test 3: WARN package still compiles ──────────────────────────────────

def test_warn_package_still_compiles():
    """Warnings don't block compilation — only errors do."""
    contract = _contract(
        _item("object_type", "equipment", "Equipment",
              api_name="equipment", display_name="Equipment",
              primary_key="equipment_id"),
        _item("property", "equipment.equipment_id", "ID",
              api_name="equipment_id", display_name="Equipment ID",
              object_type="equipment", value_type="string", required=True),
        # Action with single declared_effects → WARN
        _item("action_type", "act1", "Action",
              api_name="act1", display_name="Act",
              target_object_type="equipment",
              parameters=[{"name": "x", "value_type": "string",
                           "required": True}],
              declared_effects=["Only one effect"],
              action_contract={"required_role": "admin",
                               "confirmation_requirement": "always",
                               "evidence_requirement": ["ev"]}),
    )
    contract["action_types"][0]["action_contract"] = {
        "required_role": "admin", "confirmation_requirement": "always",
        "evidence_requirement": ["ev"],
    }
    pkg = _package(contract)

    result = compile_business_contract(pkg)
    assert result["manifest"]["semantic_hash"].startswith("sha256:")
    assert len(result["object_types"]) == 1
    assert len(result["action_types"]) == 1


# ── test 4: properties sorted by (object_type, api_name) ──────────────────

def test_properties_sorted_by_object_type_then_api_name():
    """Properties sort: (object_type, api_name). Parameters sort: name.
    declared_effects preserves manual order."""
    contract = _contract(
        _item("object_type", "work_order", "WO",
              api_name="work_order", display_name="Work Order",
              primary_key="work_order_id"),
        _item("object_type", "equipment", "EQ",
              api_name="equipment", display_name="Equipment",
              primary_key="equipment_id"),
        # Properties in deliberately unsorted order
        _item("property", "work_order.title", "T",
              api_name="title", display_name="Title",
              object_type="work_order", value_type="string", required=True),
        _item("property", "equipment.name", "N",
              api_name="name", display_name="Name",
              object_type="equipment", value_type="string", required=True),
        _item("property", "work_order.status", "S",
              api_name="status", display_name="Status",
              object_type="work_order", value_type="string", required=False),
        _item("property", "work_order.work_order_id", "ID",
              api_name="work_order_id", display_name="ID",
              object_type="work_order", value_type="string", required=True),
        _item("property", "equipment.status", "S",
              api_name="status", display_name="Status",
              object_type="equipment", value_type="string", required=False),
        _item("property", "equipment.equipment_id", "ID",
              api_name="equipment_id", display_name="ID",
              object_type="equipment", value_type="string", required=True),
        # Action with out-of-order parameters
        _item("action_type", "act1", "Action",
              api_name="act1", display_name="Act",
              target_object_type="equipment",
              parameters=[
                  {"name": "z_param", "value_type": "string", "required": True},
                  {"name": "a_param", "value_type": "integer",
                   "required": False},
              ],
              declared_effects=["Second", "First"],
              action_contract={"required_role": "admin",
                               "confirmation_requirement": "always",
                               "evidence_requirement": ["ev"]}),
    )
    contract["action_types"][0]["action_contract"] = {
        "required_role": "admin", "confirmation_requirement": "always",
        "evidence_requirement": ["ev"],
    }
    pkg = _package(contract)

    result = compile_business_contract(pkg)

    # OT sorted by api_name
    assert [o["api_name"] for o in result["object_types"]] == [
        "equipment", "work_order",
    ]

    # Properties: (object_type, api_name)
    prop_order = [(p["object_type"], p["api_name"])
                  for p in result["properties"]]
    assert prop_order == [
        ("equipment", "equipment_id"),
        ("equipment", "name"),
        ("equipment", "status"),
        ("work_order", "status"),
        ("work_order", "title"),
        ("work_order", "work_order_id"),
    ]

    # Action parameters sorted by name
    param_names = [p["name"] for p in result["action_types"][0]["parameters"]]
    assert param_names == ["a_param", "z_param"]

    # declared_effects keeps manual order (NOT sorted)
    assert result["action_types"][0]["declared_effects"] == [
        "Second", "First",
    ]


# ── test 5: consistent semantic_hash across different packages ────────────

def test_same_business_content_same_semantic_hash():
    """Different packages, same business definitions → same semantic_hash.
    Provenance differs."""
    contract1 = _contract(
        _item("object_type", "equipment", "Desc",
              api_name="equipment", display_name="Equipment",
              primary_key="eid"),
        _item("property", "equipment.eid", "ID",
              api_name="eid", display_name="ID",
              object_type="equipment", value_type="string", required=True),
    )
    contract2 = copy.deepcopy(contract1)

    pkg1 = _package(contract1, pkg_id="pkg-a", version=1, content_hash="aaa")
    pkg2 = _package(contract2, pkg_id="pkg-b", version=5, content_hash="bbb")

    r1 = compile_business_contract(pkg1)
    r2 = compile_business_contract(pkg2)

    # Same semantic_hash
    assert r1["manifest"]["semantic_hash"] == r2["manifest"]["semantic_hash"]

    # Different provenance
    assert r1["provenance"]["source_package_id"] == "pkg-a"
    assert r2["provenance"]["source_package_id"] == "pkg-b"
    assert r1["provenance"]["source_package_version"] == 1
    assert r2["provenance"]["source_package_version"] == 5
    assert r1["provenance"]["source_content_hash"] == "aaa"
    assert r2["provenance"]["source_content_hash"] == "bbb"


# ── test 6: different business content → different hash ───────────────────

def test_different_content_different_hash():
    """Changing a business field changes semantic_hash."""
    c1 = _contract(
        _item("object_type", "equipment", "Equipment",
              api_name="equipment", display_name="Equipment",
              primary_key="eid"),
        _item("property", "equipment.eid", "ID",
              api_name="eid", display_name="ID",
              object_type="equipment", value_type="string", required=True),
    )
    c2 = _contract(
        _item("object_type", "equipment", "Equipment",
              api_name="equipment", display_name="Equipment",
              primary_key="eid"),
        _item("property", "equipment.eid", "ID",
              api_name="eid", display_name="ID",
              object_type="equipment", value_type="integer", required=True),
    )

    h1 = compile_business_contract(_package(c1))[
        "manifest"]["semantic_hash"]
    h2 = compile_business_contract(_package(c2))[
        "manifest"]["semantic_hash"]
    assert h1 != h2, f"Expected different hashes, got {h1}"


# ── test 7: input not mutated ────────────────────────────────────────────

def test_input_not_mutated():
    """Package and its contract_json are never modified by compilation."""
    contract = _valid_full_contract()
    contract["action_types"][0]["action_contract"] = (
        contract["action_types"][0]["payload"]["action_contract"]
    )
    original_contract = copy.deepcopy(contract)
    pkg = _package(contract)

    compile_business_contract(pkg)

    # Contract JSON unchanged
    assert contract == original_contract, "Package contract_json was mutated"

    # Audit fields still present (not stripped from source)
    ot_item = contract["object_types"][0]
    assert "id" in ot_item
    assert "reviewed_by" in ot_item
    assert "reviewed_at" in ot_item
    assert "evidence_refs" in ot_item
    assert "payload" in ot_item
