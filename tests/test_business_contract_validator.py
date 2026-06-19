"""Tests for business_contract_validator — Phase 13.2.

6-8 parametrized tests total, organized by validation category.
"""

from __future__ import annotations

import copy

import pytest

from semantic_lighthouse.services.business_contract_validator import (
    validate_business_contract,
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
        "reviewed_by": "user-a",
        "reviewed_at": "2026-06-19T00:00:00Z",
        "review_note": "ok",
    }


def _contract(*items):
    """Build a contract_json from items, routing by draft_type."""
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


# ── test 1: valid full contract → PASS ──────────────────────────────────

def test_valid_full_business_v1_passes():
    """A complete, well-formed business_v1 contract passes with no issues."""
    contract = _contract(
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
              }),
    )
    result = validate_business_contract(contract)
    assert result["status"] == "PASS"
    assert result["error_count"] == 0
    assert result["warning_count"] == 0
    assert result["issues"] == []


# ── test 2: profile + common fields ─────────────────────────────────────

@pytest.mark.parametrize("payload_patch,expected_codes", [
    # contract_profile mismatch
    ({}, ["contract_profile_mismatch"]),
    ({"contract_profile": "knowledge_meta"}, ["contract_profile_mismatch"]),
    ({"contract_profile": None}, ["contract_profile_mismatch"]),
    # api_name
    ({"contract_profile": "business_v1", "api_name": ""},
     ["missing_api_name"]),
    ({"contract_profile": "business_v1", "api_name": "Invalid_Name"},
     ["invalid_api_name"]),
    ({"contract_profile": "business_v1", "api_name": "a" * 65},
     ["invalid_api_name"]),
    ({"contract_profile": "business_v1", "api_name": "_leading"},
     ["invalid_api_name"]),
    # display_name missing → warning (must not leak from base)
    ({"contract_profile": "business_v1", "api_name": "ok_name",
      "primary_key": "eq_id"},
     ["missing_display_name"]),
])
def test_profile_and_common_field_errors(payload_patch, expected_codes):
    """contract_profile, api_name, display_name validation."""
    # Build explicit payload — no leaking defaults
    explicit_payload: dict = {}
    if "contract_profile" not in payload_patch:
        # Omit contract_profile so _item's default gets used (business_v1)
        pass
    explicit_payload.update(payload_patch)

    # Provide defaults only when not testing their absence
    if "api_name" not in explicit_payload:
        explicit_payload["api_name"] = "equipment"
    if ("display_name" not in explicit_payload
            and "missing_display_name" not in expected_codes):
        explicit_payload["display_name"] = "Equipment"

    item = _item("object_type", "equipment", "desc", **explicit_payload)

    # Remove contract_profile when testing its absence
    if ("contract_profile" not in explicit_payload
            and "contract_profile_mismatch" in expected_codes):
        del item["payload"]["contract_profile"]

    contract = _contract(item)

    # Make the contract self-consistent for primary_key when profile is valid
    if payload_patch.get("contract_profile") == "business_v1":
        pp = {"contract_profile": "business_v1", "api_name": "eq_id",
              "display_name": "ID", "object_type": "equipment",
              "value_type": "string", "required": True}
        contract["properties"].append(
            _item("property", "eq_id", "id prop", **pp))

    result = validate_business_contract(contract)
    codes = {i["code"] for i in result["issues"]}
    for ec in expected_codes:
        assert ec in codes, f"Expected {ec} in {codes}"
    if "contract_profile_mismatch" in expected_codes:
        assert result["status"] == "FAIL"


# ── test 3: object type + primary_key ───────────────────────────────────

