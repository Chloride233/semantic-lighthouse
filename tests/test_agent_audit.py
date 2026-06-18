"""Agent audit hardening tests — Fix 1 (archive audit fields) + Fix 2 (HITL event persistence).

Independent from test_agent.py; copies necessary helpers locally.
"""

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings


def _settings(path) -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        cookie_secure=False,
        cookie_samesite="lax",
        knowledge_base_path=str(path),
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=8,
        chat_provider="fake",
        chat_model="fake-chat",
        rag_top_k=3,
    )


def _ovr(client, s):
    client.app.dependency_overrides[get_settings] = lambda: s


def _group(client, h, name="Team"):
    r = client.post("/groups", json={"name": name}, headers=h)
    assert r.status_code == 201
    return r.json()["id"]


def _upload(client, gid, h, name, text):
    r = client.post(
        f"/groups/{gid}/documents/upload",
        files={"file": (name, text.encode(), "text/markdown")},
        headers=h,
    )
    assert r.status_code == 201
    return r.json()["id"]


def _join(client, gid, owner_h, member_h):
    inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
    assert inv.status_code == 201
    code = inv.json()["invite_code"]
    r = client.post(
        "/groups/join-by-invite",
        json={"invite_code": code},
        headers=member_h,
    )
    assert r.status_code == 200


# ── Fix 1: Agent archive audit fields ──────────────────────────────────


