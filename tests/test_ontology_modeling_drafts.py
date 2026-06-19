"""Tests for Phase 11.1–11.2 ontology modeling drafts read model.

Covers: create, read, filters, group isolation, permissions, evidence linkage validation.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login
from semantic_lighthouse.models import RagRun


def _create_group(client: TestClient, headers: dict[str, str], name: str = "Team") -> str:
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _join_group(
    client: TestClient, gid: str, owner_h: dict[str, str], member_h: dict[str, str]
) -> None:
    inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
    assert inv.status_code == 201
    r = client.post(
        "/groups/join-by-invite",
        json={"invite_code": inv.json()["invite_code"]},
        headers=member_h,
    )
    assert r.status_code == 200


def _upload_doc(
    client: TestClient,
    gid: str,
    headers: dict[str, str],
    filename: str,
    frontmatter: dict,
    body: str = "# Test\n\nContent.",
) -> str:
    import time

    yaml_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            items = ", ".join(v)
            yaml_lines.append(f"{k}: [{items}]")
        else:
            yaml_lines.append(f"{k}: {v}")
    yaml_lines.append("---")
    yaml_lines.append(body)
    content = "\n".join(yaml_lines)

    r = client.post(
        f"/groups/{gid}/documents/upload",
        files={"file": (filename, content.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    time.sleep(0.3)
    return doc_id


def _scan(client: TestClient, gid: str, headers: dict[str, str]) -> dict:
    r = client.post(f"/groups/{gid}/ontology/scan", headers=headers)
    return r.json()


def _create_draft(
    client: TestClient,
    gid: str,
    headers: dict[str, str],
    draft_type: str = "object_type",
    name: str = "Test Draft",
    **extra,
) -> dict:
    body = {"draft_type": draft_type, "name": name, **extra}
    r = client.post(f"/groups/{gid}/ontology/drafts", json=body, headers=headers)
    return r


# ── P0: basic create and read ──────────────────────────────────────────


class TestDraftCreateRead:
    def test_owner_creates_draft_defaults(self, client):
        _, _, h = register_and_login(client, "d1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity-a.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        r = _create_draft(client, gid, h, name="Object Type A", source_entity_id=eid)
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["draft_type"] == "object_type"
        assert d["name"] == "Object Type A"
        assert d["status"] == "proposed"
        assert d["source_entity_id"] == eid
        assert d["created_by"] is not None

    def test_member_can_read_drafts(self, client):
        _, _, oh = register_and_login(client, "d2o@t.com")
        _, _, mh = register_and_login(client, "d2m@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, mh)
        _upload_doc(client, gid, oh, "entity-b.md", {
            "entityType": "Concept", "tags": ["b"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]
        _create_draft(client, gid, oh, name="Readable", source_entity_id=eid)

        r = client.get(f"/groups/{gid}/ontology/drafts", headers=mh)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_member_cannot_create_draft(self, client):
        _, _, oh = register_and_login(client, "d3o@t.com")
        _, _, mh = register_and_login(client, "d3m@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, mh)
        _upload_doc(client, gid, oh, "entity-c.md", {
            "entityType": "Concept", "tags": ["c"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]

        r = _create_draft(client, gid, mh, name="Blocked", source_entity_id=eid)
        assert r.status_code == 403

    def test_outsider_cannot_read_drafts(self, client):
        _, _, oh = register_and_login(client, "d4o@t.com")
        _, _, xh = register_and_login(client, "d4x@t.com")
        gid = _create_group(client, oh)

        r = client.get(f"/groups/{gid}/ontology/drafts", headers=xh)
        assert r.status_code == 403


# ── P1: group isolation ───────────────────────────────────────────────


class TestDraftIsolation:
    def test_cross_group_drafts_isolated(self, client):
        _, _, ha = register_and_login(client, "di1a@t.com")
        _, _, hb = register_and_login(client, "di1b@t.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)

        _upload_doc(client, ga, ha, "a-entity.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, ga, ha)
        entities_a = client.get(f"/groups/{ga}/ontology/entities", headers=ha).json()
        eid_a = entities_a["entities"][0]["id"]
        _create_draft(client, ga, ha, name="Group A Draft", source_entity_id=eid_a)

        # Group B not in group A — outsider blocked
        r = client.get(f"/groups/{ga}/ontology/drafts", headers=hb)
        assert r.status_code == 403

        # Group B sees own empty
        _upload_doc(client, gb, hb, "b-entity.md", {
            "entityType": "Concept", "tags": ["b"], "created": "2026-01-01",
        })
        _scan(client, gb, hb)
        r = client.get(f"/groups/{gb}/ontology/drafts", headers=hb)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_cross_group_source_entity_rejected(self, client):
        """Using another group's source_entity_id should return 404."""
        _, _, ha = register_and_login(client, "di2a@t.com")
        _, _, hb = register_and_login(client, "di2b@t.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)

        _upload_doc(client, ga, ha, "ga-entity.md", {
            "entityType": "Concept", "tags": ["ga"], "created": "2026-01-01",
        })
        _scan(client, ga, ha)
        entities_a = client.get(f"/groups/{ga}/ontology/entities", headers=ha).json()
        eid_a = entities_a["entities"][0]["id"]

        # Try to create draft in gb using ga's entity
        r = _create_draft(client, gb, hb, name="Cross", source_entity_id=eid_a)
        assert r.status_code == 404


# ── P2: evidence linkage ──────────────────────────────────────────────


class TestEvidenceLinkage:
    def test_source_entity_id_same_group(self, client):
        _, _, h = register_and_login(client, "el1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "el-entity.md", {
            "entityType": "Concept", "tags": ["el"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        r = _create_draft(client, gid, h, name="With Entity", source_entity_id=eid)
        assert r.status_code == 201

    def test_source_relation_id_same_group(self, client):
        _, _, h = register_and_login(client, "el2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "src.md", {
            "entityType": "Concept", "tags": ["src"], "created": "2026-01-01",
        }, body="[[tgt]]")
        _upload_doc(client, gid, h, "tgt.md", {
            "entityType": "Concept", "tags": ["tgt"], "created": "2026-01-01",
        }, body="tgt")
        _scan(client, gid, h)
        relations = client.get(f"/groups/{gid}/ontology/relations", headers=h).json()
        rid = relations["relations"][0]["id"]

        r = _create_draft(
            client, gid, h, draft_type="link_type", name="With Relation", source_relation_id=rid
        )
        assert r.status_code == 201

    def test_source_issue_id_same_group(self, client):
        _, _, h = register_and_login(client, "el3@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "issue-src.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        }, body="[[missing]]")
        _scan(client, gid, h)
        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        iid = issues["issues"][0]["id"]

        r = _create_draft(
            client, gid, h, draft_type="action_type", name="Fix Issue", source_issue_id=iid
        )
        assert r.status_code == 201

    def test_source_rag_run_id_same_group(self, client, db_session: Session):
        uid, _, h = register_and_login(client, "el4@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "rag-doc.md", {
            "entityType": "Concept", "tags": ["rag"], "created": "2026-01-01",
        }, body="# Ontology\n\nOntology is a semantic layer.")

        # Create a RagRun directly so we don't need a real chat provider
        run = RagRun(
            group_id=gid,
            user_id=uid["id"],
            question="What is Ontology?",
            answer="Ontology is a semantic layer.",
            confidence="medium",
            retrieval_method="keyword",
            model="fake",
            citations=[],
            knowledge_gaps=[],
            next_steps=[],
            status="success",
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        r = _create_draft(client, gid, h, name="RAG-backed", source_rag_run_id=run.id)
        assert r.status_code == 201

    def test_no_evidence_fails(self, client):
        """Creating a draft with no evidence pointer or evidence_refs should fail."""
        _, _, h = register_and_login(client, "el5@t.com")
        gid = _create_group(client, h)

        r = _create_draft(client, gid, h, name="No Evidence")
        assert r.status_code == 400


# ── P3: filtering ─────────────────────────────────────────────────────


class TestDraftFilters:
    def test_draft_type_filter(self, client):
        _, _, h = register_and_login(client, "df1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "df-entity.md", {
            "entityType": "Concept", "tags": ["df"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        _create_draft(client, gid, h, draft_type="object_type", name="OT", source_entity_id=eid)
        _create_draft(client, gid, h, draft_type="property", name="Prop", source_entity_id=eid)

        r = client.get(f"/groups/{gid}/ontology/drafts?draft_type=object_type", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert all(d["draft_type"] == "object_type" for d in data["drafts"])

    def test_status_filter(self, client):
        _, _, h = register_and_login(client, "df2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "df2-entity.md", {
            "entityType": "Concept", "tags": ["df2"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        _create_draft(client, gid, h, name="Filterable", source_entity_id=eid)

        r = client.get(f"/groups/{gid}/ontology/drafts?status=proposed", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert all(d["status"] == "proposed" for d in data["drafts"])

    def test_q_filter(self, client):
        _, _, h = register_and_login(client, "df3@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "df3-entity.md", {
            "entityType": "Concept", "tags": ["df3"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        _create_draft(client, gid, h, name="UniqueDraftName", source_entity_id=eid)

        r = client.get(f"/groups/{gid}/ontology/drafts?q=Unique", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

        r = client.get(f"/groups/{gid}/ontology/drafts?q=NotFoundZZZ", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_invalid_draft_type_422(self, client):
        _, _, h = register_and_login(client, "df4@t.com")
        gid = _create_group(client, h)

        r = _create_draft(client, gid, h, draft_type="invalid_type", name="Bad")
        assert r.status_code == 422


# ── P4: admin can create ──────────────────────────────────────────────


class TestAdminAccess:
    def test_admin_can_create_draft(self, client, db_session: Session):
        _, _, oh = register_and_login(client, "aa1o@t.com")
        _, _, ah = register_and_login(client, "aa1a@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, ah)

        # Use db_session to directly promote the member to admin
        from semantic_lighthouse.models import GroupMembership
        membership = db_session.query(GroupMembership).filter(
            GroupMembership.group_id == gid,
            GroupMembership.role == "member",
        ).first()
        assert membership is not None, "Could not find member to promote"
        membership.role = "admin"
        db_session.commit()

        _upload_doc(client, gid, oh, "aa-entity.md", {
            "entityType": "Concept", "tags": ["aa"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]

        r = _create_draft(client, gid, ah, name="Admin Draft", source_entity_id=eid)
        assert r.status_code == 201