@pytest.mark.parametrize("ot_payload,prop_payloads,expected_codes", [
    # missing primary_key
    ({"api_name": "eq", "display_name": "E"},
     [{"api_name": "eid", "display_name": "ID", "object_type": "eq",
       "value_type": "string", "required": True}],
     ["missing_primary_key"]),
    # primary_key not found in this OT
    ({"api_name": "eq", "display_name": "E", "primary_key": "nope"},
     [{"api_name": "eid", "display_name": "ID", "object_type": "eq",
       "value_type": "string", "required": True}],
     ["primary_key_not_found"]),
    # primary_key references property in wrong object_type
    ({"api_name": "eq", "display_name": "E", "primary_key": "wo_id"},
     [{"api_name": "eid", "display_name": "ID", "object_type": "eq",
       "value_type": "string", "required": True},
      {"api_name": "wo_id", "display_name": "WOID", "object_type": "wo",
       "value_type": "string", "required": True}],
     ["primary_key_wrong_object_type"]),
    # primary_key references a not-required property (other required exists)
    ({"api_name": "eq", "display_name": "E", "primary_key": "eid"},
     [{"api_name": "eid", "display_name": "ID", "object_type": "eq",
       "value_type": "string", "required": False},
      {"api_name": "name", "display_name": "N", "object_type": "eq",
       "value_type": "string", "required": True}],
     ["primary_key_not_required"]),
    # no required property at all
    ({"api_name": "eq", "display_name": "E", "primary_key": "eid"},
     [{"api_name": "eid", "display_name": "ID", "object_type": "eq",
       "value_type": "string", "required": False}],
     ["no_required_property"]),
])
def test_object_type_primary_key_validation(
    ot_payload, prop_payloads, expected_codes,
):
    """Object Type primary_key validation rules."""
    ot_full = {"contract_profile": "business_v1", **ot_payload}
    ot_item = _item("object_type", ot_payload["api_name"], "desc", **ot_full)
    items = [ot_item]

    # Add a second OT if a property references it
    known_ots = {ot_payload.get("api_name", "eq"), "eq"}
    for pp in prop_payloads:
        ot_ref = pp.get("object_type", "")
        if ot_ref not in known_ots:
            items.append(_item(
                "object_type", ot_ref, f"desc-{ot_ref}",
                contract_profile="business_v1",
                api_name=ot_ref, display_name=ot_ref.upper(),
                primary_key="dummy",
            ))
            known_ots.add(ot_ref)

    for pp in prop_payloads:
        pp_full = {"contract_profile": "business_v1", **pp}
        items.append(_item(
            "property", f"{pp['object_type']}.{pp['api_name']}", "desc",
            **pp_full,
        ))

    contract = _contract(*items)
    result = validate_business_contract(contract)
    codes = {i["code"] for i in result["issues"]}
    for ec in expected_codes:
        assert ec in codes, f"Expected {ec} in {codes}"


# ── test 4: property + link validation ──────────────────────────────────

@pytest.mark.parametrize("draft_type,payload,expected_codes", [
    # property: missing object_type
    ("property", {"api_name": "p1", "display_name": "P1",
     "value_type": "string", "required": True},
     ["missing_object_type_ref"]),
    # property: object_type not found
    ("property", {"api_name": "p1", "display_name": "P1",
     "object_type": "ghost", "value_type": "string", "required": True},
     ["object_type_not_found"]),
    # property: missing value_type
    ("property", {"api_name": "p1", "display_name": "P1",
     "object_type": "equipment", "required": True},
     ["missing_value_type"]),
    # property: invalid value_type
    ("property", {"api_name": "p1", "display_name": "P1",
     "object_type": "equipment", "value_type": "binary", "required": True},
     ["invalid_value_type"]),
    # property: required not a bool
    ("property", {"api_name": "p1", "display_name": "P1",
     "object_type": "equipment", "value_type": "string", "required": "yes"},
     ["missing_required"]),
    # property: valid with all value_types accepted
    ("property", {"api_name": "vt_test", "display_name": "VT",
     "object_type": "equipment", "value_type": "datetime", "required": True},
     []),
    # link: missing cardinality
    ("link_type", {"api_name": "l1", "display_name": "L1",
     "source_object_type": "equipment",
     "target_object_type": "work_order"},
     ["missing_cardinality"]),
    # link: invalid cardinality
    ("link_type", {"api_name": "l1", "display_name": "L1",
     "source_object_type": "equipment",
     "target_object_type": "work_order",
     "cardinality": "one_to_three"},
     ["invalid_cardinality"]),
    # link: source not found
    ("link_type", {"api_name": "l1", "display_name": "L1",
     "source_object_type": "ghost",
     "target_object_type": "work_order",
     "cardinality": "one_to_one"},
     ["object_type_not_found"]),
    # link: target not found
    ("link_type", {"api_name": "l1", "display_name": "L1",
     "source_object_type": "equipment",
     "target_object_type": "ghost",
     "cardinality": "one_to_one"},
     ["object_type_not_found"]),
])
def test_property_link_validation(draft_type, payload, expected_codes):
    """Property value_type/required, Link cardinality validation."""
    ot_equip = _item("object_type", "equipment", "Equipment",
                     contract_profile="business_v1",
                     api_name="equipment", display_name="Equipment",
                     primary_key="eq_id")
    ot_wo = _item("object_type", "work_order", "Work Order",
                  contract_profile="business_v1",
                  api_name="work_order", display_name="Work Order",
                  primary_key="wo_id")
    prop_eq = _item("property", "eq_id", "id",
                    contract_profile="business_v1",
                    api_name="eq_id", display_name="ID",
                    object_type="equipment", value_type="string",
                    required=True)
    prop_wo = _item("property", "wo_id", "id",
                    contract_profile="business_v1",
                    api_name="wo_id", display_name="WO ID",
                    object_type="work_order", value_type="string",
                    required=True)

    full_payload = {"contract_profile": "business_v1", **payload}
    test_item = _item(draft_type, payload.get("api_name", "x"), "desc",
                      **full_payload)
    contract = _contract(ot_equip, ot_wo, prop_eq, prop_wo, test_item)
    result = validate_business_contract(contract)

    if not expected_codes:
        codes = {i["code"] for i in result["issues"]}
        assert not codes, f"Expected no issues, got {codes}"
        return

    codes = {i["code"] for i in result["issues"]}
    for ec in expected_codes:
        assert ec in codes, f"Expected {ec} in {codes} for {payload}"


