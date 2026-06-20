"""S2.2 — Project Evidence Link tests.

Covers: permissions, isolation, evidence status validation, active duplicate,
removed relink, double delete, archived project/document, error/no_evidence
RagRun, provenance minimization, audit fail-closed, list filters, input validation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    BusinessProject,
    Document,
    DocumentChunk,
    Group,
    GroupMembership,
    OntologyRuntimeAudit,
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

    db.add(User(id=owner_id, email=f"own-{gid[:8]}@t.com", display_name="Owner", password_hash=hash_password("Passw0rd!")))
    db.add(User(id=member_id, email=f"mem-{gid[:8]}@t.com", display_name="Member", password_hash=hash_password("Passw0rd!")))
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


def _add_ragrun(db: Session, gid: str, run_id: str, status: str = "success") -> None:
    db.add(RagRun(
        id=run_id, group_id=gid, user_id="user-1",
        question="What is Ontology?", answer="Ontology is...",
        confidence="high", retrieval_method="hybrid", model="fake",
        citations=[], knowledge_gaps=[], next_steps=[],
        status=status,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
#  Permission tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("role,expected", [("owner", 201), ("admin", 201)])
def test_owner_admin_can_create_link(client, db_session, role, expected):
    """Owner and admin can create evidence links."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    if role == "admin":
        db_session.execute(GroupMembership.__table__.update().where(
            GroupMembership.group_id == gid, GroupMembership.user_id == member_id
        ).values(role="admin"))
        db_session.flush()
        email = f"mem-{gid[:8]}@t.com"
    else:
        email = f"own-{gid[:8]}@t.com"

    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()

    headers = _auth_headers(client, email)
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == expected, resp.text
    assert resp.json()["status"] == "active"


def test_member_cannot_create(client, db_session):
    """Member cannot create evidence links — 403."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()

    headers = _auth_headers(client, f"mem-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_non_member_cannot_create(client, db_session):
    """Non-member cannot create — 403."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()

    outsider_email = f"out-{new_id()[:8]}@t.com"
    _register(client, outsider_email)
    headers = _auth_headers(client, outsider_email)
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
#  Isolation tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_cross_group_project_returns_404(client, db_session):
    """Member (admin in route group) accessing project from another group — 404."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    other_gid = new_id()
    db_session.add(Group(id=other_gid, name="Other", created_by=owner_id))
    db_session.add(GroupMembership(group_id=other_gid, user_id=member_id, role="admin"))
    db_session.commit()

    headers = _auth_headers(client, f"mem-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{other_gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": new_id(), "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_cross_group_evidence_returns_404(client, db_session):
    """Evidence from another group — 404."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    other_gid = new_id()
    doc_id = new_id()
    db_session.add(Group(id=other_gid, name="Other", created_by=owner_id))
    db_session.add(Document(
        id=doc_id, group_id=other_gid, title="Other Doc", file_name="o.md",
        source_path="o/o.md", content_hash=f"h-{doc_id[:8]}",
        frontmatter={}, raw_content="# O", status="ready", created_by=owner_id,
    ))
    db_session.commit()

    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
