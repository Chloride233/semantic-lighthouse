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


def _execute(client, gid, h, rid):
    """Execute one step of the agent loop and assert HTTP < 400."""
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    assert r.status_code < 400, f"execute failed: {r.status_code} {r.text[:200]}"
    return r


def _respond(client, gid, h, rid, response):
    """Send a respond and assert HTTP < 400."""
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": response}, headers=h)
    assert r.status_code < 400, f"respond failed: {r.status_code} {r.text[:200]}"
    return r


def _run_agent(client, gid, h, rid, decisions):
    """Run agent loop to completion, auto-confirming risky prompts."""
    loop_client = FakeLoopChatClient(decisions)
    for _ in range(10):
        with mock.patch("semantic_lighthouse.services.chat.create_chat_client", return_value=loop_client):
            _execute(client, gid, h, rid)
        s = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()["status"]
        if s == "awaiting_confirmation":
            _respond(client, gid, h, rid, "yes")
        elif s in ("completed", "stopped", "failed"):
            break


# ── E1 — finalize with useful answer —──────────────────────────────────

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


# ── E2 — call_tool list_documents —─────────────────────────────────────

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


# ── E3 — archived doc excluded —────────────────────────────────────────

def test_eval_archived_doc_excluded_from_evidence(client, tmp_path):
    _, _, h = register_and_login(client, "e3@t.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "r.md", "# Ready\n\nOntology content.")
    UNIQUE = "ArchivedSecretDoNotLeak"
    aid = _upload(client, gid, h, "arch.md", f"# Old\n\n{UNIQUE} — outdated Ontology notes.")
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
    assert UNIQUE not in obs, f"Archived secret leaked: {obs[:200]}"
    assert "No matching" not in obs, "Expected ready doc to be found (empty result = weak test)"


# ── E4 — risky triggers confirmation (no auto-confirm) ─────────────────

def test_eval_risky_triggers_confirmation(client, tmp_path):
    _, _, h = register_and_login(client, "e4@t.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "doc.md", "# T\n\nc")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Archive"}, headers=h).json()["id"]
    decisions = [{"action": "call_tool", "tool_name": "archive_document",
                   "tool_arguments": {"title": "T"}, "thought": "A"}]
    loop_client = FakeLoopChatClient(decisions)

    # Step 1: execute — must pause for confirmation
    with mock.patch("semantic_lighthouse.services.chat.create_chat_client", return_value=loop_client):
        r = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    assert r.status_code < 400
    d = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert d["status"] == "awaiting_confirmation", f"Expected awaiting_confirmation, got {d['status']}"
    ask_steps = [s for s in d.get("steps", []) if s["action_type"] == "ask_user"]
    assert ask_steps, "Expected ask_user step for confirmation"
    ad = ask_steps[-1].get("action_detail", {})
    assert ad.get("needs_confirmation") is True or ad.get("requires_confirmation") is True, \
        f"Confirmation metadata missing: {ad}"
    # Confirm the risky action was paused — documents still ready
    docs = client.get(f"/groups/{gid}/documents", headers=h).json()
    assert any(d["status"] == "ready" for d in docs), "Risky action may have executed without confirmation"


# ── E5 — invalid tool rejected with audit —─────────────────────────────

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
    assert failed, "Invalid tool not rejected — no failed step"
    fs = failed[0]
    assert fs["action_type"] == "tool_call", f"Expected tool_call action_type, got {fs['action_type']}"
    ad = fs.get("action_detail") or {}
    assert ad.get("tool") == "delete_everything", f"Tool name not recorded: {ad}"
    err = (fs.get("error_message") or "") + (fs.get("observation") or "")
    assert any(kw in err.lower() for kw in ("error", "unknown tool", "not in agent_tools")), \
        f"Audit message missing error/unknown tool keywords: {err[:200]}"