# ── test 5: action validation ───────────────────────────────────────────

@pytest.mark.parametrize("action_payload,expected_codes", [
    # missing target_object_type
    ({"api_name": "act1", "display_name": "Act",
      "parameters": [], "declared_effects": ["Do thing"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["missing_object_type_ref"]),
    # target not found
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "ghost", "parameters": [],
      "declared_effects": ["Do thing"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["object_type_not_found"]),
    # missing declared_effects
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order", "parameters": [],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["missing_declared_effects"]),
    # empty declared_effects list
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order", "parameters": [],
      "declared_effects": [],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["missing_declared_effects"]),
    # declared_effects with only empty/whitespace strings
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order", "parameters": [],
      "declared_effects": ["  ", ""],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["missing_declared_effects"]),
    # invalid parameter name
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order",
      "parameters": [{"name": "Bad Name!", "value_type": "string",
                      "required": True}],
      "declared_effects": ["Do thing"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["invalid_parameter_name"]),
    # invalid parameter value_type
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order",
      "parameters": [{"name": "x", "value_type": "blob", "required": True}],
      "declared_effects": ["Do thing"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["invalid_parameter_value_type"]),
    # empty parameters → warning
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order", "parameters": [],
      "declared_effects": ["Do thing"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["empty_parameters"]),
    # single declared_effects → warning
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order",
      "parameters": [{"name": "x", "value_type": "string",
                      "required": True}],
      "declared_effects": ["Only one"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["declared_effects_single"]),
    # binding hint in declared_effects → warning
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order",
      "parameters": [{"name": "x", "value_type": "string",
                      "required": True}],
      "declared_effects": ["handler: createWorkOrder", "Audit trail"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["declared_effects_binding_hint"]),
    # parameters: None → only missing_parameters error, no empty_parameters
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order",
      "parameters": None,
      "declared_effects": ["Do thing"],
      "action_contract": {"required_role": "admin",
                          "confirmation_requirement": "always",
                          "evidence_requirement": ["ev"]}},
     ["missing_parameters"]),
    # missing action_contract
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order",
      "parameters": [{"name": "x", "value_type": "string",
                      "required": True}],
      "declared_effects": ["Do thing"]},
     ["missing_action_contract"]),
    # invalid action_contract fields
    ({"api_name": "act1", "display_name": "Act",
      "target_object_type": "work_order",
      "parameters": [{"name": "x", "value_type": "string",
                      "required": True}],
      "declared_effects": ["Do thing"],
      "action_contract": {"required_role": "superuser",
                          "confirmation_requirement": "sometimes",
                          "evidence_requirement": []}},
     ["missing_action_contract"]),
])
def test_action_validation(action_payload, expected_codes):
    """Action: target, parameters, declared_effects, binding hints,
    action_contract."""
    ot_wo = _item("object_type", "work_order", "Work Order",
                  contract_profile="business_v1",
                  api_name="work_order", display_name="Work Order",
                  primary_key="wo_id")
    prop_wo = _item("property", "wo_id", "id",
                    contract_profile="business_v1",
                    api_name="wo_id", display_name="WO ID",
                    object_type="work_order", value_type="string",
                    required=True)

    full_payload = {"contract_profile": "business_v1", **action_payload}
    act_item = _item("action_type", action_payload.get("api_name", "x"),
                     "desc", **full_payload)
    contract = _contract(ot_wo, prop_wo, act_item)
    result = validate_business_contract(contract)

    codes = {i["code"] for i in result["issues"]}
    for ec in expected_codes:
        assert ec in codes, f"Expected {ec} in {codes} for {action_payload}"

    # Regression: parameters=None must NOT also produce empty_parameters
    if action_payload.get("parameters") is None:
        assert "empty_parameters" not in codes, (
            f"parameters=None should not also warn empty_parameters: {codes}"
        )


