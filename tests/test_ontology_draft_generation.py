"""Tests for Phase 11.3 deterministic ontology modeling draft generation.

Covers: generate endpoint permissions, draft type generation rules,
idempotency, manual draft protection, evidence scoping, generation keys.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login
from semantic_lighthouse.models import OntologyModelingDraft


def _create_group(client: TestClient, headers: dict[str, str], name: str = "Team") -> str:
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _join_group(
    client: TestClient, gid: str, owner_h: dict[str, str], member_h: dict[str, str]
) -> None:
    inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
    assert inv.status_code == 201
    r = client.post(
        "/groups/join-by-invite",
        json={"invite_code": inv.json()["invite_code"]},
        headers=member_h,
    )
    assert r.status_code == 200


def _upload_doc(
    client: TestClient,
    gid: str,
    headers: dict[str, str],
    filename: str,
    frontmatter: dict,
    body: str = "# Test\n\nContent.",
) -> str:
    import time

    yaml_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            items = ", ".join(v)
            yaml_lines.append(f"{k}: [{items}]")
        else:
            yaml_lines.append(f"{k}: {v}")
    yaml_lines.append("---")
    yaml_lines.append(body)
    content = "\n".join(yaml_lines)

    r = client.post(
        f"/groups/{gid}/documents/upload",
        files={"file": (filename, content.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    time.sleep(0.3)
    return doc_id


def _scan(client: TestClient, gid: str, headers: dict[str, str]) -> dict:
    r = client.post(f"/groups/{gid}/ontology/scan", headers=headers)
    return r.json()


def _generate(client: TestClient, gid: str, headers: dict[str, str]):
    return client.post(f"/groups/{gid}/ontology/drafts/generate", headers=headers)


# ── P0: permissions ──────────────────────────────────────────────────────


class TestGeneratePermissions:
    def test_owner_can_generate(self, client):
        _, _, h = register_and_login(client, "go1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        r = _generate(client, gid, h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["generated_count"] >= 1  # at least object_type

    def test_admin_can_generate(self, client, db_session: Session):
        _, _, oh = register_and_login(client, "ga1o@t.com")
        _, _, ah = register_and_login(client, "ga1a@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, ah)

        from semantic_lighthouse.models import GroupMembership
        membership = db_session.query(GroupMembership).filter(
            GroupMembership.group_id == gid,
            GroupMembership.role == "member",
        ).first()
        assert membership is not None
        membership.role = "admin"
        db_session.commit()

        _upload_doc(client, gid, oh, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)

        r = _generate(client, gid, ah)
        assert r.status_code == 200, r.text
        assert r.json()["generated_count"] >= 1

    def test_member_cannot_generate(self, client):
        _, _, oh = register_and_login(client, "gm1o@t.com")
        _, _, mh = register_and_login(client, "gm1m@t.com")
        gid = _create_group(client, oh)
        _join_group(client, gid, oh, mh)
        _upload_doc(client, gid, oh, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, oh)

        r = _generate(client, gid, mh)
        assert r.status_code == 403

    def test_outsider_cannot_generate(self, client):
        _, _, oh = register_and_login(client, "gx1o@t.com")
        _, _, xh = register_and_login(client, "gx1x@t.com")
        gid = _create_group(client, oh)

        r = _generate(client, gid, xh)
        assert r.status_code == 403

    def test_no_entities_returns_400(self, client):
        _, _, h = register_and_login(client, "gne1@t.com")
        gid = _create_group(client, h)
        # No upload, no scan

        r = _generate(client, gid, h)
        assert r.status_code == 400
        assert "ontology scan" in r.json()["detail"].lower()


# ── P1: object type drafts ───────────────────────────────────────────────


class TestObjectTypeDrafts:
    def test_entity_type_generates_object_type(self, client):
        _, _, h = register_and_login(client, "ot1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        r = _generate(client, gid, h)
        assert r.status_code == 200
        data = r.json()
        assert data["counts_by_type"]["object_type"] >= 1

        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=object_type", headers=h
        ).json()
        assert drafts["total"] >= 1
        ot = drafts["drafts"][0]
        assert ot["name"] == "Concept"
        assert ot["status"] == "proposed"
        assert ot["source_entity_id"] is not None
        assert "generation_key" in ot["payload"]
        assert ot["payload"]["generation_key"].startswith("object_type:")
        assert ot["payload"]["entity_count"] >= 1

    def test_multiple_entity_types_creates_multiple_object_types(self, client):
        _, _, h = register_and_login(client, "ot2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _upload_doc(client, gid, h, "vendor.md", {
            "entityType": "Vendor", "tags": ["y"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        r = _generate(client, gid, h)
        assert r.json()["counts_by_type"]["object_type"] >= 2

    def test_evidence_refs_contain_entity_samples(self, client):
        _, _, h = register_and_login(client, "ot3@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "c1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _upload_doc(client, gid, h, "c2.md", {
            "entityType": "Concept", "tags": ["b"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        _generate(client, gid, h)
        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=object_type", headers=h
        ).json()
        ot = drafts["drafts"][0]
        assert ot["name"] == "Concept"
        assert len(ot["evidence_refs"]) >= 1
        for ref in ot["evidence_refs"]:
            assert "entity_id" in ref
            assert "document_id" in ref
            assert "source_path" in ref
            assert "title" in ref


# ── P2: property drafts ──────────────────────────────────────────────────


class TestPropertyDrafts:
    def test_frontmatter_fields_generate_property_drafts(self, client):
        _, _, h = register_and_login(client, "pr1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept",
            "tags": ["ontology"],
            "created": "2026-01-01",
            "status": "reviewed",
            "source": "official-doc",
        })
        _scan(client, gid, h)

        r = _generate(client, gid, h)
        assert r.status_code == 200
        data = r.json()
        assert data["counts_by_type"]["property"] >= 3  # tags, created, status, source

        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=property", headers=h
        ).json()
        prop_names = {d["name"] for d in drafts["drafts"]}
        assert "Concept.tags" in prop_names
        assert "Concept.created" in prop_names
        assert "Concept.status" in prop_names

    def test_entity_type_and_document_type_fields_excluded(self, client):
        _, _, h = register_and_login(client, "pr2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept",
            "tags": ["x"],
            "created": "2026-01-01",
        })
        _scan(client, gid, h)

        _generate(client, gid, h)
        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=property", headers=h
        ).json()
        prop_names = {d["name"] for d in drafts["drafts"]}
        assert "Concept.entityType" not in prop_names
        assert "Concept.documentType" not in prop_names

    def test_property_payload_has_observed_types(self, client):
        _, _, h = register_and_login(client, "pr3@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept",
            "tags": ["a", "b"],
            "created": "2026-01-01",
        })
        _scan(client, gid, h)

        _generate(client, gid, h)
        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=property", headers=h
        ).json()
        tags_draft = [d for d in drafts["drafts"] if d["name"] == "Concept.tags"][0]
        assert "observed_value_types" in tags_draft["payload"]
        assert "observed_count" in tags_draft["payload"]
        assert tags_draft["payload"]["generation_key"].startswith("property:")


# ── P3: link type drafts ─────────────────────────────────────────────────


class TestLinkTypeDrafts:
    def test_resolved_relation_generates_link_type(self, client):
        _, _, h = register_and_login(client, "lt1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "ontology.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        }, body="See [[knowledge-graph]].")
        _upload_doc(client, gid, h, "knowledge-graph.md", {
            "entityType": "Concept", "tags": ["y"], "created": "2026-01-01",
        }, body="KG.")
        _scan(client, gid, h)

        r = _generate(client, gid, h)
        data = r.json()
        assert data["counts_by_type"]["link_type"] >= 1

        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=link_type", headers=h
        ).json()
        assert drafts["total"] >= 1
        lt = drafts["drafts"][0]
        assert "Concept" in lt["name"]
        assert "wikilink" in lt["name"]
        assert lt["source_relation_id"] is not None
        assert lt["payload"]["generation_key"].startswith("link_type:")
        assert lt["payload"]["relation_count"] >= 1

    def test_unresolved_relation_does_not_generate_link_type(self, client):
        _, _, h = register_and_login(client, "lt2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "src.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        }, body="[[missing-target]]")
        _scan(client, gid, h)

        r = _generate(client, gid, h)
        assert r.json()["counts_by_type"]["link_type"] == 0

    def test_cross_type_link_has_correct_name(self, client):
        """Link between different entity types should show both in name."""
        _, _, h = register_and_login(client, "lt3@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "case-doc.md", {
            "entityType": "Case", "tags": ["c"], "created": "2026-01-01",
        }, body="Uses [[vendor-doc]].")
        _upload_doc(client, gid, h, "vendor-doc.md", {
            "entityType": "Vendor", "tags": ["v"], "created": "2026-01-01",
        }, body="Vendor.")
        _scan(client, gid, h)

        _generate(client, gid, h)
        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=link_type", headers=h
        ).json()
        lt = drafts["drafts"][0]
        assert "Case" in lt["name"]
        assert "Vendor" in lt["name"]
        assert lt["payload"]["source_object_type"] == "Case"
        assert lt["payload"]["target_object_type"] == "Vendor"


# ── P4: action type drafts ───────────────────────────────────────────────


class TestActionTypeDrafts:
    def test_confirmed_issue_generates_action_type(self, client):
        _, _, h = register_and_login(client, "at1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "src.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        }, body="[[missing-target]]")
        _scan(client, gid, h)

        # Confirm the issue
        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        iid = issues["issues"][0]["id"]
        client.post(
            f"/groups/{gid}/ontology/issues/{iid}/triage",
            json={"triage_status": "confirmed", "triage_note": "review_link_target"},
            headers=h,
        )

        r = _generate(client, gid, h)
        data = r.json()
        assert data["counts_by_type"]["action_type"] >= 1

        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=action_type", headers=h
        ).json()
        assert drafts["total"] >= 1
        at_draft = drafts["drafts"][0]
        assert at_draft["source_issue_id"] is not None
        assert at_draft["payload"]["generation_key"].startswith("action_type:")
        assert at_draft["payload"]["scope"] == "ontology_governance"
        assert len(at_draft["payload"]["issue_codes"]) >= 1

    def test_pending_issue_does_not_generate_action_type(self, client):
        _, _, h = register_and_login(client, "at2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "src.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        }, body="[[missing-target]]")
        _scan(client, gid, h)
        # Don't confirm — stays pending

        r = _generate(client, gid, h)
        assert r.json()["counts_by_type"]["action_type"] == 0

    def test_ignored_issue_does_not_generate_action_type(self, client):
        _, _, h = register_and_login(client, "at3@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "src.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        }, body="[[missing-target]]")
        _scan(client, gid, h)

        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        iid = issues["issues"][0]["id"]
        client.post(
            f"/groups/{gid}/ontology/issues/{iid}/triage",
            json={"triage_status": "ignored", "triage_note": "not now"},
            headers=h,
        )

        r = _generate(client, gid, h)
        assert r.json()["counts_by_type"]["action_type"] == 0


# ── P5: idempotency ──────────────────────────────────────────────────────


class TestIdempotency:
    def test_second_generate_produces_no_new_drafts(self, client):
        _, _, h = register_and_login(client, "id1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        r1 = _generate(client, gid, h)
        assert r1.status_code == 200
        gen1 = r1.json()["generated_count"]
        assert gen1 >= 1

        r2 = _generate(client, gid, h)
        assert r2.status_code == 200
        assert r2.json()["generated_count"] == 0
        assert r2.json()["existing_count"] >= gen1

    def test_generation_keys_are_stable(self, client):
        """Regeneration should not create duplicates because existing
        generation_keys survive in existing drafts."""
        _, _, h = register_and_login(client, "id2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        _generate(client, gid, h)
        drafts1 = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        keys1 = {d["payload"]["generation_key"] for d in drafts1["drafts"]}
        assert len(keys1) >= 1

        _generate(client, gid, h)
        drafts2 = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        keys2 = {d["payload"]["generation_key"] for d in drafts2["drafts"]}
        assert keys1 == keys2  # no new keys


# ── P6: manual draft protection ──────────────────────────────────────────


class TestManualDraftProtection:
    def test_existing_manual_draft_not_duplicated(self, client):
        """A manually created draft with same type+name blocks auto-generation."""
        _, _, h = register_and_login(client, "md1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        # Create manual draft with same name as what generation would produce
        r = client.post(
            f"/groups/{gid}/ontology/drafts",
            json={
                "draft_type": "object_type",
                "name": "Concept",
                "source_entity_id": eid,
                "description": "Manual override",
                "payload": {"manual": True},
            },
            headers=h,
        )
        assert r.status_code == 201, r.text

        # Now auto-generate
        gen = _generate(client, gid, h)
        assert gen.status_code == 200
        data = gen.json()
        # The "Concept" object_type should be counted as existing, not generated
        assert data["counts_by_type"]["object_type"] == 0
        assert data["existing_count"] >= 1

        # Manual draft should be unchanged
        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?draft_type=object_type", headers=h
        ).json()
        assert drafts["total"] == 1  # only manual draft
        assert drafts["drafts"][0]["description"] == "Manual override"
        assert drafts["drafts"][0]["payload"] == {"manual": True}

    def test_existing_accepted_draft_not_modified_by_generation(self, client, db_session):
        """Accepted/rejected drafts must not be touched by generation."""
        _, _, h = register_and_login(client, "md2@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        eid = entities["entities"][0]["id"]

        # Create a draft and mark it as accepted via direct DB
        r = client.post(
            f"/groups/{gid}/ontology/drafts",
            json={
                "draft_type": "object_type",
                "name": "Vendor",
                "source_entity_id": eid,
                "description": "Accepted draft",
            },
            headers=h,
        )
        assert r.status_code == 201
        draft_id = r.json()["id"]

        # Mark as accepted via DB
        draft = db_session.query(OntologyModelingDraft).filter(
            OntologyModelingDraft.id == draft_id
        ).first()
        draft.status = "accepted"
        draft.reviewed_by = draft.created_by
        draft.reviewed_at = draft.updated_at
        draft.review_note = "Looks good"
        db_session.commit()

        # Upload a Vendor entity and scan
        _upload_doc(client, gid, h, "vendor.md", {
            "entityType": "Vendor", "tags": ["y"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        _generate(client, gid, h)

        # Verify the accepted draft is unchanged
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()
        accepted = [d for d in drafts["drafts"] if d["id"] == draft_id]
        assert len(accepted) == 1
        assert accepted[0]["status"] == "accepted"
        assert accepted[0]["review_note"] == "Looks good"
        assert accepted[0]["description"] == "Accepted draft"


# ── P7: evidence scoping and source pointers ─────────────────────────────


class TestEvidenceScoping:
    def test_generated_draft_source_in_same_group(self, client):
        """All generated draft source pointers must belong to the correct group."""
        _, _, h = register_and_login(client, "es1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "c1.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        _generate(client, gid, h)
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()

        entity_ids = {
            e["id"] for e in
            client.get(f"/groups/{gid}/ontology/entities", headers=h).json()["entities"]
        }
        for d in drafts["drafts"]:
            if d["source_entity_id"]:
                assert d["source_entity_id"] in entity_ids, (
                    f"Draft {d['name']} source_entity_id not in group entities"
                )

    def test_cross_group_generation_isolated(self, client):
        """Generation in group A must not use group B's entities."""
        _, _, ha = register_and_login(client, "es2a@t.com")
        _, _, hb = register_and_login(client, "es2b@t.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)

        _upload_doc(client, ga, ha, "ca.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })
        _scan(client, ga, ha)

        _upload_doc(client, gb, hb, "cb.md", {
            "entityType": "Vendor", "tags": ["b"], "created": "2026-01-01",
        })
        _scan(client, gb, hb)

        _generate(client, ga, ha)
        _generate(client, gb, hb)

        # Group A drafts must only reference A's entities
        drafts_a = client.get(f"/groups/{ga}/ontology/drafts", headers=ha).json()
        for d in drafts_a["drafts"]:
            assert d["group_id"] == ga

        # Group B drafts must only reference B's entities
        drafts_b = client.get(f"/groups/{gb}/ontology/drafts", headers=hb).json()
        for d in drafts_b["drafts"]:
            assert d["group_id"] == gb


# ── P8: generation key presence ──────────────────────────────────────────


class TestGenerationKeys:
    def test_all_generated_drafts_have_generation_key(self, client):
        _, _, h = register_and_login(client, "gk1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "c.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _upload_doc(client, gid, h, "v.md", {
            "entityType": "Vendor", "tags": ["y"], "created": "2026-01-01",
        }, body="[[c]]")
        _scan(client, gid, h)

        # Confirm any issues
        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        if issues["total"] > 0:
            for iss in issues["issues"]:
                client.post(
                    f"/groups/{gid}/ontology/issues/{iss['id']}/triage",
                    json={"triage_status": "confirmed", "triage_note": "review_link_target"},
                    headers=h,
                )

        _generate(client, gid, h)
        drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h).json()

        for d in drafts["drafts"]:
            assert "generation_key" in d["payload"], (
                f"Draft {d['name']} ({d['draft_type']}) missing generation_key"
            )
            assert d["payload"]["generation_key"], (
                f"Draft {d['name']} has empty generation_key"
            )
            assert d["payload"]["generator"] == "deterministic_v1"


# ── P9: response schema ──────────────────────────────────────────────────


class TestResponseSchema:
    def test_response_has_all_fields(self, client):
        _, _, h = register_and_login(client, "rs1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "c.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        r = _generate(client, gid, h)
        data = r.json()
        assert "generated_count" in data
        assert "existing_count" in data
        assert "skipped_count" in data
        assert "counts_by_type" in data
        assert "object_type" in data["counts_by_type"]
        assert "property" in data["counts_by_type"]
        assert "link_type" in data["counts_by_type"]
        assert "action_type" in data["counts_by_type"]