#  Validation tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_invalid_evidence_type_422(client, db_session):
    """Invalid evidence_type returns 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "invalid", "evidence_id": new_id(), "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_invalid_role_422(client, db_session):
    """Invalid role returns 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "invalid_role"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_archived_document_new_link_409(client, db_session):
    """Archived document cannot be newly linked."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id, status="archived")
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_error_ragrun_new_link_409(client, db_session):
    """Error RAG run cannot be newly linked."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    _add_ragrun(db_session, gid, run_id, status="error")
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "rag_run", "evidence_id": run_id, "role": "requirement"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_no_evidence_ragrun_409(client, db_session):
    """no_evidence RAG run cannot be newly linked."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    _add_ragrun(db_session, gid, run_id, status="no_evidence")
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "rag_run", "evidence_id": run_id, "role": "requirement"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_archived_project_rejects_new_links_409(client, db_session):
    """Archived project cannot accept new evidence links."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.execute(
        BusinessProject.__table__.update().where(BusinessProject.id == pid).values(status="archived")
    )
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
#  Idempotency and lifecycle tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_active_duplicate_returns_200(client, db_session):
    """Active duplicate POST returns 200 with existing record, no new audit."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp1 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp1.status_code == 201
    link_id = resp1.json()["id"]

    # Expire so the second handler sees the committed data
    db_session.expire_all()
    audit_before = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).count()

    resp2 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp2.status_code == 200, f"Expected 200 for duplicate, got {resp2.status_code}: {resp2.text}"
    assert resp2.json()["id"] == link_id

    db_session.expire_all()
    audit_after = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).count()
    assert audit_after == audit_before  # No new audit


def test_removed_link_relink(client, db_session):
    """Removed link re-POST reactivates row with evidence_relink audit."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp1 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    link_id = resp1.json()["id"]
    assert resp1.status_code == 201

    # Delete
    db_session.expire_all()
    del_resp = client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)
    assert del_resp.status_code == 200

    # Relink
    db_session.expire_all()
    resp2 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "requirement", "note": "relinked"},
        headers=headers,
    )
    assert resp2.status_code == 200, f"Expected 200 for relink, got {resp2.status_code}: {resp2.text}"
    assert resp2.json()["id"] == link_id
    assert resp2.json()["status"] == "active"
    assert resp2.json()["role"] == "requirement"
    assert resp2.json()["note"] == "relinked"
    assert resp2.json()["removed_by"] is None
    assert resp2.json()["removed_at"] is None

    db_session.expire_all()
    relink_audit = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_relink"
    ).first()
    assert relink_audit is not None


def test_double_delete_idempotent(client, db_session):
    """Double DELETE returns 200, no duplicate audit."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    link_id = resp.json()["id"]

    db_session.expire_all()
    r1 = client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)
    assert r1.status_code == 200
    db_session.expire_all()
    unlink_count = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_unlink"
    ).count()

    r2 = client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)
    assert r2.status_code == 200
    db_session.expire_all()
    unlink_count2 = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_unlink"
    ).count()
    assert unlink_count2 == unlink_count


# ═══════════════════════════════════════════════════════════════════════════════
#  List tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_member_can_list_links(client, db_session):
    """Member can list links for their group's project."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    own_h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=own_h,
    )
    db_session.expire_all()
    mem_h = _auth_headers(client, f"mem-{gid[:8]}@t.com")
    resp = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?status_filter=active",
        headers=mem_h,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_non_member_cannot_list_links(client, db_session):
    """Non-member cannot list — 403."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()
    outsider_email = f"out-{new_id()[:8]}@t.com"
    _register(client, outsider_email)
    headers = _auth_headers(client, outsider_email)
    resp = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?status_filter=active",
        headers=headers,
    )
    assert resp.status_code == 403


def test_cross_project_list_returns_404(client, db_session):
    """Listing via wrong group route returns 404."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    other_gid = new_id()
    db_session.add(Group(id=other_gid, name="Other", created_by=owner_id))
    db_session.add(GroupMembership(group_id=other_gid, user_id=owner_id, role="owner"))
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.get(
        f"/groups/{other_gid}/projects/{pid}/evidence-links",
        headers=headers,
    )
    assert resp.status_code == 404


def test_list_removed_status(client, db_session):
    """status=removed returns removed links."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    link_id = resp.json()["id"]
    db_session.expire_all()
    client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)

    db_session.expire_all()
    resp = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?status_filter=removed",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    assert resp.json()["links"][0]["status"] == "removed"


def test_list_invalid_status_422(client, db_session):
    """Invalid status_filter returns 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?status_filter=bogus",
        headers=headers,
    )
    assert resp.status_code == 422


