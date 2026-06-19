"""Business contract validator — deterministic, pure-function validation.

Phase 13.2: validates a business_v1 contract_json dict against the
business_v1 profile specification (docs/phase13-business-contract-spec.md).
Read-only — no database, no LLM, no mutations, no API.
"""

from __future__ import annotations

import re
from typing import Any

SECTION_ORDER = ["object_types", "properties", "link_types", "action_types"]

VALID_VALUE_TYPES = frozenset({
    "string", "integer", "number", "boolean",
    "date", "datetime", "string_list",
})
VALID_CARDINALITY = frozenset({
    "one_to_one", "one_to_many", "many_to_one", "many_to_many",
})
VALID_ROLES = frozenset({"admin", "owner", "member"})
VALID_CONFIRMATION = frozenset({"always", "conditional", "none"})

API_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
API_NAME_MAX = 64

# Patterns that suggest executable binding in declared_effects text
BINDING_HINT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bhandler:",
        r"\bfunction:",
        r"\bendpoint:",
        r"\bcall_\w+\(",
        r"\binvoke_\w+\(",
        r"\bexecute\b",
        r"\bSELECT\b.*\bFROM\b",
        r"\bINSERT\b.*\bINTO\b",
        r"\bUPDATE\b.*\bSET\b",
        r"\bDELETE\b.*\bFROM\b",
        r"\bCREATE\s+TABLE\b",
        r"\bDROP\s+TABLE\b",
        r"\bALTER\s+TABLE\b",
        r"https?://",
        r"\btool:",
        r"\bmcp:",
    ]
]


def validate_business_contract(contract_json: dict) -> dict:
    """Validate a business_v1 contract_json dict.

    Pure function — no database, no LLM, no mutation, no API.
    Same input always produces identical output (deterministic).

    Args:
        contract_json: Phase 12 contract_json dict with object_types,
                       properties, link_types, action_types arrays.

    Returns:
        {"status": "PASS"|"WARN"|"FAIL",
         "error_count": int, "warning_count": int, "issues": [...]}
    """
    issues: list[dict] = []
    input_dict = _deep_copy_dict(contract_json)

    for section in SECTION_ORDER:
        items = input_dict.get(section)
        if not isinstance(items, list):
            continue
        _validate_section(section, items, input_dict, issues)

    # Deterministic sort
    for i in issues:
        i.setdefault("details", {})

    issues.sort(key=lambda i: (
        SECTION_ORDER.index(i["section"]),
        i.get("sort_key", i["item_id"]),
        i["code"],
        i["field"],
    ))
    for i in issues:
        i.pop("sort_key", None)

    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")

    if error_count > 0:
        status = "FAIL"
    elif warning_count > 0:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }


def _validate_section(
    section: str, items: list, contract: dict, issues: list[dict],
) -> None:
    """Validate all items in one section."""
    if not items:
        return

    # Build lookup sets from the contract
    ot_names: set[str] = set()
    for ot_item in contract.get("object_types", []) or []:
        p = ot_item.get("payload") if isinstance(ot_item, dict) else None
        if not isinstance(p, dict):
            continue
        an = _trimmed_str(p.get("api_name"))
        if an:
            ot_names.add(_casefold(an))

    # Collect property info for primary_key validation
    prop_index: dict[str, list[dict]] = {}  # object_type → [prop_items]
    for prop_item in contract.get("properties", []) or []:
        if not isinstance(prop_item, dict):
            continue
        p = prop_item.get("payload") if isinstance(prop_item, dict) else None
        if not isinstance(p, dict):
            continue
        ot_cf = _casefold(_trimmed_str(p.get("object_type")))
        if ot_cf:
            prop_index.setdefault(ot_cf, []).append(prop_item)

    # Sort items for deterministic output
    sorted_items = sorted(items, key=_item_sort_key)

    for item in sorted_items:
        _validate_item(section, item, ot_names, prop_index, sorted_items, issues)


