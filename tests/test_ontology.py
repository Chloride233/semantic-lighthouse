"""Tests for Phase 9.1 + 9.2 ontology governance read model.

Covers: scan (owner/admin only), entity extraction, validation issues,
group isolation, idempotent rescan, member read-only access.
"""

import time

from fastapi.testclient import TestClient

from conftest import register_and_login


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
    """Upload a markdown doc with frontmatter and return doc_id."""
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
    time.sleep(0.3)  # ingestion
    return doc_id


def _scan(client: TestClient, gid: str, headers: dict[str, str]) -> dict:
    r = client.post(f"/groups/{gid}/ontology/scan", headers=headers)
    return r.json()


# ── P0: basic entity extraction ───────────────────────────────────────


class TestEntityExtraction:
    def test_owner_scan_creates_entity(self, client):
        _, _, h = register_and_login(client, "o1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept-ontology.md", {
            "entityType": "Concept",
            "tags": ["ontology", "semantic"],
            "created": "2026-06-01",
        })

        result = _scan(client, gid, h)
        assert result["scanned_count"] >= 1
        assert result["entity_count"] >= 1

    def test_member_cannot_scan(self, client):
        _, _, owner_h = register_and_login(client, "o3@t.com")
        _, _, member_h = register_and_login(client, "m3@t.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)

        r = client.post(f"/groups/{gid}/ontology/scan", headers=member_h)
        assert r.status_code == 403

    def test_non_member_cannot_access(self, client):
        _, _, owner_h = register_and_login(client, "o4@t.com")
        _, _, outsider_h = register_and_login(client, "x4@t.com")
        gid = _create_group(client, owner_h)

        r = client.get(f"/groups/{gid}/ontology/entities", headers=outsider_h)
        assert r.status_code == 403
        r = client.get(f"/groups/{gid}/ontology/issues", headers=outsider_h)
        assert r.status_code == 403

    def test_member_can_read_entities_and_issues(self, client):
        _, _, owner_h = register_and_login(client, "o5@t.com")
        _, _, member_h = register_and_login(client, "m5@t.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        _upload_doc(client, gid, owner_h, "concept-read.md", {
            "entityType": "Concept",
            "tags": ["readable"],
            "created": "2026-01-01",
        })
        _scan(client, gid, owner_h)

        r = client.get(f"/groups/{gid}/ontology/entities", headers=member_h)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

        r = client.get(f"/groups/{gid}/ontology/issues", headers=member_h)
        assert r.status_code == 200


# ── P1: validation issues ─────────────────────────────────────────────


class TestValidationIssues:
    def test_type_conflict_generates_issue_no_entity(self, client):
        _, _, h = register_and_login(client, "tc1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "conflict.md", {
            "entityType": "Concept",
            "documentType": "Schema",
            "tags": ["x"],
            "created": "2026-01-01",
        })

        result = _scan(client, gid, h)
        assert result["entity_count"] == 0
        assert result["issue_count"] >= 1

        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        assert any(i["code"] == "type_conflict" for i in issues["issues"])

    def test_missing_tags_created_generates_warnings(self, client):
        _, _, h = register_and_login(client, "mt1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "missing-fields.md", {
            "entityType": "Concept",
        })

        result = _scan(client, gid, h)
        assert result["entity_count"] >= 1  # entity still created
        assert result["issue_count"] >= 2  # missing tags + missing created

        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        codes = [i["code"] for i in issues["issues"]]
        assert "missing_required_field" in codes
        missing = [i for i in issues["issues"] if i["code"] == "missing_required_field"]
        assert all(i["severity"] == "warning" for i in missing)

    def test_invalid_status_source_generates_warnings(self, client):
        _, _, h = register_and_login(client, "is1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "invalid-sv.md", {
            "entityType": "Concept",
            "tags": ["test"],
            "created": "2026-01-01",
            "status": "invalid-status-value",
            "source": "unknown-source-blog",
        })

        result = _scan(client, gid, h)
        assert result["entity_count"] >= 1
        assert result["issue_count"] >= 2

        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        codes = [i["code"] for i in issues["issues"]]
        assert "invalid_controlled_value" in codes

    def test_invalid_entity_type_generates_error(self, client):
        _, _, h = register_and_login(client, "ie1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "bad-type.md", {
            "entityType": "NotARealType",
            "tags": ["x"],
            "created": "2026-01-01",
        })

        result = _scan(client, gid, h)
        assert result["entity_count"] == 0
        assert result["issue_count"] >= 1

        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        assert any(
            i["code"] == "invalid_entity_type" and i["severity"] == "error"
            for i in issues["issues"]
        )

    def test_invalid_document_type_generates_error(self, client):
        _, _, h = register_and_login(client, "id1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "bad-doc.md", {
            "documentType": "NotADocType",
        })

        result = _scan(client, gid, h)
        assert result["entity_count"] == 0
        assert result["issue_count"] >= 1

        issues = client.get(f"/groups/{gid}/ontology/issues", headers=h).json()
        assert any(i["code"] == "invalid_document_type" for i in issues["issues"])

    def test_document_type_does_not_create_entity(self, client):
        _, _, h = register_and_login(client, "dt1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "schema-file.md", {
            "documentType": "Schema",
        })

        result = _scan(client, gid, h)
        assert result["entity_count"] == 0
        assert result["issue_count"] == 0  # valid documentType, no issues