def test_list_invalid_evidence_type_422(client, db_session):
    """Invalid evidence_type filter returns 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?evidence_type=bogus",
        headers=headers,
    )
    assert resp.status_code == 422


def test_list_limit_out_of_range_422(client, db_session):
    """limit out of range returns 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?limit=0",
        headers=headers,
    )
    assert resp.status_code == 422

    resp2 = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?limit=101",
        headers=headers,
    )
    assert resp2.status_code == 422


def test_list_negative_offset_422(client, db_session):
    """Negative offset returns 422."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?offset=-1",
        headers=headers,
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
#  Provenance and audit tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_provenance_excludes_source_path(client, db_session):
    """Document provenance must not include source_path or storage_path."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    data = resp.json()
    prov = data.get("provenance") or {}
    assert "source_path" not in prov
    assert "storage_path" not in prov
    assert "raw_content" not in prov
    assert prov.get("evidence_title") is not None


def test_provenance_source_label_safe(client, db_session):
    """source_label rejects absolute paths and falls back to title."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    db_session.add(Document(
        id=doc_id, group_id=gid, title="Path Test", file_name="p.md",
        source_path="kb/p.md", content_hash=f"h-{doc_id[:8]}",
        frontmatter={"source": "/etc/passwd"}, raw_content="# P",
        status="ready", created_by="user-1",
    ))
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    prov = resp.json().get("provenance") or {}
    # Must fall back to title, not the absolute path
    assert prov.get("source_label") == "Path Test"


def test_ragrun_provenance_excludes_answer(client, db_session):
    """RAGRun provenance must not include answer, snippet, prompt, or error_message."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "rag_run", "evidence_id": run_id, "role": "decision"},
        headers=headers,
    )
    data = resp.json()
    prov = data.get("provenance") or {}
    assert "answer" not in prov
    assert "snippet" not in prov
    assert "prompt" not in prov
    assert "error_message" not in prov
    assert prov.get("question") is not None


def test_audit_field_names_no_values(client, db_session):
    """Audit field_names must contain only field name strings."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    db_session.expire_all()
    audit = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).first()
    assert audit is not None
    fn = audit.field_names or []
    for name in fn:
        assert name in ("evidence_type", "role", "note", "status"), f"Unexpected: {name}"
        assert len(name) < 20


def test_audit_on_create_remove_relink(client, db_session):
    """Audit rows written on evidence_link, evidence_unlink, and evidence_relink."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    # Create
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    link_id = resp.json()["id"]
    db_session.expire_all()
    assert db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).count() == 1

    # Remove
    client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)
    db_session.expire_all()
    assert db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_unlink"
    ).count() == 1

    # Relink
    client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "validation"},
        headers=headers,
    )
    db_session.expire_all()
    assert db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_relink"
    ).count() == 1


def test_member_cannot_remove_link(client, db_session):
    """Member cannot remove evidence link — 403."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    own_h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=own_h,
    )
    link_id = resp.json()["id"]
    mem_h = _auth_headers(client, f"mem-{gid[:8]}@t.com")
    resp = client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=mem_h)
    assert resp.status_code == 403


def test_ragrun_evidence_link_201(client, db_session):
    """Successful RAG run can be linked as evidence."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    run_id = new_id()
    _add_ragrun(db_session, gid, run_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "rag_run", "evidence_id": run_id, "role": "decision"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["evidence_type"] == "rag_run"


def test_source_evidence_gone_provenance(client, db_session):
    """When source evidence is deleted, link stays active with unavailable=true."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    link_id = resp.json()["id"]
    assert resp.json()["status"] == "active"

    db_session.expire_all()
    db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
    db_session.query(Document).filter(Document.id == doc_id).delete()
    db_session.commit()

    resp2 = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?status_filter=active",
        headers=headers,
    )
    links = resp2.json()["links"]
    matched = next(li for li in links if li["id"] == link_id)
    assert matched["status"] == "active"
    assert matched["provenance"]["unavailable"] is True
    assert matched["provenance"]["evidence_status"] == "gone"


def test_blank_note_normalized_to_null(client, db_session):
    """Blank/whitespace note is normalized to null."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")
    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context", "note": "   "},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["note"] is None