def _validate_item(
    section: str,
    item: dict,
    ot_names: set[str],
    prop_index: dict[str, list[dict]],
    all_items: list[dict],
    issues: list[dict],
) -> None:
    """Validate a single item. Appends issues in-place."""
    if not isinstance(item, dict):
        return

    item_id = item.get("id", "?")
    payload = item.get("payload") if isinstance(item, dict) else None
    if not isinstance(payload, dict):
        payload = {}

    dt = item.get("draft_type", "")
    sort_key = _item_sort_key(item)

    # ── contract_profile (all items) ────────────────────────────────
    cp = payload.get("contract_profile")
    if not isinstance(cp, str) or cp != "business_v1":
        issues.append(_make_issue(
            "error", "contract_profile_mismatch", section, item_id,
            sort_key, "payload.contract_profile",
            "Draft payload.contract_profile must be 'business_v1'",
        ))
        # Continue checking remaining profile-independent fields
        return

    # ── api_name (all items) ────────────────────────────────────────
    api_name = _trimmed_str(payload.get("api_name"))
    if not api_name:
        issues.append(_make_issue(
            "error", "missing_api_name", section, item_id, sort_key,
            "payload.api_name", "api_name is missing or empty",
        ))
    elif not API_NAME_RE.match(api_name) or len(api_name) > API_NAME_MAX:
        issues.append(_make_issue(
            "error", "invalid_api_name", section, item_id, sort_key,
            "payload.api_name",
            f"api_name '{api_name}' must match ^[a-z][a-z0-9_]*$ "
            f"and be ≤ {API_NAME_MAX} chars",
            details={"api_name": api_name},
        ))

    # ── display_name (all items) ────────────────────────────────────
    display_name = _trimmed_str(payload.get("display_name"))
    if not display_name:
        issues.append(_make_issue(
            "warning", "missing_display_name", section, item_id, sort_key,
            "payload.display_name",
            "display_name is missing or empty — defaults to api_name",
        ))

    # ── description (all items, root field) ─────────────────────────
    desc = _trimmed_str(item.get("description"))
    if not desc:
        issues.append(_make_issue(
            "error", "missing_description", section, item_id, sort_key,
            "description",
            "Root description is missing or empty",
        ))

    # ── duplicate api_name detection ────────────────────────────────
    if api_name:
        _check_duplicate_api_names(
            section, item, all_items, issues, sort_key, api_name,
        )

    # ── Type-specific validation ────────────────────────────────────
    if dt == "object_type":
        _validate_object_type(
            section, item_id, sort_key, payload, api_name,
            ot_names, prop_index, issues,
        )
    elif dt == "property":
        _validate_property(
            section, item_id, sort_key, payload, api_name, ot_names, issues,
        )
    elif dt == "link_type":
        _validate_link_type(
            section, item_id, sort_key, payload, api_name, ot_names, issues,
        )
    elif dt == "action_type":
        _validate_action_type(
            section, item_id, sort_key, payload, api_name, ot_names, issues,
        )


