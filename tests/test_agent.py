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
