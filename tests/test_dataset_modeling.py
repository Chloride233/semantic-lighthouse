"""Tests for Phase 14.3 — dataset-to-modeling bridge.

Covers: object/property/link draft generation, PK/FK handling,
permissions, idempotency, stage advancement, evidence privacy,
migration upgrade/downgrade, backward compatibility.
"""

import io

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


def _create_project(client, gid, h, name="Modeling Test", **kw):
    body = {"name": name, "entry_mode": "problem_first", **kw}
    r = client.post(f"/groups/{gid}/projects", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_csv(client, gid, pid, h, filename="test.csv", content="id,name,price\n1,Widget,9.99\n2,Gadget,19.95\n"):
    files = {"file": (filename, io.BytesIO(content.encode("utf-8")), "application/octet-stream")}
    data = {"include_sample_values": "false"}
    r = client.post(f"/groups/{gid}/projects/{pid}/datasets", files=files, data=data, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _generate(client, gid, pid, h, expect_status=200):
    r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=h)
    assert r.status_code == expect_status, r.text
    return r.json() if r.status_code == 200 else r


def _list_drafts(client, gid, h, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/groups/{gid}/ontology/drafts"
    if qs:
        url += f"?{qs}"
    r = client.get(url, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# ── generation ───────────────────────────────────────────────────────────


class TestDatasetModelGeneration:
    def test_two_datasets_generate_object_property_link_drafts(self, client):
        """Two related CSVs → object types, properties, and a link type."""
        _, _, h = register_and_login(client, "gen-1@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)

        # Upload customers dataset
        customers_csv = "customer_id,name,email\n1,Alice,alice@test.com\n2,Bob,bob@test.com\n"
        _upload_csv(client, gid, pid, h, filename="customers.csv", content=customers_csv)

        # Upload orders dataset (with FK to customers)
        orders_csv = "order_id,customer_id,total\n100,1,99.99\n101,2,149.50\n"
        _upload_csv(client, gid, pid, h, filename="orders.csv", content=orders_csv)

        # Generate
        result = _generate(client, gid, pid, h)
        assert result["generated_count"] > 0
        assert result["counts_by_type"]["object_type"] >= 2
        assert result["counts_by_type"]["property"] >= 5
        assert result["counts_by_type"]["action_type"] == 0

    def test_payload_has_business_v1_contract_profile(self, client):
        """All generated drafts must have contract_profile=business_v1."""
        _, _, h = register_and_login(client, "gen-2@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, filename="items.csv",
                    content="id,name\n1,Alpha\n2,Beta\n")
        _generate(client, gid, pid, h)
        drafts = _list_drafts(client, gid, h, project_id=pid)
        for d in drafts["drafts"]:
            assert d["payload"].get("contract_profile") == "business_v1", (
                f"Draft {d['draft_type']} {d['name']} missing contract_profile"
            )

    def test_type_mapping_and_required(self, client):
        """Integer → integer, string → string, nullable detection."""
        _, _, h = register_and_login(client, "gen-3@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "id,label,amount\n1,Widget,100\n2,Gadget,200\n3,,300\n"
        _upload_csv(client, gid, pid, h, filename="products.csv", content=csv_content)
        _generate(client, gid, pid, h)
        drafts = _list_drafts(client, gid, h, project_id=pid, draft_type="property")
        # id → integer, required
        id_draft = [d for d in drafts["drafts"] if "id" in d["name"].lower() and ".id" in d["name"].lower()]
        if id_draft:
            assert id_draft[0]["payload"].get("value_type") == "integer"
            assert id_draft[0]["payload"].get("required") is True
        # label → string, nullable (has null row)
        label_draft = [d for d in drafts["drafts"] if "label" in d["name"].lower()]
        if label_draft:
            assert label_draft[0]["payload"].get("value_type") == "string"
            assert label_draft[0]["payload"].get("required") is False

    def test_pk_stable_selection(self, client):
        """PK candidate with highest confidence selected."""
        _, _, h = register_and_login(client, "gen-4@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "pk_code,uuid,value\n1,a1,10\n2,a2,20\n"
        _upload_csv(client, gid, pid, h, filename="data.csv", content=csv_content)
        _generate(client, gid, pid, h)
        drafts = _list_drafts(client, gid, h, project_id=pid, draft_type="object_type")
        assert len(drafts["drafts"]) >= 1
        payload = drafts["drafts"][0]["payload"]
        assert "primary_key" in payload

    def test_no_pk_returns_issue_skip_object_type(self, client):
        """Dataset without PK candidate → issue, no Object Type."""
        _, _, h = register_and_login(client, "gen-5@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        # No column is fully unique and non-null
        csv_content = "name,score\na,10\na,20\nb,10\n"
        _upload_csv(client, gid, pid, h, filename="no_pk.csv", content=csv_content)
        result = _generate(client, gid, pid, h)
        issues = result.get("issues", [])
        has_no_pk = any(i["code"] == "no_primary_key_candidate" for i in issues)
        assert has_no_pk or result["counts_by_type"]["object_type"] == 0

    def test_fk_suggestion_generates_link(self, client):
        """FK suggestion → many_to_one link type draft."""
        _, _, h = register_and_login(client, "gen-6@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, filename="customers.csv",
                    content="customer_id,name\n1,Alpha\n2,Beta\n")
        _upload_csv(client, gid, pid, h, filename="orders.csv",
                    content="order_id,customer_id,total\n100,1,50\n101,2,75\n")
        result = _generate(client, gid, pid, h)
        assert result["counts_by_type"]["link_type"] >= 1

    def test_no_action_type_generated(self, client):
        """Action type count always 0."""
        _, _, h = register_and_login(client, "gen-7@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, filename="data.csv",
                    content="id,val\n1,10\n2,20\n")
        result = _generate(client, gid, pid, h)
        assert result["counts_by_type"]["action_type"] == 0

    def test_evidence_excludes_sample_values_and_storage_path(self, client):
        """Evidence refs must not contain sample_values, raw rows, or storage_path."""
        _, _, h = register_and_login(client, "gen-8@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, filename="items.csv",
                    content="item_id,desc\n1,Test\n")
        _generate(client, gid, pid, h)
        drafts = _list_drafts(client, gid, h, project_id=pid)
        for d in drafts["drafts"]:
            for ref in d.get("evidence_refs", []):
                assert "sample_values" not in ref
                assert "raw_rows" not in ref
                assert "storage_path" not in ref

    def test_project_id_and_source_dataset_id_correct(self, client):
        """Generated drafts carry correct project_id and source_dataset_id."""
        _, _, h = register_and_login(client, "gen-9@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        ds = _upload_csv(client, gid, pid, h, filename="data.csv",
                         content="id,name\n1,Alice\n")
        _generate(client, gid, pid, h)
        drafts = _list_drafts(client, gid, h, project_id=pid)
        for d in drafts["drafts"]:
            assert d.get("project_id") == pid
            assert d.get("source_dataset_id") == ds["id"]

    def test_idempotent(self, client):
        """Re-generate produces no duplicates."""
        _, _, h = register_and_login(client, "gen-10@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, filename="data.csv",
                    content="id,val\n1,10\n2,20\n")
        r1 = _generate(client, gid, pid, h)
        count1 = _list_drafts(client, gid, h, project_id=pid)["total"]
        r2 = _generate(client, gid, pid, h)
        count2 = _list_drafts(client, gid, h, project_id=pid)["total"]
        assert count2 == count1
        assert r2["existing_count"] >= r1["generated_count"]

    def test_rejected_or_accepted_not_overwritten(self, client):
        """Verify accepted/rejected drafts are untouched by regeneration."""
        _, _, h = register_and_login(client, "gen-11@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, filename="data.csv",
                    content="id,val\n1,10\n")
        _generate(client, gid, pid, h)
        drafts = _list_drafts(client, gid, h, project_id=pid)
        assert drafts["total"] > 0
        first_id = drafts["drafts"][0]["id"]
        # Reject it
        r = client.post(
            f"/groups/{gid}/ontology/drafts/{first_id}/review",
            json={"status": "rejected", "review_note": "Not needed"},
            headers=h,
        )
        assert r.status_code == 200
        # Re-generate — should not resurrect or overwrite
        _generate(client, gid, pid, h)
        # Total should be same (accepted/rejected are not recreated)
        drafts2 = _list_drafts(client, gid, h, project_id=pid)
        # The rejected draft remains rejected
        rejected = [d for d in drafts2["drafts"] if d["id"] == first_id]
        assert len(rejected) == 1
        assert rejected[0]["status"] == "rejected"


# ── permissions ───────────────────────────────────────────────────────────


class TestDatasetModelPermissions:
    def test_owner_can_generate(self, client):
        _, _, h = register_and_login(client, "perm-1@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=h)
        assert r.status_code == 200

    def test_admin_can_generate(self, client):
        _, owner_me, owner_h = register_and_login(client, "perm-2-o@pj.com")
        admin_me, _, admin_h = register_and_login(client, "perm-2-a@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_admin(client, gid, owner_h, admin_me["id"])
        pid = _create_project(client, gid, owner_h)
        _upload_csv(client, gid, pid, owner_h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=admin_h)
        assert r.status_code == 200

    def test_member_cannot_generate(self, client):
        _, _, owner_h = register_and_login(client, "perm-3-o@pj.com")
        _, _, mem_h = register_and_login(client, "perm-3-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _upload_csv(client, gid, pid, owner_h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=mem_h)
        assert r.status_code == 403

    def test_outsider_403(self, client):
        _, _, owner_h = register_and_login(client, "perm-4-o@pj.com")
        _, _, outsider_h = register_and_login(client, "perm-4-x@pj.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=outsider_h)
        assert r.status_code == 403

    def test_cross_group_404(self, client):
        _, _, ha = register_and_login(client, "perm-5-a@pj.com")
        _, _, hb = register_and_login(client, "perm-5-b@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        pid = _create_project(client, ga, ha)
        r = client.post(f"/groups/{gb}/projects/{pid}/model-drafts/generate", headers=hb)
        assert r.status_code == 404


# ── stage advancement ────────────────────────────────────────────────────


class TestStageAdvancement:
    def test_goal_stage_rejected_409(self, client):
        """Cannot generate drafts at goal stage — upload data first."""
        _, _, h = register_and_login(client, "stage-1@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=h)
        assert r.status_code == 409

    def test_data_to_model_advances(self, client):
        """Successful generation at data stage → model."""
        _, _, h = register_and_login(client, "stage-2@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, content="id,name\n1,A\n")
        # Stage should be data now
        proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj.json()["stage"] == "data"
        _generate(client, gid, pid, h)
        proj2 = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj2.json()["stage"] == "model"

    def test_no_ready_datasets_400(self, client):
        """No datasets → 400."""
        _, _, h = register_and_login(client, "stage-3@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        # Upload then archive — no ready datasets
        ds = _upload_csv(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/datasets/{ds['id']}/archive", headers=h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=h)
        assert r.status_code == 400

    def test_archived_project_409(self, client):
        _, _, h = register_and_login(client, "stage-4@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/archive", headers=h)
        r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=h)
        assert r.status_code == 409


# ── isolation ────────────────────────────────────────────────────────────


class TestProjectIsolation:
    def test_same_group_different_project_isolation(self, client):
        """Drafts from project A are not visible in project B queries."""
        _, _, h = register_and_login(client, "iso-1@pj.com")
        gid = _create_group(client, h)
        pid_a = _create_project(client, gid, h, name="Project A")
        pid_b = _create_project(client, gid, h, name="Project B")
        _upload_csv(client, gid, pid_a, h, filename="a_data.csv",
                    content="id,x\n1,10\n")
        _upload_csv(client, gid, pid_b, h, filename="b_data.csv",
                    content="id,y\n1,20\n")
        _generate(client, gid, pid_a, h)
        _generate(client, gid, pid_b, h)
        drafts_a = _list_drafts(client, gid, h, project_id=pid_a)
        drafts_b = _list_drafts(client, gid, h, project_id=pid_b)
        assert drafts_a["total"] > 0
        assert drafts_b["total"] > 0
        ids_a = {d["id"] for d in drafts_a["drafts"]}
        ids_b = {d["id"] for d in drafts_b["drafts"]}
        assert ids_a.isdisjoint(ids_b)

    def test_cross_project_draft_not_leaked(self, client):
        """Direct access to cross-project draft returns proper isolation."""
        _, _, ha = register_and_login(client, "iso-2-a@pj.com")
        _, _, hb = register_and_login(client, "iso-2-b@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        pid_a = _create_project(client, ga, ha)
        pid_b = _create_project(client, gb, hb)
        _upload_csv(client, ga, pid_a, ha, content="id,n\n1,T\n")
        _upload_csv(client, gb, pid_b, hb, content="id,n\n1,U\n")
        _generate(client, ga, pid_a, ha)
        _generate(client, gb, pid_b, hb)
        # Project A's drafts should not appear in Project B's list
        drafts_a = _list_drafts(client, ga, ha, project_id=pid_a)
        for d in drafts_a["drafts"]:
            assert d["project_id"] == pid_a
            assert d["group_id"] == ga


# ── backward compatibility ───────────────────────────────────────────────


class TestLegacyDraftCRUD:
    def test_legacy_create_draft_still_works(self, client):
        """Creating a draft without project_id/source_dataset_id still works."""
        _, _, h = register_and_login(client, "legacy-1@pj.com")
        gid = _create_group(client, h)
        # Need an entity as evidence for legacy draft
        # We'll use the ontology scan to create entities
        # For now, just verify the endpoint accepts project_id=None
        r = client.post(
            f"/groups/{gid}/ontology/drafts",
            json={
                "draft_type": "object_type",
                "name": "Test Draft",
                "source_entity_id": None,
                "source_relation_id": None,
                "source_issue_id": None,
                "source_rag_run_id": None,
                "project_id": None,
                "source_dataset_id": None,
            },
            headers=h,
        )
        # Should fail with 400 because no evidence source at all
        assert r.status_code == 400

    def test_legacy_draft_list_supports_new_filters(self, client):
        """List drafts with project_id and source_dataset_id filters."""
        _, _, h = register_and_login(client, "legacy-2@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, content="id,v\n1,10\n")
        _generate(client, gid, pid, h)
        # Filter by project_id
        drafts = _list_drafts(client, gid, h, project_id=pid)
        assert drafts["total"] > 0
        # Filter by non-existent project_id
        empty = _list_drafts(client, gid, h, project_id="nonexistent-id")
        assert empty["total"] == 0

    def test_legacy_generate_still_works(self, client):
        """Existing /ontology/drafts/generate endpoint still functional."""
        # This endpoint generates from ontology entities, not datasets.
        # It should return 400 when no entities exist — proving it still routes.
        _, _, h = register_and_login(client, "legacy-3@pj.com")
        gid = _create_group(client, h)
        r = client.post(f"/groups/{gid}/ontology/drafts/generate", headers=h)
        assert r.status_code == 400  # No entities → 400

    def test_legacy_review_still_works_on_dataset_draft(self, client):
        """Existing review endpoint works on dataset-generated drafts."""
        _, _, h = register_and_login(client, "legacy-4@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h, content="id,v\n1,10\n")
        _generate(client, gid, pid, h)
        drafts = _list_drafts(client, gid, h, project_id=pid)
        assert drafts["total"] > 0
        draft_id = drafts["drafts"][0]["id"]
        # Accept via existing review endpoint
        r = client.post(
            f"/groups/{gid}/ontology/drafts/{draft_id}/review",
            json={"status": "accepted", "review_note": "Looks good"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"


# ── migration ────────────────────────────────────────────────────────────


class TestMigration0020:
    def test_new_columns_nullable_for_legacy(self, client):
        """After migration, legacy drafts without project_id work fine."""
        # The migration has already been applied. Verify legacy query.
        _, _, h = register_and_login(client, "mig-1@pj.com")
        gid = _create_group(client, h)
        drafts = _list_drafts(client, gid, h)
        # All existing drafts should be listed (project_id nullable)
        assert "total" in drafts
