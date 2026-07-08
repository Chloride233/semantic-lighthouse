"""Tests for lightweight task board — product alignment A.3 / v1.1.

source_type: rag_run | conversation | agent_run | manual. No DELETE endpoint.
V1.1: status=cancelled (soft cancel). Source traceability.
Permissions: any member can create/list/view/update-status.
Only creator can edit title/description.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login
from semantic_lighthouse.models import ProjectEvidenceLink, RagRun, new_id


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


def _create_task(
    client: TestClient, gid: str, h: dict[str, str],
    title: str = "补充知识库文档",
    source_type: str = "rag_run",
    source_id: str = "abc-123-run",
    project_id: str | None = None,
) -> dict:
    payload = {"title": title, "source_type": source_type, "source_id": source_id}
    if project_id is not None:
        payload["project_id"] = project_id
    r = client.post(
        f"/groups/{gid}/tasks",
        json=payload,
        headers=h,
    )
    assert r.status_code == 201
    return r.json()


def _create_project(client: TestClient, gid: str, h: dict[str, str]) -> dict:
    r = client.post(
        f"/groups/{gid}/projects",
        json={
            "name": "HITL evidence packet pilot",
            "entry_mode": "problem_first",
            "business_goal": "Review task evidence before action",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _add_project_rag_source(
    db: Session,
    gid: str,
    pid: str,
    user_id: str,
    *,
    status: str = "success",
) -> str:
    run_id = new_id()
    db.add(
        RagRun(
            id=run_id,
            group_id=gid,
            user_id=user_id,
            project_id=pid,
            question="Which supplier action should we confirm?",
            answer="Sensitive answer body must not be copied into the evidence packet.",
            confidence="high",
            retrieval_method="hybrid",
            model="fake",
            citations=[
                {
                    "document_id": "doc-safe",
                    "chunk_id": "chunk-safe",
                    "title": "Supplier SOP",
                    "source_path": r"C:\unsafe\raw\supplier.md",
                    "file_name": "supplier.md",
                    "chunk_index": 3,
                    "heading_path": "Review > Supplier",
                    "snippet": "Sensitive citation snippet should stay out of anchors.",
                    "retrieval_method": "hybrid",
                    "match_reason": "标题包含「supplier」等问题关键词。",
                }
            ],
            knowledge_gaps=[],
            next_steps=[],
            status=status,
        )
    )
    db.add(
        ProjectEvidenceLink(
            group_id=gid,
            project_id=pid,
            evidence_type="rag_run",
            evidence_id=run_id,
            role="validation",
            note="Review before task closure",
            status="active",
            created_by=user_id,
        )
    )
    db.commit()
    return run_id


# ── P0: create ─────────────────────────────────────────────────────────────

class TestCreateTask:
    def test_create_from_rag_run(self, client):
        _, _, h = register_and_login(client, "a@t.com")
        gid = _create_group(client, h)
        t = _create_task(client, gid, h, title="补充企业案例")
        assert t["title"] == "补充企业案例"
        assert t["status"] == "pending"
        assert t["source_type"] == "rag_run"
        assert t["source_id"] == "abc-123-run"
        assert t["group_id"] == gid

    @pytest.mark.parametrize("source_type,source_id", [
        ("conversation", "conv-456"),
        ("agent_run", "run-789"),
        ("manual", "manual"),
    ])
    def test_create_from_expanded_source_types(self, client, source_type, source_id):
        _, _, h = register_and_login(client, "create-ts@t.com")
        gid = _create_group(client, h)
        t = _create_task(client, gid, h, title="expand test", source_type=source_type, source_id=source_id)
        assert t["source_type"] == source_type
        assert t["source_id"] == source_id
        assert t["status"] == "pending"

    def test_create_empty_title_422(self, client):
        _, _, h = register_and_login(client, "b@t.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/tasks",
            json={"title": "", "source_type": "rag_run", "source_id": "x"},
            headers=h,
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("bad_type", ["", "invalid", "unknown"])
    def test_create_invalid_source_type_422(self, client, bad_type):
        _, _, h = register_and_login(client, "c@t.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/tasks",
            json={"title": "test", "source_type": bad_type, "source_id": "x"},
            headers=h,
        )
        assert r.status_code == 422

    def test_non_member_cannot_create(self, client):
        _, _, owner_h = register_and_login(client, "d@t.com")
        gid = _create_group(client, owner_h)
        _, _, outsider_h = register_and_login(client, "e@t.com")
        r = client.post(
            f"/groups/{gid}/tasks",
            json={"title": "test", "source_type": "rag_run", "source_id": "x"},
            headers=outsider_h,
        )
        assert r.status_code == 403


# ── P0: list ───────────────────────────────────────────────────────────────

class TestListTasks:
    def test_empty_list(self, client):
        _, _, h = register_and_login(client, "f@t.com")
        gid = _create_group(client, h)
        r = client.get(f"/groups/{gid}/tasks", headers=h)
        assert r.status_code == 200
        assert r.json()["tasks"] == []
        assert r.json()["total"] == 0

    def test_status_filter(self, client):
        _, _, h = register_and_login(client, "g@t.com")
        gid = _create_group(client, h)
        _create_task(client, gid, h, title="pending task")
        t2 = _create_task(client, gid, h, title="done task")
        client.patch(
            f"/groups/{gid}/tasks/{t2['id']}",
            json={"status": "done"},
            headers=h,
        )
        r = client.get(f"/groups/{gid}/tasks?status=done", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["tasks"][0]["title"] == "done task"

    def test_cross_group_isolation(self, client):
        _, _, h_a = register_and_login(client, "h@t.com")
        _, _, h_b = register_and_login(client, "i@t.com")
        ga = _create_group(client, h_a)
        gb = _create_group(client, h_b)
        _create_task(client, ga, h_a, title="group A task")
        r = client.get(f"/groups/{ga}/tasks", headers=h_b)
        assert r.status_code == 403
        r = client.get(f"/groups/{gb}/tasks", headers=h_b)
        assert r.json()["total"] == 0


# ── P0: update ─────────────────────────────────────────────────────────────

class TestUpdateTask:
    def test_any_member_can_update_status(self, client):
        _, _, owner_h = register_and_login(client, "j@t.com")
        _, _, member_h = register_and_login(client, "k@t.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        t = _create_task(client, gid, owner_h, title="shared task")
        r = client.patch(
            f"/groups/{gid}/tasks/{t['id']}",
            json={"status": "in_progress"},
            headers=member_h,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_creator_can_edit_title(self, client):
        _, _, h = register_and_login(client, "l@t.com")
        gid = _create_group(client, h)
        t = _create_task(client, gid, h, title="old title")
        r = client.patch(
            f"/groups/{gid}/tasks/{t['id']}",
            json={"title": "new title"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["title"] == "new title"

    def test_non_creator_403_on_title_edit(self, client):
        _, _, owner_h = register_and_login(client, "m@t.com")
        _, _, member_h = register_and_login(client, "n@t.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        t = _create_task(client, gid, owner_h, title="creator task")
        r = client.patch(
            f"/groups/{gid}/tasks/{t['id']}",
            json={"title": "hijacked"},
            headers=member_h,
        )
        assert r.status_code == 403


# ── P0: no DELETE ──────────────────────────────────────────────────────────

def test_no_delete_endpoint(client):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    t = _create_task(client, gid, h)
    r = client.delete(f"/groups/{gid}/tasks/{t['id']}", headers=h)
    assert r.status_code in (404, 405)


# ── P1: get detail ─────────────────────────────────────────────────────────

def test_get_task_detail(client):
    _, _, h = register_and_login(client, "p@t.com")
    gid = _create_group(client, h)
    t = _create_task(client, gid, h, title="detail test")
    r = client.get(f"/groups/{gid}/tasks/{t['id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["title"] == "detail test"


# ── V1.1: cancelled ──────────────────────────────────────────────────────────

def test_update_task_to_cancelled(client):
    _, _, h = register_and_login(client, "q@t.com")
    gid = _create_group(client, h)
    t = _create_task(client, gid, h, title="cancel me")
    r = client.patch(
        f"/groups/{gid}/tasks/{t['id']}",
        json={"status": "cancelled"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_list_cancelled_tasks(client):
    _, _, h = register_and_login(client, "r@t.com")
    gid = _create_group(client, h)
    _create_task(client, gid, h, title="pending task")
    t2 = _create_task(client, gid, h, title="cancelled task")
    client.patch(f"/groups/{gid}/tasks/{t2['id']}", json={"status": "cancelled"}, headers=h)
    r = client.get(f"/groups/{gid}/tasks?status=cancelled", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["tasks"][0]["title"] == "cancelled task"


def test_cancelled_task_visible_in_detail(client):
    """cancelled is not deleted — detail still accessible."""
    _, _, h = register_and_login(client, "s@t.com")
    gid = _create_group(client, h)
    t = _create_task(client, gid, h, title="soft cancelled")
    client.patch(f"/groups/{gid}/tasks/{t['id']}", json={"status": "cancelled"}, headers=h)
    r = client.get(f"/groups/{gid}/tasks/{t['id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert r.json()["title"] == "soft cancelled"


def test_cancelled_task_any_member_can_reopen(client):
    _, _, owner_h = register_and_login(client, "t@t.com")
    _, _, member_h = register_and_login(client, "u@t.com")
    gid = _create_group(client, owner_h)
    _join_group(client, gid, owner_h, member_h)
    t = _create_task(client, gid, owner_h, title="member reopen test")
    client.patch(f"/groups/{gid}/tasks/{t['id']}", json={"status": "cancelled"}, headers=owner_h)
    r = client.patch(
        f"/groups/{gid}/tasks/{t['id']}",
        json={"status": "pending"},
        headers=member_h,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


# ── V1.1: task detail isolation ─────────────────────────────────────────────

def test_non_member_403_on_task_detail(client):
    _, _, h_a = register_and_login(client, "v@t.com")
    _, _, h_b = register_and_login(client, "w@t.com")
    ga = _create_group(client, h_a)
    _create_group(client, h_b)  # gb — group B for isolation context
    t = _create_task(client, ga, h_a, title="group A task")
    # User B (member of group B only) tries to read group A task
    r = client.get(f"/groups/{ga}/tasks/{t['id']}", headers=h_b)
    assert r.status_code == 403


# ── HITL evidence packet v1 ────────────────────────────────────────────────

def test_manual_task_detail_returns_conservative_evidence_packet(client):
    _, _, h = register_and_login(client, "hitl-manual@t.com")
    gid = _create_group(client, h)
    task = _create_task(
        client,
        gid,
        h,
        title="Manual review task",
        source_type="manual",
        source_id="manual-source",
    )

    listed = client.get(f"/groups/{gid}/tasks", headers=h)
    assert listed.status_code == 200
    assert listed.json()["tasks"][0]["evidence_packet"] is None

    detail = client.get(f"/groups/{gid}/tasks/{task['id']}", headers=h)
    assert detail.status_code == 200
    packet = detail.json()["evidence_packet"]
    assert packet["packet_version"] == "1.0"
    assert packet["source"]["source_type"] == "manual"
    assert packet["source"]["source_status"] == "manual"
    assert packet["proposed_action"]["title"] == "Manual review task"
    assert packet["risk"]["level"] == "medium"
    assert packet["review_requirements"]["requires_human_review"] is True
    assert packet["evidence_anchors"] == []


def test_project_rag_task_detail_returns_safe_evidence_packet(client, db_session):
    owner, _, h = register_and_login(client, "hitl-rag@t.com")
    gid = _create_group(client, h)
    project = _create_project(client, gid, h)
    run_id = _add_project_rag_source(db_session, gid, project["id"], owner["id"])
    task = _create_task(
        client,
        gid,
        h,
        title="Confirm supplier action",
        source_type="rag_run",
        source_id=run_id,
        project_id=project["id"],
    )
    r = client.patch(
        f"/groups/{gid}/tasks/{task['id']}",
        json={"description": "Check the evidence before marking done."},
        headers=h,
    )
    assert r.status_code == 200
    detail = client.get(f"/groups/{gid}/tasks/{task['id']}", headers=h)
    assert detail.status_code == 200
    packet = detail.json()["evidence_packet"]
    assert packet["source"]["source_type"] == "rag_run"
    assert packet["source"]["source_status"] == "success"
    assert packet["source"]["question"] == "Which supplier action should we confirm?"
    assert packet["source"]["confidence"] == "high"
    assert packet["source"]["retrieval_method"] == "hybrid"
    assert packet["source"]["citation_count"] == 1
    assert packet["source"]["project_evidence_link"]["role"] == "validation"
    assert packet["source"]["project_evidence_link"]["status"] == "active"
    assert packet["affected_scope"]["project_id"] == project["id"]
    assert packet["risk"]["level"] == "low"
    assert packet["evidence_anchors"] == [
        {
            "document_id": "doc-safe",
            "chunk_id": "chunk-safe",
            "title": "Supplier SOP",
            "file_name": "supplier.md",
            "chunk_index": 3,
            "heading_path": "Review > Supplier",
            "retrieval_method": "hybrid",
            "match_reason": "标题包含「supplier」等问题关键词。",
        }
    ]

    body = detail.text
    assert "source_path" not in body
    assert "storage_path" not in body
    assert r"C:\unsafe\raw\supplier.md" not in body
    assert "Sensitive answer body" not in body
    assert "Sensitive citation snippet" not in body


def test_missing_rag_source_returns_high_risk_unavailable_packet(client, db_session):
    owner, _, h = register_and_login(client, "hitl-missing@t.com")
    gid = _create_group(client, h)
    project = _create_project(client, gid, h)
    run_id = _add_project_rag_source(db_session, gid, project["id"], owner["id"])
    task = _create_task(
        client,
        gid,
        h,
        title="Confirm missing-source action",
        source_type="rag_run",
        source_id=run_id,
        project_id=project["id"],
    )
    db_session.query(RagRun).filter(RagRun.id == run_id).delete()
    db_session.commit()

    detail = client.get(f"/groups/{gid}/tasks/{task['id']}", headers=h)
    assert detail.status_code == 200
    packet = detail.json()["evidence_packet"]
    assert packet["source"]["source_status"] == "unavailable"
    assert packet["risk"]["level"] == "high"
    assert "Source evidence is unavailable." in packet["risk"]["reasons"]
    assert packet["evidence_anchors"] == []


def test_non_member_cannot_read_evidence_packet(client, db_session):
    owner, _, owner_h = register_and_login(client, "hitl-owner@t.com")
    _, _, outsider_h = register_and_login(client, "hitl-outsider@t.com")
    gid = _create_group(client, owner_h)
    project = _create_project(client, gid, owner_h)
    run_id = _add_project_rag_source(db_session, gid, project["id"], owner["id"])
    task = _create_task(
        client,
        gid,
        owner_h,
        title="Group-only evidence task",
        source_type="rag_run",
        source_id=run_id,
        project_id=project["id"],
    )

    r = client.get(f"/groups/{gid}/tasks/{task['id']}", headers=outsider_h)
    assert r.status_code == 403