def _validate_object_type(
    section: str, item_id: str, sort_key: str,
    payload: dict, api_name: str,
    ot_names: set[str], prop_index: dict[str, list[dict]],
    issues: list[dict],
) -> None:
    """Validate object_type-specific fields."""
    # primary_key
    pk = _trimmed_str(payload.get("primary_key"))
    if not pk:
        issues.append(_make_issue(
            "error", "missing_primary_key", section, item_id, sort_key,
            "payload.primary_key",
            "primary_key is missing or empty",
        ))
        return  # cannot validate further without primary_key

    # Find properties belonging to this object type
    ot_cf = _casefold(api_name)
    own_props = prop_index.get(ot_cf, [])

    # Check if any required property exists
    has_required = False
    for prop_item in own_props:
        pp = prop_item.get("payload") if isinstance(prop_item, dict) else None
        if isinstance(pp, dict) and pp.get("required") is True:
            has_required = True
            break

    if not has_required:
        issues.append(_make_issue(
            "error", "no_required_property", section, item_id, sort_key,
            "payload.primary_key",
            f"Object Type '{api_name}' has no required properties — "
            f"cannot declare a valid primary_key",
            details={"primary_key": pk},
        ))
        return

    # Find the primary_key property
    pk_cf = _casefold(pk)
    pk_prop = None
    for prop_item in own_props:
        pp = prop_item.get("payload") if isinstance(prop_item, dict) else None
        if not isinstance(pp, dict):
            continue
        pn = _casefold(_trimmed_str(pp.get("api_name")))
        if pn == pk_cf:
            pk_prop = prop_item
            break

    if pk_prop is None:
        # Check if it exists under a different object_type
        found_elsewhere = False
        for _ot_cf, other_props in prop_index.items():
            for op in other_props:
                opp = op.get("payload") if isinstance(op, dict) else None
                if isinstance(opp, dict) and _casefold(
                    _trimmed_str(opp.get("api_name"))
                ) == pk_cf:
                    found_elsewhere = True
                    break
            if found_elsewhere:
                break

        if found_elsewhere:
            issues.append(_make_issue(
                "error", "primary_key_wrong_object_type", section,
                item_id, sort_key, "payload.primary_key",
                f"primary_key '{pk}' references a Property belonging "
                f"to a different Object Type",
                details={"primary_key": pk},
            ))
        else:
            issues.append(_make_issue(
                "error", "primary_key_not_found", section,
                item_id, sort_key, "payload.primary_key",
                f"primary_key '{pk}' does not match any Property api_name "
                f"in Object Type '{api_name}'",
                details={"primary_key": pk},
            ))
    else:
        pp = pk_prop.get("payload") if isinstance(pk_prop, dict) else None
        if isinstance(pp, dict) and pp.get("required") is not True:
            issues.append(_make_issue(
                "error", "primary_key_not_required", section,
                item_id, sort_key, "payload.primary_key",
                f"primary_key '{pk}' references a Property with "
                f"required=false",
                details={"primary_key": pk},
            ))


def _validate_property(
    section: str, item_id: str, sort_key: str,
    payload: dict, api_name: str, ot_names: set[str],
    issues: list[dict],
) -> None:
    """Validate property-specific fields."""
    # object_type
    ot = _trimmed_str(payload.get("object_type"))
    if not ot:
        issues.append(_make_issue(
            "error", "missing_object_type_ref", section, item_id, sort_key,
            "payload.object_type",
            "object_type is missing or empty",
        ))
    elif _casefold(ot) not in ot_names:
        issues.append(_make_issue(
            "error", "object_type_not_found", section, item_id, sort_key,
            "payload.object_type",
            f"object_type '{ot}' not found in package object_types",
            details={"object_type": ot},
        ))

    # value_type
    vt = _trimmed_str(payload.get("value_type"))
    if not vt:
        issues.append(_make_issue(
            "error", "missing_value_type", section, item_id, sort_key,
            "payload.value_type",
            "value_type is missing or empty",
        ))
    elif vt not in VALID_VALUE_TYPES:
        issues.append(_make_issue(
            "error", "invalid_value_type", section, item_id, sort_key,
            "payload.value_type",
            f"value_type '{vt}' is not in v1 allowed set: "
            f"{sorted(VALID_VALUE_TYPES)}",
            details={"value_type": vt, "allowed": sorted(VALID_VALUE_TYPES)},
        ))

    # required
    req = payload.get("required")
    if not isinstance(req, bool):
        issues.append(_make_issue(
            "error", "missing_required", section, item_id, sort_key,
            "payload.required",
            "required must be a boolean (true or false)",
        ))


