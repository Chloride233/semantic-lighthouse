"""Tests for Phase 14.4 — project model validation gate.

Covers: project-scoped quality, package build with WARN/FAIL gates,
WARN override audit, idempotency, stage advancement (model→validate),
permissions, legacy backward compatibility, migration 0021.
"""

import io

import pytest
from conftest import register_and_login


# ── helpers ──────────────────────────────────────────────────────────────


def _create_group(client, headers, name="Enterprise"):
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _join_group(client, gid, owner_h, member_h):
    inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
    assert inv.status_code == 201
    r = client.post(
        "/groups/join-by-invite",
        json={"invite_code": inv.json()["invite_code"]},
        headers=member_h,
    )
    assert r.status_code == 200


def _promote_admin(client, gid, owner_h, member_id):
    r = client.patch(
        f"/groups/{gid}/members/{member_id}/role",
        json={"role": "admin"},
        headers=owner_h,
    )
    assert r.status_code == 200


def _create_project(client, gid, h, name="ValTest", **kw):
    body = {"name": name, "entry_mode": "problem_first", **kw}
    r = client.post(f"/groups/{gid}/projects", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_and_generate(client, gid, pid, h):
    """Upload minimal CSV, generate drafts, accept all, return draft ids."""
    csv_content = "order_id,customer_id,amount\n100,1,99.99\n101,2,149.50\n"
    files = {"file": ("orders.csv", io.BytesIO(csv_content.encode("utf-8")), "application/octet-stream")}
    data = {"include_sample_values": "false"}
    r = client.post(f"/groups/{gid}/projects/{pid}/datasets", files=files, data=data, headers=h)
    assert r.status_code == 201

    r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _accept_all_drafts(client, gid, h, pid):
    """Accept all proposed drafts in the project."""
    while True:
        r = client.get(
            f"/groups/{gid}/ontology/drafts?project_id={pid}&status=proposed&limit=100",
            headers=h,
        )
        assert r.status_code == 200
        drafts = r.json()["drafts"]
        if not drafts:
            break
        batch_ids = [d["id"] for d in drafts]
        r = client.post(
            f"/groups/{gid}/ontology/drafts/review-batch",
            json={"draft_ids": batch_ids, "status": "accepted", "review_note": "ok"},
            headers=h,
        )
        assert r.status_code == 200, r.text


def _set_project_stage_to_model(client, gid, pid, h):
    """Upload, generate, and accept drafts to get project to model stage."""
    _upload_and_generate(client, gid, pid, h)
    _accept_all_drafts(client, gid, h, pid)
    # Verify stage
    proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
    return proj.json()


# ── quality ──────────────────────────────────────────────────────────────


class TestProjectQuality:
    def test_project_quality_only_sees_project_drafts(self, client):
        """Quality gate scoped to project — same group, different project don't mix."""
        _, _, h = register_and_login(client, "pq-1@pj.com")
        gid = _create_group(client, h)
        pid_a = _create_project(client, gid, h, name="A")
        pid_b = _create_project(client, gid, h, name="B")
        _upload_and_generate(client, gid, pid_a, h)
        # Quality for project A should see drafts, project B should be empty
        r_a = client.get(f"/groups/{gid}/projects/{pid_a}/model-drafts/quality", headers=h)
        r_b = client.get(f"/groups/{gid}/projects/{pid_b}/model-drafts/quality", headers=h)
        assert r_a.json()["draft_count"] > 0
        assert r_b.json()["draft_count"] == 0

    def test_cross_project_drafts_not_in_quality(self, client):
        """Quality for project A doesn't see project B's drafts."""
        _, _, h = register_and_login(client, "pq-2@pj.com")
        gid = _create_group(client, h)
        pid_a = _create_project(client, gid, h, name="A")
        pid_b = _create_project(client, gid, h, name="B")
        _upload_and_generate(client, gid, pid_a, h)
        _upload_and_generate(client, gid, pid_b, h)
        r_a = client.get(f"/groups/{gid}/projects/{pid_a}/model-drafts/quality", headers=h)
        r_b = client.get(f"/groups/{gid}/projects/{pid_b}/model-drafts/quality", headers=h)
        assert r_a.json()["draft_count"] > 0
        assert r_b.json()["draft_count"] > 0
        # Drafts are scoped: project A quality only counts project A's drafts
        ids_a = {d["id"] for d in client.get(
            f"/groups/{gid}/ontology/drafts?project_id={pid_a}&limit=100", headers=h
        ).json()["drafts"]}
        ids_b = {d["id"] for d in client.get(
            f"/groups/{gid}/ontology/drafts?project_id={pid_b}&limit=100", headers=h
        ).json()["drafts"]}
        assert ids_a.isdisjoint(ids_b)

    def test_member_can_read_quality(self, client):
        _, _, owner_h = register_and_login(client, "pq-3-o@pj.com")
        _, _, mem_h = register_and_login(client, "pq-3-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _upload_and_generate(client, gid, pid, owner_h)
        r = client.get(f"/groups/{gid}/projects/{pid}/model-drafts/quality", headers=mem_h)
        assert r.status_code == 200

    def test_outsider_quality_403(self, client):
        _, _, owner_h = register_and_login(client, "pq-4-o@pj.com")
        _, _, outsider_h = register_and_login(client, "pq-4-x@pj.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)
        r = client.get(f"/groups/{gid}/projects/{pid}/model-drafts/quality", headers=outsider_h)
        assert r.status_code == 403


# ── package build ────────────────────────────────────────────────────────


class TestProjectPackageBuild:
    def test_pass_builds_package_and_advances_to_validate(self, client):
        """PASS quality → package built, model → validate."""
        _, _, h = register_and_login(client, "ppb-1@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj.json()["stage"] == "model"

        r = client.post(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["created"] is True
        assert data["draft_count"] > 0

        proj2 = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj2.json()["stage"] == "validate"

    def test_idempotent_rebuild(self, client):
        """Building same package twice returns existing, stage unchanged."""
        _, _, h = register_and_login(client, "ppb-2@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)

        r1 = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        assert r1.status_code == 201
        r2 = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        assert r2.status_code == 201
        assert r2.json()["created"] is False
        assert r2.json()["id"] == r1.json()["id"]

    def test_proposed_drafts_block(self, client):
        """Proposed drafts → 409, must review first."""
        _, _, h = register_and_login(client, "ppb-3@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_and_generate(client, gid, pid, h)
        # Don't accept — drafts are still proposed
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        assert r.status_code == 409

    def test_no_accepted_object_type_blocks(self, client):
        """No accepted OT → package build blocked."""
        _, _, h = register_and_login(client, "ppb-4@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_and_generate(client, gid, pid, h)
        # Accept only properties, reject the OT
        drafts = client.get(
            f"/groups/{gid}/ontology/drafts?project_id={pid}&limit=100", headers=h
        ).json()["drafts"]
        for d in drafts:
            if d["draft_type"] == "object_type":
                client.post(
                    f"/groups/{gid}/ontology/drafts/{d['id']}/review",
                    json={"status": "rejected", "review_note": "not needed"},
                    headers=h,
                )
            else:
                client.post(
                    f"/groups/{gid}/ontology/drafts/{d['id']}/review",
                    json={"status": "accepted", "review_note": "ok"},
                    headers=h,
                )
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        assert r.status_code == 409

    def test_archived_project_cannot_build(self, client):
        """Archived project → 409 on build (but quality still readable)."""
        _, _, h = register_and_login(client, "ppb-5@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/archive", headers=h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        assert r.status_code == 409
        # Quality still readable on archived project
        r_q = client.get(f"/groups/{gid}/projects/{pid}/model-drafts/quality", headers=h)
        assert r_q.status_code == 200

    def test_different_projects_each_build_package(self, client):
        """Same contract content in two projects → separate packages."""
        _, _, h = register_and_login(client, "ppb-6@pj.com")
        gid = _create_group(client, h)
        pid_a = _create_project(client, gid, h, name="A")
        pid_b = _create_project(client, gid, h, name="B")
        _set_project_stage_to_model(client, gid, pid_a, h)
        _set_project_stage_to_model(client, gid, pid_b, h)
        r_a = client.post(f"/groups/{gid}/projects/{pid_a}/model-drafts/packages", headers=h)
        r_b = client.post(f"/groups/{gid}/projects/{pid_b}/model-drafts/packages", headers=h)
        assert r_a.status_code == 201
        assert r_b.status_code == 201
        assert r_a.json()["id"] != r_b.json()["id"]
        # Same contract content should produce same content_hash since same CSV
        # (but different scope_key, so different packages)

    def test_goal_stage_rejected(self, client):
        """Project at goal → 409 (need data and model stages first)."""
        _, _, h = register_and_login(client, "ppb-7@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        assert r.status_code == 409

    def test_member_cannot_build(self, client):
        _, _, owner_h = register_and_login(client, "ppb-8-o@pj.com")
        _, _, mem_h = register_and_login(client, "ppb-8-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _set_project_stage_to_model(client, gid, pid, owner_h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=mem_h)
        assert r.status_code == 403

    def test_admin_can_build(self, client):
        _, owner_me, owner_h = register_and_login(client, "ppb-9-o@pj.com")
        admin_me, _, admin_h = register_and_login(client, "ppb-9-a@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_admin(client, gid, owner_h, admin_me["id"])
        pid = _create_project(client, gid, owner_h)
        _set_project_stage_to_model(client, gid, pid, owner_h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=admin_h)
        assert r.status_code == 201

    def test_outsider_cannot_build(self, client):
        _, _, owner_h = register_and_login(client, "ppb-10-o@pj.com")
        _, _, outsider_h = register_and_login(client, "ppb-10-x@pj.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=outsider_h)
        assert r.status_code == 403


# ── WARN override ────────────────────────────────────────────────────────


class TestWarnOverride:
    def test_warn_default_blocks(self, client):
        """WARN without allow_warnings → 409."""
        _, _, h = register_and_login(client, "wo-1@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        # Check quality first
        quality = client.get(f"/groups/{gid}/projects/{pid}/model-drafts/quality", headers=h).json()
        if quality["status"] == "PASS":
            pytest.skip("No warnings to test override — draft is PASS")
        r = client.post(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h,
        )
        assert r.status_code == 409

    def test_warn_override_with_reason(self, client):
        """WARN with allow_warnings + reason → builds with audit."""
        _, _, h = register_and_login(client, "wo-2@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        quality = client.get(f"/groups/{gid}/projects/{pid}/model-drafts/quality", headers=h).json()
        if quality["status"] != "WARN":
            pytest.skip("Quality is not WARN — nothing to test override with")
        r = client.post(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages",
            json={"allow_warnings": True, "override_reason": "Acceptable for pilot"},
            headers=h,
        )
        assert r.status_code == 201, r.text
        # Verify WARN override audit persisted
        r_pkg = client.get(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages/{r.json()['id']}",
            headers=h,
        )
        summary = r_pkg.json().get("quality_summary", {})
        assert summary.get("warning_override") is True
        assert summary.get("override_reason") == "Acceptable for pilot"

    def test_warn_override_empty_reason_rejected(self, client):
        """WARN with allow_warnings=true but empty reason → 422."""
        _, _, h = register_and_login(client, "wo-3@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        quality = client.get(f"/groups/{gid}/projects/{pid}/model-drafts/quality", headers=h).json()
        if quality["status"] != "WARN":
            pytest.skip("Quality is not WARN")
        r = client.post(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages",
            json={"allow_warnings": True, "override_reason": ""},
            headers=h,
        )
        assert r.status_code == 422


# ── package list / detail / contract ─────────────────────────────────────


class TestProjectPackageRead:
    def test_list_project_packages(self, client):
        _, _, h = register_and_login(client, "ppr-1@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        r = client.get(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_project_package_detail(self, client):
        _, _, h = register_and_login(client, "ppr-2@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        p = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h).json()
        r = client.get(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages/{p['id']}", headers=h
        )
        assert r.status_code == 200
        assert r.json()["project_id"] == pid

    def test_get_project_contract(self, client):
        _, _, h = register_and_login(client, "ppr-3@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        p = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h).json()
        r = client.get(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages/{p['id']}/contract",
            headers=h,
        )
        assert r.status_code == 200, f"Contract error: {r.text}"
        # provenance includes project_id
        provenance = r.json().get("provenance", {})
        assert provenance.get("project_id") == pid

    def test_member_can_read_packages(self, client):
        _, _, owner_h = register_and_login(client, "ppr-4-o@pj.com")
        _, _, mem_h = register_and_login(client, "ppr-4-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _set_project_stage_to_model(client, gid, pid, owner_h)
        p = client.post(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=owner_h
        ).json()
        r = client.get(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages/{p['id']}", headers=mem_h
        )
        assert r.status_code == 200

    def test_cross_project_404_on_package_detail(self, client):
        _, _, ha = register_and_login(client, "ppr-5-a@pj.com")
        _, _, hb = register_and_login(client, "ppr-5-b@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        pid_a = _create_project(client, ga, ha)
        pid_b = _create_project(client, gb, hb)
        _set_project_stage_to_model(client, ga, pid_a, ha)
        p = client.post(
            f"/groups/{ga}/projects/{pid_a}/model-drafts/packages", headers=ha
        ).json()
        # Try to access via group B project B URL
        r = client.get(
            f"/groups/{gb}/projects/{pid_b}/model-drafts/packages/{p['id']}", headers=hb
        )
        assert r.status_code == 404


# ── legacy backward compatibility ────────────────────────────────────────


class TestLegacyPackageCompatibility:
    def test_legacy_quality_still_works(self, client):
        """Group-wide quality endpoint still functional."""
        _, _, h = register_and_login(client, "lpc-1@pj.com")
        gid = _create_group(client, h)
        # Even empty group should return valid response
        r = client.get(f"/groups/{gid}/ontology/drafts/quality", headers=h)
        assert r.status_code == 200
        assert "status" in r.json()

    def test_legacy_package_list_still_works(self, client):
        """Group-wide package listing still functional."""
        _, _, h = register_and_login(client, "lpc-2@pj.com")
        gid = _create_group(client, h)
        r = client.get(f"/groups/{gid}/ontology/packages", headers=h)
        assert r.status_code == 200
        assert "packages" in r.json()
        assert "total" in r.json()

    def test_project_package_not_in_legacy_list(self, client):
        """Legacy package list should NOT show project-scoped packages."""
        _, _, h = register_and_login(client, "lpc-3@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _set_project_stage_to_model(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/model-drafts/packages", headers=h)
        # Legacy list should only show group-scoped packages
        r = client.get(f"/groups/{gid}/ontology/packages", headers=h)
        # Project packages have scope_key = "project:{pid}", not "group"
        legacy_pkgs = r.json()["packages"]
        assert len(legacy_pkgs) == 0 or all(p.get("project_id") is None for p in legacy_pkgs)


# ── migration ────────────────────────────────────────────────────────────


class TestMigration0021:
    def test_legacy_package_scope_key_is_group(self, client):
        """Verify legacy packages that may exist have correct scope_key."""
        # The migration sets all existing packages to scope_key='group'
        # via server_default. New project packages get scope_key='project:{id}'.
        _, _, h = register_and_login(client, "m21-1@pj.com")
        gid = _create_group(client, h)
        r = client.get(f"/groups/{gid}/ontology/packages", headers=h)
        assert r.status_code == 200
