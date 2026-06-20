"""S2.3B — Project-bounded Retrieval & Agent Tools tests."""

from semantic_lighthouse.models import (
    AgentRun,
    AgentStep,
    BusinessProject,
    Document,
    DocumentChunk,
    Group,
    GroupMembership,
    ProjectEvidenceLink,
    User,
    new_id,
)
from semantic_lighthouse.security import hash_password
from semantic_lighthouse.services.retrieval import (
    hybrid_search,
    project_document_ids,
    _keyword_search,
)


def _auth_headers(client, email):
    resp = client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _setup(db, gid, with_project=False):
    own = new_id()
    mem = new_id()
    db.add(User(id=own, email=f"own-{gid[:8]}@t.com", display_name="O", password_hash=hash_password("Passw0rd!")))
    db.add(User(id=mem, email=f"mem-{gid[:8]}@t.com", display_name="M", password_hash=hash_password("Passw0rd!")))
    db.add(Group(id=gid, name="G", created_by=own))
    db.add(GroupMembership(group_id=gid, user_id=own, role="owner"))
    db.add(GroupMembership(group_id=gid, user_id=mem, role="member"))
    if with_project:
        pid = new_id()
        db.add(BusinessProject(id=pid, group_id=gid, name="P", business_goal="G", entry_mode="data_first", created_by=own))
        return own, mem, pid
    return own, mem


def _add_doc(db, gid, did, title="Doc", status="ready"):
    db.add(Document(
        id=did, group_id=gid, title=title, file_name=f"{did[:8]}.md",
        source_path=f"kb/{did[:8]}.md", content_hash=f"h-{did[:8]}",
        frontmatter={"source": "kb"}, raw_content=f"# {title}\n\nContent for {title}.",
        status=status, created_by="user-1",
    ))


def _add_chunk(db, gid, did, cid=None, content=None):
    c = content or "Test chunk content for search."
    db.add(DocumentChunk(
        id=cid or new_id(), document_id=did, group_id=gid,
        chunk_index=0, heading_path="Test chunk", content=c,
        content_hash=f"ch-{did[:8]}-{cid[:4] if cid else '0'}",
    ))


# ═══════════════════════════════════════════════════════════════
#  project_document_ids helper
# ═══════════════════════════════════════════════════════════════

def test_project_doc_ids_none_for_unscoped(db_session):
    assert project_document_ids(db_session, "any", None) is None


def test_project_doc_ids_empty_when_no_links(db_session):
    gid, pid = new_id(), new_id()
    own = new_id()
    db_session.add(Group(id=gid, name="G", created_by=own))
    db_session.add(BusinessProject(id=pid, group_id=gid, name="P", business_goal="G", entry_mode="data_first", created_by=own))
    db_session.commit()
    assert project_document_ids(db_session, gid, pid) == set()


def test_project_doc_ids_includes_active_links(db_session):
    gid, pid = new_id(), new_id()
    own = new_id()
    did = new_id()
    db_session.add(Group(id=gid, name="G", created_by=own))
    db_session.add(BusinessProject(id=pid, group_id=gid, name="P", business_goal="G", entry_mode="data_first", created_by=own))
    db_session.add(Document(id=did, group_id=gid, title="D", file_name="d.md", source_path="d.md", content_hash="h", frontmatter={}, raw_content="# D", status="ready", created_by=own))
    db_session.add(ProjectEvidenceLink(id=new_id(), group_id=gid, project_id=pid, evidence_type="document", evidence_id=did, role="context", status="active", created_by=own))
    db_session.commit()
    assert project_document_ids(db_session, gid, pid) == {did}


def test_project_doc_ids_excludes_removed_links(db_session):
    gid, pid = new_id(), new_id()
    own = new_id()
    did = new_id()
    db_session.add(Group(id=gid, name="G", created_by=own))
    db_session.add(BusinessProject(id=pid, group_id=gid, name="P", business_goal="G", entry_mode="data_first", created_by=own))
    db_session.add(Document(id=did, group_id=gid, title="D", file_name="d.md", source_path="d.md", content_hash="h", frontmatter={}, raw_content="# D", status="ready", created_by=own))
    db_session.add(ProjectEvidenceLink(id=new_id(), group_id=gid, project_id=pid, evidence_type="document", evidence_id=did, role="context", status="removed", created_by=own))
    db_session.commit()
    assert project_document_ids(db_session, gid, pid) == set()


