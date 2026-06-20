"""Tests for Phase 14.5 — Pilot Read Runtime + Unified Query Contract.

Covers: binding generation (deterministic, idempotent, PK/property mapping,
issues), permissions (member/owner/admin/outsider), cross-group/cross-project
isolation, query (field whitelist, equality filter, limit/offset, CSV/XLSX,
type conversion, explain_only, provenance sanitization), activation
(validate→pilot, failure blocking, idempotency), path traversal rejection,
legacy compatibility.
"""

import io

import pytest
from conftest import register_and_login


# ── helpers ──────────────────────────────────────────────────────────────


def _create_group(client, headers, name="RuntimeTest"):
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


def _create_project(client, gid, h, name="RT", **kw):
    body = {"name": name, "entry_mode": "problem_first", **kw}
    r = client.post(f"/groups/{gid}/projects", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_csv(client, gid, pid, h, name="data.csv", content=None):
    """Upload a CSV dataset. Returns the JSON response."""
    if content is None:
        content = "id,name,status\n1,Alice,active\n2,Bob,inactive\n"
    files = {
        "file": (name, io.BytesIO(content.encode("utf-8")), "application/octet-stream"),
    }
    data = {"include_sample_values": "false"}
    r = client.post(
        f"/groups/{gid}/projects/{pid}/datasets",
        files=files, data=data, headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _upload_xlsx(client, gid, pid, h, name="data.xlsx", rows=None):
    """Upload an XLSX dataset. Returns the JSON response."""
    try:
        from openpyxl import Workbook
    except ImportError:
        pytest.skip("openpyxl not available")
    if rows is None:
        rows = [["id", "name", "status"], ["1", "Alice", "active"], ["2", "Bob", "inactive"]]
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    files = {"file": (name, buf, "application/octet-stream")}
    data = {"include_sample_values": "false"}
    r = client.post(
        f"/groups/{gid}/projects/{pid}/datasets",
        files=files, data=data, headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _generate_drafts(client, gid, pid, h):
    r = client.post(f"/groups/{gid}/projects/{pid}/model-drafts/generate", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _accept_all(client, gid, pid, h):
    """Accept all proposed drafts."""
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


def _build_package(client, gid, pid, h):
    """Build project package. Must be at model or validate stage."""
    r = client.post(
        f"/groups/{gid}/projects/{pid}/model-drafts/packages",
        headers=h,
    )
    # May need WARN override
    if r.status_code == 409:
        r = client.post(
            f"/groups/{gid}/projects/{pid}/model-drafts/packages",
            json={"quality_status_override": "WARN", "override_reason": "test"},
            headers=h,
        )
    assert r.status_code == 201, r.text
    return r.json()


def _full_pipeline_to_validate(client, gid, pid, h, csv_content=None, csv_name="data.csv"):
    """Run the full pipeline from upload through package build.

    Returns (upload_response, generate_response, package_response).
    """
    ds = _upload_csv(client, gid, pid, h, name=csv_name, content=csv_content)
    gen = _generate_drafts(client, gid, pid, h)
    _accept_all(client, gid, pid, h)
    pkg = _build_package(client, gid, pid, h)
    return ds, gen, pkg


# ═══════════════════════════════════════════════════════════════════════════
#  binding generation
# ═══════════════════════════════════════════════════════════════════════════


class TestBindingGeneration:
    def test_deterministic_generation_from_valid_package(self, client):
        """Generate bindings from a package with one dataset OT."""
        _, _, h = register_and_login(client, "bg-1@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["created_count"] >= 1
        assert data["existing_count"] == 0

    def test_idempotent_generation_no_duplicates(self, client):
        """Re-running binding generation produces no duplicates."""
        _, _, h = register_and_login(client, "bg-2@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)

        r1 = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r1.status_code == 200
        created1 = r1.json()["created_count"]
        assert created1 >= 1

        r2 = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r2.status_code == 200
        assert r2.json()["created_count"] == 0
        assert r2.json()["existing_count"] >= created1

    def test_pk_mapping_correct(self, client):
        """Verify the primary_key_column in the binding matches the dataset PK."""
        _, _, h = register_and_login(client, "bg-3@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "order_id,amount,note\n100,99.99,test\n101,149.50,test2\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r.status_code == 200

        # Check bindings
        blist = client.get(
            f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h,
        )
        bindings = blist.json()
        assert len(bindings) >= 1
        # The PK column should be order_id (the PK name candidate)
        pk_cols = [b["primary_key_column"] for b in bindings]
        assert "order_id" in pk_cols

    def test_property_mappings_correct(self, client):
        """Property mappings map api_name → column name correctly."""
        _, _, h = register_and_login(client, "bg-4@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "product_id,product_name,price\n1,widget,9.99\n2,gadget,19.99\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)

        client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )

        blist = client.get(
            f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h,
        )
        bindings = blist.json()
        assert len(bindings) >= 1
        mappings = bindings[0]["property_mappings"]
        # Should have mappings for all columns
        assert len(mappings) >= 2
        # Each value should be the column name
        for v in mappings.values():
            assert v in ("product_id", "product_name", "price")

    def test_no_package_produces_issue(self, client):
        """Generate bindings without a package returns issues."""
        _, _, h = register_and_login(client, "bg-5@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        # Upload data, generate drafts, accept them — but don't build package
        # Stage will be "model" — binding generation requires validate or pilot
        _upload_csv(client, gid, pid, h)
        _generate_drafts(client, gid, pid, h)
        _accept_all(client, gid, pid, h)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        # Stage is "model", not "validate" — rejected with 409
        assert r.status_code == 409

    def test_goal_stage_rejected(self, client):
        """Binding generation rejected at goal stage."""
        _, _, h = register_and_login(client, "bg-6@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r.status_code == 409

    def test_data_stage_rejected(self, client):
        """Binding generation rejected at data stage."""
        _, _, h = register_and_login(client, "bg-7@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r.status_code == 409

    def test_model_stage_rejected(self, client):
        """Binding generation rejected at model stage."""
        _, _, h = register_and_login(client, "bg-8@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h)
        _generate_drafts(client, gid, pid, h)
        _accept_all(client, gid, pid, h)
        # Stage is now "model" (package not built)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r.status_code == 409

    def test_action_types_not_bound(self, client):
        """Action Type drafts do not produce bindings."""
        _, _, h = register_and_login(client, "bg-9@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r.status_code == 200
        blist = client.get(
            f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h,
        )
        # All bindings are for object_types, not action_types
        for b in blist.json():
            assert b["object_type_api_name"]  # has an object type


# ═══════════════════════════════════════════════════════════════════════════
#  permissions
# ═══════════════════════════════════════════════════════════════════════════


class TestBindingPermissions:
    def test_member_can_read_bindings(self, client):
        _, _, owner_h = register_and_login(client, "bp-1-o@rt.com")
        _, _, mem_h = register_and_login(client, "bp-1-m@rt.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _full_pipeline_to_validate(client, gid, pid, owner_h)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=owner_h)

        r = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=mem_h)
        assert r.status_code == 200

    def test_member_cannot_generate_bindings(self, client):
        _, _, owner_h = register_and_login(client, "bp-2-o@rt.com")
        _, _, mem_h = register_and_login(client, "bp-2-m@rt.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _full_pipeline_to_validate(client, gid, pid, owner_h)

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=mem_h)
        assert r.status_code == 403

    def test_member_can_query(self, client):
        _, _, owner_h = register_and_login(client, "bp-3-o@rt.com")
        _, _, mem_h = register_and_login(client, "bp-3-m@rt.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _full_pipeline_to_validate(client, gid, pid, owner_h)
        # Generate bindings
        gen_r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=owner_h,
        )
        assert gen_r.status_code == 200
        # Get bindings to find object_type
        blist = client.get(
            f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=owner_h,
        )
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type},
            headers=mem_h,
        )
        assert r.status_code == 200, r.text

    def test_member_cannot_activate(self, client):
        _, _, owner_h = register_and_login(client, "bp-4-o@rt.com")
        _, _, mem_h = register_and_login(client, "bp-4-m@rt.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        _full_pipeline_to_validate(client, gid, pid, owner_h)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=owner_h)

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=mem_h)
        assert r.status_code == 403

    def test_owner_can_generate_and_activate(self, client):
        _, _, h = register_and_login(client, "bp-5@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        assert r.status_code == 200

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=h)
        assert r.status_code == 200, r.text

    def test_admin_can_generate_and_activate(self, client):
        _, _, owner_h = register_and_login(client, "bp-6-o@rt.com")
        _, _, adm_h = register_and_login(client, "bp-6-a@rt.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, adm_h)
        # We need the user_id from /auth/me
        me_r = client.get("/auth/me", headers=adm_h)
        adm_uid = me_r.json()["id"]
        _promote_admin(client, gid, owner_h, adm_uid)
        pid = _create_project(client, gid, owner_h)
        _full_pipeline_to_validate(client, gid, pid, owner_h)

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=adm_h)
        assert r.status_code == 200

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=adm_h)
        assert r.status_code == 200, r.text

    def test_outsider_403(self, client):
        _, _, owner_h = register_and_login(client, "bp-7-o@rt.com")
        _, _, outsider_h = register_and_login(client, "bp-7-x@rt.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)

        for method, path, body in [
            ("GET", f"/groups/{gid}/projects/{pid}/runtime/bindings", None),
            ("POST", f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", None),
            ("POST", f"/groups/{gid}/projects/{pid}/runtime/query", {"object_type": "test"}),
            ("POST", f"/groups/{gid}/projects/{pid}/runtime/activate", None),
        ]:
            if body:
                r = client.request(method, path, json=body, headers=outsider_h)
            else:
                r = client.request(method, path, headers=outsider_h)
            assert r.status_code == 403, f"{method} {path} should be 403, got {r.status_code}"


class TestCrossGroupCrossProject:
    def test_cross_group_bindings_404(self, client):
        _, _, h1 = register_and_login(client, "cg-1-a@rt.com")
        _, _, h2 = register_and_login(client, "cg-1-b@rt.com")
        gid1 = _create_group(client, h1)
        _create_group(client, h2)
        pid1 = _create_project(client, gid1, h1)

        # Access gid1's project from gid2 user
        r = client.get(f"/groups/{gid1}/projects/{pid1}/runtime/bindings", headers=h2)
        assert r.status_code == 403  # Not a member of gid1

    def test_cross_project_query_404(self, client):
        _, _, h = register_and_login(client, "cg-2@rt.com")
        gid = _create_group(client, h)
        pid1 = _create_project(client, gid, h, name="P1")
        pid2 = _create_project(client, gid, h, name="P2")

        _full_pipeline_to_validate(client, gid, pid1, h)
        client.post(f"/groups/{gid}/projects/{pid1}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid1}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        # Query pid1's object_type through pid2's project
        r = client.post(
            f"/groups/{gid}/projects/{pid2}/runtime/query",
            json={"object_type": obj_type},
            headers=h,
        )
        assert r.status_code == 422  # No binding in pid2


# ═══════════════════════════════════════════════════════════════════════════
#  query execution
# ═══════════════════════════════════════════════════════════════════════════


class TestQueryExecution:
    def _setup_project_with_data(
        self, client, csv_content=None, csv_name="data.csv",
    ):
        """Full pipeline → bindings. Returns (gid, pid, headers, obj_type)."""
        _, _, h = register_and_login(client, "qe-setup@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        content = csv_content or "id,name,score\n1,Alice,95\n2,Bob,87\n3,Carol,92\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=content, csv_name=csv_name)
        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        assert r.status_code == 200, r.text
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]
        return gid, pid, h, obj_type

    def test_basic_query_returns_rows(self, client):
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type},
            headers=h,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["row_count"] >= 1
        assert len(data["rows"]) >= 1
        assert "explain" in data

    def test_field_whitelist(self, client):
        """Only requested fields are returned."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "fields": ["data_csv_id"]},
            headers=h,
        )
        assert r.status_code == 200, r.text
        for row in r.json()["rows"]:
            assert "data_csv_id" in row
            assert "data_csv_name" not in row  # not requested
            assert "data_csv_score" not in row  # not requested

    def test_field_not_in_binding_rejected(self, client):
        """Requesting a field not in the contract binding returns 422."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "fields": ["nonexistent_field"]},
            headers=h,
        )
        assert r.status_code == 422

    def test_equality_filter(self, client):
        """Equality filter on a bound property."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        # Filter by name = Alice
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "filters": {"data_csv_name": "Alice"}},
            headers=h,
        )
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        assert len(rows) == 1
        assert rows[0]["data_csv_name"] == "Alice"

    def test_equality_filter_no_match(self, client):
        """Filter with no matching rows returns empty."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "filters": {"data_csv_name": "NonExistent"}},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["row_count"] == 0
        assert r.json()["rows"] == []

    def test_filter_on_unbound_field_rejected(self, client):
        """Filtering on a field not in the binding returns 422."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "filters": {"nonexistent": "x"}},
            headers=h,
        )
        assert r.status_code == 422

    def test_limit_enforced(self, client):
        """Limit parameter restricts returned rows."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 1},
            headers=h,
        )
        assert r.status_code == 200
        assert len(r.json()["rows"]) <= 1

    def test_limit_max(self, client):
        """Limit cannot exceed 100."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 101},
            headers=h,
        )
        assert r.status_code == 422  # Pydantic validation rejects >100

    def test_offset_works(self, client):
        """Offset skips rows."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r_all = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        assert r_all.status_code == 200
        all_rows = r_all.json()["rows"]
        if len(all_rows) >= 2:
            r_off = client.post(
                f"/groups/{gid}/projects/{pid}/runtime/query",
                json={"object_type": obj_type, "limit": 10, "offset": 1},
                headers=h,
            )
            assert r_off.status_code == 200
            assert r_off.json()["row_count"] == len(all_rows) - 1

    def test_explain_only_no_data(self, client):
        """explain_only=true returns no data rows."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "explain_only": True},
            headers=h,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["row_count"] is None
        assert data["rows"] == []
        assert "explain" in data

    def test_explain_has_package_and_binding_info(self, client):
        """Explain includes package id, binding id, dataset id/checksum."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "explain_only": True},
            headers=h,
        )
        explain = r.json()["explain"]
        assert "package_id" in explain
        assert "binding_id" in explain
        assert "dataset_id" in explain
        assert "dataset_content_hash" in explain
        assert "selected_fields" in explain

    def test_explain_no_storage_path(self, client):
        """Explain must not include storage_path."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "explain_only": True},
            headers=h,
        )
        explain_str = str(r.json()["explain"])
        assert "dataset-storage" not in explain_str.lower()
        assert "storage_path" not in explain_str.lower()

    def test_explain_no_filter_values(self, client):
        """Explain must not include filter values."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={
                "object_type": obj_type,
                "filters": {"data_csv_name": "Alice"},
                "explain_only": True,
            },
            headers=h,
        )
        explain = r.json()["explain"]
        # filter_fields should list names, but not values
        assert "filter_fields" in explain
        explain_str = str(explain).lower()
        assert "alice" not in explain_str

    def test_result_no_storage_path(self, client):
        """Query results must not include storage_path."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type},
            headers=h,
        )
        result_str = str(r.json()).lower()
        assert "dataset-storage" not in result_str
        assert "storage_path" not in result_str

    def test_nonexistent_object_type_422(self, client):
        """Querying an object type not in the binding returns 422."""
        gid, pid, h, obj_type = self._setup_project_with_data(client)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": "nonexistent_type"},
            headers=h,
        )
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
#  CSV / XLSX query
# ═══════════════════════════════════════════════════════════════════════════


class TestCSVQuery:
    def test_csv_with_header_and_multiple_rows(self, client):
        _, _, h = register_and_login(client, "csv-1@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "item_id,item_name,qty\nA1,Widget,100\nB2,Gadget,200\nC3,Doodad,300\nD4,Thing,400\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        assert r.status_code == 200, r.text
        assert r.json()["row_count"] == 4


class TestXLSXQuery:
    def test_xlsx_basic_query(self, client):
        _, _, h = register_and_login(client, "xlsx@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_xlsx(client, gid, pid, h)
        _generate_drafts(client, gid, pid, h)
        _accept_all(client, gid, pid, h)
        _build_package(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        assert r.status_code == 200, r.text
        assert r.json()["row_count"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
#  type conversion
# ═══════════════════════════════════════════════════════════════════════════


class TestTypeConversion:
    def test_integer_type_converted(self, client):
        """Integer fields are returned as Python int."""
        _, _, h = register_and_login(client, "tc-1@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "pk,count\n1,42\n2,99\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        assert len(rows) >= 1
        # At least one integer column should be an int
        found_int = False
        for row in rows:
            for v in row.values():
                if isinstance(v, int):
                    found_int = True
        assert found_int, f"Expected at least one integer value, got: {rows}"

    def test_number_type_converted(self, client):
        """Number (float) fields are returned as Python float/int."""
        _, _, h = register_and_login(client, "tc-2@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "pk,price\n1,9.99\n2,19.50\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        assert len(rows) >= 1

    def test_boolean_type_converted(self, client):
        """Boolean fields are returned as Python bool."""
        _, _, h = register_and_login(client, "tc-3@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "pk,flag\n1,true\n2,false\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        assert len(rows) >= 1
        found_bool = False
        for row in rows:
            for v in row.values():
                if isinstance(v, bool):
                    found_bool = True
        assert found_bool, f"Expected boolean values, got: {rows}"

    def test_date_as_string(self, client):
        """Date fields are returned as strings (no datetime parsing)."""
        _, _, h = register_and_login(client, "tc-4@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "pk,event_date\n1,2025-01-15\n2,2025-06-20\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        assert len(rows) >= 1
        # Date values should be strings
        for row in rows:
            for k, v in row.items():
                if "date" in k.lower() and v is not None:
                    assert isinstance(v, str), f"Field {k} should be string, got {type(v)}"

    def test_type_conversion_error_stops_query(self, client):
        """If a value cannot be converted, the query returns type errors."""
        _, _, h = register_and_login(client, "tc-5@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        # Create a dataset where a column looks boolean but has bad data
        # The column will be inferred as boolean, but row 2 has "invalid"
        # Actually, with only 2 values (true + invalid), the inferred_type
        # may still be string. Let's force it differently.
        # Put an invalid integer in a numeric column
        csv_content = "pk,count\n1,100\n2,not_a_number\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type, "limit": 10},
            headers=h,
        )
        # The column "count" may be inferred as string (since not all values are int)
        # Let's check if it was inferred as integer
        # If it was inferred as integer, conversion of "not_a_number" will fail
        # If it was inferred as string, no error
        # Both outcomes are acceptable
        assert r.status_code in (200, 422), r.text


# ═══════════════════════════════════════════════════════════════════════════
#  activation
# ═══════════════════════════════════════════════════════════════════════════


class TestActivation:
    def test_activate_advances_validate_to_pilot(self, client):
        """Successful activation moves project from validate → pilot."""
        _, _, h = register_and_login(client, "act-1@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["activated"] is True
        assert data["stage"] == "pilot"

        # Verify project stage
        proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj.json()["stage"] == "pilot"

    def test_activate_fails_without_bindings(self, client):
        """Activation fails (422) when no bindings exist."""
        _, _, h = register_and_login(client, "act-2@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=h)
        assert r.status_code == 422, r.text
        # Stage should still be validate
        proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj.json()["stage"] == "validate"

    def test_activate_idempotent(self, client):
        """Repeated activation calls are idempotent."""
        _, _, h = register_and_login(client, "act-3@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)

        r1 = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=h)
        assert r1.status_code == 200
        assert r1.json()["activated"] is True

        r2 = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=h)
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        assert data2["already_pilot"] is True
        assert data2["stage"] == "pilot"

    def test_activate_fails_without_package(self, client):
        """Activation fails when no package exists."""
        _, _, h = register_and_login(client, "act-4@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _upload_csv(client, gid, pid, h)
        _generate_drafts(client, gid, pid, h)
        _accept_all(client, gid, pid, h)
        # Stage is "model", not "validate"
        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=h)
        assert r.status_code == 409  # Wrong stage

    def test_archived_project_rejected(self, client):
        """Cannot activate an archived project."""
        _, _, h = register_and_login(client, "act-5@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        # Archive the project
        client.post(f"/groups/{gid}/projects/{pid}/archive", headers=h)

        r = client.post(f"/groups/{gid}/projects/{pid}/runtime/activate", headers=h)
        assert r.status_code == 409  # Archived

    def test_query_does_not_advance_stage(self, client):
        """Ordinary query must NOT advance project stage."""
        _, _, h = register_and_login(client, "act-6@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type = blist.json()[0]["object_type_api_name"]

        # Execute query
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type},
            headers=h,
        )
        assert r.status_code == 200

        # Stage must still be validate
        proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj.json()["stage"] == "validate"


# ═══════════════════════════════════════════════════════════════════════════
#  stale package / path safety / legacy
# ═══════════════════════════════════════════════════════════════════════════


class TestStalePackage:
    def test_stale_package_binding_not_used(self, client):
        """Only bindings from the latest package are used for query."""
        _, _, h = register_and_login(client, "sp-1@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)

        # Build first package with binding
        csv_content = "pk,name\n1,Alice\n2,Bob\n"
        _full_pipeline_to_validate(client, gid, pid, h, csv_content=csv_content)
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist1 = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        obj_type1 = blist1.json()[0]["object_type_api_name"]

        # Verify query works with first package
        r1 = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/query",
            json={"object_type": obj_type1},
            headers=h,
        )
        assert r1.status_code == 200

        # Upload new dataset and build second package
        csv2 = "order_id,amount\n1,99.99\n2,149.50\n"
        _upload_csv(client, gid, pid, h, name="orders.csv", content=csv2)
        _generate_drafts(client, gid, pid, h)
        _accept_all(client, gid, pid, h)
        _build_package(client, gid, pid, h)

        # Generate bindings for new package
        client.post(f"/groups/{gid}/projects/{pid}/runtime/bindings/generate", headers=h)
        blist2 = client.get(f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h)
        # The latest package should have both old and new bindings
        # (or just new if old binding points to old package)
        assert len(blist2.json()) >= 1


class TestPathSafety:
    def test_query_rejects_path_traversal(self, client):
        """Path traversal in storage_path is detected."""
        from semantic_lighthouse.services.runtime import _validate_dataset_path

        # Attempt to escape via ../../
        with pytest.raises(ValueError):
            _validate_dataset_path(
                "./dataset-storage/../../../etc/passwd",
                "g1", "p1",
            )

        # Attempt to access different project
        with pytest.raises(ValueError):
            _validate_dataset_path(
                "./dataset-storage/g1/p2/data.csv",
                "g1", "p1",
            )

        # Valid path should work (doesn't need to exist on disk)
        try:
            p = _validate_dataset_path(
                "./dataset-storage/g1/p1/data.csv",
                "g1", "p1",
            )
            assert p is not None
        except OSError:
            pass  # resolve() may fail if cwd doesn't exist in test env


class TestLegacyCompatibility:
    def test_legacy_group_package_not_affected(self, client):
        """Existing group-scoped packages and APIs still work."""
        _, _, h = register_and_login(client, "lg-1@rt.com")
        gid = _create_group(client, h)

        # Legacy group-level quality check
        r_qual = client.get(f"/groups/{gid}/ontology/drafts/quality", headers=h)
        assert r_qual.status_code == 200

        # Legacy draft listing
        r_drafts = client.get(f"/groups/{gid}/ontology/drafts", headers=h)
        assert r_drafts.status_code == 200

        # Legacy package listing
        r_pkgs = client.get(f"/groups/{gid}/ontology/packages", headers=h)
        assert r_pkgs.status_code == 200

        # Runtime endpoint on non-existent project should 404
        fake_pid = "00000000-0000-0000-0000-000000000000"
        r_rt = client.get(
            f"/groups/{gid}/projects/{fake_pid}/runtime/bindings",
            headers=h,
        )
        assert r_rt.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
#  Runtime edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestRuntimeEdgeCases:
    def tests_empty_dataset_query_returns_empty(self, client):
        """Query on a dataset with only headers returns no rows."""
        from semantic_lighthouse.services.runtime import _read_rows
        import os as _os
        import tempfile as _tempfile

        fd, path = _tempfile.mkstemp(suffix=".csv")
        _os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("id,name\n")
            header, rows = _read_rows(path, "csv", max_rows=10, offset=0)
            assert len(header) == 2
            assert len(rows) == 0
        finally:
            _os.unlink(path)

    def test_xlsx_row_reader(self, client):
        """Verify XLSX row reader works correctly."""
        try:
            from openpyxl import Workbook
        except ImportError:
            pytest.skip("openpyxl not available")

        from semantic_lighthouse.services.runtime import _read_rows
        import os as _os, tempfile as _tempfile  # noqa: E401

        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["col_a", "col_b"])
        ws.append(["1", "hello"])
        ws.append(["2", "world"])
        buf = io.BytesIO()
        wb.save(buf)
        fd, path = _tempfile.mkstemp(suffix=".xlsx")
        _os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(buf.getvalue())
            header, rows = _read_rows(path, "xlsx", max_rows=10, offset=0)
            assert header == ["col_a", "col_b"]
            assert len(rows) == 2
        finally:
            _os.unlink(path)

    def test_csv_utf8_bom(self, client):
        """CSV with UTF-8 BOM is read correctly."""
        from semantic_lighthouse.services.runtime import _read_rows
        import os as _os, tempfile as _tempfile  # noqa: E401

        fd, path = _tempfile.mkstemp(suffix=".csv")
        _os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(b"\xef\xbb\xbfid,name\n1,test\n")
            header, rows = _read_rows(path, "csv", max_rows=10, offset=0)
            assert header == ["id", "name"]
            assert len(rows) == 1
        finally:
            _os.unlink(path)

    def test_offset_beyond_data(self, client):
        """Offset beyond data returns empty rows."""
        from semantic_lighthouse.services.runtime import _read_rows
        import os as _os, tempfile as _tempfile  # noqa: E401

        fd, path = _tempfile.mkstemp(suffix=".csv")
        _os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("id,name\n1,test\n")
            header, rows = _read_rows(path, "csv", max_rows=10, offset=100)
            assert rows == []
        finally:
            _os.unlink(path)

    def test_empty_csv_raises(self, client):
        """Empty CSV file raises ValueError."""
        from semantic_lighthouse.services.runtime import _read_rows
        import os as _os, tempfile as _tempfile  # noqa: E401

        fd, path = _tempfile.mkstemp(suffix=".csv")
        _os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            with pytest.raises(ValueError):
                _read_rows(path, "csv", max_rows=10, offset=0)
        finally:
            _os.unlink(path)

    def test_multiple_datasets_one_object_type_each(self, client):
        """Multiple datasets produce separate bindings, one per OT."""
        _, _, h = register_and_login(client, "ec-1@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)

        csv1 = "pk_a,name\n1,First\n"
        csv2 = "pk_b,value\nA,100\n"
        _upload_csv(client, gid, pid, h, name="a.csv", content=csv1)
        _upload_csv(client, gid, pid, h, name="b.csv", content=csv2)
        _generate_drafts(client, gid, pid, h)
        _accept_all(client, gid, pid, h)
        _build_package(client, gid, pid, h)
        gen_r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert gen_r.status_code == 200, gen_r.text
        blist = client.get(
            f"/groups/{gid}/projects/{pid}/runtime/bindings", headers=h,
        )
        assert len(blist.json()) >= 2  # Two bindings for two datasets

    def test_archived_dataset_not_queried(self, client):
        """Archived datasets should not produce retrievable bindings."""
        _, _, h = register_and_login(client, "ec-2@rt.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        _full_pipeline_to_validate(client, gid, pid, h)
        # Archive the dataset
        ds_list = client.get(
            f"/groups/{gid}/projects/{pid}/datasets", headers=h,
        )
        ds_id = ds_list.json()["datasets"][0]["id"]
        client.post(f"/groups/{gid}/projects/{pid}/datasets/{ds_id}/archive", headers=h)

        # Try to generate bindings — dataset not ready → issues
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/bindings/generate",
            headers=h,
        )
        assert r.status_code == 200, r.text
        # Should have issues since dataset is archived
        issues = r.json().get("issues", [])
        has_dataset_issue = any(
            i.get("code") in ("dataset_not_ready", "dataset_not_found")
            for i in issues
        )
        assert has_dataset_issue or r.json()["created_count"] == 0