def _validate_link_type(
    section: str, item_id: str, sort_key: str,
    payload: dict, api_name: str, ot_names: set[str],
    issues: list[dict],
) -> None:
    """Validate link_type-specific fields."""
    # source_object_type
    src = _trimmed_str(payload.get("source_object_type"))
    if not src:
        issues.append(_make_issue(
            "error", "missing_object_type_ref", section, item_id, sort_key,
            "payload.source_object_type",
            "source_object_type is missing or empty",
        ))
    elif _casefold(src) not in ot_names:
        issues.append(_make_issue(
            "error", "object_type_not_found", section, item_id, sort_key,
            "payload.source_object_type",
            f"source_object_type '{src}' not found in package object_types",
            details={"source_object_type": src},
        ))

    # target_object_type
    tgt = _trimmed_str(payload.get("target_object_type"))
    if not tgt:
        issues.append(_make_issue(
            "error", "missing_object_type_ref", section, item_id, sort_key,
            "payload.target_object_type",
            "target_object_type is missing or empty",
        ))
    elif _casefold(tgt) not in ot_names:
        issues.append(_make_issue(
            "error", "object_type_not_found", section, item_id, sort_key,
            "payload.target_object_type",
            f"target_object_type '{tgt}' not found in package object_types",
            details={"target_object_type": tgt},
        ))

    # cardinality
    card = _trimmed_str(payload.get("cardinality"))
    if not card:
        issues.append(_make_issue(
            "error", "missing_cardinality", section, item_id, sort_key,
            "payload.cardinality",
            "cardinality is missing or empty",
        ))
    elif card not in VALID_CARDINALITY:
        issues.append(_make_issue(
            "error", "invalid_cardinality", section, item_id, sort_key,
            "payload.cardinality",
            f"cardinality '{card}' is not in v1 allowed set: "
            f"{sorted(VALID_CARDINALITY)}",
            details={"cardinality": card, "allowed": sorted(VALID_CARDINALITY)},
        ))


def _validate_action_type(
    section: str, item_id: str, sort_key: str,
    payload: dict, api_name: str, ot_names: set[str],
    issues: list[dict],
) -> None:
    """Validate action_type-specific fields."""
    # target_object_type
    tgt = _trimmed_str(payload.get("target_object_type"))
    if not tgt:
        issues.append(_make_issue(
            "error", "missing_object_type_ref", section, item_id, sort_key,
            "payload.target_object_type",
            "target_object_type is missing or empty",
        ))
    elif _casefold(tgt) not in ot_names:
        issues.append(_make_issue(
            "error", "object_type_not_found", section, item_id, sort_key,
            "payload.target_object_type",
            f"target_object_type '{tgt}' not found in package object_types",
            details={"target_object_type": tgt},
        ))

    # parameters
    params = payload.get("parameters")
    params_was_missing = not isinstance(params, list)
    if params_was_missing:
        issues.append(_make_issue(
            "error", "missing_parameters", section, item_id, sort_key,
            "payload.parameters",
            "parameters must be a list",
        ))
        params = []

    if len(params) == 0 and not params_was_missing:
        issues.append(_make_issue(
            "warning", "empty_parameters", section, item_id, sort_key,
            "payload.parameters",
            "Action has no parameters — allowed but flagged for review",
        ))

    for idx, param in enumerate(params):
        if not isinstance(param, dict):
            continue
        _validate_action_param(
            section, item_id, sort_key, param, idx, issues,
        )

    # declared_effects
    effects = payload.get("declared_effects")
    if not isinstance(effects, list) or len(effects) == 0:
        issues.append(_make_issue(
            "error", "missing_declared_effects", section, item_id, sort_key,
            "payload.declared_effects",
            "declared_effects must be a non-empty list of strings",
        ))
        effects = []

    has_non_empty = False
    for effect in effects:
        if isinstance(effect, str) and effect.strip():
            has_non_empty = True
            break
    if effects and not has_non_empty:
        issues.append(_make_issue(
            "error", "missing_declared_effects", section, item_id, sort_key,
            "payload.declared_effects",
            "declared_effects contains only empty strings",
        ))

    if len(effects) == 1 and has_non_empty:
        issues.append(_make_issue(
            "warning", "declared_effects_single", section, item_id, sort_key,
            "payload.declared_effects",
            "declared_effects has only one entry — consider "
            "declaring all intended outcomes",
        ))

    # declared_effects binding hints
    for idx, effect in enumerate(effects):
        if not isinstance(effect, str):
            continue
        for pattern in BINDING_HINT_PATTERNS:
            if pattern.search(effect):
                issues.append(_make_issue(
                    "warning", "declared_effects_binding_hint",
                    section, item_id, sort_key,
                    f"payload.declared_effects[{idx}]",
                    f"declared_effects[{idx}] contains text suggesting "
                    f"executable binding: '{effect[:80]}'",
                    details={"effect_index": idx,
                             "matched_pattern": pattern.pattern},
                ))
                break  # one warning per effect string

    # action_contract
    ac = payload.get("action_contract")
    if not isinstance(ac, dict):
        issues.append(_make_issue(
            "error", "missing_action_contract", section, item_id, sort_key,
            "payload.action_contract",
            "action_contract is missing or not a dict",
        ))
    else:
        _validate_action_contract(
            section, item_id, sort_key, ac, issues,
        )