# ═══════════════════════════════════════════════════════════════
#  keyword search bounded
# ═══════════════════════════════════════════════════════════════

def test_keyword_empty_allowed_returns_nothing(db_session):
    gid = new_id()
    _setup(db_session, gid)
    did = new_id()
    _add_doc(db_session, gid, did)
    _add_chunk(db_session, gid, did)
    db_session.commit()
    r = _keyword_search(db_session, gid, "test", 10, allowed_document_ids=set())
    assert r == []


def test_keyword_only_allowed_docs(db_session):
    gid = new_id()
    _setup(db_session, gid)
    d1, d2 = new_id(), new_id()
    _add_doc(db_session, gid, d1, "Alpha")
    _add_chunk(db_session, gid, d1, content="unique alpha search term")
    _add_doc(db_session, gid, d2, "Beta")
    _add_chunk(db_session, gid, d2, content="beta content only")
    db_session.commit()
    r = _keyword_search(db_session, gid, "unique alpha", 10, allowed_document_ids={d1})
    assert len(r) > 0
    assert all(c.chunk.document_id == d1 for c in r)


def test_keyword_none_returns_full_group(db_session):
    gid = new_id()
    _setup(db_session, gid)
    d1, d2 = new_id(), new_id()
    _add_doc(db_session, gid, d1, "A")
    _add_chunk(db_session, gid, d1, content="unique gamma search")
    _add_doc(db_session, gid, d2, "B")
    _add_chunk(db_session, gid, d2, content="beta content")
    db_session.commit()
    r = _keyword_search(db_session, gid, "unique gamma", 10)
    assert len(r) > 0


# ═══════════════════════════════════════════════════════════════
#  hybrid search bounded
# ═══════════════════════════════════════════════════════════════

class _FakeSettings:
    embedding_provider = "fake"
    embedding_model = "fake"
    embedding_dimension = 1024
    chat_model = "fake"
    chat_provider = "fake"

def test_hybrid_empty_allowed_returns_nothing(db_session):
    gid = new_id()
    _setup(db_session, gid)
    did = new_id()
    _add_doc(db_session, gid, did)
    _add_chunk(db_session, gid, did)
    db_session.commit()
    r = hybrid_search(db_session, gid, "test", 10, 0.5, _FakeSettings(), allowed_document_ids=set())
    assert r == []


def test_conversation_semantic_passes_allowed_docs(db_session, monkeypatch):
    import semantic_lighthouse.routers.conversations as conversations

    gid = new_id()
    _setup(db_session, gid)
    allowed_id = new_id()
    captured = {}

    def fake_semantic(db, group_id, query, limit, settings, *, allowed_document_ids=None):
        captured["allowed_document_ids"] = allowed_document_ids
        if allowed_document_ids != {allowed_id}:
            blocked_doc = Document(
                id=new_id(), group_id=group_id, title="Blocked", file_name="b.md",
                source_path="b.md", content_hash="b", frontmatter={},
                raw_content="", status="ready", created_by="user-1",
            )
            blocked_chunk = DocumentChunk(
                id=new_id(), document_id=blocked_doc.id, group_id=group_id,
                chunk_index=0, content="blocked", content_hash="blocked",
            )
            return [conversations.ScoredChunk(blocked_chunk, blocked_doc, 1.0, "semantic")]
        return []

    monkeypatch.setattr(conversations, "_semantic_search", fake_semantic)

    results = conversations._retrieve(
        db_session, gid, "semantic", "semantic", 10, _FakeSettings(),
        allowed_document_ids={allowed_id},
    )

    assert captured["allowed_document_ids"] == {allowed_id}
    assert results == []


# ═══════════════════════════════════════════════════════════════
#  Agent tools scoped
# ═══════════════════════════════════════════════════════════════

def test_agent_tool_schemas_excludes_archive_when_scoped():
    from semantic_lighthouse.services.agent_orchestrator import _tool_schemas_for_llm
    unscoped = _tool_schemas_for_llm(project_id=None)
    scoped = _tool_schemas_for_llm(project_id="some-pid")
    unscoped_names = {s["function"]["name"] for s in unscoped}
    scoped_names = {s["function"]["name"] for s in scoped}
    assert "archive_document" in unscoped_names
    assert "archive_document" not in scoped_names