# ═══════════════════════════════════════════════════════════════════════════════
#  Safety review tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_active_duplicate_survives_archived_project(client, db_session):
    """Active duplicate returns 200 even after project is archived."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 201
    link_id = resp.json()["id"]

    # Archive the project
    db_session.execute(
        BusinessProject.__table__.update().where(BusinessProject.id == pid).values(status="archived")
    )
    db_session.commit()
    db_session.expire_all()

    # Active duplicate must still return 200
    resp2 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == link_id


def test_removed_relink_blocked_by_archived_project(client, db_session):
    """Removed relink returns 409 when project is archived, status stays removed."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    link_id = resp.json()["id"]
    db_session.expire_all()
    client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)

    # Archive project
    db_session.execute(
        BusinessProject.__table__.update().where(BusinessProject.id == pid).values(status="archived")
    )
    db_session.commit()
    db_session.expire_all()

    # Relink must fail
    resp2 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "requirement"},
        headers=headers,
    )
    assert resp2.status_code == 409

    # Status must remain removed
    db_session.expire_all()
    link = db_session.get(ProjectEvidenceLink, link_id)
    assert link.status == "removed"


def test_source_label_rejects_windows_paths(client, db_session):
    """source_label rejects Windows drive paths and UNC paths."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    for bad_source, title in [
        ("C:\\Users\\test\\doc.md", "Win Drive"),
        ("\\\\server\\share\\doc.md", "UNC Path"),
        ("subdir/file.md", "Rel Path"),
        ("folder\\nested\\doc.md", "Backslash Path"),
    ]:
        doc_id = new_id()
        db_session.add(Document(
            id=doc_id, group_id=gid, title=title, file_name="x.md",
            source_path="kb/x.md", content_hash=f"h-{doc_id[:8]}",
            frontmatter={"source": bad_source}, raw_content="# X",
            status="ready", created_by="user-1",
        ))
        db_session.commit()
        db_session.expire_all()

        resp = client.post(
            f"/groups/{gid}/projects/{pid}/evidence-links",
            json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
            headers=headers,
        )
        prov = resp.json().get("provenance") or {}
        assert prov.get("source_label") == title, f"Expected {title} for {bad_source}, got {prov.get('source_label')}"
        assert "\\" not in (prov.get("source_label") or "")
        assert "/" not in (prov.get("source_label") or "")


def test_agent_registry_has_no_evidence_write_tools():
    """Agent tool registry must not include evidence link/unlink/relink write operations."""
    from semantic_lighthouse.services.agent_orchestrator import _tool_schemas_for_llm

    schemas = _tool_schemas_for_llm()
    tool_names = {s.get("function", {}).get("name", "") for s in schemas}
    for forbidden in ("evidence_link", "evidence_unlink", "evidence_relink",
                       "create_evidence_link", "remove_evidence_link",
                       "link_evidence", "unlink_evidence"):
        assert forbidden not in tool_names, f"Agent must not have evidence write tool: {forbidden}"


def test_link_and_audit_share_transaction(client, db_session):
    """Link and audit are in the same db.commit() — atomic pass or fail."""
    gid, pid, owner_id, member_id = _setup_group_and_project(db_session)
    doc_id = new_id()
    _add_document(db_session, gid, doc_id)
    db_session.commit()
    headers = _auth_headers(client, f"own-{gid[:8]}@t.com")

    resp = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 201

    # Verify both link and audit row exist
    db_session.expire_all()
    links = db_session.query(ProjectEvidenceLink).filter(
        ProjectEvidenceLink.project_id == pid
    ).all()
    assert len(links) == 1

    audits = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).all()
    assert len(audits) == 1, "Audit row must exist alongside the link"
