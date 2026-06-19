"""Tests for Phase 12.3b model package builder service."""

import pytest
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    Document,
    Group,
    OntologyEntity,
    OntologyModelingDraft,
    OntologyRelation,
    User,
)
from semantic_lighthouse.services.ontology_packages import (
    PackageBuildError,
    build_model_package,
)

DT = "deterministic_v1"


def _seed_entity(db, gid, uid, eid, title, entity_type="Concept"):
    did = f"d-{eid}"
    db.add(Document(id=did, group_id=gid, title=title, file_name=f"{title}.md",
                    source_path=f"{title}.md", content_hash=f"h-{eid}",
                    raw_content="x", created_by=uid, status="ready"))
    db.add(OntologyEntity(id=eid, group_id=gid, document_id=did,
                          title=title, entity_type=entity_type,
                          source_path=f"{title}.md"))
    db.flush()


def _make(gid, uid, **kw):
    d = {"group_id": gid, "status": "proposed", "payload": {},
         "evidence_refs": [{"x": 1}], "created_by": uid}
    d.update(kw)
    return OntologyModelingDraft(**d)


class TestBuildErrors:
    def test_no_accepted_drafts_raises(self, db_session: Session):
        gid, uid = "bg1", "u1"
        db_session.add(Group(id=gid, name="G1", created_by=uid))
        db_session.add(User(id=uid, email="u1@t.com", password_hash="x",
                            display_name="U1"))
        db_session.flush()
        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="OT", source_entity_id="e1"))
        db_session.commit()
        with pytest.raises(PackageBuildError, match="No accepted"):
            build_model_package(db_session, gid, uid)

    def test_accepted_with_quality_error_blocks(self, db_session: Session):
        gid, uid = "bg2", "u2"
        db_session.add(Group(id=gid, name="G2", created_by=uid))
        db_session.add(User(id=uid, email="u2@t.com", password_hash="x",
                            display_name="U2"))
        db_session.flush()
        # No source pointer → error
        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="Bad", status="accepted"))
        db_session.commit()
        with pytest.raises(PackageBuildError, match="quality errors"):
            build_model_package(db_session, gid, uid)

    def test_property_missing_object_type_blocks(self, db_session: Session):
        gid, uid = "bg3", "u3"
        db_session.add(Group(id=gid, name="G3", created_by=uid))
        db_session.add(User(id=uid, email="u3@t.com", password_hash="x",
                            display_name="U3"))
        _seed_entity(db_session, gid, uid, "e3", "Source")
        db_session.flush()
        # Accepted property referencing non-accepted object_type
        db_session.add(_make(gid, uid, draft_type="property",
                             name="Concept.prop", status="accepted",
                             source_entity_id="e3",
                             payload={"object_type": "Concept",
                                      "property_name": "prop"}))
        db_session.commit()
        with pytest.raises(PackageBuildError, match="not in accepted"):
            build_model_package(db_session, gid, uid)

    def test_link_missing_object_types_blocks(self, db_session: Session):
        gid, uid = "bg4", "u4"
        db_session.add(Group(id=gid, name="G4", created_by=uid))
        db_session.add(User(id=uid, email="u4@t.com", password_hash="x",
                            display_name="U4"))
        _seed_entity(db_session, gid, uid, "e4", "Src")
        db_session.flush()
        db_session.add(_make(gid, uid, draft_type="link_type",
                             name="A->B", status="accepted",
                             source_relation_id="e4",
                             payload={"source_object_type": "A",
                                      "target_object_type": "B"}))
        db_session.commit()
        # quality gate fires first (e4 is not a real relation), still blocked
        with pytest.raises(PackageBuildError):
            build_model_package(db_session, gid, uid)


class TestDependencyMissing:
    def test_property_missing_object_type_field_blocks(self, db_session: Session):
        """Accepted manual property with payload={} and valid source → blocked
        because payload.object_type is missing entirely."""
        gid, uid = "bh1", "uh1"
        db_session.add(Group(id=gid, name="H1", created_by=uid))
        db_session.add(User(id=uid, email="h1@t.com", password_hash="x",
                            display_name="H1"))
        _seed_entity(db_session, gid, uid, "eh1", "Concept")
        db_session.flush()
        db_session.add(_make(gid, uid, draft_type="property",
                             name="ManualProp", status="accepted",
                             source_entity_id="eh1",
                             payload={}))
        db_session.commit()
        with pytest.raises(PackageBuildError, match="missing or empty"):
            build_model_package(db_session, gid, uid)

    def test_link_missing_object_type_fields_blocks(self, db_session: Session):
        """Accepted link with valid source, payload missing target_object_type
        → blocked with missing_dependency, not quality error."""
        gid, uid = "bh2", "uh2"
        db_session.add(Group(id=gid, name="H2", created_by=uid))
        db_session.add(User(id=uid, email="h2@t.com", password_hash="x",
                            display_name="H2"))
        _seed_entity(db_session, gid, uid, "eh2", "Src")
        # Need accepted object_type "Src" so source dep check passes
        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="Src", status="accepted",
                             source_entity_id="eh2",
                             payload={"generator": DT, "generation_key": "ot:src",
                                      "source_entity_type": "Concept",
                                      "entity_count": 1}))
        # Seed valid relation so quality gate passes
        db_session.add(OntologyRelation(
            id="rh2", group_id=gid, source_entity_id="eh2",
            source_document_id="d-eh2",
            target_path="tgt", relation_type="wikilink", status="resolved",
            evidence_document_id="d-eh2",
        ))
        db_session.flush()

        db_session.add(_make(gid, uid, draft_type="link_type",
                             name="MissingTgt", status="accepted",
                             source_relation_id="rh2",
                             payload={"source_object_type": "Src",
                                      "target_object_type": "  "}))
        db_session.commit()
        # source "Src" exists but target is whitespace → missing or empty
        with pytest.raises(PackageBuildError, match="missing or empty"):
            build_model_package(db_session, gid, uid)


