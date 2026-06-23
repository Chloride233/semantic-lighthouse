"""Runtime contract helpers — latest package lookup and compiled contract context.

Extracted from services/runtime.py per R1B.
No API, permission, migration, or query semantic changes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import OntologyModelPackage
from semantic_lighthouse.services.business_contract_compiler import (
    compile_business_contract,
)


def _get_latest_project_package(
    db: Session, group_id: str, project_id: str,
) -> OntologyModelPackage | None:
    """Return the latest (highest version) project-scoped package."""
    return db.scalar(
        select(OntologyModelPackage)
        .where(
            OntologyModelPackage.group_id == group_id,
            OntologyModelPackage.scope_key == f"project:{project_id}",
        )
        .order_by(OntologyModelPackage.version.desc())
        .limit(1)
    )


def _build_contract_context(pkg: OntologyModelPackage) -> dict:
    """Compile the package into a runtime-ready context.

    Returns dict with:
      - manifest: the compiled business manifest
      - semantic_hash: from manifest
      - ot_map: {api_name: {primary_key, ...}}
      - prop_map: {api_name: {object_type, value_type, required}}
      - fields_by_ot: {object_type_api_name: [prop_api_names]}
    """
    compiled = compile_business_contract(pkg)
    manifest = compiled["manifest"]

    ot_map: dict[str, dict] = {}
    for ot in compiled.get("object_types", []):
        an = ot.get("api_name")
        if an:
            ot_map[an] = {
                "primary_key": ot.get("primary_key", ""),
                "display_name": ot.get("display_name", ""),
            }

    prop_map: dict[str, dict] = {}
    fields_by_ot: dict[str, list[str]] = {}
    for prop in compiled.get("properties", []):
        an = prop.get("api_name")
        ot = prop.get("object_type", "")
        vt = prop.get("value_type", "string")
        if an:
            prop_map[an] = {
                "object_type": ot,
                "value_type": vt,
                "required": prop.get("required", False),
            }
            fields_by_ot.setdefault(ot, []).append(an)

    return {
        "manifest": manifest,
        "semantic_hash": manifest.get("semantic_hash", ""),
        "ot_map": ot_map,
        "prop_map": prop_map,
        "fields_by_ot": fields_by_ot,
    }
