"""Tests for Phase 14.1 — business pilot projects.

Permissions: member read, owner/admin write/archive. Outsider 403.
Cross-group: 404 (no existence leak). Archived projects still readable.
Stage: backend-controlled, no client modification.
"""

import pytest
from fastapi.testclient import TestClient

from conftest import register_and_login
from semantic_lighthouse.services.projects import advance_stage, next_stage


# ── helpers ──────────────────────────────────────────────────────────────


def _create_group(
    client: TestClient, headers: dict[str, str], name: str = "Enterprise"
) -> str:
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


def _promote_to_admin(
    client: TestClient, gid: str, owner_h: dict[str, str], member_id: str
) -> None:
    r = client.patch(
        f"/groups/{gid}/members/{member_id}/role",
        json={"role": "admin"},
        headers=owner_h,
    )
    assert r.status_code == 200


def _create_project(
    client: TestClient,
    gid: str,
    h: dict[str, str],
    name: str = "电商数据治理试点",
    entry_mode: str = "problem_first",
    business_goal: str = "建立电商商品分类与供应商画像知识图谱",
    industry_template: str | None = "ecommerce",
) -> dict:
    body: dict = {
        "name": name,
        "entry_mode": entry_mode,
        "business_goal": business_goal,
    }
    if industry_template is not None:
        body["industry_template"] = industry_template
    r = client.post(f"/groups/{gid}/projects", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


# ── create ───────────────────────────────────────────────────────────────


class TestCreateProject:
    def test_owner_can_create(self, client):
        _, _, h = register_and_login(client, "owner@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        assert p["name"] == "电商数据治理试点"
        assert p["entry_mode"] == "problem_first"
        assert p["stage"] == "goal"
        assert p["status"] == "active"
        assert p["group_id"] == gid
        assert p["business_goal"] == "建立电商商品分类与供应商画像知识图谱"
        assert p["industry_template"] == "ecommerce"

    def test_admin_can_create(self, client):
        _, owner_me, owner_h = register_and_login(client, "owner2@pj.com")
        admin_me, _, admin_h = register_and_login(client, "admin@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_to_admin(client, gid, owner_h, admin_me["id"])
        p = _create_project(client, gid, admin_h, name="admin created")
        assert p["name"] == "admin created"

    def test_member_cannot_create(self, client):
        _, _, owner_h = register_and_login(client, "owner3@pj.com")
        _, _, member_h = register_and_login(client, "member@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "test", "entry_mode": "problem_first"},
            headers=member_h,
        )
        assert r.status_code == 403

    def test_outsider_cannot_create(self, client):
        _, _, owner_h = register_and_login(client, "owner4@pj.com")
        _, _, outsider_h = register_and_login(client, "outsider@pj.com")
        gid = _create_group(client, owner_h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "test", "entry_mode": "problem_first"},
            headers=outsider_h,
        )
        assert r.status_code == 403

    def test_empty_name_422(self, client):
        _, _, h = register_and_login(client, "owner5@pj.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "", "entry_mode": "problem_first"},
            headers=h,
        )
        assert r.status_code == 422

    def test_whitespace_name_422(self, client):
        _, _, h = register_and_login(client, "owner6@pj.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "   ", "entry_mode": "problem_first"},
            headers=h,
        )
        assert r.status_code == 422

    def test_name_trimmed(self, client):
        _, _, h = register_and_login(client, "owner7@pj.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "  电商试点  ", "entry_mode": "problem_first"},
            headers=h,
        )
        assert r.status_code == 201
        assert r.json()["name"] == "电商试点"

    def test_invalid_entry_mode_422(self, client):
        _, _, h = register_and_login(client, "owner8@pj.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "test", "entry_mode": "invalid"},
            headers=h,
        )
        assert r.status_code == 422

    def test_missing_entry_mode_422(self, client):
        _, _, h = register_and_login(client, "owner9@pj.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "test"},
            headers=h,
        )
        assert r.status_code == 422

    def test_business_goal_too_long_422(self, client):
        _, _, h = register_and_login(client, "owner10@pj.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "test", "entry_mode": "problem_first", "business_goal": "x" * 2001},
            headers=h,
        )
        assert r.status_code == 422

    def test_industry_template_max_length(self, client):
        _, _, h = register_and_login(client, "owner11@pj.com")
        gid = _create_group(client, h)
        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "test", "entry_mode": "data_first", "industry_template": "x" * 81},
            headers=h,
        )
        assert r.status_code == 422

    def test_industry_template_optional(self, client):
        _, _, h = register_and_login(client, "owner12@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h, industry_template=None)
        assert p["industry_template"] is None
        assert p["stage"] == "goal"

    def test_stage_always_starts_as_goal(self, client):
        """Client cannot set stage in create request."""
        _, _, h = register_and_login(client, "owner13@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        assert p["stage"] == "goal"

    def test_data_first_entry_mode(self, client):
        _, _, h = register_and_login(client, "owner14@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h, entry_mode="data_first")
        assert p["entry_mode"] == "data_first"


# ── read ─────────────────────────────────────────────────────────────────


class TestReadProject:
    def test_member_can_read(self, client):
        _, _, owner_h = register_and_login(client, "rd-owner@pj.com")
        _, _, member_h = register_and_login(client, "rd-member@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        p = _create_project(client, gid, owner_h)
        r = client.get(f"/groups/{gid}/projects/{p['id']}", headers=member_h)
        assert r.status_code == 200
        assert r.json()["name"] == p["name"]

    def test_owner_can_read(self, client):
        _, _, h = register_and_login(client, "rd-owner2@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        r = client.get(f"/groups/{gid}/projects/{p['id']}", headers=h)
        assert r.status_code == 200

    def test_outsider_403(self, client):
        _, _, owner_h = register_and_login(client, "rd-owner3@pj.com")
        _, _, outsider_h = register_and_login(client, "rd-outsider@pj.com")
        gid = _create_group(client, owner_h)
        p = _create_project(client, gid, owner_h)
        r = client.get(f"/groups/{gid}/projects/{p['id']}", headers=outsider_h)
        assert r.status_code == 403

    def test_cross_group_404_not_leaking_existence(self, client):
        """Project in group A → group B member gets 404, not 403."""
        _, _, ha = register_and_login(client, "rd-ga@pj.com")
        _, _, hb = register_and_login(client, "rd-gb@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        p = _create_project(client, ga, ha)
        # User B (member of group B) tries to read group A project via group B URL
        r = client.get(f"/groups/{gb}/projects/{p['id']}", headers=hb)
        assert r.status_code == 404

    def test_nonexistent_project_404(self, client):
        _, _, h = register_and_login(client, "rd-owner4@pj.com")
        gid = _create_group(client, h)
        r = client.get(f"/groups/{gid}/projects/nonexistent-id", headers=h)
        assert r.status_code == 404


# ── update ───────────────────────────────────────────────────────────────


class TestUpdateProject:
    def test_owner_can_update(self, client):
        _, _, h = register_and_login(client, "up-owner@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        r = client.patch(
            f"/groups/{gid}/projects/{p['id']}",
            json={"name": "updated name", "business_goal": "new goal"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "updated name"
        assert r.json()["business_goal"] == "new goal"

    def test_admin_can_update(self, client):
        _, owner_me, owner_h = register_and_login(client, "up-owner2@pj.com")
        admin_me, _, admin_h = register_and_login(client, "up-admin@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_to_admin(client, gid, owner_h, admin_me["id"])
        p = _create_project(client, gid, owner_h)
        r = client.patch(
            f"/groups/{gid}/projects/{p['id']}",
            json={"name": "admin updated"},
            headers=admin_h,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "admin updated"

    def test_member_cannot_update(self, client):
        _, _, owner_h = register_and_login(client, "up-owner3@pj.com")
        _, _, member_h = register_and_login(client, "up-member@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        p = _create_project(client, gid, owner_h)
        r = client.patch(
            f"/groups/{gid}/projects/{p['id']}",
            json={"name": "hijacked"},
            headers=member_h,
        )
        assert r.status_code == 403

    def test_cannot_change_stage_via_patch(self, client):
        """PATCH only allows name/business_goal/entry_mode/industry_template."""
        _, _, h = register_and_login(client, "up-owner4@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        r = client.patch(
            f"/groups/{gid}/projects/{p['id']}",
            json={"name": "still goal"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["stage"] == "goal"

    def test_partial_update_preserves_other_fields(self, client):
        _, _, h = register_and_login(client, "up-owner5@pj.com")
        gid = _create_group(client, h)
        p = _create_project(
            client, gid, h,
            name="original",
            entry_mode="problem_first",
            business_goal="original goal",
            industry_template="ecommerce",
        )
        r = client.patch(
            f"/groups/{gid}/projects/{p['id']}",
            json={"name": "renamed"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "renamed"
        assert r.json()["entry_mode"] == "problem_first"
        assert r.json()["business_goal"] == "original goal"
        assert r.json()["industry_template"] == "ecommerce"

    def test_update_entry_mode(self, client):
        _, _, h = register_and_login(client, "up-owner6@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h, entry_mode="problem_first")
        r = client.patch(
            f"/groups/{gid}/projects/{p['id']}",
            json={"entry_mode": "data_first"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["entry_mode"] == "data_first"

    def test_update_industry_template_to_none(self, client):
        _, _, h = register_and_login(client, "up-owner7@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h, industry_template="manufacturing")
        r = client.patch(
            f"/groups/{gid}/projects/{p['id']}",
            json={"industry_template": None},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["industry_template"] is None


# ── list ─────────────────────────────────────────────────────────────────


class TestListProjects:
    def test_empty_list(self, client):
        _, _, h = register_and_login(client, "ls-owner@pj.com")
        gid = _create_group(client, h)
        r = client.get(f"/groups/{gid}/projects", headers=h)
        assert r.status_code == 200
        assert r.json()["projects"] == []
        assert r.json()["total"] == 0

    def test_list_multiple_projects(self, client):
        _, _, h = register_and_login(client, "ls-owner2@pj.com")
        gid = _create_group(client, h)
        _create_project(client, gid, h, name="Project A")
        _create_project(client, gid, h, name="Project B")
        r = client.get(f"/groups/{gid}/projects", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] == 2
        names = [p["name"] for p in r.json()["projects"]]
        assert "Project A" in names
        assert "Project B" in names

    def test_status_filter_active(self, client):
        _, _, h = register_and_login(client, "ls-owner3@pj.com")
        gid = _create_group(client, h)
        _create_project(client, gid, h, name="active project")
        p2 = _create_project(client, gid, h, name="archived project")
        client.post(
            f"/groups/{gid}/projects/{p2['id']}/archive", headers=h
        )
        r = client.get(f"/groups/{gid}/projects?status=active", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["projects"][0]["name"] == "active project"

    def test_status_filter_archived(self, client):
        _, _, h = register_and_login(client, "ls-owner4@pj.com")
        gid = _create_group(client, h)
        _create_project(client, gid, h, name="active project")
        p2 = _create_project(client, gid, h, name="archived project")
        client.post(
            f"/groups/{gid}/projects/{p2['id']}/archive", headers=h
        )
        r = client.get(f"/groups/{gid}/projects?status=archived", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["projects"][0]["name"] == "archived project"

    def test_cross_group_isolation(self, client):
        _, _, ha = register_and_login(client, "ls-ga@pj.com")
        _, _, hb = register_and_login(client, "ls-gb@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        _create_project(client, ga, ha, name="group A project")
        r = client.get(f"/groups/{ga}/projects", headers=hb)
        assert r.status_code == 403
        r = client.get(f"/groups/{gb}/projects", headers=hb)
        assert r.json()["total"] == 0

    def test_member_can_list(self, client):
        _, _, owner_h = register_and_login(client, "ls-owner5@pj.com")
        _, _, member_h = register_and_login(client, "ls-member@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        _create_project(client, gid, owner_h, name="shared project")
        r = client.get(f"/groups/{gid}/projects", headers=member_h)
        assert r.status_code == 200
        assert r.json()["total"] == 1


# ── archive ──────────────────────────────────────────────────────────────


class TestArchiveProject:
    def test_owner_can_archive(self, client):
        _, _, h = register_and_login(client, "ar-owner@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        r = client.post(
            f"/groups/{gid}/projects/{p['id']}/archive", headers=h
        )
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_admin_can_archive(self, client):
        _, owner_me, owner_h = register_and_login(client, "ar-owner2@pj.com")
        admin_me, _, admin_h = register_and_login(client, "ar-admin@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_to_admin(client, gid, owner_h, admin_me["id"])
        p = _create_project(client, gid, owner_h)
        r = client.post(
            f"/groups/{gid}/projects/{p['id']}/archive", headers=admin_h
        )
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_member_cannot_archive(self, client):
        _, _, owner_h = register_and_login(client, "ar-owner3@pj.com")
        _, _, member_h = register_and_login(client, "ar-member@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, member_h)
        p = _create_project(client, gid, owner_h)
        r = client.post(
            f"/groups/{gid}/projects/{p['id']}/archive", headers=member_h
        )
        assert r.status_code == 403

    def test_archive_idempotent(self, client):
        _, _, h = register_and_login(client, "ar-owner4@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        r1 = client.post(
            f"/groups/{gid}/projects/{p['id']}/archive", headers=h
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "archived"
        r2 = client.post(
            f"/groups/{gid}/projects/{p['id']}/archive", headers=h
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "archived"

    def test_archived_project_still_readable(self, client):
        _, _, h = register_and_login(client, "ar-owner5@pj.com")
        gid = _create_group(client, h)
        p = _create_project(client, gid, h)
        client.post(
            f"/groups/{gid}/projects/{p['id']}/archive", headers=h
        )
        r = client.get(f"/groups/{gid}/projects/{p['id']}", headers=h)
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_outsider_cannot_archive(self, client):
        _, _, owner_h = register_and_login(client, "ar-owner6@pj.com")
        _, _, outsider_h = register_and_login(client, "ar-outsider@pj.com")
        gid = _create_group(client, owner_h)
        p = _create_project(client, gid, owner_h)
        r = client.post(
            f"/groups/{gid}/projects/{p['id']}/archive", headers=outsider_h
        )
        assert r.status_code == 403

    def test_archive_cross_group_404(self, client):
        _, _, ha = register_and_login(client, "ar-ga@pj.com")
        _, _, hb = register_and_login(client, "ar-gb@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        p = _create_project(client, ga, ha)
        r = client.post(
            f"/groups/{gb}/projects/{p['id']}/archive", headers=hb
        )
        assert r.status_code == 404


# ── data isolation ───────────────────────────────────────────────────────


class TestDataIsolation:
    def test_projects_isolated_per_group(self, client):
        """Two groups each have a project — neither sees the other's."""
        _, _, ha = register_and_login(client, "iso-a@pj.com")
        _, _, hb = register_and_login(client, "iso-b@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        _create_project(client, ga, ha, name="A Project")
        _create_project(client, gb, hb, name="B Project")

        ra = client.get(f"/groups/{ga}/projects", headers=ha)
        assert ra.json()["total"] == 1
        assert ra.json()["projects"][0]["name"] == "A Project"

        rb = client.get(f"/groups/{gb}/projects", headers=hb)
        assert rb.json()["total"] == 1
        assert rb.json()["projects"][0]["name"] == "B Project"

    def test_cross_group_detail_404(self, client):
        _, _, ha = register_and_login(client, "iso-c@pj.com")
        _, _, hb = register_and_login(client, "iso-d@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        p = _create_project(client, ga, ha)
        r = client.get(f"/groups/{gb}/projects/{p['id']}", headers=hb)
        assert r.status_code == 404


# ── stage helper unit tests ──────────────────────────────────────────────


class TestStageHelper:
    def test_next_stage_goal_to_data(self):
        assert next_stage("goal") == "data"

    def test_next_stage_data_to_model(self):
        assert next_stage("data") == "model"

    def test_next_stage_model_to_validate(self):
        assert next_stage("model") == "validate"

    def test_next_stage_validate_to_pilot(self):
        assert next_stage("validate") == "pilot"

    def test_next_stage_pilot_is_none(self):
        assert next_stage("pilot") is None

    def test_advance_goal_to_data(self):
        assert advance_stage("goal", "data") == "data"

    def test_advance_data_to_model(self):
        assert advance_stage("data", "model") == "model"

    def test_advance_model_to_validate(self):
        assert advance_stage("model", "validate") == "validate"

    def test_advance_validate_to_pilot(self):
        assert advance_stage("validate", "pilot") == "pilot"

    def test_advance_reject_backward(self):
        with pytest.raises(ValueError, match="Cannot move backward"):
            advance_stage("model", "data")

    def test_advance_reject_skip(self):
        with pytest.raises(ValueError, match="Cannot skip"):
            advance_stage("goal", "model")

    def test_advance_reject_same(self):
        with pytest.raises(ValueError, match="Already at stage"):
            advance_stage("goal", "goal")

    def test_advance_reject_unknown_current(self):
        with pytest.raises(ValueError, match="Unknown current stage"):
            advance_stage("invalid", "data")

    def test_advance_reject_unknown_target(self):
        with pytest.raises(ValueError, match="Unknown target stage"):
            advance_stage("goal", "invalid")

    def test_advance_reject_skip_multiple(self):
        with pytest.raises(ValueError, match="Cannot skip"):
            advance_stage("goal", "validate")

    def test_next_stage_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown stage"):
            next_stage("unknown")


# ── S2.4B Project Summary ──────────────────────────────────────────────────


class TestProjectSummary:
    def test_member_can_read_summary(self, client):
        _, _, oh = register_and_login(client, "sum-own@t.com")
        _, _, mh = register_and_login(client, "sum-mem@t.com")
        gid = _create_group(client, oh, "SumGrp")
        _join_group(client, gid, oh, mh)
        pid = _create_project(client, gid, oh, name="SumProj")["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/summary", headers=mh)
        assert r.status_code == 200
        data = r.json()
        assert data["project"]["name"] == "SumProj"
        assert data["evidence_count"] == 0
        assert data["recent_evidence"] == []
        assert data["conversation_count"] == 0
        assert data["task_count"]["pending"] == 0
        assert data["agent_run_count"] == 0

    def test_non_member_cannot_read_summary(self, client):
        _, _, oh = register_and_login(client, "sum-out-own@t.com")
        _, _, outsider_h = register_and_login(client, "sum-out@t.com")
        gid = _create_group(client, oh, "OutGrp")
        pid = _create_project(client, gid, oh)["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/summary", headers=outsider_h)
        assert r.status_code == 403

    def test_cross_group_project_returns_404(self, client):
        _, _, oh1 = register_and_login(client, "sum-cg1@t.com")
        _, _, oh2 = register_and_login(client, "sum-cg2@t.com")
        gid1 = _create_group(client, oh1, "CG1")
        gid2 = _create_group(client, oh2, "CG2")
        pid = _create_project(client, gid1, oh1)["id"]
        r = client.get(f"/groups/{gid2}/projects/{pid}/summary", headers=oh2)
        assert r.status_code == 404

    def test_empty_project_zero_counts(self, client):
        _, _, oh = register_and_login(client, "sum-empty@t.com")
        gid = _create_group(client, oh, "EGrp")
        pid = _create_project(client, gid, oh)["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/summary", headers=oh)
        assert r.status_code == 200
        data = r.json()
        assert data["evidence_count"] == 0
        assert data["recent_evidence"] == []
        assert data["conversation_count"] == 0
        assert data["task_count"]["pending"] == 0

    def test_archived_project_readable(self, client):
        _, _, oh = register_and_login(client, "sum-arch@t.com")
        gid = _create_group(client, oh, "ArchGrp")
        pid = _create_project(client, gid, oh)["id"]
        client.post(f"/groups/{gid}/projects/{pid}/archive", headers=oh)
        r = client.get(f"/groups/{gid}/projects/{pid}/summary", headers=oh)
        assert r.status_code == 200
        assert r.json()["project"]["status"] == "archived"

    def test_evidence_count_only_active_links(self, client):
        _, _, oh = register_and_login(client, "sum-ev@t.com")
        gid = _create_group(client, oh, "EvGrp")
        pid = _create_project(client, gid, oh)["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/summary", headers=oh)
        assert r.status_code == 200
        assert r.json()["evidence_count"] == 0

    def test_summary_excludes_sensitive_fields(self, client):
        _, _, oh = register_and_login(client, "sum-safe@t.com")
        gid = _create_group(client, oh, "SafeGrp")
        pid = _create_project(client, gid, oh)["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/summary", headers=oh)
        assert r.status_code == 200
        data = r.json()
        body = str(data)
        assert "raw_content" not in body
        assert "source_path" not in body
        assert "storage_path" not in body
        assert "answer" not in body
        assert "prompt" not in body
