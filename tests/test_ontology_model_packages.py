"""Tests for Phase 12.3a ontology model package schema.

Covers: create, JSON round-trip, unique constraints, cross-group isolation,
absence of mutable fields.
"""

import pytest
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    Group,
    OntologyModelPackage,
    User,
)


class TestPackageCreate:
    def test_create_full_package_snapshot(self, db_session: Session):
        """A complete package can be saved with all fields."""
        gid, uid = "pkg-g1", "pkg-u1"
        db_session.add(Group(id=gid, name="P1", created_by=uid))
        db_session.add(User(id=uid, email="p1@t.com", password_hash="x",
                            display_name="P1"))
        db_session.flush()

        contract = {
            "object_types": [{"name": "Concept", "properties": ["tags"]}],
            "link_types": [],
            "action_types": [],
        }
        pkg = OntologyModelPackage(
            group_id=gid, version=1,
            content_hash="a" * 64,
            contract_json=contract,
            source_draft_ids=["d1", "d2"],
            draft_count=2,
            quality_status="WARN",
            quality_summary={"warning_codes": {"weak_property_evidence": 1}},
            created_by=uid,
        )
        db_session.add(pkg)
        db_session.commit()
        db_session.refresh(pkg)

        assert pkg.id is not None
        assert pkg.group_id == gid
        assert pkg.version == 1
        assert pkg.schema_version == "1.0"
        assert pkg.content_hash == "a" * 64
        assert pkg.contract_json == contract
        assert pkg.source_draft_ids == ["d1", "d2"]
        assert pkg.draft_count == 2
        assert pkg.quality_status == "WARN"
        assert pkg.quality_summary == {"warning_codes": {"weak_property_evidence": 1}}
        assert pkg.created_by == uid
        assert pkg.created_at is not None

    def test_json_fields_round_trip(self, db_session: Session):
        """contract_json, source_draft_ids, quality_summary preserve types."""
        gid, uid = "pkg-g2", "pkg-u2"
        db_session.add(Group(id=gid, name="P2", created_by=uid))
        db_session.add(User(id=uid, email="p2@t.com", password_hash="x",
                            display_name="P2"))
        db_session.flush()

        contract = {"object_types": [{"name": "Vendor", "properties": ["tags"]}]}
        drafts = ["draft-1", "draft-2", "draft-3"]
        summary = {"total_warnings": 5, "codes": {"weak_link_evidence": 3}}

        pkg = OntologyModelPackage(
            group_id=gid, version=2,
            content_hash="b" * 64,
            contract_json=contract,
            source_draft_ids=drafts,
            draft_count=len(drafts),
            quality_status="WARN",
            quality_summary=summary,
            created_by=uid,
        )
        db_session.add(pkg)
        db_session.commit()
        db_session.refresh(pkg)

        assert pkg.contract_json == contract
        assert pkg.source_draft_ids == drafts
        assert pkg.quality_summary == summary


class TestUniqueConstraints:
    def test_same_group_version_unique(self, db_session: Session):
        """Duplicate (group_id, version) violates unique constraint."""
        gid, uid = "pkg-g3", "pkg-u3"
        db_session.add(Group(id=gid, name="P3", created_by=uid))
        db_session.add(User(id=uid, email="p3@t.com", password_hash="x",
                            display_name="P3"))
        db_session.flush()

        db_session.add(OntologyModelPackage(
            group_id=gid, version=1, content_hash="c" * 64,
            contract_json={}, source_draft_ids=["d1"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        ))
        db_session.commit()

        pkg2 = OntologyModelPackage(
            group_id=gid, version=1, content_hash="d" * 64,
            contract_json={}, source_draft_ids=["d2"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        )
        db_session.add(pkg2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_same_group_content_hash_unique(self, db_session: Session):
        """Duplicate (group_id, content_hash) violates unique constraint."""
        gid, uid = "pkg-g4", "pkg-u4"
        db_session.add(Group(id=gid, name="P4", created_by=uid))
        db_session.add(User(id=uid, email="p4@t.com", password_hash="x",
                            display_name="P4"))
        db_session.flush()

        db_session.add(OntologyModelPackage(
            group_id=gid, version=1, content_hash="e" * 64,
            contract_json={"v": 1}, source_draft_ids=["d1"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        ))
        db_session.commit()

        pkg2 = OntologyModelPackage(
            group_id=gid, version=2, content_hash="e" * 64,
            contract_json={"v": 1}, source_draft_ids=["d1"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        )
        db_session.add(pkg2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_different_groups_same_version(self, db_session: Session):
        """Different groups can use the same version number."""
        uid = "pkg-u5"
        db_session.add(User(id=uid, email="p5@t.com", password_hash="x",
                            display_name="P5"))
        db_session.add(Group(id="pkg-g5a", name="P5A", created_by=uid))
        db_session.add(Group(id="pkg-g5b", name="P5B", created_by=uid))
        db_session.flush()

        db_session.add(OntologyModelPackage(
            group_id="pkg-g5a", version=1, content_hash="f" * 64,
            contract_json={}, source_draft_ids=["da"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        ))
        db_session.add(OntologyModelPackage(
            group_id="pkg-g5b", version=1, content_hash="g" * 64,
            contract_json={}, source_draft_ids=["db"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        ))
        db_session.commit()

    def test_different_groups_same_hash(self, db_session: Session):
        """Different groups can use the same content_hash."""
        uid = "pkg-u6"
        db_session.add(User(id=uid, email="p6@t.com", password_hash="x",
                            display_name="P6"))
        db_session.add(Group(id="pkg-g6a", name="P6A", created_by=uid))
        db_session.add(Group(id="pkg-g6b", name="P6B", created_by=uid))
        db_session.flush()

        same_hash = "h" * 64
        db_session.add(OntologyModelPackage(
            group_id="pkg-g6a", version=1, content_hash=same_hash,
            contract_json={"a": 1}, source_draft_ids=["da"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        ))
        db_session.add(OntologyModelPackage(
            group_id="pkg-g6b", version=2, content_hash=same_hash,
            contract_json={"a": 1}, source_draft_ids=["db"], draft_count=1,
            quality_status="PASS", quality_summary={}, created_by=uid,
        ))
        db_session.commit()


class TestNoMutableFields:
    def test_model_has_no_updated_at_status_published(self):
        """Package model must not have mutable lifecycle fields."""
        columns = {c.name for c in OntologyModelPackage.__table__.columns}
        assert "updated_at" not in columns
        assert "status" not in columns
        assert "published_at" not in columns
        assert "reviewed_at" not in columns
        assert "reviewed_by" not in columns

    def test_model_has_no_fk_source_draft_to_ontology_drafts(self):
        """source_draft_ids is JSON list, not an FK to modeling drafts."""
        columns = {c.name for c in OntologyModelPackage.__table__.columns}
        assert "source_draft_id" not in columns
        assert "source_draft_ids" in columns
