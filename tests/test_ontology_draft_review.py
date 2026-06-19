"""Tests for Phase 11.4 ontology modeling draft human review workflow.

Covers: single accept/reject, batch accept/reject, status transitions,
permissions, atomic batch semantics, idempotency audit, cross-group isolation.
"""

import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login
# ── helpers ───────────────────────────────────────────────────────────


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


def _review_draft(
    client: TestClient,
    gid: str,
    draft_id: str,
    headers: dict[str, str],
    status: str = "accepted",
    review_note: str | None = None,
):
    body: dict = {"status": status}
    if review_note is not None:
        body["review_note"] = review_note
    return client.post(
        f"/groups/{gid}/ontology/drafts/{draft_id}/review",
        json=body,
        headers=headers,
    )


def _review_batch(
    client: TestClient,
    gid: str,
    draft_ids: list[str],
    headers: dict[str, str],
    status: str = "accepted",
    review_note: str | None = None,
):
    body: dict = {"draft_ids": draft_ids, "status": status}
    if review_note is not None:
        body["review_note"] = review_note
    return client.post(
        f"/groups/{gid}/ontology/drafts/review-batch",
        json=body,
        headers=headers,
    )


# ── P0: single review — accept / reject ───────────────────────────────


class TestSingleAcceptReject:
    def test_owner_accepts_proposed_draft(self, client):
        _, _, h = register_and_login(client, "sr1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Accept Me", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev.status_code == 200, rev.text
        d = rev.json()
        assert d["status"] == "accepted"
        assert d["reviewed_by"] is not None
        assert d["reviewed_at"] is not None

    def test_owner_rejects_proposed_draft_with_note(self, client):
        _, _, h = register_and_login(client, "sr2o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Reject Me", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(
            client, gid, draft_id, h,
            status="rejected", review_note="Name does not match convention",
        )
        assert rev.status_code == 200, rev.text
        d = rev.json()
        assert d["status"] == "rejected"
        assert d["reviewed_by"] is not None
        assert d["reviewed_at"] is not None
        assert d["review_note"] == "Name does not match convention"

    def test_rejected_without_note_fails(self, client):
        _, _, h = register_and_login(client, "sr3o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="No Note", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h, status="rejected")
        assert rev.status_code == 422, rev.text

    def test_accepted_without_note_succeeds(self, client):
        """accept does NOT require a review_note."""
        _, _, h = register_and_login(client, "sr4o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Accept No Note", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev.status_code == 200, rev.text
        assert rev.json()["status"] == "accepted"
        assert rev.json()["review_note"] is None

    def test_rejected_with_whitespace_only_note_fails(self, client):
        """Whitespace-only review_note should fail for rejected."""
        _, _, h = register_and_login(client, "sr5o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Whitespace Note", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(
            client, gid, draft_id, h,
            status="rejected", review_note="   ",
        )
        assert rev.status_code == 422, rev.text


# ── P1: permissions ───────────────────────────────────────────────────


class TestReviewPermissions:
    def test_admin_can_review(self, client, db_session: Session):
        _, _, oh = register_and_login(client, "rp1o@t.com")
        _, _, ah = register_and_login(client, "rp1a@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, ah)

        # Promote to admin
        from semantic_lighthouse.models import GroupMembership
        membership = db_session.query(GroupMembership).filter(
            GroupMembership.group_id == gid,
            GroupMembership.role == "member",
        ).first()
        assert membership is not None
        membership.role = "admin"
        db_session.commit()

        _upload_doc(client, gid, oh, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, oh, name="Admin Review", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, ah, status="accepted")
        assert rev.status_code == 200, rev.text
        assert rev.json()["status"] == "accepted"

    def test_member_cannot_review(self, client):
        _, _, oh = register_and_login(client, "rp2o@t.com")
        _, _, mh = register_and_login(client, "rp2m@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, mh)
        _upload_doc(client, gid, oh, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, oh, name="Member Blocked", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, mh, status="accepted")
        assert rev.status_code == 403, rev.text

    def test_member_cannot_batch_review(self, client):
        _, _, oh = register_and_login(client, "rp3o@t.com")
        _, _, mh = register_and_login(client, "rp3m@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, mh)
        _upload_doc(client, gid, oh, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, oh, name="Batch Blocked", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_batch(client, gid, [draft_id], mh, status="accepted")
        assert rev.status_code == 403, rev.text

    def test_outsider_cannot_review(self, client):
        _, _, oh = register_and_login(client, "rp4o@t.com")
        _, _, xh = register_and_login(client, "rp4x@t.com")
        gid = _create_group(client, oh)
        _upload_doc(client, gid, oh, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, oh, name="Outsider Blocked", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, xh, status="accepted")
        assert rev.status_code == 403, rev.text

    def test_cross_group_draft_returns_404(self, client):
        """Using another group's draft_id should return 404, not leak existence."""
        _, _, ha = register_and_login(client, "rp5a@t.com")
        _, _, hb = register_and_login(client, "rp5b@t.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)

        _upload_doc(client, ga, ha, "entity-a.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, ga, ha)
        entities_a = client.get(f"/groups/{ga}/ontology/entities", headers=ha).json()
        eid_a = entities_a["entities"][0]["id"]
        r = _create_draft(client, ga, ha, name="A Draft", source_entity_id=eid_a)
        draft_id_a = r.json()["id"]

        # Try to review A's draft from group B
        rev = _review_draft(client, gb, draft_id_a, hb, status="accepted")
        assert rev.status_code == 404, rev.text


# ── P2: invalid input ─────────────────────────────────────────────────


class TestInvalidInput:
    def test_invalid_status_returns_422(self, client):
        _, _, h = register_and_login(client, "iv1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Bad Status", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h, status="proposed")
        assert rev.status_code == 422, rev.text

        rev = _review_draft(client, gid, draft_id, h, status="invalid")
        assert rev.status_code == 422, rev.text

    def test_empty_batch_draft_ids_returns_422(self, client):
        _, _, h = register_and_login(client, "iv2o@t.com")
        gid = _create_group(client, h)

        rev = _review_batch(client, gid, [], h, status="accepted")
        assert rev.status_code == 422, rev.text

    def test_too_many_batch_draft_ids_returns_422(self, client):
        _, _, h = register_and_login(client, "iv3o@t.com")
        gid = _create_group(client, h)

        rev = _review_batch(
            client, gid,
            [f"id-{i}" for i in range(101)],
            h,
            status="accepted",
        )
        assert rev.status_code == 422, rev.text


# ── P3: status transition rules ───────────────────────────────────────


class TestStatusTransitions:
    def test_accepted_draft_cannot_be_reviewed_again(self, client):
        """Once accepted, re-review returns 409."""
        _, _, h = register_and_login(client, "st1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Once Accepted", source_entity_id=eid)
        draft_id = r.json()["id"]

        # First review: accept
        rev1 = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev1.status_code == 200, rev1.text

        # Second review: must return 409
        rev2 = _review_draft(client, gid, draft_id, h, status="rejected",
                             review_note="Trying to change")
        assert rev2.status_code == 409, rev2.text

        # Verify first metadata unchanged
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        d = drafts["drafts"][0]
        assert d["status"] == "accepted"
        assert d["reviewed_by"] == rev1.json()["reviewed_by"]
        assert d["reviewed_at"] == rev1.json()["reviewed_at"]
        assert d["review_note"] is None  # first accepted without note

    def test_rejected_draft_cannot_be_reviewed_again(self, client):
        """Once rejected, re-review returns 409."""
        _, _, h = register_and_login(client, "st2o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Once Rejected", source_entity_id=eid)
        draft_id = r.json()["id"]

        # First review: reject
        rev1 = _review_draft(
            client, gid, draft_id, h,
            status="rejected", review_note="Bad name",
        )
        assert rev1.status_code == 200, rev1.text

        # Second review: must return 409
        rev2 = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev2.status_code == 409, rev2.text

        # Verify first metadata unchanged
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        d = drafts["drafts"][0]
        assert d["status"] == "rejected"
        assert d["review_note"] == "Bad name"
        assert d["reviewed_at"] == rev1.json()["reviewed_at"]

    def test_admin_re_review_of_accepted_returns_409(self, client, db_session: Session):
        """Admin trying to re-review gets 409, original reviewer metadata preserved."""
        _, _, oh = register_and_login(client, "st3o@t.com")
        _, _, ah = register_and_login(client, "st3a@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, ah)

        from semantic_lighthouse.models import GroupMembership
        membership = db_session.query(GroupMembership).filter(
            GroupMembership.group_id == gid,
            GroupMembership.role == "member",
        ).first()
        assert membership is not None
        membership.role = "admin"
        db_session.commit()

        _upload_doc(client, gid, oh, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=oh).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, oh, name="Admin Re-review Blocked", source_entity_id=eid)
        draft_id = r.json()["id"]

        # Owner accepts first
        rev1 = _review_draft(client, gid, draft_id, oh, status="accepted")
        assert rev1.status_code == 200, rev1.text
        first_reviewer = rev1.json()["reviewed_by"]
        first_reviewed_at = rev1.json()["reviewed_at"]

        # Admin tries to re-review → 409
        rev2 = _review_draft(
            client, gid, draft_id, ah,
            status="rejected", review_note="Admin override attempt",
        )
        assert rev2.status_code == 409, rev2.text

        # Verify first metadata unchanged
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=oh).json()
        d = drafts["drafts"][0]
        assert d["status"] == "accepted"
        assert d["reviewed_by"] == first_reviewer
        assert d["reviewed_at"] == first_reviewed_at
        assert d["review_note"] is None


# ── P4: draft metadata preservation ───────────────────────────────────


class TestReviewPreservesMetadata:
    def test_review_does_not_modify_payload(self, client):
        _, _, h = register_and_login(client, "md1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        original_payload = {"generator": "manual", "fields": ["name", "desc"]}
        r = _create_draft(
            client, gid, h, name="Payload Test",
            source_entity_id=eid,
            payload=original_payload,
        )
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev.status_code == 200, rev.text
        assert rev.json()["payload"] == original_payload

    def test_review_does_not_modify_evidence_refs(self, client):
        _, _, h = register_and_login(client, "md2o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        original_refs = [{"type": "citation", "doc_id": "test-ref"}]
        r = _create_draft(
            client, gid, h, name="Refs Test",
            source_entity_id=eid,
            evidence_refs=original_refs,
        )
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h,
                            status="rejected", review_note="Not good")
        assert rev.status_code == 200, rev.text
        assert rev.json()["evidence_refs"] == original_refs

    def test_review_does_not_modify_created_by_and_created_at(self, client):
        _, _, h = register_and_login(client, "md3o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Creator Test", source_entity_id=eid)
        original_created_by = r.json()["created_by"]
        original_created_at = r.json()["created_at"]
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev.status_code == 200, rev.text
        assert rev.json()["created_by"] == original_created_by
        assert rev.json()["created_at"] == original_created_at

    def test_review_does_not_modify_source_pointers(self, client):
        _, _, h = register_and_login(client, "md4o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Source Test", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev.status_code == 200, rev.text
        assert rev.json()["source_entity_id"] == eid
        assert rev.json()["source_relation_id"] is None
        assert rev.json()["source_issue_id"] is None
        assert rev.json()["source_rag_run_id"] is None

    def test_review_note_strips_whitespace(self, client):
        _, _, h = register_and_login(client, "md5o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Strip Test", source_entity_id=eid)
        draft_id = r.json()["id"]

        rev = _review_draft(
            client, gid, draft_id, h,
            status="rejected",
            review_note="  Needs better description  ",
        )
        assert rev.status_code == 200, rev.text
        assert rev.json()["review_note"] == "Needs better description"


# ── P5: GET filter for accepted/rejected ──────────────────────────────


class TestDraftStatusFilter:
    def test_status_filter_accepted(self, client):
        _, _, h = register_and_login(client, "sf1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        # Create and accept one draft
        r = _create_draft(client, gid, h, name="Accepted Draft", source_entity_id=eid)
        _review_draft(client, gid, r.json()["id"], h, status="accepted")

        # Create another proposed draft
        _create_draft(client, gid, h, name="Proposed Draft", source_entity_id=eid)

        # Filter by accepted
        result = client.get(
            f"/groups/{gid}/ontology/drafts?status=accepted", headers=h
        ).json()
        assert result["total"] >= 1
        assert all(d["status"] == "accepted" for d in result["drafts"])

        # Filter by rejected (should be empty)
        result = client.get(
            f"/groups/{gid}/ontology/drafts?status=rejected", headers=h
        ).json()
        assert result["total"] == 0

    def test_status_filter_rejected(self, client):
        _, _, h = register_and_login(client, "sf2o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "entity.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        # Create and reject one draft
        r = _create_draft(client, gid, h, name="Rejected Draft", source_entity_id=eid)
        _review_draft(
            client, gid, r.json()["id"], h,
            status="rejected", review_note="Bad",
        )

        result = client.get(
            f"/groups/{gid}/ontology/drafts?status=rejected", headers=h
        ).json()
        assert result["total"] >= 1
        assert all(d["status"] == "rejected" for d in result["drafts"])


# ── P6: batch review — atomic operations ──────────────────────────────


class TestBatchReview:
    def test_batch_accept_multiple(self, client):
        _, _, h = register_and_login(client, "br1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "e1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _upload_doc(client, gid, h, "e2.md", {
            "entityType": "Vendor", "tags": ["b"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid1 = entities["entities"][0]["id"]
        eid2 = entities["entities"][1]["id"]

        r1 = _create_draft(client, gid, h, name="Batch 1", source_entity_id=eid1)
        r2 = _create_draft(client, gid, h, name="Batch 2",
                           draft_type="property", source_entity_id=eid2)
        ids = [r1.json()["id"], r2.json()["id"]]

        rev = _review_batch(client, gid, ids, h, status="accepted")
        assert rev.status_code == 200, rev.text
        data = rev.json()
        assert data["reviewed_count"] == 2
        assert data["status"] == "accepted"
        assert set(data["draft_ids"]) == set(ids)
        assert data["reviewed_by"] is not None
        assert data["reviewed_at"] is not None

        # Verify both are accepted
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        for d in drafts["drafts"]:
            assert d["status"] == "accepted"

    def test_batch_reject_with_note(self, client):
        _, _, h = register_and_login(client, "br2o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "e1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        # Create 3 drafts
        ids = []
        for i in range(3):
            r = _create_draft(
                client, gid, h,
                name=f"Batch Reject {i}",
                source_entity_id=eid,
            )
            ids.append(r.json()["id"])

        note = "All three have naming issues"
        rev = _review_batch(
            client, gid, ids, h,
            status="rejected", review_note=note,
        )
        assert rev.status_code == 200, rev.text
        assert rev.json()["reviewed_count"] == 3
        assert rev.json()["status"] == "rejected"

        # Verify all are rejected with the same note
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        for d in drafts["drafts"]:
            assert d["status"] == "rejected"
            assert d["review_note"] == note

    def test_batch_duplicate_ids_deduplicated(self, client):
        _, _, h = register_and_login(client, "br3o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "e1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Dedup", source_entity_id=eid)
        draft_id = r.json()["id"]

        # Send same ID 3 times
        rev = _review_batch(
            client, gid,
            [draft_id, draft_id, draft_id],
            h,
            status="accepted",
        )
        assert rev.status_code == 200, rev.text
        # Should count once
        assert rev.json()["reviewed_count"] == 1
        assert rev.json()["draft_ids"] == [draft_id]

    def test_batch_missing_id_atomic_404(self, client):
        """If any ID doesn't exist in group, the entire batch fails — no partial updates."""
        _, _, h = register_and_login(client, "br4o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "e1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]
        r = _create_draft(client, gid, h, name="Valid", source_entity_id=eid)
        valid_id = r.json()["id"]

        rev = _review_batch(
            client, gid,
            [valid_id, "nonexistent-id-12345"],
            h,
            status="accepted",
        )
        assert rev.status_code == 404, rev.text

        # Verify the valid draft was NOT modified
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        d = drafts["drafts"][0]
        assert d["status"] == "proposed"

    def test_batch_cross_group_id_atomic_404(self, client):
        """If any ID belongs to another group, entire batch fails atomically."""
        _, _, ha = register_and_login(client, "br5a@t.com")
        _, _, hb = register_and_login(client, "br5b@t.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)

        # Setup group A
        _upload_doc(client, ga, ha, "ea.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, ga, ha)
        entities_a = client.get(f"/groups/{ga}/ontology/entities", headers=ha).json()
        eid_a = entities_a["entities"][0]["id"]
        r_a = _create_draft(client, ga, ha, name="A Draft", source_entity_id=eid_a)

        # Setup group B
        _upload_doc(client, gb, hb, "eb.md", {
            "entityType": "Concept", "tags": ["b"], "created": "2026-01-01",
        })
        _scan(client, gb, hb)
        entities_b = client.get(f"/groups/{gb}/ontology/entities", headers=hb).json()
        eid_b = entities_b["entities"][0]["id"]
        r_b = _create_draft(client, gb, hb, name="B Draft", source_entity_id=eid_b)

        # Batch in group B with A's draft → 404
        rev = _review_batch(
            client, gb,
            [r_b.json()["id"], r_a.json()["id"]],
            hb,
            status="accepted",
        )
        assert rev.status_code == 404, rev.text

        # Verify B's draft was NOT modified
        drafts_b = client.get(f"/groups/{gb}/ontology/drafts", headers=hb).json()
        d_b = drafts_b["drafts"][0]
        assert d_b["status"] == "proposed"

    def test_batch_already_reviewed_409_no_partial(self, client):
        """If any draft is already reviewed, batch fails with 409. No partial updates."""
        _, _, h = register_and_login(client, "br6o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "e1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        r1 = _create_draft(client, gid, h, name="Already Done", source_entity_id=eid)
        r2 = _create_draft(client, gid, h, name="Still Fresh", source_entity_id=eid)

        # Accept the first draft individually
        _review_draft(client, gid, r1.json()["id"], h, status="accepted")

        # Batch the accepted + fresh → 409
        rev = _review_batch(
            client, gid,
            [r1.json()["id"], r2.json()["id"]],
            h,
            status="accepted",
        )
        assert rev.status_code == 409, rev.text

        # Verify the fresh draft was NOT modified
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        d2 = [d for d in drafts["drafts"] if d["id"] == r2.json()["id"]][0]
        assert d2["status"] == "proposed"

    def test_batch_all_already_reviewed_409(self, client):
        """When ALL drafts in batch are already reviewed."""
        _, _, h = register_and_login(client, "br7o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "e1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        ids = []
        for i in range(2):
            r = _create_draft(client, gid, h, name=f"All Done {i}", source_entity_id=eid)
            ids.append(r.json()["id"])
            _review_draft(client, gid, r.json()["id"], h, status="accepted")

        rev = _review_batch(client, gid, ids, h, status="accepted")
        assert rev.status_code == 409, rev.text


# ── P7: generated and manual drafts both reviewable ────────────────────


class TestReviewAnyDraft:
    def test_generated_draft_can_be_reviewed(self, client):
        _, _, h = register_and_login(client, "ra1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        # Generate drafts
        gen = client.post(f"/groups/{gid}/ontology/drafts/generate", headers=h)
        assert gen.status_code == 200

        # Get the generated object_type draft
        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=object_type", headers=h
        ).json()
        assert drafts["total"] >= 1
        draft_id = drafts["drafts"][0]["id"]

        # Accept it
        rev = _review_draft(client, gid, draft_id, h, status="accepted")
        assert rev.status_code == 200, rev.text
        assert rev.json()["status"] == "accepted"
        # Payload should still have generation_key
        assert "generation_key" in rev.json()["payload"]

    def test_manual_draft_can_be_reviewed(self, client):
        _, _, h = register_and_login(client, "ra2o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        r = _create_draft(
            client, gid, h, name="Manual Draft",
            source_entity_id=eid,
            description="Created by hand",
        )
        draft_id = r.json()["id"]

        rev = _review_draft(
            client, gid, draft_id, h,
            status="rejected", review_note="Needs evidence",
        )
        assert rev.status_code == 200, rev.text
        assert rev.json()["status"] == "rejected"
        assert rev.json()["description"] == "Created by hand"

    def test_batch_includes_generated_and_manual_drafts(self, client):
        _, _, h = register_and_login(client, "ra3o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _upload_doc(client, gid, h, "vendor.md", {
            "entityType": "Vendor", "tags": ["y"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()

        # Generate one draft
        gen = client.post(f"/groups/{gid}/ontology/drafts/generate", headers=h)
        assert gen.status_code == 200

        # Manually create another
        eid = entities["entities"][0]["id"]
        _create_draft(
            client, gid, h, name="Mixed Manual",
            draft_type="property", source_entity_id=eid,
        )

        # Get all draft IDs
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        all_ids = [d["id"] for d in drafts["drafts"]]
        assert len(all_ids) >= 2

        # Batch accept all
        rev = _review_batch(client, gid, all_ids, h, status="accepted")
        assert rev.status_code == 200, rev.text
        assert rev.json()["reviewed_count"] == len(all_ids)

        # All should be accepted
        drafts_after = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        for d in drafts_after["drafts"]:
            assert d["status"] == "accepted"