def test_agent_archive_rejected_when_scoped(db_session):
    from semantic_lighthouse.services.agent_orchestrator import execute_tool
    gid = new_id()
    _setup(db_session, gid)
    db_session.commit()
    result = execute_tool("archive_document", {"title": "X"}, db_session, gid, "owner", project_id="some-pid")
    assert "not available" in result


def test_agent_v1_archive_rejected_without_confirmation_when_scoped(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup(db_session, gid)
    db_session.add(
        BusinessProject(
            id=pid, group_id=gid, name="P", business_goal="G",
            entry_mode="data_first", created_by=own,
        )
    )
    run_id = new_id()
    db_session.add(
        AgentRun(
            id=run_id, group_id=gid, user_id=own, project_id=pid,
            goal="Doc", status="planning", plan_json=[], citations=[],
        )
    )
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(
        f"/groups/{gid}/agent/runs/{run_id}/execute",
        params={"tool": "archive_document"},
        headers=h,
    )

    assert resp.status_code == 200
    step = resp.json()
    assert step["action_type"] == "tool_call"
    assert step["status"] == "failed"
    assert "not available" in step["observation"]

    detail = client.get(f"/groups/{gid}/agent/runs/{run_id}", headers=h)
    assert detail.json()["status"] == "failed"


def test_agent_loop_archive_rejected_without_confirmation_when_scoped(db_session):
    from semantic_lighthouse.services.agent_orchestrator import AgentDecision, agent_loop

    gid, pid = new_id(), new_id()
    own, _ = _setup(db_session, gid)
    db_session.add(
        BusinessProject(
            id=pid, group_id=gid, name="P", business_goal="G",
            entry_mode="data_first", created_by=own,
        )
    )
    run = AgentRun(
        id=new_id(), group_id=gid, user_id=own, project_id=pid,
        goal="Doc", status="executing", current_phase="execute",
        plan_json=[], citations=[],
    )
    db_session.add(run)
    db_session.commit()

    step = agent_loop(
        db_session, run, gid, "owner",
        lambda messages, tools: AgentDecision(
            thought="try archive",
            action="call_tool",
            tool_name="archive_document",
            tool_arguments={"title": "Doc"},
        ),
        max_steps=1,
    )

    assert step is not None
    assert step.action_type == "tool_call"
    assert step.status == "failed"
    assert "not available" in (step.observation or "")
    db_session.refresh(run)
    assert run.status == "failed"


def test_agent_legacy_scoped_archive_confirmation_fails_run(client, db_session):
    gid, pid = new_id(), new_id()
    own, _ = _setup(db_session, gid)
    db_session.add(
        BusinessProject(
            id=pid, group_id=gid, name="P", business_goal="G",
            entry_mode="data_first", created_by=own,
        )
    )
    run_id = new_id()
    db_session.add(
        AgentRun(
            id=run_id, group_id=gid, user_id=own, project_id=pid,
            goal="Doc", status="awaiting_confirmation", current_phase="execute",
            plan_json=[], citations=[],
        )
    )
    db_session.add(
        AgentStep(
            run_id=run_id, phase="execute", step_index=0,
            thought="legacy scoped archive confirmation",
            action_type="ask_user",
            action_detail={"tool": "archive_document", "arguments": {"title": "Doc"}},
            status="running",
        )
    )
    db_session.commit()
    h = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(
        f"/groups/{gid}/agent/runs/{run_id}/respond",
        json={"response": "yes"},
        headers=h,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


def test_agent_search_knowledge_scoped_empty(db_session):
    from semantic_lighthouse.services.agent_orchestrator import execute_tool
    gid, pid = new_id(), new_id()
    _setup(db_session, gid)
    db_session.add(BusinessProject(id=pid, group_id=gid, name="P", business_goal="G", entry_mode="data_first", created_by="x"))
    db_session.commit()
    # No evidence links → empty scope → no results
    result = execute_tool("search_knowledge_base", {"query": "test"}, db_session, gid, "owner", project_id=pid)
    assert "No matching" in result


def test_agent_list_documents_scoped_empty(db_session):
    from semantic_lighthouse.services.agent_orchestrator import execute_tool
    gid, pid = new_id(), new_id()
    _setup(db_session, gid)
    db_session.add(BusinessProject(id=pid, group_id=gid, name="P", business_goal="G", entry_mode="data_first", created_by="x"))
    db_session.commit()
    result = execute_tool("list_documents", {}, db_session, gid, "owner", project_id=pid)
    assert "No documents linked" in result
