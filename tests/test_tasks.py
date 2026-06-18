"""Tests for lightweight task board — product alignment A.3 / v1.1.

source_type: rag_run | conversation | agent_run | manual. No DELETE endpoint.
V1.1: status=cancelled (soft cancel). Source traceability.
Permissions: any member can create/list/view/update-status.
Only creator can edit title/description.
"""

import pytest
from fastapi.testclient import TestClient

from conftest import register_and_login


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
) -> dict:
    r = client.post(
        f"/groups/{gid}/tasks",
        json={"title": title, "source_type": source_type, "source_id": source_id},
        headers=h,
    )
    assert r.status_code == 201
    return r.json()


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