# ── P2: isolation and idempotency ─────────────────────────────────────


class TestIsolationAndIdempotency:
    def test_cross_group_isolation(self, client):
        _, _, h_a = register_and_login(client, "cg1@t.com")
        _, _, h_b = register_and_login(client, "cg2@t.com")
        ga = _create_group(client, h_a)
        gb = _create_group(client, h_b)
        _upload_doc(client, ga, h_a, "a-doc.md", {
            "entityType": "Concept", "tags": ["private"], "created": "2026-01-01",
        })
        _upload_doc(client, gb, h_b, "b-doc.md", {
            "entityType": "Vendor", "tags": ["vendor"], "created": "2026-01-01",
        })

        _scan(client, ga, h_a)
        _scan(client, gb, h_b)

        r_a = client.get(f"/groups/{ga}/ontology/entities", headers=h_a)
        assert r_a.status_code == 200
        entities_a = r_a.json()["entities"]
        assert all(e["group_id"] == ga for e in entities_a)

        # Cross-access blocked
        r = client.get(f"/groups/{ga}/ontology/entities", headers=h_b)
        assert r.status_code == 403

    def test_rescan_is_idempotent_no_duplicates(self, client):
        _, _, h = register_and_login(client, "rs1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept-a.md", {
            "entityType": "Concept", "tags": ["a"], "created": "2026-01-01",
        })

        r1 = _scan(client, gid, h)
        r2 = _scan(client, gid, h)

        assert r1["entity_count"] == r2["entity_count"]
        assert r1["issue_count"] == r2["issue_count"]

        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        assert entities["total"] == r1["entity_count"]


# ── P3: entity detail fields ──────────────────────────────────────────


class TestEntityFields:
    def test_entity_fields_are_correct(self, client):
        _, _, h = register_and_login(client, "ef1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "vendor-palantir.md", {
            "entityType": "Vendor",
            "tags": ["palantir", "foundry"],
            "created": "2025-06-01",
            "status": "reviewed",
            "source": "official-doc",
            "aliases": ["PLTR", "帕兰提尔"],
        })

        _scan(client, gid, h)
        entities = client.get(f"/groups/{gid}/ontology/entities", headers=h).json()
        assert entities["total"] >= 1
        e = entities["entities"][0]
        assert e["entity_type"] == "Vendor"
        assert "palantir" in e["tags"]
        assert e["status"] == "reviewed"
        assert e["source"] == "official-doc"
        assert "PLTR" in e["aliases"]


# ── P4: filtering ─────────────────────────────────────────────────────


class TestFiltering:
    def test_entity_type_filter(self, client):
        _, _, h = register_and_login(client, "ft1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "concept-x.md", {
            "entityType": "Concept", "tags": ["x"], "created": "2026-01-01",
        })
        _upload_doc(client, gid, h, "vendor-y.md", {
            "entityType": "Vendor", "tags": ["y"], "created": "2026-01-01",
        })
        _scan(client, gid, h)

        r = client.get(
            f"/groups/{gid}/ontology/entities?entity_type=Concept", headers=h
        )
        assert r.status_code == 200
        data = r.json()
        assert all(e["entity_type"] == "Concept" for e in data["entities"])

    def test_issue_severity_filter(self, client):
        _, _, h = register_and_login(client, "isf1@t.com")
        gid = _create_group(client, h)
        _upload_doc(client, gid, h, "bad-type2.md", {
            "entityType": "InvalidXYZ",
            "tags": ["x"],
            "created": "2026-01-01",
        })
        _scan(client, gid, h)

        r = client.get(
            f"/groups/{gid}/ontology/issues?severity=error", headers=h
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert all(i["severity"] == "error" for i in data["issues"])