def _validate_action_param(
    section: str, item_id: str, sort_key: str,
    param: dict, idx: int, issues: list[dict],
) -> None:
    """Validate a single action parameter."""
    # name
    pname = _trimmed_str(param.get("name"))
    if not pname:
        issues.append(_make_issue(
            "error", "invalid_parameter_name", section, item_id, sort_key,
            f"payload.parameters[{idx}].name",
            f"Parameter [{idx}] name is missing or empty",
            details={"parameter_index": idx},
        ))
    elif not API_NAME_RE.match(pname) or len(pname) > API_NAME_MAX:
        issues.append(_make_issue(
            "error", "invalid_parameter_name", section, item_id, sort_key,
            f"payload.parameters[{idx}].name",
            f"Parameter [{idx}] name '{pname}' must match "
            f"^[a-z][a-z0-9_]*$ and be ≤ {API_NAME_MAX} chars",
            details={"parameter_index": idx, "name": pname},
        ))

    # value_type
    pvt = _trimmed_str(param.get("value_type"))
    if not pvt:
        issues.append(_make_issue(
            "error", "invalid_parameter_value_type", section, item_id,
            sort_key, f"payload.parameters[{idx}].value_type",
            f"Parameter [{idx}] value_type is missing or empty",
            details={"parameter_index": idx},
        ))
    elif pvt not in VALID_VALUE_TYPES:
        issues.append(_make_issue(
            "error", "invalid_parameter_value_type", section, item_id,
            sort_key, f"payload.parameters[{idx}].value_type",
            f"Parameter [{idx}] value_type '{pvt}' is not in v1 allowed set",
            details={
                "parameter_index": idx, "value_type": pvt,
                "allowed": sorted(VALID_VALUE_TYPES),
            },
        ))

    # required
    preq = param.get("required")
    if not isinstance(preq, bool):
        issues.append(_make_issue(
            "warning", "missing_required", section, item_id, sort_key,
            f"payload.parameters[{idx}].required",
            f"Parameter [{idx}] required is not a boolean — "
            f"defaulting to false",
            details={"parameter_index": idx},
        ))


def _validate_action_contract(
    section: str, item_id: str, sort_key: str,
    ac: dict, issues: list[dict],
) -> None:
    """Validate action_contract fields."""
    role = ac.get("required_role")
    if not isinstance(role, str) or role not in VALID_ROLES:
        issues.append(_make_issue(
            "error", "missing_action_contract", section, item_id, sort_key,
            "payload.action_contract.required_role",
            f"required_role must be one of {sorted(VALID_ROLES)}, "
            f"got {role!r}",
            details={"required_role": role},
        ))

    confirm = ac.get("confirmation_requirement")
    if not isinstance(confirm, str) or confirm not in VALID_CONFIRMATION:
        issues.append(_make_issue(
            "error", "missing_action_contract", section, item_id, sort_key,
            "payload.action_contract.confirmation_requirement",
            f"confirmation_requirement must be one of "
            f"{sorted(VALID_CONFIRMATION)}, got {confirm!r}",
            details={"confirmation_requirement": confirm},
        ))

    evidence = ac.get("evidence_requirement")
    if not isinstance(evidence, list) or len(evidence) == 0:
        issues.append(_make_issue(
            "error", "missing_action_contract", section, item_id, sort_key,
            "payload.action_contract.evidence_requirement",
            "evidence_requirement must be a non-empty list of strings",
        ))
    else:
        cleaned = [s.strip() for s in evidence if isinstance(s, str)]
        if len(cleaned) != len(evidence) or any(not c for c in cleaned):
            issues.append(_make_issue(
                "error", "missing_action_contract", section, item_id, sort_key,
                "payload.action_contract.evidence_requirement",
                "evidence_requirement elements must be "
                "non-empty strings after trimming",
            ))