def test_agent_archive_sets_audit_fields(client, tmp_path):
    """Agent archive_document via V1 path sets archived_by, archived_at, archive_reason."""
    _, _, h = register_and_login(client, "arc@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    content = "# Test\n\narchive target"
    doc_id = _upload(client, gid, h, "doc.md", content)
    rid = client.post(
        f"/groups/{gid}/agent/runs",
        json={"goal": "Test"},
        headers=h,
    ).json()["id"]
    client.post(
        f"/groups/{gid}/agent/runs/{rid}/execute",
        params={"tool": "archive_document"},
        headers=h,
    )
    client.post(
        f"/groups/{gid}/agent/runs/{rid}/respond",
        json={"response": "yes"},
        headers=h,
    )
    doc = client.get(f"/groups/{gid}/documents/{doc_id}", headers=h).json()
    assert doc["status"] == "archived"
    assert doc["archived_by"] is not None, "archived_by must be set"
    assert doc["archived_at"] is not None, "archived_at must be set"
    assert doc["archive_reason"] is not None, "archive_reason must be set"


def test_formal_archive_still_works(client, tmp_path):
    """POST /documents/{id}/archive still returns correct audit fields."""
    _, _, h = register_and_login(client, "fma@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    content = "# Test\n\ncontent"
    doc_id = _upload(client, gid, h, "doc.md", content)
    r = client.post(
        f"/groups/{gid}/documents/{doc_id}/archive", headers=h
    )
    assert r.status_code == 200
    doc = r.json()
    assert doc["status"] == "archived"
    assert doc["archived_by"] is not None
    assert doc["archived_at"] is not None
    assert doc["archive_reason"] is not None


# ── Fix 2: HITL audit event persistence ────────────────────────────────


def test_hitl_confirm_creates_audit_steps(client, tmp_path):
    """Respond yes: original ask_user preserved + confirmation step + tool_call step."""
    _, _, h = register_and_login(client, "ht1@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    _upload(client, gid, h, "doc.md", "# Test\n\ncontent")
    rid = client.post(
        f"/groups/{gid}/agent/runs",
        json={"goal": "Test"},
        headers=h,
    ).json()["id"]
    client.post(
        f"/groups/{gid}/agent/runs/{rid}/execute",
        params={"tool": "archive_document"},
        headers=h,
    )
    run_before = client.get(
        f"/groups/{gid}/agent/runs/{rid}", headers=h
    ).json()
    original_ask = [
        s for s in run_before["steps"] if s["action_type"] == "ask_user"
    ]
    assert len(original_ask) == 1, "Expected one original ask_user step"

    client.post(
        f"/groups/{gid}/agent/runs/{rid}/respond",
        json={"response": "yes"},
        headers=h,
    )
    run_after = client.get(
        f"/groups/{gid}/agent/runs/{rid}", headers=h
    ).json()

    ask_steps = [
        s for s in run_after["steps"] if s["action_type"] == "ask_user"
    ]
    assert len(ask_steps) >= 2, (
        f"Expected >=2 ask_user steps, got {len(ask_steps)}"
    )
    first_ask = ask_steps[0]
    ad = first_ask.get("action_detail") or {}
    assert ad.get("needs_confirmation") or ad.get(
        "requires_confirmation"
    ), "Original ask_user step must still carry confirmation request"

    confirm_steps = [
        s
        for s in ask_steps
        if (s.get("action_detail") or {}).get("confirmed")
    ]
    assert len(confirm_steps) == 1, "Expected user confirmation step"
    cs = confirm_steps[0]
    assert (cs.get("action_detail") or {}).get("user_id") is not None
    assert (cs.get("action_detail") or {}).get("responded_at") is not None

    tool_steps = [
        s
        for s in run_after["steps"]
        if s["action_type"] == "tool_call"
    ]
    assert tool_steps, "Expected a tool_call step after confirmation"

    docs = client.get(f"/groups/{gid}/documents", headers=h).json()
    archived = [d for d in docs if d["status"] == "archived"]
    assert archived, "Document should be archived after confirm + execution"


def test_hitl_reject_creates_rejection_step(client, tmp_path):
    """Respond no: original ask_user preserved + rejection step; doc NOT archived."""
    _, _, h = register_and_login(client, "ht2@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    doc_id = _upload(client, gid, h, "doc.md", "# Test\n\nkeep me")
    rid = client.post(
        f"/groups/{gid}/agent/runs",
        json={"goal": "Test"},
        headers=h,
    ).json()["id"]
    client.post(
        f"/groups/{gid}/agent/runs/{rid}/execute",
        params={"tool": "archive_document"},
        headers=h,
    )
    run_before = client.get(
        f"/groups/{gid}/agent/runs/{rid}", headers=h
    ).json()
    assert run_before["status"] == "awaiting_confirmation"

    client.post(
        f"/groups/{gid}/agent/runs/{rid}/respond",
        json={"response": "no"},
        headers=h,
    )
    run_after = client.get(
        f"/groups/{gid}/agent/runs/{rid}", headers=h
    ).json()
    assert run_after["status"] == "executing"

    ask_steps = [
        s for s in run_after["steps"] if s["action_type"] == "ask_user"
    ]
    assert len(ask_steps) >= 2, (
        f"Expected >=2 ask_user steps, got {len(ask_steps)}"
    )
    first_ask = ask_steps[0]
    assert (first_ask.get("action_detail") or {}).get(
        "needs_confirmation"
    ) or (first_ask.get("action_detail") or {}).get("requires_confirmation")

    reject_steps = [
        s
        for s in ask_steps
        if (s.get("action_detail") or {}).get("rejected")
    ]
    assert len(reject_steps) == 1, "Expected user rejection step"
    rs = reject_steps[0]
    assert (rs.get("action_detail") or {}).get("user_id") is not None
    assert "REJECTED" in (rs.get("observation") or "")

    doc = client.get(f"/groups/{gid}/documents/{doc_id}", headers=h).json()
    assert (
        doc["status"] != "archived"
    ), "Document must NOT be archived after rejection"


def test_risky_tool_not_executed_before_confirm(client, tmp_path):
    """High-risk tool pauses; document unchanged until user confirms."""
    _, _, h = register_and_login(client, "ht3@e.com")
    gid = _group(client, h)
    _ovr(client, _settings(tmp_path))
    doc_id = _upload(client, gid, h, "doc.md", "# Test\n\nsafe")
    rid = client.post(
        f"/groups/{gid}/agent/runs",
        json={"goal": "Test"},
        headers=h,
    ).json()["id"]
    client.post(
        f"/groups/{gid}/agent/runs/{rid}/execute",
        params={"tool": "archive_document"},
        headers=h,
    )
    doc = client.get(f"/groups/{gid}/documents/{doc_id}", headers=h).json()
    assert (
        doc["status"] == "ready"
    ), "Document should NOT be archived before user confirmation"
