"""Tests for Phase 14.2 — dataset asset upload and profiling.

Covers: CSV/XLSX profiling, PK/FK detection, PII masking,
permissions, dedup, stage advancement, error handling.
"""

import io
import os
from pathlib import Path

import pytest

from conftest import register_and_login
from semantic_lighthouse.services.dataset_profiling import (
    ColumnProfile,
    _mask_pii,
    _infer_type,
    compute_content_hash,
    profile_csv,
    profile_xlsx,
    suggest_foreign_keys,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _text_to_csv(content: str, filename: str = "test.csv") -> io.BytesIO:
    """Encode a string as UTF-8 CSV bytes for upload."""
    return io.BytesIO(content.encode("utf-8"))


def _xlsx_bytes() -> io.BytesIO:
    """Create a minimal XLSX in memory."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["id", "name", "price"])
    ws.append([1, "Widget", 9.99])
    ws.append([2, "Gadget", 19.95])
    ws.append([3, "Doohickey", 4.50])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _xlsx_bytes_multi_sheet() -> io.BytesIO:
    """Create XLSX with multiple sheets, first hidden."""
    from openpyxl import Workbook

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Hidden"
    ws1.sheet_state = "hidden"
    ws1.append(["a", "b"])
    ws1.append([1, 2])

    ws2 = wb.create_sheet("Visible")
    ws2.append(["id", "value"])
    ws2.append([10, 100])
    ws2.append([20, 200])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── unit: PII masking ────────────────────────────────────────────────────


class TestPIIMasking:
    def test_email_masked(self):
        assert _mask_pii("test@example.com") == "te***@example.com"

    def test_phone_masked(self):
        assert _mask_pii("13812345678") == "138****5678"

    def test_id_card_masked(self):
        assert _mask_pii("110101199001011234") == "110***********34"

    def test_non_pii_preserved(self):
        assert _mask_pii("Widget") == "Widget"
        assert _mask_pii("123") == "123"


# ── unit: type inference ─────────────────────────────────────────────────


class TestTypeInference:
    def test_integer(self):
        assert _infer_type(["1", "2", "-3", "0"]) == "integer"

    def test_number(self):
        assert _infer_type(["1.5", "2.0", "-3.14", "1e10"]) == "number"

    def test_boolean(self):
        assert _infer_type(["true", "false", "TRUE", "0", "1"]) == "boolean"

    def test_date(self):
        assert _infer_type(["2024-01-01", "2024-12-31"]) == "date"

    def test_datetime(self):
        assert _infer_type(["2024-01-01 12:00", "2024-01-01T12:00:00"]) == "datetime"

    def test_string(self):
        assert _infer_type(["hello", "world", "123abc"]) == "string"

    def test_empty_all_null(self):
        assert _infer_type([None, None]) == "string"


# ── unit: CSV profiling ──────────────────────────────────────────────────


class TestCSVProfiling:
    def test_basic_csv(self):
        csv_content = "id,name,price\n1,Widget,9.99\n2,Gadget,19.95\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_basic.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp))
            assert result.rows_scanned == 2
            assert len(result.columns) == 3
            assert result.columns[0].name == "id"
            assert result.columns[0].inferred_type == "integer"
            assert result.columns[0].nullable is False
            assert result.sample_policy == "none"
            assert all(c.sample_values is None for c in result.columns)
        finally:
            tmp.unlink(missing_ok=True)

    def test_utf8_bom(self):
        # encode with utf-8-sig adds BOM marker automatically
        content = "id,name\n1,Hello\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_bom.csv"
        tmp.write_bytes(content.encode("utf-8-sig"))
        try:
            result = profile_csv(str(tmp))
            assert result.columns[0].name == "id"
            assert result.rows_scanned == 1
        finally:
            tmp.unlink(missing_ok=True)

    def test_csv_with_nulls(self):
        csv_content = "id,name\n1,Alpha\n2,\n,Gamma\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_nulls.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp))
            col_name = result.columns[1]
            assert col_name.name == "name"
            assert col_name.nullable is True
            assert col_name.null_count == 1
            assert col_name.non_null_count == 2
        finally:
            tmp.unlink(missing_ok=True)

    def test_pk_candidate_detected(self):
        csv_content = "id,value\n1,10\n2,20\n3,30\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_pk.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp))
            pks = {p["column"] for p in result.primary_key_candidates}
            assert "id" in pks
        finally:
            tmp.unlink(missing_ok=True)

    def test_non_pk_column_not_candidate(self):
        # No column is non-null + fully unique, so no PK candidates
        csv_content = "name,score\na,10\na,10\nb,30\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_nonpk.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp))
            assert result.primary_key_candidates == []
        finally:
            tmp.unlink(missing_ok=True)

    def test_with_samples(self):
        csv_content = "color\nred\nblue\nred\ngreen\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_samples.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp), include_samples=True)
            assert result.sample_policy == "opt-in-masked"
            samples = result.columns[0].sample_values
            assert samples is not None
            assert len(samples) <= 3
            assert set(samples) == {"red", "blue", "green"}
        finally:
            tmp.unlink(missing_ok=True)

    def test_pii_samples_masked(self):
        csv_content = "email,phone\nuser@test.com,13800001111\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_pii.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp), include_samples=True)
            email_sample = result.columns[0].sample_values[0]
            phone_sample = result.columns[1].sample_values[0]
            assert "user@test.com" not in email_sample
            assert "13800001111" not in phone_sample
        finally:
            tmp.unlink(missing_ok=True)

    def test_truncated_rows(self):
        rows = ["id,value"] + [f"{i},{i}" for i in range(15)]
        content = "\n".join(rows)
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_trunc.csv"
        tmp.write_text(content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp))
            assert result.truncated is False
        finally:
            tmp.unlink(missing_ok=True)

    def test_empty_csv_raises(self):
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_empty.csv"
        tmp.write_text("", encoding="utf-8")
        try:
            with pytest.raises(ValueError, match="Empty CSV"):
                profile_csv(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)

    def test_duplicate_columns_raises(self):
        csv_content = "id,id,name\n1,2,3\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_dup.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            with pytest.raises(ValueError, match="Duplicate"):
                profile_csv(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)

    def test_no_rows_raises(self):
        csv_content = "id,name\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_norows.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp))
            assert result.rows_scanned == 0
        finally:
            tmp.unlink(missing_ok=True)

    def test_quoted_fields(self):
        csv_content = 'id,description\n1,"Hello, World"\n2,"Line1\nLine2"\n'
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_quoted.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            result = profile_csv(str(tmp))
            assert result.rows_scanned == 2
            assert result.columns[0].name == "id"
        finally:
            tmp.unlink(missing_ok=True)

    def test_empty_header_raises(self):
        csv_content = ",name\n1,2\n"
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_emptyhdr.csv"
        tmp.write_text(csv_content, encoding="utf-8")
        try:
            with pytest.raises(ValueError, match="empty column name"):
                profile_csv(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)


# ── unit: XLSX profiling ─────────────────────────────────────────────────


class TestXLSXProfiling:
    def test_basic_xlsx(self):
        buf = _xlsx_bytes()
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_basic.xlsx"
        tmp.write_bytes(buf.read())
        try:
            result = profile_xlsx(str(tmp))
            assert result.rows_scanned == 3
            assert len(result.columns) == 3
            assert result.columns[0].name == "id"
            assert result.sheet_name == "Sheet1"
        finally:
            tmp.unlink(missing_ok=True)

    def test_xlsx_first_visible_sheet(self):
        buf = _xlsx_bytes_multi_sheet()
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_multi.xlsx"
        tmp.write_bytes(buf.read())
        try:
            result = profile_xlsx(str(tmp))
            # Should get the visible sheet, not the hidden one
            assert result.sheet_name == "Visible"
            assert result.columns[0].name == "id"
        finally:
            tmp.unlink(missing_ok=True)

    def test_xlsx_with_samples(self):
        buf = _xlsx_bytes()
        tmp = Path(os.environ.get("TEMP", "/tmp")) / "test_xlsx_samples.xlsx"
        tmp.write_bytes(buf.read())
        try:
            result = profile_xlsx(str(tmp), include_samples=True)
            assert result.sample_policy == "opt-in-masked"
            assert result.columns[0].sample_values is not None
        finally:
            tmp.unlink(missing_ok=True)


# ── unit: FK suggestions ─────────────────────────────────────────────────


class TestFKSuggestions:
    def test_fk_suggestion_same_project(self):
        new_cols = [
            ColumnProfile(
                name="customer_id", position=0, inferred_type="integer",
                nullable=False, non_null_count=100, null_count=0,
                distinct_count=50, distinct_count_capped=False,
            ),
        ]
        existing = [{
            "id": "ds-1",
            "original_name": "customers.csv",
            "profile_json": {
                "primary_key_candidates": [
                    {"column": "id", "confidence": "high", "reason": "test"}
                ],
            },
        }]
        suggestions = suggest_foreign_keys(new_cols, existing)
        assert len(suggestions) >= 1
        s = suggestions[0]
        assert s["source_column"] == "customer_id"
        assert s["target_dataset_id"] == "ds-1"
        assert s["target_column"] == "id"


# ── unit: content hash ───────────────────────────────────────────────────


class TestContentHash:
    def test_same_content_same_hash(self):
        tmp1 = Path(os.environ.get("TEMP", "/tmp")) / "hash_a.txt"
        tmp2 = Path(os.environ.get("TEMP", "/tmp")) / "hash_b.txt"
        tmp1.write_text("hello", encoding="utf-8")
        tmp2.write_text("hello", encoding="utf-8")
        try:
            assert compute_content_hash(str(tmp1)) == compute_content_hash(str(tmp2))
        finally:
            tmp1.unlink(missing_ok=True)
            tmp2.unlink(missing_ok=True)

    def test_different_content_different_hash(self):
        tmp1 = Path(os.environ.get("TEMP", "/tmp")) / "hash_c.txt"
        tmp2 = Path(os.environ.get("TEMP", "/tmp")) / "hash_d.txt"
        tmp1.write_text("hello", encoding="utf-8")
        tmp2.write_text("world", encoding="utf-8")
        try:
            assert compute_content_hash(str(tmp1)) != compute_content_hash(str(tmp2))
        finally:
            tmp1.unlink(missing_ok=True)
            tmp2.unlink(missing_ok=True)


# ── integration: API tests ───────────────────────────────────────────────


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


def _create_project(client, gid, h, name="Test Project", **kw):
    body = {"name": name, "entry_mode": "problem_first", **kw}
    r = client.post(f"/groups/{gid}/projects", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]  # Return just the project ID string


def _upload_dataset(
    client, gid, pid, h, content=None, filename="test.csv",
    include_samples=False, expect_status=201,
):
    if content is None:
        content = io.BytesIO("id,name\n1,Test\n".encode("utf-8"))
    elif isinstance(content, str):
        content = io.BytesIO(content.encode("utf-8"))

    files = {"file": (filename, content, "application/octet-stream")}
    data = {"include_sample_values": str(include_samples).lower()}
    r = client.post(
        f"/groups/{gid}/projects/{pid}/datasets",
        files=files,
        data=data,
        headers=h,
    )
    return r


class TestDatasetUploadAPI:
    def test_owner_upload_csv(self, client):
        _, _, h = register_and_login(client, "ds-owner@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = _upload_dataset(client, gid, pid, h)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["file_format"] == "csv"
        assert data["status"] == "ready"
        assert data["column_count"] == 2
        assert data["deduplicated"] is False

    def test_admin_upload(self, client):
        _, owner_me, owner_h = register_and_login(client, "ds-admin-o@pj.com")
        admin_me, _, admin_h = register_and_login(client, "ds-admin-a@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_admin(client, gid, owner_h, admin_me["id"])
        pid = _create_project(client, gid, owner_h)
        r = _upload_dataset(client, gid, pid, admin_h)
        assert r.status_code == 201

    def test_member_cannot_upload(self, client):
        _, _, owner_h = register_and_login(client, "ds-mem-o@pj.com")
        _, _, mem_h = register_and_login(client, "ds-mem-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        r = _upload_dataset(client, gid, pid, mem_h)
        assert r.status_code == 403

    def test_outsider_403(self, client):
        _, _, owner_h = register_and_login(client, "ds-out-o@pj.com")
        _, _, outsider_h = register_and_login(client, "ds-out-x@pj.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)
        r = _upload_dataset(client, gid, pid, outsider_h)
        assert r.status_code == 403

    def test_cross_group_404(self, client):
        _, _, ha = register_and_login(client, "ds-cg-a@pj.com")
        _, _, hb = register_and_login(client, "ds-cg-b@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        pid_a = _create_project(client, ga, ha)
        r = _upload_dataset(client, gb, pid_a, hb)
        assert r.status_code == 404

    def test_wrong_extension_422(self, client):
        _, _, h = register_and_login(client, "ds-ext@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = _upload_dataset(client, gid, pid, h, filename="test.pdf")
        assert r.status_code == 422

    def test_xls_rejected(self, client):
        _, _, h = register_and_login(client, "ds-xls@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = _upload_dataset(client, gid, pid, h, filename="legacy.xls")
        assert r.status_code == 422

    def test_empty_csv_422(self, client):
        _, _, h = register_and_login(client, "ds-empty@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = _upload_dataset(client, gid, pid, h, content="")
        assert r.status_code == 422

    def test_duplicate_upload_idempotent(self, client):
        _, _, h = register_and_login(client, "ds-dup@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "id,val\n1,10\n2,20\n"
        r1 = _upload_dataset(client, gid, pid, h, content=csv_content)
        assert r1.status_code == 201
        assert r1.json()["deduplicated"] is False
        r2 = _upload_dataset(client, gid, pid, h, content=csv_content)
        assert r2.status_code == 201
        assert r2.json()["deduplicated"] is True
        assert r2.json()["id"] == r1.json()["id"]

    def test_different_project_same_content_ok(self, client):
        _, _, h = register_and_login(client, "ds-dp@pj.com")
        gid = _create_group(client, h)
        p1 = _create_project(client, gid, h, name="Project A")
        p2 = _create_project(client, gid, h, name="Project B")
        csv_content = "id,val\n1,10\n"
        r1 = _upload_dataset(client, gid, p1, h, content=csv_content)
        r2 = _upload_dataset(client, gid, p2, h, content=csv_content)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

    def test_archived_project_rejects_upload(self, client):
        _, _, h = register_and_login(client, "ds-arch@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = client.post(f"/groups/{gid}/projects/{pid}/archive", headers=h)
        assert r.status_code == 200
        r2 = _upload_dataset(client, gid, pid, h)
        assert r2.status_code == 409

    def test_first_asset_advances_goal_to_data(self, client):
        _, _, h = register_and_login(client, "ds-adv@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj.json()["stage"] == "goal"
        r = _upload_dataset(client, gid, pid, h)
        assert r.status_code == 201
        proj2 = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj2.json()["stage"] == "data"

    def test_stage_does_not_advance_on_duplicate(self, client):
        """Upload → stage=goal→data. Duplicate upload → deduplicated, stage stays data."""
        _, _, h = register_and_login(client, "ds-noadv@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h, name="NoAdv")
        csv_content = "id,val\n1,10\n"
        r1 = _upload_dataset(client, gid, pid, h, content=csv_content)
        assert r1.status_code == 201
        proj = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj.json()["stage"] == "data"

        # Duplicate upload returns existing asset, stage does not change
        r2 = _upload_dataset(client, gid, pid, h, content=csv_content)
        assert r2.status_code == 201
        assert r2.json()["deduplicated"] is True
        proj2 = client.get(f"/groups/{gid}/projects/{pid}", headers=h)
        assert proj2.json()["stage"] == "data"  # still data after duplicate

    def test_list_datasets(self, client):
        _, _, h = register_and_login(client, "ds-list@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "id,val\n1,10\n"
        _upload_dataset(client, gid, pid, h, content=csv_content)
        r = client.get(f"/groups/{gid}/projects/{pid}/datasets", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert len(data["datasets"]) == 1

    def test_get_dataset_detail(self, client):
        _, _, h = register_and_login(client, "ds-get@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "id,val\n1,10\n"
        up = _upload_dataset(client, gid, pid, h, content=csv_content)
        ds_id = up.json()["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/datasets/{ds_id}", headers=h)
        assert r.status_code == 200
        assert r.json()["file_format"] == "csv"

    def test_member_can_read(self, client):
        _, _, owner_h = register_and_login(client, "ds-rd-o@pj.com")
        _, _, mem_h = register_and_login(client, "ds-rd-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        up = _upload_dataset(client, gid, pid, owner_h)
        ds_id = up.json()["id"]
        r = client.get(f"/groups/{gid}/projects/{pid}/datasets/{ds_id}", headers=mem_h)
        assert r.status_code == 200

    def test_archive_idempotent(self, client):
        _, _, h = register_and_login(client, "ds-arc@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        up = _upload_dataset(client, gid, pid, h)
        ds_id = up.json()["id"]
        r1 = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/{ds_id}/archive", headers=h
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "archived"
        r2 = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/{ds_id}/archive", headers=h
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "archived"

    def test_archive_requires_owner(self, client):
        _, _, owner_h = register_and_login(client, "ds-arc-o@pj.com")
        _, _, mem_h = register_and_login(client, "ds-arc-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        up = _upload_dataset(client, gid, pid, owner_h)
        ds_id = up.json()["id"]
        r = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/{ds_id}/archive", headers=mem_h
        )
        assert r.status_code == 403

    def test_cross_project_404(self, client):
        _, _, ha = register_and_login(client, "ds-cp-a@pj.com")
        _, _, hb = register_and_login(client, "ds-cp-b@pj.com")
        ga = _create_group(client, ha)
        gb = _create_group(client, hb)
        pid_a = _create_project(client, ga, ha)
        pid_b = _create_project(client, gb, hb)
        up = _upload_dataset(client, ga, pid_a, ha)
        # Try to read dataset from project A via project B's URL
        r = client.get(
            f"/groups/{gb}/projects/{pid_b}/datasets/{up.json()['id']}", headers=hb
        )
        assert r.status_code == 404

    def test_xlsx_upload(self, client):
        _, _, h = register_and_login(client, "ds-xlsx@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        buf = _xlsx_bytes()
        files = {"file": ("test.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = client.post(
            f"/groups/{gid}/projects/{pid}/datasets",
            files=files,
            data={"include_sample_values": "false"},
            headers=h,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["file_format"] == "xlsx"
        assert data["profile_json"]["sheet_name"] == "Sheet1"

    def test_status_filter(self, client):
        _, _, h = register_and_login(client, "ds-stf@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        up = _upload_dataset(client, gid, pid, h)
        ds_id = up.json()["id"]
        client.post(f"/groups/{gid}/projects/{pid}/datasets/{ds_id}/archive", headers=h)
        r_active = client.get(
            f"/groups/{gid}/projects/{pid}/datasets?status=ready", headers=h
        )
        r_arch = client.get(
            f"/groups/{gid}/projects/{pid}/datasets?status=archived", headers=h
        )
        assert r_active.json()["total"] == 0
        assert r_arch.json()["total"] == 1

    def test_profile_json_structure_csv(self, client):
        """Verify profile_json contains all required top-level keys."""
        _, _, h = register_and_login(client, "ds-struct@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        csv_content = "id,name,price\n1,Widget,9.99\n2,Gadget,19.95\n"
        r = _upload_dataset(client, gid, pid, h, content=csv_content)
        assert r.status_code == 201
        p = r.json()["profile_json"]
        assert p["schema_version"] == "1.0"
        assert p["sheet_name"] is None
        assert "columns" in p
        assert "primary_key_candidates" in p
        assert "foreign_key_suggestions" in p
        assert "sample_policy" in p
        # Columns have required fields
        col = p["columns"][0]
        assert "name" in col
        assert "position" in col
        assert "inferred_type" in col
        assert "nullable" in col
        assert "null_count" in col
        assert "non_null_count" in col
        assert "distinct_count" in col
        assert "distinct_count_capped" in col
        assert "primary_key_candidate" in col


class TestDoubleUploadCleanup:
    """Verify failed uploads leave no DB records."""

    def test_failed_csv_no_db_record(self, client):
        _, _, h = register_and_login(client, "ds-cln@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        # Empty CSV should fail
        r = _upload_dataset(client, gid, pid, h, content="")
        assert r.status_code == 422
        # Should be no datasets
        r_list = client.get(f"/groups/{gid}/projects/{pid}/datasets", headers=h)
        assert r_list.json()["total"] == 0


# ── P1.2 Demo data onboarding ───────────────────────────────────────────────


class TestDemoDataOnboarding:
    """Verify demo data import endpoint (P1.2)."""

    def test_owner_imports_demo_data_success(self, client):
        """Owner imports demo data — returns 201 with 13 datasets."""
        _, _, h = register_and_login(client, "demo-own@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/demo-data",
            headers=h,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["demo_data_imported"] is True
        assert data["files_generated"] == 13
        assert data["datasets_imported"] == 13
        assert data["datasets_skipped"] == 0
        assert data["total_rows"] > 0

        # Verify datasets appear in list
        r_list = client.get(
            f"/groups/{gid}/projects/{pid}/datasets", headers=h,
        )
        assert r_list.json()["total"] == 13

    def test_admin_imports_demo_data_success(self, client):
        """Admin can also import demo data."""
        _, owner_me, owner_h = register_and_login(client, "demo-adm-o@pj.com")
        admin_me, _, admin_h = register_and_login(client, "demo-adm-a@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, admin_h)
        _promote_admin(client, gid, owner_h, admin_me["id"])
        pid = _create_project(client, gid, owner_h)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/demo-data",
            headers=admin_h,
        )
        assert r.status_code == 201, r.text
        assert r.json()["datasets_imported"] == 13

    def test_member_cannot_import_demo_data(self, client):
        """Member gets 403."""
        _, _, owner_h = register_and_login(client, "demo-mem-o@pj.com")
        _, _, mem_h = register_and_login(client, "demo-mem-m@pj.com")
        gid = _create_group(client, owner_h)
        _join_group(client, gid, owner_h, mem_h)
        pid = _create_project(client, gid, owner_h)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/demo-data",
            headers=mem_h,
        )
        assert r.status_code == 403

    def test_outsider_403_demo_data(self, client):
        """Non-member gets 403."""
        _, _, owner_h = register_and_login(client, "demo-out-o@pj.com")
        _, _, outsider_h = register_and_login(client, "demo-out-x@pj.com")
        gid = _create_group(client, owner_h)
        pid = _create_project(client, gid, owner_h)
        r = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/demo-data",
            headers=outsider_h,
        )
        assert r.status_code == 403

    def test_demo_data_idempotent(self, client):
        """Second import skips all datasets as duplicates."""
        _, _, h = register_and_login(client, "demo-dup@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        r1 = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/demo-data",
            headers=h,
        )
        assert r1.status_code == 201
        assert r1.json()["datasets_imported"] == 13

        r2 = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/demo-data",
            headers=h,
        )
        assert r2.status_code == 201
        data2 = r2.json()
        assert data2["datasets_imported"] == 0
        assert data2["datasets_skipped"] == 13

        # Still only 13 datasets total
        r_list = client.get(
            f"/groups/{gid}/projects/{pid}/datasets", headers=h,
        )
        assert r_list.json()["total"] == 13

    def test_archived_project_rejects_demo_data(self, client):
        """Cannot import demo data into an archived project."""
        _, _, h = register_and_login(client, "demo-arch@pj.com")
        gid = _create_group(client, h)
        pid = _create_project(client, gid, h)
        # Archive the project
        client.post(
            f"/groups/{gid}/projects/{pid}/archive",
            headers=h,
        )
        r = client.post(
            f"/groups/{gid}/projects/{pid}/datasets/demo-data",
            headers=h,
        )
        assert r.status_code == 409
