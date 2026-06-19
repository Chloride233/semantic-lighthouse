"""Tests for Phase 13.5 manufacturing pilot demo — verification suite.

5-8 tests covering fixed model counts, full pipeline, evidence audit,
hash idempotency, group isolation, and action declaration-only posture.
"""

from conftest import register_and_login


# ── helpers ──────────────────────────────────────────────────────────────

def _create_group(client, headers, name="T"):
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _seed_evidence(db_session, gid, uid):
    """Seed minimal evidence rows for pilot drafts."""
    from semantic_lighthouse.models import Document, OntologyEntity

    PILOT_BASE = (
        "F:\\ontology-kb\\knowledge-graph\\proposals\\"
        "manufacturing-mid-size-ontology-pilot.md"
    )
    eids: dict[str, str] = {}
    for ent_name in ("equipment", "work_order", "create_work_order",
                      "equipment_id"):
        did = f"d-pilot-{ent_name}"
        db_session.add(Document(
            id=did, group_id=gid, title=f"Evidence: {ent_name}",
            file_name=f"{ent_name}.md",
            source_path=PILOT_BASE, content_hash=f"h-{ent_name}",
            raw_content=f"Evidence for {ent_name}",
            created_by=uid, status="ready",
        ))
        eid = f"e-pilot-{ent_name}"
        db_session.add(OntologyEntity(
            id=eid, group_id=gid, document_id=did,
            title=ent_name, entity_type="BusinessObject",
            source_path=PILOT_BASE,
        ))
        eids[ent_name] = eid
    db_session.commit()
    return eids


def _create_business_v1_drafts(client, gid, headers, eids):
    """Create all 11 pilot drafts via API. Returns list of draft ids."""
    draft_ids: list[str] = []

    def _post(draft_type, name, payload, source_key, description=""):
        r = client.post(
            f"/groups/{gid}/ontology/drafts",
            json={
                "draft_type": draft_type, "name": name,
                "description": description or f"Pilot {name}",
                "source_entity_id": eids[source_key],
                "payload": {"contract_profile": "business_v1", **payload},
                "evidence_refs": [
                    {"source_path": "proposals/manufacturing-pilot.md",
                     "note": "Manufacturing pilot proposal"},
                ],
            },
            headers=headers,
        )
        assert r.status_code == 201, (
            f"Draft {name}: {r.status_code} {r.json()}"
        )
        draft_ids.append(r.json()["id"])

    # 2 Object Types
    _post("object_type", "equipment",
          {"api_name": "equipment", "display_name": "Equipment",
           "primary_key": "equipment_id"},
          "equipment", "Physical equipment asset")
    _post("object_type", "work_order",
          {"api_name": "work_order", "display_name": "Work Order",
           "primary_key": "work_order_id"},
          "work_order", "Maintenance work order")

    # 6 Properties
    for api_name, ot, sk in [
        ("equipment_id", "equipment", "equipment_id"),
        ("name", "equipment", "equipment"),
        ("status", "equipment", "equipment"),
        ("work_order_id", "work_order", "work_order"),
        ("title", "work_order", "work_order"),
        ("status", "work_order", "work_order"),
    ]:
        _post("property", f"{ot}.{api_name}",
              {"api_name": api_name,
               "display_name": api_name.replace("_", " ").title(),
               "object_type": ot, "value_type": "string",
               "required": True},
              sk)

    # 2 Link Types
    _post("link_type", "equipment_work_orders",
          {"api_name": "equipment_work_orders",
           "display_name": "Equipment Work Orders",
           "source_object_type": "equipment",
           "target_object_type": "work_order",
           "cardinality": "one_to_many"},
          "equipment", "Equipment↔WorkOrder link")
    _post("link_type", "work_order_equipment",
          {"api_name": "work_order_equipment",
           "display_name": "Work Order Equipment",
           "source_object_type": "work_order",
           "target_object_type": "equipment",
           "cardinality": "many_to_one"},
          "work_order", "WorkOrder→Equipment link")

    # 1 Action Type
    _post("action_type", "create_work_order",
          {"api_name": "create_work_order",
           "display_name": "Create Work Order",
           "target_object_type": "work_order",
           "parameters": [
               {"name": "title", "value_type": "string", "required": True},
               {"name": "equipment_id", "value_type": "string",
                "required": True},
               {"name": "priority", "value_type": "string", "required": True},
               {"name": "description", "value_type": "string",
                "required": False},
           ],
           "declared_effects": [
               "Creates a new work order",
               "Links the work order to the equipment asset",
           ],
           "action_contract": {
               "required_role": "admin",
               "confirmation_requirement": "always",
               "evidence_requirement": ["ontology_validation_issue"],
           }},
          "create_work_order", "Create maintenance work orders")

    return draft_ids


