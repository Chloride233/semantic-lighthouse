"""Phase 15.3 Slice A — Evidence-backed modeling draft endpoint tests.

Covers: permissions, evidence link validation, idempotency, evidence_refs privacy,
group/project isolation, removed evidence link, source_rag_run_id derivation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    BusinessProject,
    Document,
    Group,
    GroupMembership,
    OntologyModelingDraft,
    ProjectEvidenceLink,
    RagRun,
    User,
    new_id,
)
from semantic_lighthouse.security import hash_password


def _auth_headers(client: TestClient, email: str, password: str = "Passw0rd!"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str, name: str = "Test"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": name},
    )


def _setup_group_and_project(db: Session) -> tuple[str, str, str, str]:
    """Create group, owner user, project. Returns (gid, pid, owner_id, member_id)."""
    gid = new_id()
    owner_id = new_id()
    member_id = new_id()
    pid = new_id()

    db.add(User(
        id=owner_id, email=f"own-{gid[:8]}@t.com",
        display_name="Owner", password_hash=hash_password("Passw0rd!"),
    ))
    db.add(User(
        id=member_id, email=f"mem-{gid[:8]}@t.com",
        display_name="Member", password_hash=hash_password("Passw0rd!"),
    ))
    db.add(Group(id=gid, name="Test Group", created_by=owner_id))
    db.add(GroupMembership(group_id=gid, user_id=owner_id, role="owner"))
    db.add(GroupMembership(group_id=gid, user_id=member_id, role="member"))
    db.add(BusinessProject(
        id=pid, group_id=gid, name="Test Project",
        business_goal="Test", entry_mode="data_first", created_by=owner_id,
    ))
    db.flush()
    return gid, pid, owner_id, member_id


def _add_document(db: Session, gid: str, doc_id: str, status: str = "ready") -> None:
    db.add(Document(
        id=doc_id, group_id=gid, title="Test Doc", file_name="test.md",
        source_path="kb/test.md", content_hash=f"hash-{doc_id[:8]}",
        frontmatter={"source": "knowledge-graph"}, raw_content="# Test",
        status=status, created_by="user-1",
    ))


def _add_ragrun(
    db: Session, gid: str, run_id: str, status: str = "success",
    question: str = "What is Ontology?",
) -> None:
    db.add(RagRun(
        id=run_id, group_id=gid, user_id="user-1",
        question=question, answer="Ontology is a semantic operating layer.",
        confidence="high", retrieval_method="hybrid", model="fake",
        citations=[], knowledge_gaps=[], next_steps=[],
        status=status,
    ))


def _add_evidence_link(
    db: Session, gid: str, pid: str, link_id: str,
    evidence_type: str, evidence_id: str,
    role: str = "decision", status: str = "active",
) -> None:
    db.add(ProjectEvidenceLink(
        id=link_id, group_id=gid, project_id=pid,
        evidence_type=evidence_type, evidence_id=evidence_id,
        role=role, status=status, created_by="user-1",
    ))


def _create_evidence_draft(
    client: TestClient, gid: str, pid: str, headers: dict,
    draft_type: str = "object_type", name: str = "Evidence Draft",
    description: str = "From evidence",
    evidence_link_ids: list | None = None,
    source_entity_id: str | None = None,
    source_issue_id: str | None = None,
):
    body = {
        "draft_type": draft_type,
        "name": name,
        "description": description,
        "evidence_link_ids": evidence_link_ids or [],
    }
    if source_entity_id:
        body["source_entity_id"] = source_entity_id
    if source_issue_id:
        body["source_issue_id"] = source_issue_id
    return client.post(
        f"/groups/{gid}/projects/{pid}/evidence-draft",
        json=body,
        headers=headers,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Permission tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("role,expected", [("owner", 201), ("admin", 201)])
def test_owner_admin_can_create_evidence_draft(client, db_session, role, expected):
    """Owner and admin can create an evidence-backed draft from a rag_run link."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    if role == "admin":
        db_session.execute(GroupMembership.__table__.update().where(
            GroupMembership.group_id == gid, GroupMembership.user_id == member_id
        ).values(role="admin"))
        db_session.commit()
        headers = _auth_headers(client, f"mem-{gid[:8]}@t.com")
    else:
        headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = _create_evidence_draft(
        client, gid, pid, headers,
        draft_type="object_type", name="WorkOrder",
        description="From evidence question",
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == expected, resp.text
    data = resp.json()
    assert data["status"] == "proposed"
    assert data["draft_type"] == "object_type"
    assert data["name"] == "WorkOrder"
    assert data["source_rag_run_id"] == run_id
    assert data["project_id"] == pid
    assert len(data["evidence_refs"]) == 1
    assert data["evidence_refs"][0]["evidence_type"] == "rag_run"
    assert data["evidence_refs"][0]["evidence_link_id"] == link_id
    assert data["payload"]["generator"] == "evidence_backed_v1"
    assert data["payload"]["evidence_link_ids"] == [link_id]


def test_member_cannot_create(client, db_session):
    """Member cannot create evidence draft — 403."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"mem-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 403


def test_non_member_cannot_create(client, db_session):
    """Non-member cannot create — 403."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    outsider_email = f"out-{new_id()[:8]}@t.com"
    _register(client, outsider_email)
    headers = _auth_headers(client, outsider_email)
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
#  Isolation tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_cross_group_project_returns_404(client, db_session):
    """Project from another group on route — 404."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    other_gid = new_id()
    db_session.add(Group(id=other_gid, name="Other", created_by=owner_id))
    db_session.add(GroupMembership(group_id=other_gid, user_id=owner_id, role="owner"))
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, other_gid, pid, headers,
        evidence_link_ids=[new_id()],
    )
    assert resp.status_code == 404


def test_cross_group_evidence_link_returns_404(client, db_session):
    """Evidence link from another group — 404."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    other_gid = new_id()
    run_id = new_id()
    other_pid = new_id()
    link_id = new_id()
    db_session.add(Group(id=other_gid, name="Other", created_by=owner_id))
    db_session.add(GroupMembership(group_id=other_gid, user_id=owner_id, role="owner"))
    db_session.add(BusinessProject(
        id=other_pid, group_id=other_gid, name="OP", business_goal="OG",
        entry_mode="data_first", created_by=owner_id,
    ))
    _add_ragrun(db_session, other_gid, run_id)
    _add_evidence_link(db_session, other_gid, other_pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 404


def test_evidence_link_from_other_project_returns_422(client, db_session):
    """Evidence link from a different project in same group — 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    other_pid = new_id()
    run_id = new_id()
    link_id = new_id()
    db_session.add(BusinessProject(
        id=other_pid, group_id=gid, name="Other Project",
        business_goal="Other", entry_mode="data_first", created_by=owner_id,
    ))
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, other_pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
#  Evidence link validation tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_removed_evidence_link_rejected(client, db_session):
    """Removed evidence link returns 409."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id, status="removed")
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 409


def test_empty_evidence_link_ids_rejected(client, db_session):
    """Empty evidence_link_ids returns 422 (Pydantic min_length validation)."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[],
    )
    assert resp.status_code == 422


def test_invalid_draft_type_rejected(client, db_session):
    """Invalid draft_type returns 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        draft_type="invalid_type",
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 422


def test_nonexistent_evidence_link_returns_404(client, db_session):
    """Non-existent evidence link id returns 404."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[new_id()],
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
#  source_rag_run_id derivation tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_rag_run_sets_source_rag_run_id(client, db_session):
    """Evidence link with rag_run evidence sets source_rag_run_id."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 201
    assert resp.json()["source_rag_run_id"] == run_id


def test_document_only_sets_no_source_rag_run_id(client, db_session):
    """Evidence link with only document evidence leaves source_rag_run_id None."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    link_id = new_id()
    _add_document(db_session, gid, doc_id)
    _add_evidence_link(db_session, gid, pid, link_id, "document", doc_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 201
    assert resp.json()["source_rag_run_id"] is None


def test_mixed_evidence_uses_first_rag_run(client, db_session):
    """Multiple evidence links (doc + rag_run) — first rag_run becomes source_rag_run_id."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    run_id = new_id()
    doc_link_id = new_id()
    run_link_id = new_id()
    _add_document(db_session, gid, doc_id)
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, doc_link_id, "document", doc_id, role="context")
    _add_evidence_link(db_session, gid, pid, run_link_id, "rag_run", run_id, role="decision")
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[doc_link_id, run_link_id],
    )
    assert resp.status_code == 201
    assert resp.json()["source_rag_run_id"] == run_id
    assert len(resp.json()["evidence_refs"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
#  Idempotency tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_duplicate_request_is_idempotent(client, db_session):
    """Same group/project/draft_type/name/evidence_link_ids returns existing — 200."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    # First request — create
    r1 = _create_evidence_draft(
        client, gid, pid, headers,
        draft_type="object_type", name="WorkOrder",
        evidence_link_ids=[link_id],
    )
    assert r1.status_code == 201
    draft_id = r1.json()["id"]

    # Second request — idempotent, returns existing
    r2 = _create_evidence_draft(
        client, gid, pid, headers,
        draft_type="object_type", name="WorkOrder",
        evidence_link_ids=[link_id],
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == draft_id

    # Verify only one draft exists in DB
    drafts = db_session.query(OntologyModelingDraft).filter(
        OntologyModelingDraft.group_id == gid,
        OntologyModelingDraft.project_id == pid,
    ).all()
    assert len(drafts) == 1


def test_different_name_creates_new_draft(client, db_session):
    """Different name creates a new draft, not idempotent."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    r1 = _create_evidence_draft(
        client, gid, pid, headers,
        draft_type="object_type", name="Draft A",
        evidence_link_ids=[link_id],
    )
    assert r1.status_code == 201

    r2 = _create_evidence_draft(
        client, gid, pid, headers,
        draft_type="object_type", name="Draft B",
        evidence_link_ids=[link_id],
    )
    assert r2.status_code == 201
    assert r2.json()["id"] != r1.json()["id"]


def test_different_evidence_links_creates_new_draft(client, db_session):
    """Different evidence link IDs create a new draft, not idempotent."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id_1 = new_id()
    run_id_2 = new_id()
    link_id_1 = new_id()
    link_id_2 = new_id()
    _add_ragrun(db_session, gid, run_id_1, question="Q1")
    _add_ragrun(db_session, gid, run_id_2, question="Q2")
    _add_evidence_link(db_session, gid, pid, link_id_1, "rag_run", run_id_1)
    _add_evidence_link(db_session, gid, pid, link_id_2, "rag_run", run_id_2)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    r1 = _create_evidence_draft(
        client, gid, pid, headers,
        name="SameName",
        evidence_link_ids=[link_id_1],
    )
    assert r1.status_code == 201

    r2 = _create_evidence_draft(
        client, gid, pid, headers,
        name="SameName",
        evidence_link_ids=[link_id_2],
    )
    assert r2.status_code == 201
    assert r2.json()["id"] != r1.json()["id"]


# ═══════════════════════════════════════════════════════════════════════════════
#  evidence_refs privacy tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_evidence_refs_no_raw_answer(client, db_session):
    """evidence_refs never include raw answer text."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 201
    refs_json = resp.text
    assert "Ontology is a semantic operating layer" not in refs_json  # raw answer
    assert "answer" not in refs_json.lower() or '"answer"' not in refs_json


def test_evidence_refs_no_raw_content_or_path(client, db_session):
    """evidence_refs from document never expose raw_content, source_path, storage_path."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    link_id = new_id()
    _add_document(db_session, gid, doc_id)
    _add_evidence_link(db_session, gid, pid, link_id, "document", doc_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 201
    refs_json = resp.text
    assert "# Test" not in refs_json  # raw_content
    assert "raw_content" not in refs_json
    assert "source_path" not in refs_json
    assert "storage_path" not in refs_json
    assert "kb/test.md" not in refs_json  # source_path value


def test_evidence_refs_no_secrets(client, db_session):
    """evidence_refs never expose secrets or tokens."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 201
    refs_json = resp.text
    for secret_term in ("secret", "token", "password", "api_key", "stack_trace"):
        assert secret_term not in refs_json.lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  Draft lifecycle integration tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_created_draft_visible_in_draft_list(client, db_session):
    """Evidence-backed draft appears in existing ontology draft list endpoint."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    # Create evidence-backed draft
    r1 = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert r1.status_code == 201
    draft_id = r1.json()["id"]

    # Read via existing draft list
    r2 = client.get(f"/groups/{gid}/ontology/drafts", headers=headers)
    assert r2.status_code == 200
    draft_ids = [d["id"] for d in r2.json()["drafts"]]
    assert draft_id in draft_ids


def test_created_draft_is_proposed_not_accepted(client, db_session):
    """Evidence-backed draft starts as proposed, never auto-accepted."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    link_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    _add_evidence_link(db_session, gid, pid, link_id, "rag_run", run_id)
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = _create_evidence_draft(
        client, gid, pid, headers,
        evidence_link_ids=[link_id],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "proposed"
    assert data["reviewed_by"] is None
    assert data["reviewed_at"] is None
