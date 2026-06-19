"""Tests for Phase 12.5 action contract validation in package builder."""

import pytest
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    Document, Group, OntologyEntity, OntologyModelingDraft,
    OntologyValidationIssue, User,
)
from semantic_lighthouse.services.ontology_packages import (
    PackageBuildError, build_model_package,
)

DT = "deterministic_v1"


def _seed_entity(db, gid, uid, eid, title="E", entity_type="Concept"):
    did = f"d-{eid}"
    db.add(Document(id=did, group_id=gid, title=title, file_name=f"{title}.md",
                    source_path=f"{title}.md", content_hash=f"h-{eid}",
                    raw_content="x", created_by=uid, status="ready"))
    db.add(OntologyEntity(id=eid, group_id=gid, document_id=did,
                          title=title, entity_type=entity_type,
                          source_path=f"{title}.md"))
    db.flush()
    return eid, did


def _seed_issue(db, gid, iid, eid, did):
    db.add(OntologyValidationIssue(
        id=iid, group_id=gid, document_id=did, entity_id=eid,
        severity="warning", code="unresolved_wikilink", message="test",
        source_path="x.md", triage_status="confirmed", issue_key=f"ik-{iid}",
    ))
    db.flush()


def _make(gid, uid, **kw):
    d = {"group_id": gid, "status": "proposed", "payload": {},
         "evidence_refs": [{"x": 1}], "created_by": uid}
    d.update(kw)
    return OntologyModelingDraft(**d)


def _setup(db, suffix):
    gid, uid = f"g-{suffix}", f"u-{suffix}"
    db.add(Group(id=gid, name=f"G{suffix}", created_by=uid))
    db.add(User(id=uid, email=f"{suffix}@t.com", password_hash="x",
                display_name=f"U{suffix}"))
    eid, did = _seed_entity(db, gid, uid, f"e-{suffix}", "Concept")
    iid = f"i-{suffix}"
    _seed_issue(db, gid, iid, eid, did)
    return gid, uid, iid


class TestDetActionDefaults:
    def test_deterministic_governance_gets_conservative_defaults(
        self, db_session: Session,
    ):
        gid, uid, iid = _setup(db_session, "ac1")
        db_session.add(_make(gid, uid, draft_type="action_type",
                             name="Review Links", status="accepted",
                             source_issue_id=iid,
                             payload={"generator": DT,
                                      "generation_key": "ac:rl",
                                      "scope": "ontology_governance",
                                      "issue_count": 10,
                                      "issue_codes": ["unresolved_wikilink"]}))
        db_session.commit()

        pkg, created = build_model_package(db_session, gid, uid)
        assert created is True
        ac = pkg.contract_json["action_types"][0]["action_contract"]
        assert ac == {
            "required_role": "admin",
            "confirmation_requirement": "always",
            "evidence_requirement": ["ontology_validation_issue"],
        }

    def test_explicit_contract_in_snapshot_and_hash(self, db_session: Session):
        gid, uid, iid = _setup(db_session, "ac1b")
        db_session.add(_make(gid, uid, draft_type="action_type",
                             name="A1", status="accepted",
                             source_issue_id=iid,
                             payload={"generator": DT,
                                      "generation_key": "ac:r2",
                                      "scope": "ontology_governance",
                                      "issue_count": 10,
                                      "issue_codes": ["x"],
                                      "action_contract": {
                                          "required_role": "owner",
                                          "confirmation_requirement": "always",
                                          "evidence_requirement": ["i"],
                                      }}))
        db_session.commit()

        pkg, _ = build_model_package(db_session, gid, uid)
        ac = pkg.contract_json["action_types"][0]["action_contract"]
        assert ac["required_role"] == "owner"
        # Rebuild must be idempotent (same hash)
        pkg2, c2 = build_model_package(db_session, gid, uid)
        assert c2 is False and pkg2.id == pkg.id


class TestManualActionContracts:
    def test_valid_explicit_contract_succeeds(self, db_session: Session):
        gid, uid, iid = _setup(db_session, "ac2")
        db_session.add(_make(gid, uid, draft_type="action_type",
                             name="Manual", status="accepted",
                             source_issue_id=iid,
                             payload={"action_contract": {
                                 "required_role": "member",
                                 "confirmation_requirement": "none",
                                 "evidence_requirement": ["doc_ref"],
                             }}))
        db_session.commit()

        pkg, created = build_model_package(db_session, gid, uid)
        assert created is True
        ac = pkg.contract_json["action_types"][0]["action_contract"]
        assert ac["required_role"] == "member"
        assert ac["confirmation_requirement"] == "none"

    def test_manual_missing_contract_blocks(self, db_session: Session):
        gid, uid, iid = _setup(db_session, "ac3")
        db_session.add(_make(gid, uid, draft_type="action_type",
                             name="NoCtr", status="accepted",
                             source_issue_id=iid,
                             payload={"some": "data"}))
        db_session.commit()

        with pytest.raises(PackageBuildError, match="missing payload.action_contract"):
            build_model_package(db_session, gid, uid)

    @pytest.mark.parametrize("field,value,match", [
        ("required_role", "superuser", "required_role"),
        ("required_role", "", "required_role"),
        ("confirmation_requirement", "maybe", "confirmation_requirement"),
        ("confirmation_requirement", "", "confirmation_requirement"),
        ("evidence_requirement", [], "evidence_requirement"),
        ("evidence_requirement", [""], "evidence_requirement"),
        ("evidence_requirement", ["  "], "evidence_requirement"),
        ("evidence_requirement", ["ok", ""], "evidence_requirement"),
    ])
    def test_invalid_contract_blocked(
        self, db_session: Session, field, value, match,
    ):
        gid, uid, iid = _setup(db_session, f"ac4-{field}")
        ac = {
            "required_role": "admin",
            "confirmation_requirement": "always",
            "evidence_requirement": ["valid_ref"],
        }
        ac[field] = value

        db_session.add(_make(gid, uid, draft_type="action_type",
                             name="Bad", status="accepted",
                             source_issue_id=iid,
                             payload={"action_contract": ac}))
        db_session.commit()

        with pytest.raises(PackageBuildError, match=match):
            build_model_package(db_session, gid, uid)

    def test_explicit_invalid_not_overridden(self, db_session: Session):
        gid, uid, iid = _setup(db_session, "ac5")
        db_session.add(_make(gid, uid, draft_type="action_type",
                             name="BadOvr", status="accepted",
                             source_issue_id=iid,
                             payload={"generator": DT,
                                      "generation_key": "ac:bo",
                                      "scope": "ontology_governance",
                                      "issue_count": 1,
                                      "issue_codes": ["x"],
                                      "action_contract": {
                                          "required_role": "invalid",
                                          "confirmation_requirement": "maybe",
                                          "evidence_requirement": [],
                                      }}))
        db_session.commit()

        with pytest.raises(PackageBuildError, match="required_role"):
            build_model_package(db_session, gid, uid)


class TestNoActionPackagesUnaffected:
    def test_package_without_actions_still_works(self, db_session: Session):
        gid, uid, iid = _setup(db_session, "ac6")
        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="Concept", status="accepted",
                             source_entity_id="e-ac6",
                             payload={"generator": DT, "generation_key": "ot:c",
                                      "source_entity_type": "Concept",
                                      "entity_count": 3}))
        db_session.commit()

        pkg, created = build_model_package(db_session, gid, uid)
        assert created is True
        assert pkg.contract_json["action_types"] == []