# ── test 6: duplicate api_name scoping ──────────────────────────────────

def test_duplicate_api_name_scoping():
    """Properties only deduplicate within same object_type.
    Different object_types may reuse api_name. OT/Link/Action
    deduplicate flat within their section."""
    contract = _contract(
        _item("object_type", "equipment", "Equipment",
              api_name="equipment", display_name="Equipment",
              primary_key="equipment_id"),
        _item("object_type", "work_order", "Work Order",
              api_name="work_order", display_name="Work Order",
              primary_key="work_order_id"),
        # Same api_name across different object_types → OK
        _item("property", "equipment.status", "Status",
              api_name="status", display_name="Status",
              object_type="equipment", value_type="string", required=True),
        _item("property", "work_order.status", "Status",
              api_name="status", display_name="Status",
              object_type="work_order", value_type="string", required=True),
        # Required props for primary_key validation
        _item("property", "equipment_id", "ID",
              api_name="equipment_id", display_name="ID",
              object_type="equipment", value_type="string", required=True),
        _item("property", "work_order_id", "ID",
              api_name="work_order_id", display_name="ID",
              object_type="work_order", value_type="string", required=True),
    )
    result = validate_business_contract(contract)
    dupes = [i for i in result["issues"]
             if i["code"] == "duplicate_api_name"]
    assert len(dupes) == 0, f"Expected 0 dupes, got {dupes}"

    # Duplicate within same object_type → ERROR
    contract["properties"].append(
        _item("property", "equipment.status2", "Status 2",
              api_name="status", display_name="Status 2",
              object_type="equipment", value_type="string", required=False))
    result2 = validate_business_contract(contract)
    dupes2 = [i for i in result2["issues"]
              if i["code"] == "duplicate_api_name"]
    assert len(dupes2) >= 1, "Expected duplicate_api_name for same OT"

    # Duplicate OT api_name → ERROR
    contract3 = _contract(
        _item("object_type", "equipment", "Equipment",
              api_name="equipment", display_name="Equipment",
              primary_key="eq_id"),
        _item("object_type", "equipment2", "Equipment 2",
              api_name="equipment", display_name="Equipment 2",
              primary_key="eq_id2"),
        _item("property", "eq_id", "ID",
              api_name="eq_id", display_name="ID",
              object_type="equipment", value_type="string", required=True),
        _item("property", "eq_id2", "ID",
              api_name="eq_id2", display_name="ID",
              object_type="equipment", value_type="string", required=True),
    )
    result3 = validate_business_contract(contract3)
    dupes3 = [i for i in result3["issues"]
              if i["code"] == "duplicate_api_name"]
    assert len(dupes3) >= 1, "Expected duplicate_api_name for OT"


# ── test 7: immutability + deterministic order ──────────────────────────

def test_input_not_mutated_and_output_deterministic():
    """Validator never mutates input. Same input → identical output.
    Issues are in deterministic section order."""
    contract = _contract(
        _item("object_type", "work_order", "WO",
              api_name="work_order", display_name="Work Order",
              primary_key="wo_id"),
        _item("object_type", "equipment", "Equip",
              api_name="equipment", display_name="Equipment",
              primary_key="eq_id"),
        _item("property", "eq_id", "id",
              api_name="eq_id", display_name="ID",
              object_type="equipment", value_type="string", required=True),
        _item("property", "wo_id", "id",
              api_name="wo_id", display_name="WO ID",
              object_type="work_order", value_type="string", required=True),
        # Duplicate api_name to generate issues for order testing
        _item("object_type", "equipment_dup", "Dup",
              api_name="equipment", display_name="Dup",
              primary_key="eq_id"),
    )

    original = copy.deepcopy(contract)

    result1 = validate_business_contract(contract)
    assert contract == original, "Input was mutated"

    result2 = validate_business_contract(contract)
    assert result1 == result2, "Non-deterministic output"

    # Section order: object_types issues before properties issues
    sections = [i["section"] for i in result1["issues"]]
    ot_indices = [j for j, s in enumerate(sections) if s == "object_types"]
    prop_indices = [j for j, s in enumerate(sections) if s == "properties"]
    if ot_indices and prop_indices:
        assert max(ot_indices) < max(prop_indices), (
            "object_types issues must come before properties issues"
        )

    # Test contract without any profile → FAIL
    bad = _contract(
        _item("object_type", "x", "desc",
              api_name="x", display_name="X", primary_key="xid"),
    )
    del bad["object_types"][0]["payload"]["contract_profile"]
    result_bad = validate_business_contract(bad)
    assert result_bad["status"] == "FAIL"
    assert any(i["code"] == "contract_profile_mismatch"
               for i in result_bad["issues"])
