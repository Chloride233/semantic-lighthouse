"""Phase 13.5 Manufacturing Pilot v1 — full pipeline demo runner.

Usage:
  DATABASE_URL=sqlite+pysqlite:///.tmp/manufacturing-pilot-demo.db \\
  .venv/Scripts/python scripts/run_manufacturing_pilot_demo.py

Pre-requisites:
  1. alembic upgrade head against DATABASE_URL.
  2. Does NOT modify the external knowledge base.
  3. Does NOT call web, LLM, Agent, ERP, MES, or PLC.
  4. Does NOT execute CreateWorkOrder — declared only.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from semantic_lighthouse.database import SessionLocal, engine
from semantic_lighthouse.main import app
from semantic_lighthouse.models import (
    Base,
    Document,
    OntologyEntity,
    OntologyModelPackage,
)

REPORT_PATH = Path("docs/manufacturing-pilot-demo-report.md")
GROUP_NAME = "Manufacturing Pilot Demo v1"
PILOT_BASE = os.environ.get(
    "PILOT_BASE_PATH",
    "proposals/manufacturing-mid-size-ontology-pilot.md",
)

# ── Fixed business model ──────────────────────────────────────────────────

OBJECT_TYPES = [
    ("equipment", "Equipment", "equipment_id",
     "Physical equipment asset on the factory floor"),
    ("work_order", "Work Order", "work_order_id",
     "Maintenance work order for equipment repair or inspection"),
]

PROPERTIES = [
    # Equipment (3)
    ("equipment_id", "equipment", "string", True, "Equipment ID",
     "Unique identifier for the equipment asset"),
    ("name", "equipment", "string", True, "Equipment Name",
     "Human-readable name of the equipment"),
    ("status", "equipment", "string", True, "Status",
     "Current operational status of the equipment"),
    # WorkOrder (3)
    ("work_order_id", "work_order", "string", True, "Work Order ID",
     "Unique identifier for the work order"),
    ("title", "work_order", "string", True, "Title",
     "Brief title describing the work order"),
    ("status", "work_order", "string", True, "Status",
     "Current status of the work order"),
]

LINK_TYPES = [
    ("equipment_work_orders", "Equipment Work Orders",
     "equipment", "work_order", "one_to_many",
     "Each equipment can have many work orders"),
    ("work_order_equipment", "Work Order Equipment",
     "work_order", "equipment", "many_to_one",
     "Each work order belongs to exactly one equipment"),
]

ACTION_TYPES = [
    ("create_work_order", "Create Work Order", "work_order",
     [
         {"name": "title", "value_type": "string", "required": True},
         {"name": "equipment_id", "value_type": "string", "required": True},
         {"name": "priority", "value_type": "string", "required": True},
         {"name": "description", "value_type": "string", "required": False},
     ],
     [
         "Creates a new work order for the specified equipment",
         "Links the work order to the equipment asset",
     ],
     "Allow creation of maintenance work orders"),
]


def _log(msg: str) -> None:
    print(f"[demo] {msg}")


def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        _log("FATAL: DATABASE_URL not set")
        sys.exit(1)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    client = TestClient(app)
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── 1. Register, create group ────────────────────────────────────────
    _log("Registering pilot user...")
    email = "mfg-pilot@semantic-lighthouse.local"
    r_reg = client.post(
        "/auth/register",
        json={"email": email, "password": "Pilot123!", "display_name": "Mfg Pilot"},
    )
    if r_reg.status_code == 201:
        owner_id = r_reg.json()["id"]
    elif r_reg.status_code == 409:
        # Already exists — login then lookup
        r_lk = client.post(
            "/auth/login", json={"email": email, "password": "Pilot123!"},
        )
        assert r_lk.status_code == 200
        owner_id = "?"  # Fallback — email is enough for seed
    else:
        raise SystemExit(f"Register failed: {r_reg.status_code}")
    r_login = client.post(
        "/auth/login", json={"email": email, "password": "Pilot123!"},
    )
    assert r_login.status_code == 200, f"Login failed: {r_login.status_code}"
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}
    _log(f"User ready: {owner_id}")

    r = client.post("/groups", json={"name": GROUP_NAME}, headers=headers)
    assert r.status_code == 201, f"Group create failed: {r.status_code}"
    gid = r.json()["id"]
    _log(f"Group created: {gid}")

    # ── 2. Seed minimal evidence (direct DB) ─────────────────────────────
    _log("Seeding evidence rows...")
    db = SessionLocal()
    evidence_entity_ids: dict[str, str] = {}
    for ent_name, ent_type, _is_equip in [
        ("equipment", "BusinessObject", True),
        ("work_order", "BusinessObject", False),
        ("create_work_order", "BusinessAction", False),
    ]:
        did = f"doc-pilot-{ent_name}"
        db.add(Document(
            id=did, group_id=gid,
            title=f"Pilot Evidence: {ent_name}",
            file_name=f"{ent_name}.md",
            source_path=PILOT_BASE, content_hash=f"h-pilot-{ent_name}",
            raw_content=f"Evidence document for {ent_name}",
            created_by=owner_id, status="ready",
        ))
        eid = f"e-pilot-{ent_name}"
        db.add(OntologyEntity(
            id=eid, group_id=gid, document_id=did,
            title=ent_name, entity_type=ent_type,
            source_path=PILOT_BASE,
        ))
        evidence_entity_ids[ent_name] = eid
    # Also seed for equipment sub-properties
    did_ep = "doc-pilot-equipment-id"
    db.add(Document(
        id=did_ep, group_id=gid,
        title="Pilot Evidence: Equipment ID",
        file_name="equipment-id.md",
        source_path=PILOT_BASE, content_hash="h-pilot-eqid",
        raw_content="Evidence document for equipment ID",
        created_by=owner_id, status="ready",
    ))
    eid_ep = "e-pilot-equipment-id"
    db.add(OntologyEntity(
        id=eid_ep, group_id=gid, document_id=did_ep,
        title="equipment_id", entity_type="BusinessObject",
        source_path=PILOT_BASE,
    ))
    evidence_entity_ids["equipment_id"] = eid_ep
    db.commit()
    _log("Evidence seeded: 4 documents, 4 entities")

    # ── 3. Create 11 drafts via API ──────────────────────────────────────
    _log("Creating 11 business_v1 drafts...")
    draft_ids: list[str] = []

    def _post_draft(draft_type, name, payload, source_key, description=""):
        body = {
            "draft_type": draft_type, "name": name,
            "description": description or f"Pilot {name}",
            "source_entity_id": evidence_entity_ids[source_key],
            "payload": {"contract_profile": "business_v1", **payload},
            "evidence_refs": [
                {"source_path": PILOT_BASE,
                 "note": "Manufacturing mid-size ontology pilot proposal"},
            ],
        }
        r = client.post(
            f"/groups/{gid}/ontology/drafts", json=body, headers=headers,
        )
        if r.status_code != 201:
            _log(f"  FAIL draft {name}: {r.status_code} {r.json()}")
            raise SystemExit(1)
        draft_ids.append(r.json()["id"])
        _log(f"  Created: {draft_type} {name}")

    for api_name, display_name, pk, desc in OBJECT_TYPES:
        _post_draft("object_type", api_name, {
            "api_name": api_name, "display_name": display_name,
            "primary_key": pk,
        }, source_key=api_name, description=desc)

    for api_name, ot, vt, req, display_name, desc in PROPERTIES:
        sk = "equipment_id" if api_name == "equipment_id" else ot
        _post_draft("property", f"{ot}.{api_name}", {
            "api_name": api_name, "display_name": display_name,
            "object_type": ot, "value_type": vt, "required": req,
        }, source_key=sk, description=desc)

    for api_name, display_name, src, tgt, card, desc in LINK_TYPES:
        _post_draft("link_type", api_name, {
            "api_name": api_name, "display_name": display_name,
            "source_object_type": src, "target_object_type": tgt,
            "cardinality": card,
        }, source_key=src, description=desc)

    for api_name, display_name, target, params, effects, desc in ACTION_TYPES:
        _post_draft("action_type", api_name, {
            "api_name": api_name, "display_name": display_name,
            "target_object_type": target,
            "parameters": params,
            "declared_effects": effects,
            "action_contract": {
                "required_role": "admin",
                "confirmation_requirement": "always",
                "evidence_requirement": [
                    "ontology_validation_issue",
                ],
            },
        }, source_key=api_name, description=desc)

    assert len(draft_ids) == 11, f"Expected 11 drafts, got {len(draft_ids)}"
    _log("All 11 drafts created")

    # ── 4. Batch review → accepted ───────────────────────────────────────
    _log("Reviewing all 11 drafts...")
    r = client.post(
        f"/groups/{gid}/ontology/drafts/review-batch",
        json={
            "draft_ids": draft_ids,
            "status": "accepted",
            "review_note": "All business_v1 drafts reviewed for manufacturing pilot",
        },
        headers=headers,
    )
    assert r.status_code == 200, f"Review failed: {r.status_code} {r.json()}"
    review_result = r.json()
    assert review_result["reviewed_count"] == 11
    assert review_result["status"] == "accepted"
    reviewer_id = review_result["reviewed_by"]
    reviewed_at = review_result["reviewed_at"]
    _log(f"Reviewed: {review_result['reviewed_count']} accepted by {reviewer_id}")

    # ── 5. Build package ─────────────────────────────────────────────────
    _log("Building immutable package...")
    r = client.post(
        f"/groups/{gid}/ontology/packages", headers=headers,
    )
    assert r.status_code in (200, 201), f"Build failed: {r.status_code} {r.json()}"
    pkg = r.json()
    pid = pkg["id"]
    quality_status = pkg["quality_status"]
    _log(f"Package v{pkg['version']}: {pid} quality={quality_status} "
         f"created={pkg['created']}")
    lines.append(f"Package build: version={pkg['version']} "
                  f"quality_status={quality_status} created={pkg['created']}")

    # ── 6. Export compiled business contract ─────────────────────────────
    _log("Exporting compiled contract via API...")
    r = client.get(
        f"/groups/{gid}/ontology/packages/{pid}/contract", headers=headers,
    )
    assert r.status_code == 200, f"Contract export failed: {r.status_code}"
    manifest = r.json()
    semantic_hash = manifest["manifest"]["semantic_hash"]
    provenance = manifest["provenance"]
    _log(f"Contract exported: semantic_hash={semantic_hash}")

    # ── 7. Verify counts ─────────────────────────────────────────────────
    assert len(manifest["object_types"]) == 2, (
        f"Expected 2 OTs, got {len(manifest['object_types'])}")
    assert len(manifest["properties"]) == 6, (
        f"Expected 6 props, got {len(manifest['properties'])}")
    assert len(manifest["link_types"]) == 2, (
        f"Expected 2 links, got {len(manifest['link_types'])}")
    assert len(manifest["action_types"]) == 1, (
        f"Expected 1 action, got {len(manifest['action_types'])}")
    _log("Counts verified: 2 OT / 6 Prop / 2 Link / 1 Action")
    lines.append(f"Compiled counts: 2 object_types, 6 properties, "
                  f"2 link_types, {len(manifest['action_types'])} action_type")

    # ── 8. Verify idempotent rebuild ─────────────────────────────────────
    _log("Rebuilding package (should be idempotent)...")
    r2 = client.post(
        f"/groups/{gid}/ontology/packages", headers=headers,
    )
    assert r2.status_code == 200
    pkg2 = r2.json()
    assert pkg2["id"] == pid, f"Expected same package ID: {pid} vs {pkg2['id']}"
    assert pkg2["version"] == pkg["version"]
    assert not pkg2["created"]
    _log("Package rebuild: idempotent (same id, same version)")

    r3 = client.get(
        f"/groups/{gid}/ontology/packages/{pid}/contract", headers=headers,
    )
    assert r3.status_code == 200
    assert r3.json()["manifest"]["semantic_hash"] == semantic_hash
    _log("semantic_hash stable across rebuilds")

    # ── 9. Verify provenance ─────────────────────────────────────────────
    assert provenance["source_package_id"] == pid
    assert provenance["source_package_version"] == pkg["version"]
    lines.append(f"Provenance: package_id={pid} version={pkg['version']}")
    lines.append(f"semantic_hash: {semantic_hash}")

    # ── 10. Verify action is declaration-only ────────────────────────────
    act = manifest["action_types"][0]
    assert "declared_effects" in act
    assert "action_contract" in act
    assert act["action_contract"]["required_role"] == "admin"
    # No executable binding fields
    for forbidden in ("handler", "endpoint", "function", "sql", "tool"):
        for effect in act["declared_effects"]:
            assert forbidden not in effect.lower(), (
                f"declared_effect contains '{forbidden}': {effect}")
    _log("Action verified: declaration-only, no executable binding")
    lines.append("Action: declaration-only, no handler/endpoint/SQL/tool binding")

    # ── 11. Verify audit chain ───────────────────────────────────────────
    # Check draft review audit via API
    r = client.get(
        f"/groups/{gid}/ontology/drafts?status=accepted&limit=20",
        headers=headers,
    )
    assert r.status_code == 200
    accepted = r.json()["drafts"]
    for draft in accepted:
        assert draft["reviewed_by"] is not None, (
            f"Draft {draft['name']} missing reviewed_by")
        assert draft["reviewed_at"] is not None, (
            f"Draft {draft['name']} missing reviewed_at")
        assert draft["status"] == "accepted"
    _log(f"Audit chain verified: {len(accepted)} accepted drafts with reviewer audit")

    # Package creator audit
    db = SessionLocal()
    pkg_row = db.get(OntologyModelPackage, pid)
    assert pkg_row is not None
    assert pkg_row.created_by is not None
    db.close()

    # ── 12. Verify cross-group isolation ─────────────────────────────────
    _log("Testing cross-group isolation...")
    client.post(
        "/auth/register",
        json={"email": "mfg-other@semantic-lighthouse.local",
              "password": "Other123!", "display_name": "Other User"},
    )
    # Continue regardless (409 = already exists)
    r2_login = client.post(
        "/auth/login",
        json={"email": "mfg-other@semantic-lighthouse.local",
              "password": "Other123!"},
    )
    assert r2_login.status_code == 200, f"Other login failed: {r2_login.status_code}"
    other_headers = {
        "Authorization": f"Bearer {r2_login.json()['access_token']}",
    }
    r_iso = client.get(
        f"/groups/{gid}/ontology/packages/{pid}/contract",
        headers=other_headers,
    )
    assert r_iso.status_code == 403, (
        f"Cross-group should be 403, got {r_iso.status_code}")
    _log("Cross-group isolation verified: 403")
    lines.append("Cross-group isolation: 403 confirmed")

    # ── Write report ────────────────────────────────────────────────────
    report = f"""# Manufacturing Pilot Demo v1 — Report

