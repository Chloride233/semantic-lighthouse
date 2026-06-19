"""Tests for Phase 13.4 read-only business contract export API.

5-8 parametrized tests covering member read, outsider 403,
cross-group 404, validation failures, hash stability, and immutability.
"""

from conftest import register_and_login


# ── helpers ──────────────────────────────────────────────────────────────

def _create_group(client, headers, name="T"):
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _join(client, gid, owner_headers, member_headers):
    inv = client.post(f"/groups/{gid}/invites", headers=owner_headers)
    assert inv.status_code == 201
    r = client.post(
        "/groups/join-by-invite",
        json={"invite_code": inv.json()["invite_code"]},
        headers=member_headers,
    )
    assert r.status_code == 200


def _seed_business_v1_draft(db_session, gid, uid, name, draft_type, payload):
    """Create an accepted business_v1 draft with proper evidence."""
    from semantic_lighthouse.models import (
        Document, OntologyEntity, OntologyModelingDraft,
    )
    eid = f"e-{name}-{draft_type}"
    did = f"d-{name}-{draft_type}"
    db_session.add(Document(
        id=did, group_id=gid, title=name, file_name=f"{name}.md",
        source_path=f"{name}.md", content_hash=f"h-{eid}",
        raw_content="x", created_by=uid, status="ready",
    ))
    db_session.add(OntologyEntity(
        id=eid, group_id=gid, document_id=did, title=name,
        entity_type="BusinessModel", source_path=f"{name}.md",
    ))
    db_session.flush()

    full_payload = {"contract_profile": "business_v1", **payload}
    d = OntologyModelingDraft(
        group_id=gid, draft_type=draft_type, name=name,
        description=f"Description for {name}",
        status="accepted", source_entity_id=eid,
        payload=full_payload,
        evidence_refs=[{"ref": "evidence"}],
        created_by=uid,
    )
    db_session.add(d)
    db_session.commit()
    return d


def _build_package(client, gid, headers):
    """Create a package via the API, return response JSON."""
    r = client.post(f"/groups/{gid}/ontology/packages", headers=headers)
    assert r.status_code in (200, 201), f"Build failed: {r.json()}"
    return r.json()


def _create_valid_contract_setup(client, db_session):
    """Create a group with valid business_v1 package. Returns (gid, pid, owner_headers)."""
    u, _, h = register_and_login(client, f"u{id(db_session)}@t.com")
    gid = _create_group(client, h)

    # 2 Object Types
    _seed_business_v1_draft(db_session, gid, u["id"],
                            "equipment", "object_type",
                            {"api_name": "equipment", "display_name": "Equipment",
                             "primary_key": "equipment_id"})
    _seed_business_v1_draft(db_session, gid, u["id"],
                            "work_order", "object_type",
                            {"api_name": "work_order", "display_name": "Work Order",
                             "primary_key": "work_order_id"})

    # 6 Properties (4 required for pk, 2 optional)
    for name, ot, req in [
        ("equipment_id", "equipment", True),
        ("name", "equipment", True),
        ("status", "equipment", False),
        ("work_order_id", "work_order", True),
        ("title", "work_order", True),
        ("status", "work_order", False),
    ]:
        _seed_business_v1_draft(db_session, gid, u["id"],
                                f"{ot}.{name}", "property",
                                {"api_name": name, "display_name": name.title(),
                                 "object_type": ot, "value_type": "string",
                                 "required": req})

    # 2 Links
    _seed_business_v1_draft(db_session, gid, u["id"],
                            "equipment_work_orders", "link_type",
                            {"api_name": "equipment_work_orders",
                             "display_name": "Equipment Work Orders",
                             "source_object_type": "equipment",
                             "target_object_type": "work_order",
                             "cardinality": "one_to_many"})
    _seed_business_v1_draft(db_session, gid, u["id"],
                            "work_order_equipment", "link_type",
                            {"api_name": "work_order_equipment",
                             "display_name": "Work Order Equipment",
                             "source_object_type": "work_order",
                             "target_object_type": "equipment",
                             "cardinality": "many_to_one"})

    # 1 Action
    _seed_business_v1_draft(db_session, gid, u["id"],
                            "create_work_order", "action_type",
                            {"api_name": "create_work_order",
                             "display_name": "Create Work Order",
                             "target_object_type": "work_order",
                             "parameters": [
                                 {"name": "title", "value_type": "string",
                                  "required": True},
                                 {"name": "equipment_id", "value_type": "string",
                                  "required": True},
                                 {"name": "priority", "value_type": "string",
                                  "required": True},
                             ],
                             "declared_effects": [
                                 "Creates a new work order",
                                 "Links to equipment asset",
                             ],
                             "action_contract": {
                                 "required_role": "admin",
                                 "confirmation_requirement": "always",
                                 "evidence_requirement": ["evidence"],
                             }})

    pkg = _build_package(client, gid, h)
    return gid, pkg["id"], h


