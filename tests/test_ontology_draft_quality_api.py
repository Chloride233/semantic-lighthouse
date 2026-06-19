"""Tests for Phase 12.2b quality API endpoint.

Covers: permissions, WARN/FAIL status, read-only immutability.
"""

import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login


def _create_group(client: TestClient, headers: dict[str, str], name: str = "Team") -> str:
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _join_group(client, gid, owner_h, member_h):
    inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
    assert inv.status_code == 201
    r = client.post(
        "/groups/join-by-invite",
        json={"invite_code": inv.json()["invite_code"]},
        headers=member_h,
    )
    assert r.status_code == 200


def _upload_doc(client, gid, headers, filename, frontmatter, body="# Test\n\nContent."):
    yaml_lines = ["---"]
    for k, v in frontmatter.items():
        yaml_lines.append(f"{k}: {[', '.join(v)] if isinstance(v, list) else v}")
    yaml_lines.append("---")
    yaml_lines.append(body)
    content = "\n".join(yaml_lines)
    r = client.post(
        f"/groups/{gid}/documents/upload",
        files={"file": (filename, content.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    time.sleep(0.3)
    return r.json()["id"]


def _quality(client, gid, headers):
    return client.get(f"/groups/{gid}/ontology/drafts/quality", headers=headers)


class TestQualityPermissions:
    def test_member_can_read_quality(self, client):
        _, _, oh = register_and_login(client, "qa1o@t.com")
        _, _, mh = register_and_login(client, "qa1m@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, mh)
        _upload_doc(client, gid, oh, "c.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        client.post(f"/groups/{gid}/ontology/scan", headers=oh)
        client.post(f"/groups/{gid}/ontology/drafts/generate", headers=oh)

        r = _quality(client, gid, mh)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "status" in data
        assert data["draft_count"] >= 1

    def test_outsider_cannot_read_quality(self, client):
        _, _, oh = register_and_login(client, "qa2o@t.com")
        _, _, xh = register_and_login(client, "qa2x@t.com")
        gid = _create_group(client, oh)

        r = _quality(client, gid, xh)
        assert r.status_code == 403


class TestQualityStatus:
    def test_generated_drafts_return_warn_no_errors(self, client):
        """Generated drafts: error_count=0, status=WARN (semantic warnings)."""
        _, _, h = register_and_login(client, "qs1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "c.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        client.post(f"/groups/{gid}/ontology/scan", headers=h)
        client.post(f"/groups/{gid}/ontology/drafts/generate", headers=h)

        r = _quality(client, gid, h)
        assert r.status_code == 200
        data = r.json()
        assert data["error_count"] == 0
        assert data["status"] in ("WARN", "PASS")

    def test_malformed_draft_returns_fail(self, client, db_session: Session):
        """A draft with no source pointer should produce FAIL."""
        from semantic_lighthouse.models import OntologyModelingDraft
        user_info, _, h = register_and_login(client, "qs2o@t.com")
        gid = _create_group(client, h)

        db_session.add(OntologyModelingDraft(
            group_id=gid, draft_type="object_type", name="Bad",
            status="proposed", payload={}, evidence_refs=[],
            created_by=user_info["id"],
        ))
        db_session.commit()

        r = _quality(client, gid, h)
        assert r.status_code == 200
        data = r.json()
        assert data["error_count"] >= 1
        assert data["status"] == "FAIL"


class TestQualityReadOnly:
    def test_api_does_not_modify_drafts(self, client):
        """Calling quality endpoint must not change draft status or review metadata."""
        _, _, h = register_and_login(client, "qr1o@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "c.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        client.post(f"/groups/{gid}/ontology/scan", headers=h)
        client.post(f"/groups/{gid}/ontology/drafts/generate", headers=h)

        before = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        before_snap = {(d["id"], d["status"], d["reviewed_by"] or "",
                        d["review_note"] or "") for d in before["drafts"]}

        _quality(client, gid, h)

        after = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        after_snap = {(d["id"], d["status"], d["reviewed_by"] or "",
                       d["review_note"] or "") for d in after["drafts"]}

        assert before_snap == after_snap
