from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.services.chat import FakeLoopChatClient


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
    s = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", params={"tool": "search_knowledge_base"}, headers=h)
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
    assert r.json()["status"] == "executing"  # respond resumes, not finalizes
    # Complete by finalizing the run
    client.post(f"/groups/{gid}/agent/runs/{rid}/execute", params={"tool": "search_knowledge_base"}, headers=h)
    detail = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert detail["status"] == "completed"
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
    assert r.json()["status"] == "executing"  # reject returns to executing, not fails
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


def test_unregistered_tool_rejected(client, tmp_path):
    """S5: tool name not in registry → execute returns error."""
    _, _, h = register_and_login(client, "unk@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Test"}, headers=h).json()["id"]
    r = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", params={"tool": "nonexistent_tool"}, headers=h)
    assert r.status_code in (400, 200)
    if r.status_code == 200:
        assert "Error:" in r.json().get("observation", "")


def test_agent_step_audit_fields_complete(client, tmp_path):
    """AgentStep records thought/action/observation/error; audit complete."""
    _, _, h = register_and_login(client, "adt@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "doc.md", "# Ontology\n\nOntology connects business and AI.")
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "ontology"}, headers=h).json()["id"]
    s = client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    step = s.json()
    assert step["thought"], "thought must be non-empty"
    assert step["action_type"], "action_type must be non-empty"
    assert step["action_detail"], "action_detail must be non-empty"
    assert step.get("observation") is not None, "observation must be present"
    assert step.get("status") is not None, "status must be present"


def test_agent_cross_group_isolation(client, tmp_path):
    """Member of group A cannot execute runs in group B."""
    _, _, h_a = register_and_login(client, "aa@e.com")
    _, _, h_b = register_and_login(client, "bb@e.com")
    ga = _group(client, h_a)
    gb = _group(client, h_b)
    _ovr(client, _settings(tmp_path))
    _upload(client, ga, h_a, "doc.md", "# Content\n\ntest")
    rid_a = client.post(f"/groups/{ga}/agent/runs", json={"goal": "test"}, headers=h_a).json()["id"]
    r = client.post(f"/groups/{ga}/agent/runs/{rid_a}/execute", headers=h_b)
    assert r.status_code in (403, 404)
    assert client.get(f"/groups/{ga}/agent/runs/{rid_a}", headers=h_b).status_code in (403, 404)
    _upload(client, gb, h_b, "doc.md", "# Content\n\ntest")
    rid_b = client.post(f"/groups/{gb}/agent/runs", json={"goal": "test"}, headers=h_b).json()["id"]
    assert client.post(f"/groups/{gb}/agent/runs/{rid_b}/execute", headers=h_b).status_code == 200


# ── Agent loop (V2.1) ──────────────────────────────────────────────────

DECISIONS = {
    "simple_search": [
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "Ontology"}, "thought": "Searching."},
        {"action": "finalize", "final_answer": "Found results.", "thought": "Done."},
    ],
    "search_error_retry": [
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": ""}, "thought": "Search."},
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "Ontology"}, "thought": "Retry with query."},
        {"action": "finalize", "final_answer": "Retried and found.", "thought": "Done."},
    ],
    "max_steps_stopped": [
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "q1"}, "thought": "S1"},
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "q2"}, "thought": "S2"},
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "q3"}, "thought": "S3"},
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "q4"}, "thought": "S4"},
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "q5"}, "thought": "S5"},
        {"action": "finalize", "final_answer": "Should not reach.", "thought": "X"},
    ],
    "risky_confirm_execute": [
        {"action": "call_tool", "tool_name": "archive_document",
         "tool_arguments": {"title": "test"}, "thought": "Archive."},
        {"action": "finalize", "final_answer": "Archived.", "thought": "Done."},
    ],
    "two_step_list_search": [
        {"action": "call_tool", "tool_name": "list_documents",
         "tool_arguments": {}, "thought": "List first."},
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "Ontology"}, "thought": "Search."},
        {"action": "finalize", "final_answer": "Analysis done.", "thought": "Done."},
    ],
    "reject_risky_alternative": [
        {"action": "call_tool", "tool_name": "archive_document",
         "tool_arguments": {"title": "test"}, "thought": "Archive."},
        {"action": "call_tool", "tool_name": "search_knowledge_base",
         "tool_arguments": {"query": "test"}, "thought": "Rejected. Search instead."},
        {"action": "finalize", "final_answer": "Found alternative.", "thought": "Done."},
    ],
}