# ── tests ────────────────────────────────────────────────────────────────


class TestBusinessContractAPI:
    """Phase 13.4 read-only contract export endpoint."""

    def test_member_reads_contract_200(self, client, db_session):
        """Any member can read the compiled business contract."""
        gid, pid, oh = _create_valid_contract_setup(client, db_session)
        url = f"/groups/{gid}/ontology/packages/{pid}/contract"
        r = client.get(url, headers=oh)
        assert r.status_code == 200
        body = r.json()
        assert body["manifest"]["contract_profile"] == "business_v1"
        assert body["manifest"]["semantic_hash"].startswith("sha256:")
        assert body["provenance"]["source_package_id"] == pid
        assert len(body["object_types"]) == 2
        assert len(body["properties"]) == 6
        assert len(body["link_types"]) == 2
        assert len(body["action_types"]) == 1
        assert "compiled_at" not in body["manifest"]

    def test_outsider_403(self, client, db_session):
        """Non-member cannot read the contract."""
        gid, pid, oh = _create_valid_contract_setup(client, db_session)
        _, _, outsider_h = register_and_login(
            client, f"outsider{id(db_session)}@t.com")
        url = f"/groups/{gid}/ontology/packages/{pid}/contract"
        r = client.get(url, headers=outsider_h)
        assert r.status_code == 403

    def test_cross_group_package_404(self, client, db_session):
        """Package from group A is 404 in group B."""
        gid_a, pid, oh_a = _create_valid_contract_setup(client, db_session)
        u_b, _, h_b = register_and_login(
            client, f"g2owner{id(db_session)}@t.com")
        gid_b = _create_group(client, h_b)
        # Member of group B tries to access group A's package
        url = f"/groups/{gid_b}/ontology/packages/{pid}/contract"
        r = client.get(url, headers=h_b)
        assert r.status_code == 404

    def test_invalid_package_returns_422(self, client, db_session):
        """Package that fails business_v1 validation returns 422 with
        structured validation_result."""
        u, _, h = register_and_login(client, f"inv{id(db_session)}@t.com")
        gid = _create_group(client, h)

        # Create a package with drafts missing contract_profile
        from semantic_lighthouse.models import (
            Document, OntologyEntity, OntologyModelingDraft,
        )
        for name, dt, payload in [
            ("Concept", "object_type",
             {"api_name": "concept", "display_name": "Concept",
              "primary_key": "concept_id", "observed_value_types": ["string"]}),
            ("concept_id", "property",
             {"api_name": "concept_id", "display_name": "ID",
              "object_type": "Concept", "value_type": "string",
              "required": True, "observed_value_types": ["string"]}),
        ]:
            eid = f"e-{name}-{dt}"
            did = f"d-{name}-{dt}"
            db_session.add(Document(
                id=did, group_id=gid, title=name, file_name=f"{name}.md",
                source_path=f"{name}.md", content_hash=f"h-{eid}",
                raw_content="x", created_by=u["id"], status="ready",
            ))
            db_session.add(OntologyEntity(
                id=eid, group_id=gid, document_id=did, title=name,
                entity_type="Concept", source_path=f"{name}.md",
            ))
            db_session.flush()
            db_session.add(OntologyModelingDraft(
                group_id=gid, draft_type=dt, name=name,
                description=f"Desc {name}",
                status="accepted", source_entity_id=eid,
                payload=payload,
                evidence_refs=[{"x": 1}], created_by=u["id"],
            ))
        db_session.commit()

        pkg = _build_package(client, gid, h)
        url = f"/groups/{gid}/ontology/packages/{pkg['id']}/contract"
        r = client.get(url, headers=h)
        assert r.status_code == 422, r.json()
        detail = r.json()["detail"]
        assert "validation_result" in detail
        vr = detail["validation_result"]
        assert vr["status"] == "FAIL"
        codes = {i["code"] for i in vr["issues"]}
        assert "contract_profile_mismatch" in codes

    def test_contract_profile_mismatch_422(self, client, db_session):
        """Explicitly test contract_profile_mismatch as a 422 detail."""
        u, _, h = register_and_login(client, f"cpm{id(db_session)}@t.com")
        gid = _create_group(client, h)

        _seed_business_v1_draft(db_session, gid, u["id"],
                                "x", "object_type",
                                {"api_name": "x", "display_name": "X",
                                 "primary_key": "x_id"})
        _seed_business_v1_draft(db_session, gid, u["id"],
                                "x_id", "property",
                                {"api_name": "x_id", "display_name": "ID",
                                 "object_type": "x", "value_type": "string",
                                 "required": True})
        # This one is missing contract_profile
        from semantic_lighthouse.models import OntologyModelingDraft
        db_session.query(OntologyModelingDraft).filter(
            OntologyModelingDraft.name == "x",
        ).update({"payload": {"api_name": "x", "display_name": "X",
                              "primary_key": "x_id"}})
        db_session.commit()

        pkg = _build_package(client, gid, h)
        url = f"/groups/{gid}/ontology/packages/{pkg['id']}/contract"
        r = client.get(url, headers=h)
        assert r.status_code == 422
        detail = r.json()["detail"]
        vr = detail["validation_result"]
        codes = {i["code"] for i in vr["issues"]}
        assert "contract_profile_mismatch" in codes

    def test_semantic_hash_stable_across_requests(self, client, db_session):
        """Two GET calls on the same package return identical
        semantic_hash."""
        gid, pid, oh = _create_valid_contract_setup(client, db_session)
        url = f"/groups/{gid}/ontology/packages/{pid}/contract"

        r1 = client.get(url, headers=oh)
        r2 = client.get(url, headers=oh)
        assert r1.status_code == 200
        assert r2.status_code == 200
        h1 = r1.json()["manifest"]["semantic_hash"]
        h2 = r2.json()["manifest"]["semantic_hash"]
        assert h1 == h2

    def test_read_does_not_mutate_package(self, client, db_session):
        """A GET request against the contract endpoint does not change
        package data or database state."""
        gid, pid, oh = _create_valid_contract_setup(client, db_session)
        from semantic_lighthouse.models import OntologyModelPackage

        # Snapshot before
        pkg_before = db_session.get(OntologyModelPackage, pid)
        version_before = pkg_before.version
        hash_before = pkg_before.content_hash
        draft_count_before = pkg_before.draft_count
        contract_before = dict(pkg_before.contract_json)

        url = f"/groups/{gid}/ontology/packages/{pid}/contract"
        r = client.get(url, headers=oh)
        assert r.status_code == 200

        # Snapshot after
        db_session.expire_all()
        pkg_after = db_session.get(OntologyModelPackage, pid)
        assert pkg_after.version == version_before
        assert pkg_after.content_hash == hash_before
        assert pkg_after.draft_count == draft_count_before
        assert pkg_after.contract_json == contract_before

    def test_post_patch_delete_not_allowed(self, client, db_session):
        """Only GET is supported on the contract endpoint."""
        gid, pid, oh = _create_valid_contract_setup(client, db_session)
        base = f"/groups/{gid}/ontology/packages/{pid}/contract"

        r_post = client.post(base, headers=oh, json={})
        assert r_post.status_code == 405

        r_patch = client.patch(base, headers=oh, json={})
        assert r_patch.status_code == 405

        r_delete = client.delete(base, headers=oh)
        assert r_delete.status_code == 405
