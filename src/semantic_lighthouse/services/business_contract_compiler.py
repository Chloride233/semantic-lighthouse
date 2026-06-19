"""Business contract compiler — derive stable manifest from validated packages.

Phase 13.3: transforms a Phase 12 OntologyModelPackage into a compiled
business manifest with semantic_hash. No persistence, no API, no DB.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from semantic_lighthouse.models import OntologyModelPackage
from semantic_lighthouse.services.business_contract_validator import (
    validate_business_contract,
)


class BusinessContractCompilationError(Exception):
    """Raised when validation fails — compilation blocked."""

    def __init__(self, message: str, validation_result: dict):
        self.validation_result = validation_result
        super().__init__(message)


# Fields allowed in compiled output per entity_type.
OT_FIELDS = frozenset({
    "entity_type", "api_name", "display_name", "description", "primary_key",
})
PROP_FIELDS = frozenset({
    "entity_type", "api_name", "display_name", "description",
    "object_type", "value_type", "required",
})
LINK_FIELDS = frozenset({
    "entity_type", "api_name", "display_name", "description",
    "source_object_type", "target_object_type", "cardinality",
})
ACTION_FIELDS = frozenset({
    "entity_type", "api_name", "display_name", "description",
    "target_object_type", "parameters", "declared_effects",
    "action_contract",
})


def compile_business_contract(package: OntologyModelPackage) -> dict:
    """Derive a stable compiled business manifest from a Phase 12 package.

    1. Validate business_v1 contract (FAIL raises error).
    2. Compile each entity with field whitelist.
    3. Sort deterministically.
    4. Compute semantic_hash from business arrays only.

    Returns: {"manifest": {...}, "provenance": {...},
              "object_types": [...], "properties": [...],
              "link_types": [...], "action_types": [...]}

    Raises BusinessContractCompilationError if validation fails.
    """
    # ── Pre-compile validation ──────────────────────────────────────
    validation = validate_business_contract(package.contract_json)
    if validation["status"] == "FAIL":
        raise BusinessContractCompilationError(
            f"Cannot compile: {validation['error_count']} validation error(s)",
            validation,
        )

    # ── Compile each entity ─────────────────────────────────────────
    contract = package.contract_json
    compiled_ots = _compile_entities(
        contract.get("object_types", []) or [], OT_FIELDS, "object_type",
    )
    compiled_props = _compile_entities(
        contract.get("properties", []) or [], PROP_FIELDS, "property",
    )
    compiled_links = _compile_entities(
        contract.get("link_types", []) or [], LINK_FIELDS, "link_type",
    )
    compiled_actions = _compile_entities(
        contract.get("action_types", []) or [], ACTION_FIELDS, "action_type",
    )

    # ── Deterministic sort ──────────────────────────────────────────
    compiled_ots.sort(key=lambda e: e["api_name"])
    # Properties: by (object_type, api_name)
    compiled_props.sort(key=lambda e: (e["object_type"], e["api_name"]))
    compiled_links.sort(key=lambda e: e["api_name"])
    compiled_actions.sort(key=lambda e: e["api_name"])
    # Action parameters: by name within each action
    for act in compiled_actions:
        if isinstance(act.get("parameters"), list):
            act["parameters"].sort(key=lambda p: p.get("name", ""))

    # ── semantic_hash ───────────────────────────────────────────────
    content = {
        "object_types": compiled_ots,
        "properties": compiled_props,
        "link_types": compiled_links,
        "action_types": compiled_actions,
    }
    canonical = json.dumps(
        content, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    hex_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    semantic_hash = f"sha256:{hex_digest}"

    return {
        "manifest": {
            "contract_profile": "business_v1",
            "schema_version": "1.0",
            "semantic_hash": semantic_hash,
        },
        "provenance": {
            "source_package_id": package.id,
            "source_package_version": package.version,
            "source_content_hash": package.content_hash,
        },
        "object_types": compiled_ots,
        "properties": compiled_props,
        "link_types": compiled_links,
        "action_types": compiled_actions,
    }


def _compile_entities(
    items: list[dict], allowed_fields: frozenset, entity_type: str,
) -> list[dict]:
    """Compile a list of contract_json items into whitelisted entities."""
    result: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            payload = {}

        entity: dict[str, Any] = {"entity_type": entity_type}

        # api_name from payload.api_name (NOT root name)
        an = payload.get("api_name")
        if isinstance(an, str) and an.strip():
            entity["api_name"] = an.strip()

        # display_name from payload.display_name
        dn = payload.get("display_name")
        if isinstance(dn, str) and dn.strip():
            entity["display_name"] = dn.strip()

        # description from root description
        desc = item.get("description")
        if isinstance(desc, str) and desc.strip():
            entity["description"] = desc.strip()

        # ── Type-specific fields ────────────────────────────────────
        if entity_type == "object_type":
            pk = payload.get("primary_key")
            if isinstance(pk, str) and pk.strip():
                entity["primary_key"] = pk.strip()

        elif entity_type == "property":
            ot = payload.get("object_type")
            if isinstance(ot, str) and ot.strip():
                entity["object_type"] = ot.strip()
            vt = payload.get("value_type")
            if isinstance(vt, str) and vt.strip():
                entity["value_type"] = vt.strip()
            entity["required"] = bool(payload.get("required"))

        elif entity_type == "link_type":
            for fld in ("source_object_type", "target_object_type", "cardinality"):
                val = payload.get(fld)
                if isinstance(val, str) and val.strip():
                    entity[fld] = val.strip()

        elif entity_type == "action_type":
            tgt = payload.get("target_object_type")
            if isinstance(tgt, str) and tgt.strip():
                entity["target_object_type"] = tgt.strip()
            # parameters — copy with name/value_type/required only
            params = payload.get("parameters")
            if isinstance(params, list):
                entity["parameters"] = [
                    {
                        "name": p.get("name", "") if isinstance(p, dict) else "",
                        "value_type": (
                            p.get("value_type", "")
                            if isinstance(p, dict) else ""
                        ),
                        "required": bool(
                            p.get("required")
                        ) if isinstance(p, dict) else False,
                    }
                    for p in params if isinstance(p, dict)
                ]
            else:
                entity["parameters"] = []
            # declared_effects — preserve manual order
            effects = payload.get("declared_effects")
            if isinstance(effects, list):
                entity["declared_effects"] = [
                    e for e in effects if isinstance(e, str) and e.strip()
                ]
            else:
                entity["declared_effects"] = []
            # action_contract from top-level item (set by Phase 12 builder)
            ac = item.get("action_contract")
            if isinstance(ac, dict):
                entity["action_contract"] = dict(ac)

        # ── Enforce field whitelist ─────────────────────────────────
        entity = {k: v for k, v in entity.items() if k in allowed_fields}

        result.append(entity)

    return result
