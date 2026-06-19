"""Tests for Phase 12.4 model package API."""

from conftest import register_and_login

DT = "deterministic_v1"


def _create_group(client, headers, name="T"):
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _join(client, gid, oh, mh):
    inv = client.post(f"/groups/{gid}/invites", headers=oh)
    assert inv.status_code == 201
    r = client.post("/groups/join-by-invite",
                    json={"invite_code": inv.json()["invite_code"]}, headers=mh)
    assert r.status_code == 200


def _seed_accepted_draft(
    db_session, gid, uid, name="Concept", draft_type="object_type",
    extra_payload=None,
):
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
        entity_type="Concept", source_path=f"{name}.md",
    ))
    db_session.flush()

    payload = {"generator": DT, "generation_key": f"k:{name}",
               "source_entity_type": "Concept", "entity_count": 3}
    if extra_payload:
        payload.update(extra_payload)
    d = OntologyModelingDraft(
        group_id=gid, draft_type=draft_type, name=name,
        status="accepted", source_entity_id=eid,
        payload=payload, evidence_refs=[{"x": 1}], created_by=uid,
    )
    db_session.add(d)
    db_session.commit()
    return d.id


class TestPackageCreate:
    def test_owner_creates_package_201(self, client, db_session):
        u, _, h = register_and_login(client, "p1@t.com")
        gid = _create_group(client, h)
        _seed_accepted_draft(db_session, gid, u["id"])
        r = client.post(f"/groups/{gid}/ontology/packages", headers=h)
        assert r.status_code == 201
        data = r.json()
        assert data["created"] is True
        assert data["version"] == 1

    def test_member_cannot_create_admin_can(self, client, db_session):
        uo, _, oh = register_and_login(client, "p2o@t.com")
        _, _, mh = register_and_login(client, "p2m@t.com")
        admin_info, _, ah = register_and_login(client, "p2a@t.com")
        gid = _create_group(client, oh)
        _join(client, gid, oh, mh)
        _join(client, gid, oh, ah)
        from semantic_lighthouse.models import GroupMembership
        db_session.query(GroupMembership).filter(
            GroupMembership.group_id == gid,
            GroupMembership.user_id == admin_info["id"],
        ).update({"role": "admin"})
        db_session.commit()

        _seed_accepted_draft(db_session, gid, uo["id"])
        assert client.post(
            f"/groups/{gid}/ontology/packages", headers=mh,
        ).status_code == 403
        r = client.post(f"/groups/{gid}/ontology/packages", headers=ah)
        assert r.status_code == 201

    def test_no_accepted_drafts_409(self, client):
        _, _, h = register_and_login(client, "p3@t.com")
        gid = _create_group(client, h)
        r = client.post(f"/groups/{gid}/ontology/packages", headers=h)
        assert r.status_code == 409

    def test_idempotent_200(self, client, db_session):
        u, _, h = register_and_login(client, "p4@t.com")
        gid = _create_group(client, h)
        _seed_accepted_draft(db_session, gid, u["id"])
        r1 = client.post(f"/groups/{gid}/ontology/packages", headers=h)
        assert r1.status_code == 201
        r2 = client.post(f"/groups/{gid}/ontology/packages", headers=h)
        assert r2.status_code == 200
        assert r2.json()["created"] is False
        assert r2.json()["id"] == r1.json()["id"]


class TestPackageRead:
    def test_member_list_detail_export(self, client, db_session):
        uo, _, oh = register_and_login(client, "r1o@t.com")
        _, _, mh = register_and_login(client, "r1m@t.com")
        gid = _create_group(client, oh)
        _join(client, gid, oh, mh)
        _seed_accepted_draft(db_session, gid, uo["id"])
        pid = client.post(
            f"/groups/{gid}/ontology/packages", headers=oh,
        ).json()["id"]

        r = client.get(f"/groups/{gid}/ontology/packages", headers=mh)
        assert r.status_code == 200 and r.json()["total"] >= 1

        r = client.get(f"/groups/{gid}/ontology/packages/{pid}", headers=mh)
        assert r.status_code == 200 and "contract_json" in r.json()

        r = client.get(f"/groups/{gid}/ontology/packages/{pid}/export", headers=mh)
        assert r.status_code == 200
        assert "contract" in r.json()

    def test_outsider_cannot_access(self, client, db_session):
        uo, _, oh = register_and_login(client, "r2o@t.com")
        _, _, xh = register_and_login(client, "r2x@t.com")
        gid = _create_group(client, oh)
        _seed_accepted_draft(db_session, gid, uo["id"])
        pid = client.post(
            f"/groups/{gid}/ontology/packages", headers=oh,
        ).json()["id"]

        assert client.get(
            f"/groups/{gid}/ontology/packages", headers=xh,
        ).status_code == 403
        assert client.get(
            f"/groups/{gid}/ontology/packages/{pid}", headers=xh,
        ).status_code == 403
        assert client.get(
            f"/groups/{gid}/ontology/packages/{pid}/export", headers=xh,
        ).status_code == 403

    def test_cross_group_package_404(self, client, db_session):
        ua, _, ha = register_and_login(client, "r3a@t.com")
        ub, _, hb = register_and_login(client, "r3b@t.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        _seed_accepted_draft(db_session, ga, ua["id"])
        pid = client.post(
            f"/groups/{ga}/ontology/packages", headers=ha,
        ).json()["id"]

        assert client.get(
            f"/groups/{gb}/ontology/packages/{pid}", headers=hb,
        ).status_code == 404
        assert client.get(
            f"/groups/{gb}/ontology/packages/{pid}/export", headers=hb,
        ).status_code == 404

    def test_list_desc_and_no_mutate(self, client, db_session):
        u, _, h = register_and_login(client, "r4@t.com")
        gid = _create_group(client, h)
        _seed_accepted_draft(db_session, gid, u["id"], name="C1")
        client.post(f"/groups/{gid}/ontology/packages", headers=h)
        _seed_accepted_draft(db_session, gid, u["id"], name="C2")
        client.post(f"/groups/{gid}/ontology/packages", headers=h)

        r = client.get(f"/groups/{gid}/ontology/packages", headers=h)
        vs = [p["version"] for p in r.json()["packages"]]
        assert vs == sorted(vs, reverse=True)

        pid = r.json()["packages"][0]["id"]
        assert client.patch(
            f"/groups/{gid}/ontology/packages/{pid}", headers=h,
        ).status_code == 405
        assert client.delete(
            f"/groups/{gid}/ontology/packages/{pid}", headers=h,
        ).status_code == 405
