"""Tests for Phase 12.2a ontology draft quality validator.

Covers: structural errors, cross-reference errors, semantic warnings,
status computation, idempotency (no mutations).
"""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login
from semantic_lighthouse.models import OntologyModelingDraft
from semantic_lighthouse.services.ontology_draft_quality import (
    validate_modeling_drafts,
)


def _create_group(client: TestClient, headers: dict[str, str], name: str = "Team") -> str:
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _upload_doc(client, gid, headers, filename, frontmatter, body="# Test\n\nContent."):
    yaml_lines = ["---"]
    for k, v in frontmatter.items():
        yaml_lines.append(f"{k}: {[', '.join(v)] if isinstance(v, list) else v}")
    yaml_lines.append("---")
    yaml_lines.append(body)
    content = "\n".join(yaml_lines)
    r = client.post(
        f"/groups/{gid}/documents/upload",
        files={"file": (filename, content.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    time.sleep(0.3)
    return r.json()["id"]


def _scan(client, gid, headers):
    return client.post(f"/groups/{gid}/ontology/scan", headers=headers).json()


class TestValidDraftPasses:
    def test_complete_generated_object_draft_no_errors(self, client, db_session: Session):
        """A properly generated object_type draft should produce no errors."""
        _, _, h = register_and_login(client, "q1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        gen = client.post(f"/groups/{gid}/ontology/drafts/generate", headers=h)
        assert gen.status_code == 200

        result = validate_modeling_drafts(db_session, gid)
        assert result["draft_count"] >= 1
        assert result["error_count"] == 0
        # knowledge_meta_model_candidate warning expected on object_type
        assert any(
            i["code"] == "knowledge_meta_model_candidate"
            for i in result["issues"]
        )


class TestStructuralErrors:
    def test_missing_source_pointer_fails(self, db_session: Session):
        """Draft with no source pointer must produce an error."""
        from semantic_lighthouse.models import Group, User
        gid, uid = "g-q2", "u-q2"
        db_session.add(Group(id=gid, name="Q2", created_by=uid))
        db_session.add(User(id=uid, email="q2@t.com", password_hash="x",
                            display_name="Q2"))
        db_session.flush()

        draft = OntologyModelingDraft(
            group_id=gid, draft_type="object_type", name="NoSource",
            status="proposed", payload={"generation_key": "object_type:x"},
            created_by=uid,
        )
        db_session.add(draft)
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        assert result["draft_count"] == 1
        assert any(i["code"] == "missing_source_pointer" for i in result["issues"])
        assert result["status"] == "FAIL"

    @pytest.mark.parametrize("payload,error_code", [
        ({}, "source_pointer_not_in_group"),
        ({"generation_key": "property:x:y", "object_type": "X",
          "property_name": "p", "observed_value_types": ["str"],
          "observed_count": 1, "entity_count": 1},
         "source_pointer_not_in_group"),
    ])
    def test_deterministic_draft_errors(self, db_session: Session, payload, error_code):
        """Deterministic draft without proper source or missing fields → errors."""
        from semantic_lighthouse.models import Group, User
        gid, uid = "g-q3", "u-q3"
        db_session.add(Group(id=gid, name="Q3", created_by=uid))
        db_session.add(User(id=uid, email="q3@t.com", password_hash="x",
                            display_name="Q3"))
        db_session.flush()

        # First case: empty payload + fake source_entity_id
        # Second case: complete payload but fake source_entity_id
        draft = OntologyModelingDraft(
            group_id=gid, draft_type="property", name="BadProp",
            status="proposed", source_entity_id="fake-eid",
            payload=payload, evidence_refs=[{"x": 1}],
            created_by=uid,
        )
        db_session.add(draft)
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        codes = {i["code"] for i in result["issues"]}
        assert error_code in codes
        assert result["status"] == "FAIL"


class TestCrossReferenceErrors:
    def test_property_citing_nonexistent_object_type_fails(self, db_session: Session):
        """Property payload.object_type not in object_type drafts → error."""
        from semantic_lighthouse.models import Group, User
        gid, uid = "g-q4", "u-q4"
        db_session.add(Group(id=gid, name="Q4", created_by=uid))
        db_session.add(User(id=uid, email="q4@t.com", password_hash="x",
                            display_name="Q4"))
        db_session.flush()

        ot = OntologyModelingDraft(
            group_id=gid, draft_type="object_type", name="Concept",
            status="proposed", source_entity_id="fake-eid",
            payload={"generator": "deterministic_v1",
                     "generation_key": "object_type:concept",
                     "source_entity_type": "Concept", "entity_count": 5},
            evidence_refs=[{"e": 1}], created_by=uid,
        )
        prop = OntologyModelingDraft(
            group_id=gid, draft_type="property", name="BadObj.Property",
            status="proposed", source_entity_id="fake-eid",
            payload={"generator": "deterministic_v1",
                     "generation_key": "property:x", "object_type": "UnknownType",
                     "property_name": "p", "observed_value_types": ["str"],
                     "observed_count": 5, "entity_count": 1},
            evidence_refs=[{"e": 2}], created_by=uid,
        )
        db_session.add_all([ot, prop])
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        codes = {i["code"] for i in result["issues"]}
        assert "property_object_type_not_found" in codes
        assert result["status"] == "FAIL"

    def test_link_citing_nonexistent_object_types_fails(self, db_session: Session):
        """Link payload source/target object_type not found → errors."""
        from semantic_lighthouse.models import Group, User
        gid, uid = "g-q5", "u-q5"
        db_session.add(Group(id=gid, name="Q5", created_by=uid))
        db_session.add(User(id=uid, email="q5@t.com", password_hash="x",
                            display_name="Q5"))
        db_session.flush()

        link = OntologyModelingDraft(
            group_id=gid, draft_type="link_type", name="X -> Y (wikilink)",
            status="proposed", source_relation_id="fake-rid",
            payload={"generator": "deterministic_v1",
                     "generation_key": "link_type:x:y",
                     "source_object_type": "X", "target_object_type": "Y",
                     "relation_type": "wikilink", "relation_count": 3},
            evidence_refs=[{"r": 1}], created_by=uid,
        )
        db_session.add(link)
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        codes = {i["code"] for i in result["issues"]}
        assert "link_source_object_type_not_found" in codes
        assert "link_target_object_type_not_found" in codes


class TestWarnings:
    def test_weak_and_mixed_property_warns(self, db_session: Session):
        """Property with observed_count=1 + mixed types produces specific warnings."""
        from semantic_lighthouse.models import Group, User, OntologyEntity, Document
        gid, uid = "g-q6", "u-q6"
        db_session.add(Group(id=gid, name="Q6", created_by=uid))
        db_session.add(User(id=uid, email="q6@t.com", password_hash="x",
                            display_name="Q6"))
        # Create a real entity so the source pointer is valid
        eid = "e-q6"
        did = "d-q6"
        db_session.add(Document(id=did, group_id=gid, title="Q6 Doc",
                                file_name="q6.md", source_path="q6.md",
                                content_hash="h", raw_content="x",
                                created_by=uid, status="ready"))
        db_session.add(OntologyEntity(id=eid, group_id=gid, document_id=did,
                                      title="Concept", entity_type="Concept",
                                      source_path="q6.md"))
        db_session.flush()

        ot = OntologyModelingDraft(
            group_id=gid, draft_type="object_type", name="Concept",
            status="proposed", source_entity_id=eid,
            payload={"generator": "deterministic_v1",
                     "generation_key": "object_type:concept",
                     "source_entity_type": "Concept", "entity_count": 5},
            evidence_refs=[{"e": 1}], created_by=uid,
        )
        prop = OntologyModelingDraft(
            group_id=gid, draft_type="property", name="Concept.weak",
            status="proposed", source_entity_id=eid,
            payload={"generator": "deterministic_v1",
                     "generation_key": "property:concept:weak",
                     "object_type": "Concept", "property_name": "weak",
                     "observed_value_types": ["str", "list"],
                     "observed_count": 1, "entity_count": 1},
            evidence_refs=[{"e": 2}], created_by=uid,
        )
        db_session.add_all([ot, prop])
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        assert result["error_count"] == 0
        codes = {i["code"] for i in result["issues"]}
        assert "weak_property_evidence" in codes
        assert "mixed_property_value_types" in codes
        assert result["status"] == "WARN"

    def test_wikilink_and_governance_action_semantic_warnings(self, db_session: Session):
        """Link with wikilink + action with ontology_governance → semantic warnings."""
        from semantic_lighthouse.models import (
            Group, User, OntologyEntity, OntologyRelation, OntologyValidationIssue,
            Document,
        )
        gid, uid = "g-q7", "u-q7"
        db_session.add(Group(id=gid, name="Q7", created_by=uid))
        db_session.add(User(id=uid, email="q7@t.com", password_hash="x",
                            display_name="Q7"))
        # Create real sources so pointers are valid in group
        eid, rid, iid, did = "e-q7", "r-q7", "i-q7", "d-q7"
        db_session.add(Document(id=did, group_id=gid, title="Q7 Doc",
                                file_name="q7.md", source_path="q7.md",
                                content_hash="h", raw_content="x",
                                created_by=uid, status="ready"))
        db_session.add(OntologyEntity(id=eid, group_id=gid, document_id=did,
                                      title="Concept", entity_type="Concept",
                                      source_path="q7.md"))
        db_session.add(OntologyRelation(
            id=rid, group_id=gid, source_entity_id=eid, source_document_id=did,
            target_path="tgt", relation_type="wikilink", status="resolved",
            evidence_document_id=did,
        ))
        db_session.add(OntologyValidationIssue(
            id=iid, group_id=gid, document_id=did, entity_id=eid,
            severity="warning", code="unresolved_wikilink",
            message="test", source_path="q7.md", triage_status="confirmed",
            issue_key="ik-q7",
        ))
        db_session.flush()

        ot = OntologyModelingDraft(
            group_id=gid, draft_type="object_type", name="Concept",
            status="proposed", source_entity_id=eid,
            payload={"generator": "deterministic_v1",
                     "generation_key": "object_type:concept",
                     "source_entity_type": "Concept", "entity_count": 5},
            evidence_refs=[{"e": 1}], created_by=uid,
        )
        link = OntologyModelingDraft(
            group_id=gid, draft_type="link_type",
            name="Concept -> Concept (wikilink)",
            status="proposed", source_relation_id=rid,
            payload={"generator": "deterministic_v1",
                     "generation_key": "link_type:c:c:w",
                     "source_object_type": "Concept", "target_object_type": "Concept",
                     "relation_type": "wikilink", "relation_count": 10},
            evidence_refs=[{"r": 1}], created_by=uid,
        )
        action = OntologyModelingDraft(
            group_id=gid, draft_type="action_type", name="Review Links",
            status="proposed", source_issue_id=iid,
            payload={"generator": "deterministic_v1",
                     "generation_key": "action_type:review",
                     "scope": "ontology_governance", "issue_count": 30,
                     "issue_codes": ["unresolved_wikilink"]},
            evidence_refs=[{"i": 1}], created_by=uid,
        )
        db_session.add_all([ot, link, action])
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        codes = {i["code"] for i in result["issues"]}
        assert "untyped_wikilink_candidate" in codes
        assert "governance_action_candidate" in codes
        assert result["status"] == "WARN"


class TestHotfixDetVsManual:
    def test_deterministic_missing_gen_key_fails(self, db_session: Session):
        """Deterministic draft (generator=deterministic_v1) missing
        generation_key must produce missing_generation_key error."""
        from semantic_lighthouse.models import Group, User
        gid, uid = "g-h1", "u-h1"
        db_session.add(Group(id=gid, name="H1", created_by=uid))
        db_session.add(User(id=uid, email="h1@t.com", password_hash="x",
                            display_name="H1"))
        db_session.flush()

        draft = OntologyModelingDraft(
            group_id=gid, draft_type="object_type", name="NoKey",
            status="proposed", source_entity_id="fake-eid",
            payload={"generator": "deterministic_v1",
                     "source_entity_type": "Concept", "entity_count": 5},
            evidence_refs=[{"e": 1}], created_by=uid,
        )
        db_session.add(draft)
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        codes = {i["code"] for i in result["issues"]}
        assert "missing_generation_key" in codes
        assert result["status"] == "FAIL"

    def test_manual_object_draft_no_det_errors_or_warnings(self, db_session: Session):
        """Legal manual object draft with payload={}, valid source + evidence
        must NOT produce: missing_generation_key, missing_required_payload_fields,
        weak_*_evidence, or knowledge_meta_model_candidate."""
        from semantic_lighthouse.models import Group, User, OntologyEntity, Document
        gid, uid = "g-h2", "u-h2"
        db_session.add(Group(id=gid, name="H2", created_by=uid))
        db_session.add(User(id=uid, email="h2@t.com", password_hash="x",
                            display_name="H2"))
        eid, did = "e-h2", "d-h2"
        db_session.add(Document(id=did, group_id=gid, title="H2 Doc",
                                file_name="h2.md", source_path="h2.md",
                                content_hash="h", raw_content="x",
                                created_by=uid, status="ready"))
        db_session.add(OntologyEntity(id=eid, group_id=gid, document_id=did,
                                      title="ManualOT", entity_type="Concept",
                                      source_path="h2.md"))
        db_session.flush()

        draft = OntologyModelingDraft(
            group_id=gid, draft_type="object_type", name="ManualOT",
            status="proposed", source_entity_id=eid,
            payload={},
            evidence_refs=[{"manual": True}], created_by=uid,
        )
        db_session.add(draft)
        db_session.commit()

        result = validate_modeling_drafts(db_session, gid)
        codes = {i["code"] for i in result["issues"]}

        # Must NOT have deterministic-specific errors/warnings
        assert "missing_generation_key" not in codes
        assert "missing_required_payload_fields" not in codes
        assert "knowledge_meta_model_candidate" not in codes

        # Must still pass basic checks
        assert result["error_count"] == 0
        assert result["status"] == "PASS"


class TestReadOnly:
    def test_validator_does_not_modify_drafts(self, client, db_session: Session):
        """Running the validator must not change any draft state."""
        _, _, h = register_and_login(client, "q8@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        client.post(f"/groups/{gid}/ontology/drafts/generate", headers=h)

        drafts_before = [
            (d.id, d.status, d.reviewed_by, d.reviewed_at, d.review_note,
             dict(d.payload or {}), list(d.evidence_refs or []))
            for d in db_session.query(OntologyModelingDraft).filter(
                OntologyModelingDraft.group_id == gid
            ).all()
        ]

        validate_modeling_drafts(db_session, gid)

        drafts_after = [
            (d.id, d.status, d.reviewed_by, d.reviewed_at, d.review_note,
             dict(d.payload or {}), list(d.evidence_refs or []))
            for d in db_session.query(OntologyModelingDraft).filter(
                OntologyModelingDraft.group_id == gid
            ).all()
        ]

        assert drafts_before == drafts_after
