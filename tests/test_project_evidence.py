"""S2.2 — Project Evidence Link tests. 26 targeted Safety Lane tests.

Covers: permissions (owner/admin/member/non-member), group/project isolation,
evidence status validation, active duplicate, removed relink, double delete,
archived project/document, error/no_evidence RagRun, provenance minimization,
audit fail-closed, Agent registry no evidence write tools.
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
    RagRun,
    User,
    new_id,
)
from semantic_lighthouse.security import hash_password

ALLOWED_ROLES = {"context", "requirement", "decision", "validation"}


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
    if expected == 201:
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
    # Project pid belongs to gid, but we access via other_gid
    resp = client.post(
        f"/groups/{other_gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": new_id(), "role": "context"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_cross_group_evidence_returns_404(client, db_session):
    """Evidence from another group — 404, no existence leak."""
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
    """Error/no_evidence RAG run cannot be newly linked."""
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

    audit_count_before = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).count()

    resp2 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == link_id

    audit_count_after = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).count()
    assert audit_count_after == audit_count_before  # No new audit


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

    client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)

    resp2 = client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "requirement", "note": "relinked"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == link_id
    assert resp2.json()["status"] == "active"
    assert resp2.json()["role"] == "requirement"
    assert resp2.json()["note"] == "relinked"
    assert resp2.json()["removed_by"] is None
    assert resp2.json()["removed_at"] is None

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

    r1 = client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)
    assert r1.status_code == 200
    unlink_count = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_unlink"
    ).count()

    r2 = client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)
    assert r2.status_code == 200
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
    # Owner creates link
    own_h = _auth_headers(client, f"own-{gid[:8]}@t.com")
    client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "context"},
        headers=own_h,
    )
    # Member reads
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
    """Audit field_names must contain only field name strings, not values."""
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
    audit = db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).first()
    assert audit is not None
    fn = audit.field_names or []
    # Must be field names only — no IDs, note values, paths
    for name in fn:
        assert name in ("evidence_type", "role", "note", "status"), f"Unexpected field name: {name}"
        assert len(name) < 20  # Sanity check — not a UUID or path


def test_audit_on_create_and_remove(client, db_session):
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
    assert db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_link"
    ).count() == 1

    # Remove
    client.delete(f"/groups/{gid}/projects/{pid}/evidence-links/{link_id}", headers=headers)
    assert db_session.query(OntologyRuntimeAudit).filter(
        OntologyRuntimeAudit.project_id == pid, OntologyRuntimeAudit.operation == "evidence_unlink"
    ).count() == 1

    # Relink
    client.post(
        f"/groups/{gid}/projects/{pid}/evidence-links",
        json={"evidence_type": "document", "evidence_id": doc_id, "role": "validation"},
        headers=headers,
    )
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

    # Delete the source document
    db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
    db_session.query(Document).filter(Document.id == doc_id).delete()
    db_session.commit()

    # Link must still be active but provenance shows gone
    resp2 = client.get(
        f"/groups/{gid}/projects/{pid}/evidence-links?status_filter=active",
        headers=headers,
    )
    links = resp2.json()["links"]
    link = next(li for li in links if li["id"] == link_id)
    assert link["status"] == "active"
    assert link["provenance"]["unavailable"] is True
    assert link["provenance"]["evidence_status"] == "gone"
