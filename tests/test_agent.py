from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings


def _settings(path: Path) -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        cookie_secure=False, cookie_samesite="lax",
        knowledge_base_path=str(path),
        embedding_provider="fake", embedding_model="fake-embedding", embedding_dimension=8,
        chat_provider="fake", chat_model="fake-chat", rag_top_k=3,
    )


def _ovr(client: TestClient, s: Settings) -> None:
    client.app.dependency_overrides[get_settings] = lambda: s


def _group(client: TestClient, h: dict, name: str = "Team") -> str:
    r = client.post("/groups", json={"name": name}, headers=h)
    assert r.status_code == 201
    return r.json()["id"]


def _upload(client: TestClient, gid: str, h: dict, name: str, text: str) -> str:
    r = client.post(
        f"/groups/{gid}/documents/upload",
        files={"file": (name, text.encode(), "text/markdown")},
        headers=h,
    )
    assert r.status_code == 201
    return r.json()["id"]


def _join(client: TestClient, gid: str, owner_h: dict, member_h: dict) -> None:
    inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
    assert inv.status_code == 201
    code = inv.json()["invite_code"]
    r = client.post("/groups/join-by-invite", json={"invite_code": code}, headers=member_h)
    assert r.status_code == 200


# ── runs ──────────────────────────────────────────────────────────────


def test_create_agent_run(client, tmp_path):
    _, _, h = register_and_login(client, "a@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))

    resp = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Find ontology"}, headers=h)
    assert resp.status_code == 201
    d = resp.json()
    assert d["goal"] == "Find ontology"
    assert d["status"] == "planning"
    assert d["current_phase"] == "plan"
    assert d["step_count"] == 1


def test_non_member_cannot_create(client, tmp_path):
    _, _, o = register_and_login(client, "o@e.com")
    _, _, x = register_and_login(client, "x@e.com")
    gid = _group(client, o)
    _ovr(client, _settings(tmp_path))
    assert client.post(f"/groups/{gid}/agent/runs", json={"goal": "X"}, headers=x).status_code == 403


def test_list_own_only(client, tmp_path):
    _, _, o = register_and_login(client, "o@e.com")
    _, _, m = register_and_login(client, "m@e.com")
    gid = _group(client, o)
    _join(client, gid, o, m)
    _ovr(client, _settings(tmp_path))
    client.post(f"/groups/{gid}/agent/runs", json={"goal": "O"}, headers=o)
    assert len(client.get(f"/groups/{gid}/agent/runs", headers=o).json()) == 1
    assert client.get(f"/groups/{gid}/agent/runs", headers=m).json() == []


def test_get_detail(client, tmp_path):
    _, _, h = register_and_login(client, "a@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "S"}, headers=h).json()["id"]
    d = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert d["goal"] == "S" and len(d["steps"]) == 1


def test_cannot_access_others(client, tmp_path):
    _, _, o = register_and_login(client, "o@e.com")
    _, _, m = register_and_login(client, "m@e.com")
    gid = _group(client, o)
    _ovr(client, _settings(tmp_path))
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "O"}, headers=o).json()["id"]
    assert client.get(f"/groups/{gid}/agent/runs/{rid}", headers=m).status_code == 403


def test_execute_runs_search(client, tmp_path):
    _, _, h = register_and_login(client, "a@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "onto.md", "# Ontology\n\nOntology connects business and AI.")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "ontology"}, headers=h).json()["id"]
    s = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    assert s.status_code == 200 and s.json()["status"] == "completed"
    assert "Ontology" in s.json()["observation"]
    assert client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()["status"] == "completed"


def test_execute_finished_rejected(client, tmp_path):
    _, _, h = register_and_login(client, "a@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "test"}, headers=h).json()["id"]
    client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    assert client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h).status_code == 400


def test_user_reject_fails(client, tmp_path):
    _, _, h = register_and_login(client, "a@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "test"}, headers=h).json()["id"]
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "reject"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "failed"


def test_user_confirm_resumes(client, tmp_path):
    _, _, h = register_and_login(client, "a@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "test"}, headers=h).json()["id"]
    assert client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "yes"}, headers=h).json()["status"] == "executing"


def test_memory_crud(client, tmp_path):
    _, _, h = register_and_login(client, "a@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))

    r = client.post(f"/groups/{gid}/agent/memories", json={"key": "k", "value": "v1", "scope": "user"}, headers=h)
    assert r.status_code == 201
    mid = r.json()["id"]

    assert len(client.get(f"/groups/{gid}/agent/memories", headers=h).json()) == 1

    r2 = client.post(f"/groups/{gid}/agent/memories", json={"key": "k", "value": "v2", "scope": "user"}, headers=h)
    assert r2.status_code == 201 and r2.json()["id"] == mid and r2.json()["value"] == "v2"

    assert client.delete(f"/groups/{gid}/agent/memories/{mid}", headers=h).status_code == 204
    assert client.get(f"/groups/{gid}/agent/memories", headers=h).json() == []


# ── Agent eval: risky tool confirmation ─────────────────────────────────

def test_risky_tool_requires_confirmation(client, tmp_path):
    """S2: archive_document is risky → execute pauses for confirmation."""
    _, _, h = register_and_login(client, "rsk@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "doc.md", "# Test\n\ncontent")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Test"}, headers=h).json()["id"]
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", params={"tool": "archive_document"}, headers=h)
    assert r.status_code == 200
    step = r.json()
    assert step["action_detail"]["needs_confirmation"] is True
    run = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert run["status"] == "awaiting_confirmation"


def test_risky_tool_confirmed_then_executed(client, tmp_path):
    """S2b: confirm → tool executes → document archived."""
    _, _, h = register_and_login(client, "cnf@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    doc_id = _upload(client, gid, h, "doc.md", "# Test\n\ncontent")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Test"}, headers=h).json()["id"]
    client.post(f"/groups/{gid}/agent/runs/{rid}/execute", params={"tool": "archive_document"}, headers=h)
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "yes"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    detail = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert detail["final_answer"] is not None
    doc = client.get(f"/groups/{gid}/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "archived"


def test_risky_tool_rejected_stops(client, tmp_path):
    """S3: reject → run failed, document NOT archived."""
    _, _, h = register_and_login(client, "rej@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    doc_id = _upload(client, gid, h, "doc.md", "# Test\n\nkeep me")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Test"}, headers=h).json()["id"]
    client.post(f"/groups/{gid}/agent/runs/{rid}/execute", params={"tool": "archive_document"}, headers=h)
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "reject"}, headers=h)
    assert r.json()["status"] == "failed"
    doc = client.get(f"/groups/{gid}/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "ready"


def test_non_admin_cannot_use_archive_tool(client, tmp_path):
    """S4: member tries archive_document → role error blocks execution."""
    _, _, owner_h = register_and_login(client, "own@e.com")
    _, _, member_h = register_and_login(client, "mem@e.com")
    gid = _group(client, owner_h)
    _join(client, gid, owner_h, member_h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, owner_h, "doc.md", "# Test\n\ncontent")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Test"}, headers=member_h).json()["id"]
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", params={"tool": "archive_document"}, headers=member_h)
    step = r.json()
    if step.get("action_detail", {}).get("needs_confirmation"):
        # Risky check fired — confirm, then expect role error in tool execution
        client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "yes"}, headers=member_h)
        run = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=member_h).json()
        last_step = run.get("steps", [])[-1] if run.get("steps") else {}
        assert "Error:" in str(last_step.get("observation", "")) or "failed" in str(run.get("status", ""))
    else:
        assert "Error:" in step.get("observation", "")
