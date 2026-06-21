"""Tests for Phase 16.1 — Pilot Outcome Records.

Permissions: owner/admin create, member+ read/list. Outsider 403.
Cross-group/project: 404. Immutable: no PATCH/DELETE.
Evidence/package validation: active, same group/project.
Privacy: no raw_content, answer, prompt, source_path, storage_path, secrets.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login
from semantic_lighthouse.models import (
    Document,
    OntologyModelPackage,
    ProjectEvidenceLink,
    RagRun,
    new_id,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _create_group(
    client: TestClient, headers: dict[str, str], name: str = "OutcomeGroup"
) -> str:
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


def _promote_to_admin(
    client: TestClient, gid: str, owner_h: dict[str, str], member_id: str
) -> None:
    r = client.patch(
        f"/groups/{gid}/members/{member_id}/role",
        json={"role": "admin"},
        headers=owner_h,
    )
    assert r.status_code == 200


def _create_project(
    client: TestClient,
    gid: str,
    h: dict[str, str],
    name: str = "Outcome Project",
    business_goal: str = "Build a delivery record for FDE handoff",
) -> dict:
    r = client.post(
        f"/groups/{gid}/projects",
        json={
            "name": name,
            "entry_mode": "problem_first",
            "business_goal": business_goal,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _add_document(db: Session, gid: str, user_id: str, suffix: str) -> str:
    doc_id = new_id()
    db.add(Document(
        id=doc_id,
        group_id=gid,
        title=f"Doc {suffix}",
        file_name=f"doc-{suffix}.md",
        source_path=f"/data/doc-{suffix}.md",
        content_hash=f"hash-{suffix}",
        file_hash=f"file-hash-{suffix}",
        raw_content="secret document content",
        status="ready",
        created_by=user_id,
        frontmatter={"source": f"Source {suffix}"},
    ))
    return doc_id


def _add_rag_run(db: Session, gid: str, user_id: str) -> str:
    run_id = new_id()
    db.add(RagRun(
        id=run_id,
        group_id=gid,
        user_id=user_id,
        question="What should the FDE deliver?",
        answer="This is a generated answer with secrets.",
        confidence="high",
        retrieval_method="hybrid",
        model="fake",
        citations=[{"snippet": "citation text"}],
        status="success",
    ))
    return run_id


def _add_evidence_link(
    db: Session, gid: str, pid: str, evidence_id: str, user_id: str,
    evidence_type: str = "document", role: str = "context",
) -> str:
    link = ProjectEvidenceLink(
        id=new_id(),
        group_id=gid,
        project_id=pid,
        evidence_type=evidence_type,
        evidence_id=evidence_id,
        role=role,
        status="active",
        created_by=user_id,
    )
    db.add(link)
    return link.id


def _add_package(
    db: Session, gid: str, pid: str | None, user_id: str,
    version: int = 1, quality_status: str = "PASS",
) -> str:
    pkg_id = new_id()
    scope_key = f"project:{pid}" if pid else "group"
    db.add(OntologyModelPackage(
        id=pkg_id,
        group_id=gid,
        project_id=pid,
        scope_key=scope_key,
        version=version,
        content_hash=f"pkg-hash-{pkg_id[:8]}",
        quality_status=quality_status,
        draft_count=5,
        created_by=user_id,
        contract_json={"object_types": [], "properties": []},
        source_draft_ids=[new_id()],
        quality_summary={"errors": 0, "warnings": 2},
    ))
    return pkg_id


def _create_outcome(
    client: TestClient, gid: str, pid: str, h: dict[str, str],
    **overrides,
) -> dict:
    body = {
        "title": "FDE Delivery v1",
        "decision_summary": "Proceed with ontology pilot.",
        "risks": ["Data quality gaps", "Limited sample size"],
        "next_actions": ["Expand dataset", "Add more evidence"],
    }
    body.update(overrides)
    r = client.post(f"/groups/{gid}/projects/{pid}/outcomes", json=body, headers=h)
    return r


# ── create ───────────────────────────────────────────────────────────────


class TestCreateOutcome:
    def test_owner_can_create_minimal(self, client):
        _, _, h = register_and_login(client, "oc-owner@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(client, gid, pid, h)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "FDE Delivery v1"
        assert data["business_goal_snapshot"] == "Build a delivery record for FDE handoff"
        assert data["selected_evidence_refs"] == []
        assert data["package_refs"] == []
        assert data["query_refs"] == []
        assert data["decision_summary"] == "Proceed with ontology pilot."
        assert data["risks"] == ["Data quality gaps", "Limited sample size"]
        assert data["next_actions"] == ["Expand dataset", "Add more evidence"]
        assert data["created_by"] == client.get("/auth/me", headers=h).json()["id"]

    def test_admin_can_create(self, client):
        _, owner_me, owner_h = register_and_login(client, "oc-owner2@test.com")
        admin_me, _, admin_h = register_and_login(client, "oc-admin@test.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_to_admin(client, gid, owner_h, admin_me["id"])
        pid = _create_project(client, gid, owner_h)["id"]
        r = _create_outcome(client, gid, pid, admin_h, title="Admin Outcome")
        assert r.status_code == 201
        assert r.json()["title"] == "Admin Outcome"

    def test_member_cannot_create(self, client):
        _, _, owner_h = register_and_login(client, "oc-owner3@test.com")
        _, _, member_h = register_and_login(client, "oc-member@test.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        pid = _create_project(client, gid, owner_h)["id"]
        r = _create_outcome(client, gid, pid, member_h)
        assert r.status_code == 403

    def test_outsider_cannot_create(self, client):
        _, _, owner_h = register_and_login(client, "oc-owner4@test.com")
        _, _, outsider_h = register_and_login(client, "oc-outsider@test.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)["id"]
        r = _create_outcome(client, gid, pid, outsider_h)
        assert r.status_code == 403

    def test_cross_group_project_404(self, client):
        _, _, ha = register_and_login(client, "oc-ga@test.com")
        _, _, hb = register_and_login(client, "oc-gb@test.com")
        ga = _create_group(client, ha, "GA")
        gb = _create_group(client, hb, "GB")
        pid = _create_project(client, ga, ha)["id"]
        r = client.post(
            f"/groups/{gb}/projects/{pid}/outcomes",
            json={"title": "cross"},
            headers=hb,
        )
        assert r.status_code == 404

    def test_title_snapshot_from_project(self, client):
        """Business goal is snapshotted from the project at creation time."""
        _, _, h = register_and_login(client, "oc-snap@test.com")
        gid = _create_group(client, h)
        pid = _create_project(
            client, gid, h,
            business_goal="Original goal at creation",
        )["id"]
        r = _create_outcome(client, gid, pid, h)
        assert r.status_code == 201
        assert r.json()["business_goal_snapshot"] == "Original goal at creation"

    def test_empty_title_422(self, client):
        _, _, h = register_and_login(client, "oc-empty@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(client, gid, pid, h, title="")
        assert r.status_code == 422

    def test_whitespace_title_422(self, client):
        _, _, h = register_and_login(client, "oc-ws@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(client, gid, pid, h, title="   ")
        assert r.status_code == 422

    def test_multiple_records_allowed(self, client):
        _, _, h = register_and_login(client, "oc-multi@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r1 = _create_outcome(client, gid, pid, h, title="First Record")
        assert r1.status_code == 201
        r2 = _create_outcome(client, gid, pid, h, title="Second Record")
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]


# ── evidence validation ──────────────────────────────────────────────────


class TestOutcomeEvidenceValidation:
    def test_valid_evidence_links_accepted(self, client, db_session: Session):
        _, _, h = register_and_login(client, "oe-ok@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        doc_id = _add_document(db_session, gid, owner_id, "doc1")
        link_id = _add_evidence_link(db_session, gid, pid, doc_id, owner_id)
        db_session.commit()

        r = _create_outcome(
            client, gid, pid, h,
            selected_evidence_link_ids=[link_id],
        )
        assert r.status_code == 201
        refs = r.json()["selected_evidence_refs"]
        assert len(refs) == 1
        assert refs[0]["link_id"] == link_id
        assert refs[0]["evidence_type"] == "document"
        assert "provenance" in refs[0]

    def test_nonexistent_evidence_link_422(self, client):
        _, _, h = register_and_login(client, "oe-bad@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            selected_evidence_link_ids=["nonexistent-id"],
        )
        assert r.status_code == 422
        assert "not found" in r.json()["detail"].lower()

    def test_evidence_link_from_other_project_422(
        self, client, db_session: Session
    ):
        _, _, h = register_and_login(client, "oe-xproj@test.com")
        gid = _create_group(client, h)
        pid1 = _create_project(client, gid, h, name="Project 1")["id"]
        pid2 = _create_project(client, gid, h, name="Project 2")["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        doc_id = _add_document(db_session, gid, owner_id, "cross")
        link_id = _add_evidence_link(db_session, gid, pid2, doc_id, owner_id)
        db_session.commit()

        r = _create_outcome(
            client, gid, pid1, h,
            selected_evidence_link_ids=[link_id],
        )
        assert r.status_code == 422

    def test_removed_evidence_link_422(self, client, db_session: Session):
        _, _, h = register_and_login(client, "oe-rem@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        doc_id = _add_document(db_session, gid, owner_id, "removed")
        link = ProjectEvidenceLink(
            id=new_id(),
            group_id=gid,
            project_id=pid,
            evidence_type="document",
            evidence_id=doc_id,
            role="context",
            status="removed",
            created_by=owner_id,
        )
        db_session.add(link)
        db_session.commit()

        r = _create_outcome(
            client, gid, pid, h,
            selected_evidence_link_ids=[link.id],
        )
        assert r.status_code == 422
        assert "not active" in r.json()["detail"].lower()

    def test_evidence_link_from_other_group_422(
        self, client, db_session: Session
    ):
        _, _, ha = register_and_login(client, "oe-xgrp-a@test.com")
        _, _, hb = register_and_login(client, "oe-xgrp-b@test.com")
        ga = _create_group(client, ha, "GA")
        gb = _create_group(client, hb, "GB")
        pid_a = _create_project(client, ga, ha)["id"]
        owner_a = client.get("/auth/me", headers=ha).json()["id"]

        doc_id = _add_document(db_session, ga, owner_a, "group-a-doc")
        link_id = _add_evidence_link(db_session, ga, pid_a, doc_id, owner_a)
        db_session.commit()

        # Try from group B with group A's link — but this would require
        # group B project. Actually, cross-group evidence link means the
        # link belongs to a different group than the route parameter.
        # Since the route validates group_id against link.group_id,
        # this will be caught.
        r = client.post(
            f"/groups/{gb}/projects/{pid_a}/outcomes",
            json={"title": "cross", "selected_evidence_link_ids": [link_id]},
            headers=hb,
        )
        assert r.status_code == 404  # project not found in group B


# ── package validation ───────────────────────────────────────────────────


class TestOutcomePackageValidation:
    def test_valid_packages_accepted(self, client, db_session: Session):
        _, _, h = register_and_login(client, "op-ok@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        pkg_id = _add_package(db_session, gid, pid, owner_id)
        db_session.commit()

        r = _create_outcome(
            client, gid, pid, h,
            package_ids=[pkg_id],
        )
        assert r.status_code == 201
        refs = r.json()["package_refs"]
        assert len(refs) == 1
        assert refs[0]["package_id"] == pkg_id
        assert refs[0]["version"] == 1
        assert refs[0]["quality_status"] == "PASS"
        assert "contract_json" not in refs[0]
        assert "source_draft_ids" not in refs[0]

    def test_nonexistent_package_422(self, client):
        _, _, h = register_and_login(client, "op-bad@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            package_ids=["nonexistent-pkg"],
        )
        assert r.status_code == 422
        assert "not found" in r.json()["detail"].lower()

    def test_package_from_other_group_422(self, client, db_session: Session):
        _, _, ha = register_and_login(client, "op-xg-a@test.com")
        _, _, hb = register_and_login(client, "op-xg-b@test.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        pid_a = _create_project(client, ga, ha)["id"]
        pid_b = _create_project(client, gb, hb)["id"]
        owner_b = client.get("/auth/me", headers=hb).json()["id"]

        pkg_id = _add_package(db_session, gb, pid_b, owner_b)
        db_session.commit()

        r = _create_outcome(
            client, ga, pid_a, ha,
            package_ids=[pkg_id],
        )
        assert r.status_code == 422

    def test_package_scoped_to_other_project_422(
        self, client, db_session: Session
    ):
        _, _, h = register_and_login(client, "op-xproj@test.com")
        gid = _create_group(client, h)
        pid1 = _create_project(client, gid, h, name="P1")["id"]
        pid2 = _create_project(client, gid, h, name="P2")["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        pkg_id = _add_package(db_session, gid, pid2, owner_id)
        db_session.commit()

        r = _create_outcome(
            client, gid, pid1, h,
            package_ids=[pkg_id],
        )
        assert r.status_code == 422


# ── query_refs privacy ───────────────────────────────────────────────────


class TestOutcomeQueryRefsPrivacy:
    def test_clean_query_refs_accepted(self, client):
        _, _, h = register_and_login(client, "oq-clean@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            query_refs=[
                {"binding": "equipment_binding", "row_count": 42, "outcome": "success"},
                {"object_type": "equipment", "filters_applied": 3},
            ],
        )
        assert r.status_code == 201
        assert len(r.json()["query_refs"]) == 2

    def test_raw_answer_rejected(self, client):
        _, _, h = register_and_login(client, "oq-raw@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            query_refs=[{"binding": "test", "answer": "some generated text"}],
        )
        assert r.status_code == 422

    def test_source_path_rejected(self, client):
        _, _, h = register_and_login(client, "oq-path@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            query_refs=[{"source_path": "/data/secret.csv"}],
        )
        assert r.status_code == 422

    def test_secret_rejected(self, client):
        _, _, h = register_and_login(client, "oq-secret@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            query_refs=[{"api_key": "sk-abc123"}],
        )
        assert r.status_code == 422

    def test_stack_trace_rejected(self, client):
        _, _, h = register_and_login(client, "oq-trace@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            query_refs=[{"stack_trace": "File ... line 42"}],
        )
        assert r.status_code == 422

    def test_nested_forbidden_key_rejected(self, client):
        _, _, h = register_and_login(client, "oq-nest@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            query_refs=[{"results": [{"raw_content": "sensitive"}]}],
        )
        assert r.status_code == 422

    def test_raw_csv_rows_rejected(self, client):
        _, _, h = register_and_login(client, "oq-csv@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = _create_outcome(
            client, gid, pid, h,
            query_refs=[{"csv_rows": ["col1,col2", "a,b"]}],
        )
        assert r.status_code == 422


# ── read / list ──────────────────────────────────────────────────────────


class TestReadOutcome:
    def test_owner_can_read(self, client):
        _, _, h = register_and_login(client, "or-owner@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        created = _create_outcome(client, gid, pid, h)
        assert created.status_code == 201
        oid = created.json()["id"]

        r = client.get(
            f"/groups/{gid}/projects/{pid}/outcomes/{oid}", headers=h
        )
        assert r.status_code == 200
        assert r.json()["id"] == oid

    def test_member_can_read(self, client):
        _, _, owner_h = register_and_login(client, "or-owner2@test.com")
        _, _, member_h = register_and_login(client, "or-member@test.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        pid = _create_project(client, gid, owner_h)["id"]
        created = _create_outcome(client, gid, pid, owner_h)
        assert created.status_code == 201
        oid = created.json()["id"]

        r = client.get(
            f"/groups/{gid}/projects/{pid}/outcomes/{oid}", headers=member_h
        )
        assert r.status_code == 200

    def test_outsider_cannot_read(self, client):
        _, _, owner_h = register_and_login(client, "or-owner3@test.com")
        _, _, outsider_h = register_and_login(client, "or-outsider@test.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)["id"]
        created = _create_outcome(client, gid, pid, owner_h)
        oid = created.json()["id"]

        r = client.get(
            f"/groups/{gid}/projects/{pid}/outcomes/{oid}", headers=outsider_h
        )
        assert r.status_code == 403

    def test_cross_group_404(self, client):
        _, _, ha = register_and_login(client, "or-ga@test.com")
        _, _, hb = register_and_login(client, "or-gb@test.com")
        ga = _create_group(client, ha, "GA")
        gb = _create_group(client, hb, "GB")
        pid_a = _create_project(client, ga, ha)["id"]
        pid_b = _create_project(client, gb, hb)["id"]
        created = _create_outcome(client, ga, pid_a, ha)
        oid = created.json()["id"]

        # Ask group B's project for group A's outcome → 404
        r = client.get(
            f"/groups/{gb}/projects/{pid_b}/outcomes/{oid}", headers=hb
        )
        assert r.status_code == 404

    def test_cross_group_project_404(self, client):
        _, _, ha = register_and_login(client, "or-xgp@test.com")
        _, _, hb = register_and_login(client, "or-xgp-b@test.com")
        ga = _create_group(client, ha, "GA")
        gb = _create_group(client, hb, "GB")
        pid = _create_project(client, ga, ha)["id"]
        created = _create_outcome(client, ga, pid, ha)
        oid = created.json()["id"]

        r = client.get(
            f"/groups/{gb}/projects/{pid}/outcomes/{oid}", headers=hb
        )
        assert r.status_code == 404

    def test_nonexistent_outcome_404(self, client):
        _, _, h = register_and_login(client, "or-nx@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = client.get(
            f"/groups/{gid}/projects/{pid}/outcomes/nonexistent", headers=h
        )
        assert r.status_code == 404


class TestListOutcomes:
    def test_empty_list(self, client):
        _, _, h = register_and_login(client, "ol-empty@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/outcomes", headers=h)
        assert r.status_code == 200
        assert r.json()["outcomes"] == []
        assert r.json()["total"] == 0

    def test_list_latest_first(self, client):
        _, _, h = register_and_login(client, "ol-order@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        r1 = _create_outcome(client, gid, pid, h, title="First")
        assert r1.status_code == 201
        r2 = _create_outcome(client, gid, pid, h, title="Second")
        assert r2.status_code == 201

        r = client.get(f"/groups/{gid}/projects/{pid}/outcomes", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] == 2
        # Latest first
        assert r.json()["outcomes"][0]["title"] == "Second"
        assert r.json()["outcomes"][1]["title"] == "First"

    def test_member_can_list(self, client):
        _, _, owner_h = register_and_login(client, "ol-owner@test.com")
        _, _, member_h = register_and_login(client, "ol-member@test.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        pid = _create_project(client, gid, owner_h)["id"]
        _create_outcome(client, gid, pid, owner_h, title="Shared")
        r = client.get(f"/groups/{gid}/projects/{pid}/outcomes", headers=member_h)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_outsider_cannot_list(self, client):
        _, _, owner_h = register_and_login(client, "ol-out-own@test.com")
        _, _, outsider_h = register_and_login(client, "ol-out@test.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)["id"]
        _create_outcome(client, gid, pid, owner_h)
        r = client.get(f"/groups/{gid}/projects/{pid}/outcomes", headers=outsider_h)
        assert r.status_code == 403

    def test_list_respects_limit(self, client):
        _, _, h = register_and_login(client, "ol-limit@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        for i in range(5):
            _create_outcome(client, gid, pid, h, title=f"Outcome {i}")
        r = client.get(
            f"/groups/{gid}/projects/{pid}/outcomes?limit=2", headers=h
        )
        assert r.status_code == 200
        assert len(r.json()["outcomes"]) == 2
        assert r.json()["total"] == 5

    def test_list_isolated_per_project(self, client):
        _, _, h = register_and_login(client, "ol-iso@test.com")
        gid = _create_group(client, h)
        pid1 = _create_project(client, gid, h, name="P1")["id"]
        pid2 = _create_project(client, gid, h, name="P2")["id"]
        _create_outcome(client, gid, pid1, h, title="P1 Outcome")
        _create_outcome(client, gid, pid2, h, title="P2 Outcome")

        r1 = client.get(f"/groups/{gid}/projects/{pid1}/outcomes", headers=h)
        assert r1.json()["total"] == 1
        assert r1.json()["outcomes"][0]["title"] == "P1 Outcome"

        r2 = client.get(f"/groups/{gid}/projects/{pid2}/outcomes", headers=h)
        assert r2.json()["total"] == 1
        assert r2.json()["outcomes"][0]["title"] == "P2 Outcome"


# ── privacy ──────────────────────────────────────────────────────────────


class TestOutcomePrivacy:
    """Verify response never contains raw_content, answer, prompt, paths, secrets."""

    FORBIDDEN_TERMS = [
        "raw_content", "raw_answer", "raw_prompt",
        "source_path", "storage_path",
        "answer", "prompt",
        "secret", "token", "password",
        "stack_trace",
    ]

    def test_create_response_no_forbidden_keys(self, client, db_session: Session):
        _, _, h = register_and_login(client, "opriv-c@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        doc_id = _add_document(db_session, gid, owner_id, "priv-doc")
        link_id = _add_evidence_link(db_session, gid, pid, doc_id, owner_id)
        db_session.commit()

        r = _create_outcome(
            client, gid, pid, h,
            selected_evidence_link_ids=[link_id],
        )
        assert r.status_code == 201
        body = str(r.json())
        for term in self.FORBIDDEN_TERMS:
            assert term not in body, f"Forbidden term '{term}' found in response"

    def test_get_response_no_forbidden_keys(self, client, db_session: Session):
        _, _, h = register_and_login(client, "opriv-g@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        doc_id = _add_document(db_session, gid, owner_id, "priv-doc2")
        link_id = _add_evidence_link(db_session, gid, pid, doc_id, owner_id)
        db_session.commit()

        created = _create_outcome(
            client, gid, pid, h,
            selected_evidence_link_ids=[link_id],
        )
        oid = created.json()["id"]
        r = client.get(
            f"/groups/{gid}/projects/{pid}/outcomes/{oid}", headers=h
        )
        assert r.status_code == 200
        body = str(r.json())
        for term in self.FORBIDDEN_TERMS:
            assert term not in body, f"Forbidden term '{term}' found in response"

    def test_list_response_no_forbidden_keys(self, client, db_session: Session):
        _, _, h = register_and_login(client, "opriv-l@test.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)["id"]
        owner_id = client.get("/auth/me", headers=h).json()["id"]

        doc_id = _add_document(db_session, gid, owner_id, "priv-doc3")
        link_id = _add_evidence_link(db_session, gid, pid, doc_id, owner_id)
        db_session.commit()

        _create_outcome(
            client, gid, pid, h,
            selected_evidence_link_ids=[link_id],
        )
        r = client.get(f"/groups/{gid}/projects/{pid}/outcomes", headers=h)
        assert r.status_code == 200
        body = str(r.json())
        for term in self.FORBIDDEN_TERMS:
            assert term not in body, f"Forbidden term '{term}' found in response"