def _check_duplicate_api_names(
    section: str, item: dict, all_items: list[dict],
    issues: list[dict], sort_key: str, api_name: str,
) -> None:
    """Check for duplicate api_name within the same section scope."""
    payload = item.get("payload") if isinstance(item, dict) else None
    if not isinstance(payload, dict):
        return

    api_name_cf = _casefold(api_name)
    item_id = item.get("id", "?")

    if section == "properties":
        # Duplicate check is scoped to (object_type, api_name)
        obj_type_cf = _casefold(_trimmed_str(payload.get("object_type")))
        if not obj_type_cf:
            return
        for other in all_items:
            if other is item:
                continue
            op = other.get("payload") if isinstance(other, dict) else None
            if not isinstance(op, dict):
                continue
            other_ot_cf = _casefold(_trimmed_str(op.get("object_type")))
            other_an_cf = _casefold(_trimmed_str(op.get("api_name")))
            if other_ot_cf == obj_type_cf and other_an_cf == api_name_cf:
                issues.append(_make_issue(
                    "error", "duplicate_api_name", section, item_id, sort_key,
                    "payload.api_name",
                    f"Property api_name '{api_name}' duplicates another "
                    f"property in object_type "
                    f"'{payload.get('object_type', '?')}'",
                    details={"api_name": api_name,
                             "object_type": _trimmed_str(
                                 payload.get("object_type"))},
                ))
                return
    else:
        # Flat duplicate check within the section
        for other in all_items:
            if other is item:
                continue
            op = other.get("payload") if isinstance(other, dict) else None
            if not isinstance(op, dict):
                continue
            other_an_cf = _casefold(_trimmed_str(op.get("api_name")))
            if other_an_cf == api_name_cf:
                issues.append(_make_issue(
                    "error", "duplicate_api_name", section, item_id, sort_key,
                    "payload.api_name",
                    f"Duplicate {section.rstrip('s')} api_name: '{api_name}'",
                    details={"api_name": api_name},
                ))
                return


# ── helpers ──────────────────────────────────────────────────────────────


def _make_issue(
    severity: str, code: str, section: str,
    item_id: str, sort_key: str, field: str,
    message: str, details: dict | None = None,
) -> dict:
    """Create a structured issue dict."""
    return {
        "severity": severity,
        "code": code,
        "section": section,
        "item_id": item_id,
        "field": field,
        "message": message,
        "details": details or {},
        "sort_key": sort_key,
    }


def _item_sort_key(item: dict) -> str:
    """Deterministic sort key for an item within its section."""
    if not isinstance(item, dict):
        return "?"
    payload = item.get("payload") if isinstance(item, dict) else None
    api_name = ""
    if isinstance(payload, dict):
        api_name = _trimmed_str(payload.get("api_name"))
    return api_name or item.get("id", "?")


def _casefold(s: str) -> str:
    """Case-normalize for comparison."""
    return s.strip().casefold()


def _trimmed_str(val: Any) -> str:
    """Return trimmed string if val is a string, else empty string."""
    if isinstance(val, str):
        return val.strip()
    return ""


def _deep_copy_dict(d: Any) -> Any:
    """Make a deep copy to ensure input is never mutated."""
    if isinstance(d, dict):
        return {k: _deep_copy_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_deep_copy_dict(v) for v in d]
    return d