Generated: {now}
Group: {GROUP_NAME} ({gid})

## Pipeline

1. Created 11 business_v1 drafts (2 OT + 6 Property + 2 Link + 1 Action)
2. Batch reviewed → 11 accepted (reviewer: {reviewer_id}, at: {reviewed_at})
3. Built immutable package (id: {pid})
4. Exported compiled contract via API
5. Verified idempotent rebuild
6. Verified cross-group isolation

## Results

- **Package quality**: {quality_status}
- **Compiled counts**: 2 object_types / 6 properties / 2 link_types / 1 action_type
- **semantic_hash**: {semantic_hash}
- **Iterative stability**: semantic_hash identical across rebuilds
- **Audit**: all 11 drafts have reviewed_by/reviewed_at; package has created_by
- **Provenance**: source_package_id={pid} version={pkg['version']}
- **Cross-group isolation**: 403 confirmed
- **Action declaration-only**: no handler/endpoint/SQL/tool binding in declared_effects

## Boundary

- No object instances stored. No ERP/MES/PLC connected.
- CreateWorkOrder declared, never executed.
- No SDK, MCP, Graph RAG, or Agent tooling.
- Independent demo group — does not share data with Phase 12 knowledge_meta group.
- External knowledge base unchanged.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    _log(f"Report written to {REPORT_PATH}")
    _log("Pipeline PASS — all assertions green")


if __name__ == "__main__":
    main()