class TestBuildSuccess:
    def test_warn_draft_creates_package(self, db_session: Session):
        gid, uid = "bg5", "u5"
        db_session.add(Group(id=gid, name="G5", created_by=uid))
        db_session.add(User(id=uid, email="u5@t.com", password_hash="x",
                            display_name="U5"))
        _seed_entity(db_session, gid, uid, "e5", "Concept")
        db_session.flush()
        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="Concept", status="accepted",
                             source_entity_id="e5",
                             payload={"generator": DT,
                                      "generation_key": "ot:concept",
                                      "source_entity_type": "Concept",
                                      "entity_count": 5}))
        db_session.commit()
        pkg, created = build_model_package(db_session, gid, uid)
        assert created is True
        assert pkg.version == 1
        assert pkg.quality_status == "WARN"
        assert pkg.draft_count == 1
        assert pkg.quality_summary["warning_count"] >= 1
        assert len(pkg.contract_json["object_types"]) == 1

    def test_idempotent_same_content(self, db_session: Session):
        gid, uid = "bg6", "u6"
        db_session.add(Group(id=gid, name="G6", created_by=uid))
        db_session.add(User(id=uid, email="u6@t.com", password_hash="x",
                            display_name="U6"))
        _seed_entity(db_session, gid, uid, "e6", "Concept")
        db_session.flush()
        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="Concept", status="accepted",
                             source_entity_id="e6",
                             payload={"generator": DT,
                                      "generation_key": "ot:c",
                                      "source_entity_type": "Concept",
                                      "entity_count": 3}))
        db_session.commit()
        p1, c1 = build_model_package(db_session, gid, uid)
        assert c1 is True and p1.version == 1
        p2, c2 = build_model_package(db_session, gid, uid)
        assert c2 is False and p2.id == p1.id

    def test_content_change_version_2(self, db_session: Session):
        gid, uid = "bg7", "u7"
        db_session.add(Group(id=gid, name="G7", created_by=uid))
        db_session.add(User(id=uid, email="u7@t.com", password_hash="x",
                            display_name="U7"))
        _seed_entity(db_session, gid, uid, "e7a", "Concept")
        _seed_entity(db_session, gid, uid, "e7b", "Vendor", "Vendor")
        db_session.flush()
        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="Concept", status="accepted",
                             source_entity_id="e7a",
                             payload={"generator": DT, "generation_key": "ot:c",
                                      "source_entity_type": "Concept",
                                      "entity_count": 3}))
        db_session.commit()
        p1, _ = build_model_package(db_session, gid, uid)
        assert p1.version == 1 and p1.draft_count == 1

        db_session.add(_make(gid, uid, draft_type="object_type",
                             name="Vendor", status="accepted",
                             source_entity_id="e7b",
                             payload={"generator": DT, "generation_key": "ot:v",
                                      "source_entity_type": "Vendor",
                                      "entity_count": 2}))
        db_session.commit()
        p2, c2 = build_model_package(db_session, gid, uid)
        assert c2 is True
        assert p2.version == 2 and p2.draft_count == 2
        assert p2.content_hash != p1.content_hash
        db_session.refresh(p1)
        assert p1.version == 1

    def test_cross_group_isolation(self, db_session: Session):
        uid = "u8"
        db_session.add(User(id=uid, email="u8@t.com", password_hash="x",
                            display_name="U8"))
        db_session.add(Group(id="g8a", name="GA", created_by=uid))
        db_session.add(Group(id="g8b", name="GB", created_by=uid))
        _seed_entity(db_session, "g8a", uid, "ea", "Concept")
        _seed_entity(db_session, "g8b", uid, "eb", "Vendor", "Vendor")
        db_session.flush()
        db_session.add(_make("g8a", uid, draft_type="object_type",
                             name="Concept", status="accepted",
                             source_entity_id="ea",
                             payload={"generator": DT, "generation_key": "ot:c",
                                      "source_entity_type": "Concept",
                                      "entity_count": 3}))
        db_session.add(_make("g8b", uid, draft_type="object_type",
                             name="Vendor", status="accepted",
                             source_entity_id="eb",
                             payload={"generator": DT, "generation_key": "ot:v",
                                      "source_entity_type": "Vendor",
                                      "entity_count": 2}))
        db_session.commit()
        pa, _ = build_model_package(db_session, "g8a", uid)
        pb, _ = build_model_package(db_session, "g8b", uid)
        assert pa.group_id == "g8a" and pb.group_id == "g8b"
        assert pa.version == 1 and pb.version == 1
        assert pa.content_hash != pb.content_hash
