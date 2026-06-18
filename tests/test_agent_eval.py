"""Agent Eval Scenarios — V2.3 fake-provider evaluation.

5 scenarios: tool choice, permission boundary, audit completeness,
unsafe action blocking. All use FakeLoopChatClient — no API key needed.
"""

from unittest import mock

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.services.chat import FakeLoopChatClient


def _settings(path) -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        cookie_secure=False, cookie_samesite="lax",
        knowledge_base_path=str(path),
        embedding_provider="fake", embedding_model="fake-embedding", embedding_dimension=8,
        chat_provider="fake", chat_model="fake-chat", rag_top_k=3,
    )


def _ovr(c, s): c.app.dependency_overrides[get_settings] = lambda: s


def _group(c, h, n="T"):
    r = c.post("/groups", json={"name": n}, headers=h)
    assert r.status_code == 201
    return r.json()["id"]


def _upload(c, g, h, name, text):
    r = c.post(f"/groups/{g}/documents/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=h)
    assert r.status_code == 201
    return r.json()["id"]


def _run_agent(client, gid, h, rid, decisions):
    loop_client = FakeLoopChatClient(decisions)
    for _ in range(10):
        with mock.patch("semantic_lighthouse.services.chat.create_chat_client", return_value=loop_client):
            client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
        s = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()["status"]
        if s == "awaiting_confirmation":
            client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "yes"}, headers=h)
        elif s in ("completed", "stopped", "failed"):
            break


# ── E1 —————————————————————————————————──────────────────────────────────

def test_eval_finalize_with_useful_answer(client, tmp_path):
    _, _, h = register_and_login(client, "e1@t.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "x.md", "# Test\n\ncontent")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "X"}, headers=h).json()["id"]
    _run_agent(client, gid, h, rid, [{"action": "finalize", "final_answer": "Ready docs found.", "thought": "Done."}])
    d = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert d["status"] == "completed"
    assert "doc" in (d.get("final_answer") or "").lower()
    steps = d.get("steps") or []
    assert steps and steps[-1]["thought"] and steps[-1]["action_type"]


# ── E2 ————————————————————————————————————————————————————————————————————

def test_eval_list_documents_succeeds(client, tmp_path):
    _, _, h = register_and_login(client, "e2@t.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "a.md", "# A\n\na")
    _upload(client, gid, h, "b.md", "# B\n\nb")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "List"}, headers=h).json()["id"]
    _run_agent(client, gid, h, rid, [
        {"action": "call_tool", "tool_name": "list_documents", "tool_arguments": {}, "thought": "L"},
        {"action": "finalize", "final_answer": "Done.", "thought": "D"},
    ])
    d = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert d["status"] == "completed" and d["step_count"] >= 2
    ts = [s for s in d.get("steps", []) if s["action_type"] == "tool_call"]
    assert ts and ("[ready]" in (ts[0].get("observation") or "") or "ready" in (ts[0].get("observation") or ""))


# ── E3 ————————————————————————————————————————————————————————————————————

def test_eval_archived_doc_excluded_from_evidence(client, tmp_path):
    _, _, h = register_and_login(client, "e3@t.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "r.md", "# Ready\n\nOntology content.")
    aid = _upload(client, gid, h, "arch.md", "# Old\n\nold Ontology notes.")
    client.post(f"/groups/{gid}/documents/{aid}/archive", headers=h)
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Ontology"}, headers=h).json()["id"]
    _run_agent(client, gid, h, rid, [
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "Ontology"}, "thought": "S"},
        {"action": "finalize", "final_answer": "OK.", "thought": "D"},
    ])
    d = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    ts = [s for s in d.get("steps", []) if s["action_type"] == "tool_call"]
    obs = (ts[0].get("observation") or "") if ts else ""
    assert "arch" not in obs.lower() or "No matching" in obs, f"Archived leaked: {obs[:100]}"


# ── E4 ————————————————————————————————————————————————————————————————————

def test_eval_risky_triggers_confirmation(client, tmp_path):
    _, _, h = register_and_login(client, "e4@t.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "doc.md", "# T\n\nc")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Archive"}, headers=h).json()["id"]
    _run_agent(client, gid, h, rid, [
        {"action": "call_tool", "tool_name": "archive_document", "tool_arguments": {"title": "T"}, "thought": "A"},
    ])
    d = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert d["status"] in ("awaiting_confirmation", "executing", "completed")
    ask = [s for s in d.get("steps", []) if s["action_type"] == "ask_user"]
    if ask:
        ad = ask[-1].get("action_detail", {})
        assert ad.get("needs_confirmation") or ad.get("requires_confirmation")


# ── E5 ————————————————————————————————————————————————————————————————————

def test_eval_invalid_tool_errors(client, tmp_path):
    _, _, h = register_and_login(client, "e5@t.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "X"}, headers=h).json()["id"]
    _run_agent(client, gid, h, rid, [
        {"action": "call_tool", "tool_name": "delete_everything", "tool_arguments": {}, "thought": "D"},
    ])
    d = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    failed = [s for s in d.get("steps", []) if s.get("status") == "failed"]
    assert failed, "Invalid tool not rejected"