def _review_all(client, gid, headers, draft_ids):
    r = client.post(
        f"/groups/{gid}/ontology/drafts/review-batch",
        json={"draft_ids": draft_ids, "status": "accepted",
              "review_note": "All business_v1 drafts for manufacturing pilot"},
        headers=headers,
    )
    assert r.status_code == 200, f"Review failed: {r.json()}"
    return r.json()


def _build_package(client, gid, headers):
    r = client.post(f"/groups/{gid}/ontology/packages", headers=headers)
    assert r.status_code in (200, 201)
    return r.json()


def _get_contract(client, gid, pid, headers):
    r = client.get(
        f"/groups/{gid}/ontology/packages/{pid}/contract", headers=headers,
    )
    return r


# ── tests ────────────────────────────────────────────────────────────────


class TestManufacturingPilot:
    """Phase 13.5 manufacturing pilot verification."""

    def test_fixed_model_counts_and_payload(self, client, db_session):
        """Exactly 11 drafts: 2 OT, 6 Prop, 2 Link, 1 Action."""
        u, _, h = register_and_login(client, f"m1{id(db_session)}@t.com")
        gid = _create_group(client, h)
        eids = _seed_evidence(db_session, gid, u["id"])
        draft_ids = _create_business_v1_drafts(client, gid, h, eids)

        assert len(draft_ids) == 11

        # Verify payloads via GET
        r = client.get(
            f"/groups/{gid}/ontology/drafts?limit=20", headers=h,
        )
        drafts = r.json()["drafts"]
        assert len(drafts) == 11

        for d in drafts:
            p = d["payload"]
            assert p.get("contract_profile") == "business_v1", (
                f"Draft {d['name']} missing contract_profile"
            )
            assert "api_name" in p, (
                f"Draft {d['name']} missing api_name"
            )

        # Count by type
        ots = [d for d in drafts if d["draft_type"] == "object_type"]
        props = [d for d in drafts if d["draft_type"] == "property"]
        links = [d for d in drafts if d["draft_type"] == "link_type"]
        actions = [d for d in drafts if d["draft_type"] == "action_type"]
        assert len(ots) == 2
        assert len(props) == 6
        assert len(links) == 2
        assert len(actions) == 1

    def test_full_pipeline_success(self, client, db_session):
        """Draft → review → package → contract → all assertions pass."""
        u, _, h = register_and_login(client, f"m2{id(db_session)}@t.com")
        gid = _create_group(client, h)
        eids = _seed_evidence(db_session, gid, u["id"])
        draft_ids = _create_business_v1_drafts(client, gid, h, eids)

        # Review
        review = _review_all(client, gid, h, draft_ids)
        assert review["reviewed_count"] == 11
        assert review["status"] == "accepted"

        # Package
        pkg = _build_package(client, gid, h)
        assert pkg["id"]
        assert pkg["quality_status"] in ("PASS", "WARN")

        # Contract
        r = _get_contract(client, gid, pkg["id"], h)
        assert r.status_code == 200
        manifest = r.json()
        assert len(manifest["object_types"]) == 2
        assert len(manifest["properties"]) == 6
        assert len(manifest["link_types"]) == 2
        assert len(manifest["action_types"]) == 1
        assert manifest["manifest"]["semantic_hash"].startswith("sha256:")

    def test_evidence_and_review_audit_complete(self, client, db_session):
        """All drafts have evidence_refs and reviewer audit after accept."""
        u, _, h = register_and_login(client, f"m3{id(db_session)}@t.com")
        gid = _create_group(client, h)
        eids = _seed_evidence(db_session, gid, u["id"])
        draft_ids = _create_business_v1_drafts(client, gid, h, eids)
        _review_all(client, gid, h, draft_ids)

        r = client.get(
            f"/groups/{gid}/ontology/drafts?status=accepted&limit=20",
            headers=h,
        )
        drafts = r.json()["drafts"]
        assert len(drafts) == 11

        for d in drafts:
            assert d["evidence_refs"], (
                f"Draft {d['name']} has no evidence_refs"
            )
            assert d["reviewed_by"] is not None, (
                f"Draft {d['name']} not reviewed"
            )
            assert d["reviewed_at"] is not None, (
                f"Draft {d['name']} missing reviewed_at"
            )
            assert d["status"] == "accepted"

        # Package creator audit
        pkg = _build_package(client, gid, h)
        r2 = _get_contract(client, gid, pkg["id"], h)
        assert r2.status_code == 200
        provenance = r2.json()["provenance"]
        assert provenance["source_package_id"] == pkg["id"]

    def test_package_and_hash_idempotent(self, client, db_session):
        """Rebuild returns same package; semantic_hash unchanged."""
        u, _, h = register_and_login(client, f"m4{id(db_session)}@t.com")
        gid = _create_group(client, h)
        eids = _seed_evidence(db_session, gid, u["id"])
        draft_ids = _create_business_v1_drafts(client, gid, h, eids)
        _review_all(client, gid, h, draft_ids)

        pkg1 = _build_package(client, gid, h)
        r1 = _get_contract(client, gid, pkg1["id"], h)
        h1 = r1.json()["manifest"]["semantic_hash"]

        # Rebuild
        pkg2 = _build_package(client, gid, h)
        assert pkg2["id"] == pkg1["id"]
        assert not pkg2["created"]

        r2 = _get_contract(client, gid, pkg2["id"], h)
        h2 = r2.json()["manifest"]["semantic_hash"]
        assert h1 == h2

    def test_independent_group_and_cross_group_isolation(
        self, client, db_session,
    ):
        """Pilot group is independent; cross-group access returns 403."""
        u1, _, h1 = register_and_login(client, f"m5a{id(db_session)}@t.com")
        gid1 = _create_group(client, h1)
        eids1 = _seed_evidence(db_session, gid1, u1["id"])
        drafts1 = _create_business_v1_drafts(client, gid1, h1, eids1)
        _review_all(client, gid1, h1, drafts1)
        pkg1 = _build_package(client, gid1, h1)

        # Another user / different group
        u2, _, h2 = register_and_login(client, f"m5b{id(db_session)}@t.com")
        gid2 = _create_group(client, h2)

        # h2 in gid2 cannot access gid1's package
        url = f"/groups/{gid2}/ontology/packages/{pkg1['id']}/contract"
        r = client.get(url, headers=h2)
        assert r.status_code == 404, (
            f"Cross-group should 404, got {r.status_code}"
        )

        # Outsider (not member of gid1)
        _, _, h3 = register_and_login(client, f"m5c{id(db_session)}@t.com")
        url2 = f"/groups/{gid1}/ontology/packages/{pkg1['id']}/contract"
        r2 = client.get(url2, headers=h3)
        assert r2.status_code == 403, (
            f"Outsider should 403, got {r2.status_code}"
        )

    def test_action_declaration_only_no_execution(self, client, db_session):
        """Action declares effects and contract but has no executable
        binding."""
        u, _, h = register_and_login(client, f"m6{id(db_session)}@t.com")
        gid = _create_group(client, h)
        eids = _seed_evidence(db_session, gid, u["id"])
        draft_ids = _create_business_v1_drafts(client, gid, h, eids)
        _review_all(client, gid, h, draft_ids)
        pkg = _build_package(client, gid, h)
        r = _get_contract(client, gid, pkg["id"], h)
        assert r.status_code == 200
        manifest = r.json()
        act = manifest["action_types"][0]

        assert act["api_name"] == "create_work_order"
        assert "declared_effects" in act
        assert "action_contract" in act
        assert "parameters" in act
        assert act["action_contract"]["required_role"] == "admin"

        # No executable binding in declared_effects
        for forbidden in ("handler", "endpoint", "function", "sql",
                          "tool", "mcp", "execute"):
            for effect in act["declared_effects"]:
                assert forbidden not in effect.lower(), (
                    f"Effect contains '{forbidden}': {effect}"
                )

        # No executable fields on the action entity
        for forbidden_key in (
            "handler", "endpoint", "function_name", "sql_statement",
        ):
            assert forbidden_key not in act, (
                f"Action has '{forbidden_key}' field"
            )

    def test_all_properties_have_required_true(self, client, db_session):
        """All 6 pilot properties are required=true (primary_key constraint
        needs at least one, but the pilot model has all required)."""
        u, _, h = register_and_login(client, f"m7{id(db_session)}@t.com")
        gid = _create_group(client, h)
        eids = _seed_evidence(db_session, gid, u["id"])
        _create_business_v1_drafts(client, gid, h, eids)

        r = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=property&limit=20",
            headers=h,
        )
        props = r.json()["drafts"]
        assert len(props) == 6
        for p in props:
            assert p["payload"]["required"] is True, (
                f"Property {p['name']} should be required=true"
            )
