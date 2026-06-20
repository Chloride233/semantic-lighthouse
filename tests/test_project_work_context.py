"""S2.3A — Project Work Context Persistence & Validation tests."""

import pytest

from semantic_lighthouse.models import (
    BusinessProject,
    Group,
    GroupMembership,
    ProjectEvidenceLink,
    RagRun,
    User,
    new_id,
)
from semantic_lighthouse.security import hash_password


def _auth_headers(client, email, password="Passw0rd!"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _setup_users(db, gid):
    own = new_id()
    mem = new_id()
    db.add(User(id=own, email=f"own-{gid[:8]}@t.com", display_name="O", password_hash=hash_password("Passw0rd!")))
    db.add(User(id=mem, email=f"mem-{gid[:8]}@t.com", display_name="M", password_hash=hash_password("Passw0rd!")))
    db.add(Group(id=gid, name="G", created_by=own))
    db.add(GroupMembership(group_id=gid, user_id=own, role="owner"))
    db.add(GroupMembership(group_id=gid, user_id=mem, role="member"))
    return own, mem


def _add_project(db, gid, pid, owner_id, status="active"):
    db.add(BusinessProject(id=pid, group_id=gid, name="P", business_goal="G", entry_mode="data_first", created_by=owner_id, status=status))


# ═══════════════════════════════════════════════════════════════
#  Conversation tests
# ═══════════════════════════════════════════════════════════════

def test_conversation_create_with_project_id(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/conversations", json={"title": "T", "project_id": pid}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["project_id"] == pid


def test_conversation_nullable_compat(client, db_session):
    gid = new_id()
    own, _ = _setup_users(db_session, gid)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/conversations", json={"title": "T"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["project_id"] is None


def test_conversation_cross_group_project_404(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    other_gid = new_id()
    db_session.add(Group(id=other_gid, name="O", created_by=own))
    _add_project(db_session, other_gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/conversations", json={"title": "T", "project_id": pid}, headers=h)
    assert resp.status_code == 404


def test_conversation_archived_project_409(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own, "archived")
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/conversations", json={"title": "T", "project_id": pid}, headers=h)
    assert resp.status_code == 409


def test_conversation_list_project_filter(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    client.post(f"/groups/{gid}/conversations", json={"title": "Scoped", "project_id": pid}, headers=h)
    client.post(f"/groups/{gid}/conversations", json={"title": "Unscoped"}, headers=h)
    resp = client.get(f"/groups/{gid}/conversations?project_id={pid}", headers=h)
    assert resp.status_code == 200
    items = resp.json()
    assert all(c["project_id"] == pid for c in items)
    assert len(items) >= 1


def test_conversation_message_blocked_archived_project(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/conversations", json={"title": "T", "project_id": pid}, headers=h)
    cid = resp.json()["id"]

    db_session.execute(BusinessProject.__table__.update().where(BusinessProject.id == pid).values(status="archived"))
    db_session.commit()

    resp2 = client.post(f"/groups/{gid}/conversations/{cid}/messages", json={"question": "Q?"}, headers=h)
    assert resp2.status_code == 409

    detail = client.get(f"/groups/{gid}/conversations/{cid}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["project_id"] == pid


@pytest.mark.parametrize("path", ["conversations", "tasks", "agent/runs"])
def test_list_filter_rejects_cross_group_project(client, db_session, path):
    gid, other_gid, pid = new_id(), new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    db_session.add(Group(id=other_gid, name="Other", created_by=own))
    _add_project(db_session, other_gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.get(f"/groups/{gid}/{path}?project_id={pid}", headers=h)
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
#  Task tests
# ═══════════════════════════════════════════════════════════════

def test_task_create_with_project_id(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/tasks", json={
        "title": "T", "source_type": "manual", "source_id": "ignored", "project_id": pid
    }, headers=h)
    assert resp.status_code == 201
    assert resp.json()["project_id"] == pid


def test_task_nullable_compat(client, db_session):
    gid = new_id()
    own, _ = _setup_users(db_session, gid)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/tasks", json={
        "title": "T", "source_type": "manual", "source_id": "ignored"
    }, headers=h)
    assert resp.status_code == 201
    assert resp.json()["project_id"] is None


def test_task_list_filter(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    client.post(f"/groups/{gid}/tasks", json={"title": "S", "source_type": "manual", "source_id": "x", "project_id": pid}, headers=h)
    client.post(f"/groups/{gid}/tasks", json={"title": "U", "source_type": "manual", "source_id": "y"}, headers=h)
    resp = client.get(f"/groups/{gid}/tasks?project_id={pid}", headers=h)
    assert resp.status_code == 200
    items = resp.json()["tasks"]
    assert all(t["project_id"] == pid for t in items)
    assert len(items) >= 1


def test_task_archived_project_409(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own, "archived")
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/tasks", json={
        "title": "T", "source_type": "manual", "source_id": "x", "project_id": pid
    }, headers=h)
    assert resp.status_code == 409


def test_task_update_blocked_after_project_archive(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    created = client.post(f"/groups/{gid}/tasks", json={
        "title": "T", "source_type": "manual", "source_id": "x", "project_id": pid
    }, headers=h)
    task_id = created.json()["id"]
    db_session.execute(
        BusinessProject.__table__.update()
        .where(BusinessProject.id == pid)
        .values(status="archived")
    )
    db_session.commit()

    resp = client.patch(
        f"/groups/{gid}/tasks/{task_id}", json={"status": "done"}, headers=h
    )
    assert resp.status_code == 409


def test_scoped_task_rejects_unscoped_conversation(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    conv = client.post(
        f"/groups/{gid}/conversations", json={"title": "Unscoped"}, headers=h
    ).json()

    resp = client.post(f"/groups/{gid}/tasks", json={
        "title": "T", "source_type": "conversation",
        "source_id": conv["id"], "project_id": pid,
    }, headers=h)
    assert resp.status_code == 409


def test_scoped_task_accepts_matching_conversation(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    conv = client.post(f"/groups/{gid}/conversations", json={
        "title": "Scoped", "project_id": pid,
    }, headers=h).json()

    resp = client.post(f"/groups/{gid}/tasks", json={
        "title": "T", "source_type": "conversation",
        "source_id": conv["id"], "project_id": pid,
    }, headers=h)
    assert resp.status_code == 201


def test_scoped_task_rejects_rag_link_with_wrong_group(client, db_session):
    gid, other_gid, pid, run_id = new_id(), new_id(), new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    db_session.add(Group(id=other_gid, name="Other", created_by=own))
    _add_project(db_session, gid, pid, own)
    db_session.add(RagRun(
        id=run_id, group_id=gid, user_id=own, question="Q", answer="A",
        confidence="high", retrieval_method="keyword", model="fake",
        citations=[], knowledge_gaps=[], next_steps=[], status="success",
    ))
    db_session.add(ProjectEvidenceLink(
        group_id=other_gid, project_id=pid, evidence_type="rag_run",
        evidence_id=run_id, role="context", status="active", created_by=own,
    ))
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(f"/groups/{gid}/tasks", json={
        "title": "T", "source_type": "rag_run",
        "source_id": run_id, "project_id": pid,
    }, headers=h)
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
#  Agent tests
# ═══════════════════════════════════════════════════════════════

def test_agent_create_with_project_id(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/agent/runs", json={"goal": "G", "project_id": pid}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["project_id"] == pid


def test_agent_nullable_compat(client, db_session):
    gid = new_id()
    own, _ = _setup_users(db_session, gid)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/agent/runs", json={"goal": "G"}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["project_id"] is None


def test_agent_conversation_inherits_project(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    cr = client.post(f"/groups/{gid}/conversations", json={"title": "C", "project_id": pid}, headers=h)
    cid = cr.json()["id"]
    resp = client.post(f"/groups/{gid}/agent/runs", json={"goal": "G", "conversation_id": cid}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["project_id"] == pid


def test_agent_conversation_project_conflict_409(client, db_session):
    gid, pid1, pid2 = new_id(), new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid1, own)
    _add_project(db_session, gid, pid2, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    cr = client.post(f"/groups/{gid}/conversations", json={"title": "C", "project_id": pid1}, headers=h)
    cid = cr.json()["id"]
    resp = client.post(f"/groups/{gid}/agent/runs", json={"goal": "G", "conversation_id": cid, "project_id": pid2}, headers=h)
    assert resp.status_code == 409


def test_agent_rejects_scoped_project_with_unscoped_conversation(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    conv = client.post(
        f"/groups/{gid}/conversations", json={"title": "Unscoped"}, headers=h
    ).json()

    resp = client.post(f"/groups/{gid}/agent/runs", json={
        "goal": "G", "conversation_id": conv["id"], "project_id": pid,
    }, headers=h)
    assert resp.status_code == 409


def test_agent_conversation_must_be_owned_by_caller(client, db_session):
    gid = new_id()
    own, mem = _setup_users(db_session, gid)
    db_session.commit()
    owner_h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    member_h = _auth_headers(client, f"mem-{gid[:8]}@t.com")
    conv = client.post(
        f"/groups/{gid}/conversations", json={"title": "Private"}, headers=owner_h
    ).json()

    resp = client.post(f"/groups/{gid}/agent/runs", json={
        "goal": "G", "conversation_id": conv["id"],
    }, headers=member_h)
    assert resp.status_code == 404


def test_agent_detail_preserves_project_id(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    run = client.post(
        f"/groups/{gid}/agent/runs", json={"goal": "G", "project_id": pid}, headers=h
    ).json()

    detail = client.get(f"/groups/{gid}/agent/runs/{run['id']}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["project_id"] == pid


def test_agent_archived_project_block_execute(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup_users(db_session, gid)
    _add_project(db_session, gid, pid, own)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(f"/groups/{gid}/agent/runs", json={"goal": "G", "project_id": pid}, headers=h)
    rid = resp.json()["id"]
    db_session.execute(BusinessProject.__table__.update().where(BusinessProject.id == pid).values(status="archived"))
    db_session.commit()
    resp2 = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    assert resp2.status_code == 409


# ═══════════════════════════════════════════════════════════════
#  No backfill
# ═══════════════════════════════════════════════════════════════

def test_existing_records_project_id_null(client, db_session):
    """Pre-0025 records have null project_id — no auto-backfill."""
    gid = new_id()
    own, _ = _setup_users(db_session, gid)
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")

    # Create unscoped conversation
    cr = client.post(f"/groups/{gid}/conversations", json={"title": "Old"}, headers=h)
    cid = cr.json()["id"]
    detail = client.get(f"/groups/{gid}/conversations/{cid}", headers=h)
    assert detail.json()["project_id"] is None