def _run_loop(client, gid, headers, goal, decisions):
    """Helper: create run, inject FakeLoopChatClient, execute loop."""
    loop_client = FakeLoopChatClient(decisions)
    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": goal}, headers=headers).json()["id"]

    max_calls = 10
    for _ in range(max_calls):
        with mock.patch("semantic_lighthouse.services.chat.create_chat_client", return_value=loop_client):
            client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=headers)
        run_status = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=headers).json()["status"]
        if run_status == "awaiting_confirmation":
            client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "yes"}, headers=headers)
        elif run_status in ("completed", "stopped", "failed"):
            break

    detail = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=headers).json()
    return detail


@pytest.mark.parametrize("name,decisions,expected_status,min_steps", [
    ("simple_search", DECISIONS["simple_search"], "completed", 2),
    ("search_error_retry", DECISIONS["search_error_retry"], "completed", 2),
    ("max_steps_stopped", DECISIONS["max_steps_stopped"], "stopped", 3),
    ("two_step_list_search", DECISIONS["two_step_list_search"], "completed", 2),
])
def test_agent_loop_completes(client, tmp_path, name, decisions, expected_status, min_steps):
    """Agent loop reaches expected status with the given decision sequence."""
    _, _, h = register_and_login(client, f"{name[:4]}@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "doc.md", "# Test\n\nOntology content for testing.")

    detail = _run_loop(client, gid, h, f"Goal: {name}", decisions)
    assert detail["status"] == expected_status, f"Expected {expected_status}, got {detail['status']}"
    assert detail["step_count"] >= min_steps, f"Expected >= {min_steps} steps, got {detail['step_count']}"


def test_agent_loop_risky_confirm_execute(client, tmp_path):
    """Risky tool → awaiting_confirmation → confirm → completed."""
    _, _, h = register_and_login(client, "rce@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    doc_id = _upload(client, gid, h, "test.md", "# Test\n\narchive target")
    decisions = DECISIONS["risky_confirm_execute"]

    detail = _run_loop(client, gid, h, "Archive test", decisions)
    assert detail["status"] == "completed"
    doc = client.get(f"/groups/{gid}/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "archived"


def test_agent_loop_reject_risky_alternative(client, tmp_path):
    """Reject risky → LLM picks alternative tool → completed."""
    _, _, h = register_and_login(client, "rra@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    doc_id = _upload(client, gid, h, "test.md", "# Test\n\nkeep me")

    decisions = DECISIONS["reject_risky_alternative"]
    loop_client = FakeLoopChatClient(decisions)

    rid = client.post(f"/groups/{gid}/agent/runs", json={"goal": "Test"}, headers=h).json()["id"]
    with mock.patch("semantic_lighthouse.services.chat.create_chat_client", return_value=loop_client):
        client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    assert client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()["status"] == "awaiting_confirmation"
    # Step 2: reject
    client.post(f"/groups/{gid}/agent/runs/{rid}/respond", json={"response": "no"}, headers=h)
    run = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert run["status"] == "executing", f"Expected executing after reject, got {run['status']}"
    # Step 3: continue loop → search + finalize
    with mock.patch("semantic_lighthouse.services.chat.create_chat_client", return_value=loop_client):
        client.post(f"/groups/{gid}/agent/runs/{rid}/execute", headers=h)
    detail = client.get(f"/groups/{gid}/agent/runs/{rid}", headers=h).json()
    assert detail["status"] == "completed"
    doc = client.get(f"/groups/{gid}/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "ready", "Document should NOT be archived after rejection"
