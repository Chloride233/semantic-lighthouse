"""Tests for R2C-R2F runtime relationship traversal.

Covers: single-hop + two-hop hash join, FK/PK column resolution, field
whitelist, root filters, limit/offset, explain_only, error cases
(no link_type, no binding, no FK column, missing FK/PK annotation,
path length), provenance safety (no storage_path, no FK values, no
filter values), router permissions/isolation, audit (success/empty/
failure/explain_only/provenance/fail-closed), multi-hop chaining.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from semantic_lighthouse.services.runtime_traverse import execute_traversal


# Helpers.

def _write_csv(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _mock_package(pkg_id="pkg-1", version=1):
    pkg = MagicMock()
    pkg.id = pkg_id
    pkg.version = version
    pkg.content_hash = "abc"
    return pkg


def _mock_binding(
    binding_id, package_id, dataset_id,
    ot_api_name, property_mappings,
    group_id="g1", project_id="p1",
):
    b = MagicMock()
    b.id = binding_id
    b.package_id = package_id
    b.dataset_id = dataset_id
    b.object_type_api_name = ot_api_name
    b.property_mappings = property_mappings
    b.group_id = group_id
    b.project_id = project_id
    b.status = "active"
    return b


def _mock_dataset(ds_id, storage_path, file_format="csv",
                  group_id="g1", project_id="p1"):
    ds = MagicMock()
    ds.id = ds_id
    ds.storage_path = storage_path
    ds.file_format = file_format
    ds.group_id = group_id
    ds.project_id = project_id
    ds.status = "ready"
    return ds


def _contract_context(**overrides):
    """Build a minimal contract context with optional overrides."""
    ctx = {
        "manifest": {"semantic_hash": "sha256:abc123"},
        "semantic_hash": "sha256:abc123",
        "ot_map": {
            "equipment": {"primary_key": "equipment_id",
                          "display_name": "Equipment"},
            "maintenance": {"primary_key": "maintenance_id",
                            "display_name": "Maintenance"},
        },
        "prop_map": {
            "equipment_id": {"object_type": "equipment",
                             "value_type": "string", "required": True},
            "equipment_name": {"object_type": "equipment",
                               "value_type": "string", "required": True},
            "status": {"object_type": "equipment",
                       "value_type": "string", "required": False},
            "maintenance_id": {"object_type": "maintenance",
                               "value_type": "string", "required": True},
            "equipment_fk": {"object_type": "maintenance",
                             "value_type": "string", "required": True},
            "maint_type": {"object_type": "maintenance",
                           "value_type": "string", "required": True},
            "downtime_hours": {"object_type": "maintenance",
                               "value_type": "number", "required": False},
        },
        "fields_by_ot": {
            "equipment": ["equipment_id", "equipment_name", "status"],
            "maintenance": ["maintenance_id", "equipment_fk",
                            "maint_type", "downtime_hours"],
        },
        "link_types": [
            {
                "entity_type": "link_type",
                "api_name": "equipment_maintenance",
                "source_object_type": "equipment",
                "target_object_type": "maintenance",
                "cardinality": "one_to_many",
                "source_fk_property": "equipment_id",
                "target_pk_property": "equipment_fk",
            },
        ],
        "link_map": {
            "equipment_maintenance": {
                "api_name": "equipment_maintenance",
                "source_object_type": "equipment",
                "target_object_type": "maintenance",
                "cardinality": "one_to_many",
                "source_fk_property": "equipment_id",
                "target_pk_property": "equipment_fk",
            },
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(ctx.get(k), dict):
            ctx[k].update(v)
        else:
            ctx[k] = v
    return ctx


# Single-hop traversal tests: happy paths.

class TestSingleHopTraversal:
    """Equipment to Maintenance (one-to-many) traversal."""

    def _setup(self, monkeypatch, src_csv, tgt_csv,
               ctx_overrides=None):
        """Create temp CSV files, patch DB/services, return args tuple."""
        tmp = tempfile.mkdtemp()
        src_path = os.path.join(tmp, "equipment.csv")
        tgt_path = os.path.join(tmp, "maintenance.csv")
        _write_csv(src_path, src_csv)
        _write_csv(tgt_path, tgt_csv)

        pkg = _mock_package()
        src_ds = _mock_dataset("ds-src", src_path)
        tgt_ds = _mock_dataset("ds-tgt", tgt_path)
        src_b = _mock_binding(
            "bind-src", pkg.id, src_ds.id, "equipment",
            {"equipment_id": "eq_id", "equipment_name": "eq_name",
             "status": "status"},
        )
        tgt_b = _mock_binding(
            "bind-tgt", pkg.id, tgt_ds.id, "maintenance",
            {"maintenance_id": "maint_id", "equipment_fk": "equipment_id",
             "maint_type": "type", "downtime_hours": "hours"},
        )

        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_get_latest_project_package",
            lambda db, gid, pid: pkg,
        )
        ctx = _contract_context(**(ctx_overrides or {}))
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_build_contract_context",
            lambda pkg: ctx,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_validate_dataset_path",
            lambda sp, gid, pid: Path(sp),
        )

        # Use cycling side_effect for reusable mock across multiple calls.
        # Each execute_traversal calls db.scalar exactly 2 (src, tgt).
        _scalar_values = [src_b, tgt_b]
        _scalar_iter = iter(lambda: _scalar_values, None)  # never ends

        def _scalar(stmt):
            try:
                return next(iter(_scalar_values))
            except StopIteration:
                return None

        db = MagicMock()
        db.scalar = MagicMock()
        # Pre-build an infinite cycling iterator
        import itertools
        _scalar_cycle = itertools.cycle([src_b, tgt_b])
        db.scalar = MagicMock(side_effect=lambda stmt: next(_scalar_cycle))
        db.get = MagicMock(side_effect=lambda model, ds_id:
                           {"ds-src": src_ds, "ds-tgt": tgt_ds}.get(ds_id))

        return db, "g1", "p1", ["equipment", "maintenance"], "user-1"

    #  basic traversal 

    def test_basic_traversal_returns_joined_rows(self, monkeypatch):
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\nEQ2,Motor-B,inactive\n"
        tgt_csv = (
            "maint_id,equipment_id,type,hours\n"
            "M1,EQ1,preventive,2.5\n"
            "M2,EQ1,corrective,8.0\n"
            "M3,EQ2,preventive,1.0\n"
        )
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(
            db, gid, pid, path, uid,
            fields={"equipment": ["equipment_name", "status"],
                    "maintenance": ["maint_type", "downtime_hours"]},
        )
        assert result["row_count"] == 3
        # EQ1 has 2 maintenance rows
        eq1_rows = [r for r in result["rows"]
                    if r["equipment__equipment_name"] == "Pump-A"]
        assert len(eq1_rows) == 2

        for r in result["rows"]:
            assert "equipment__equipment_name" in r
            assert "equipment__status" in r
            assert "maintenance__maint_type" in r
            assert "maintenance__downtime_hours" in r
            # No unprefixed field leak
            assert "equipment_name" not in r
            assert "maint_type" not in r

    def test_field_whitelist_per_ot(self, monkeypatch):
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(
            db, gid, pid, path, uid,
            fields={"equipment": ["equipment_name"],
                    "maintenance": ["maint_type"]},
        )
        row = result["rows"][0]
        assert "equipment__equipment_name" in row
        assert "equipment__status" not in row
        assert "maintenance__maint_type" in row
        assert "maintenance__downtime_hours" not in row

    def test_default_fields_all_bound(self, monkeypatch):
        """When fields not specified, all bound contract fields returned."""
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(db, gid, pid, path, uid)
        row = result["rows"][0]
        assert "equipment__equipment_name" in row
        assert "equipment__status" in row
        assert "maintenance__maint_type" in row
        assert "maintenance__downtime_hours" in row

    #  filters 

    def test_root_filter(self, monkeypatch):
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\nEQ2,Motor-B,inactive\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\nM2,EQ2,preventive,1.0\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(
            db, gid, pid, path, uid,
            fields={"equipment": ["equipment_name"],
                    "maintenance": ["maint_type"]},
            filters={"status": "active"},
        )
        assert result["row_count"] == 1
        assert result["rows"][0]["equipment__equipment_name"] == "Pump-A"

    def test_filter_no_match(self, monkeypatch):
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(
            db, gid, pid, path, uid,
            filters={"status": "nonexistent"},
        )
        assert result["row_count"] == 0
        assert result["rows"] == []

    #  join semantics 

    def test_fk_no_match_in_target(self, monkeypatch):
        """Inner join: source row with no target match is excluded."""
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\nEQ3,Orphan,active\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(db, gid, pid, path, uid)
        assert result["row_count"] == 1
        assert result["rows"][0]["equipment__equipment_name"] == "Pump-A"

    def test_multiple_target_rows_per_source(self, monkeypatch):
        """One source row with N target rows produces N joined rows."""
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        tgt_csv = (
            "maint_id,equipment_id,type,hours\n"
            "M1,EQ1,preventive,1.0\nM2,EQ1,corrective,2.0\n"
            "M3,EQ1,inspection,3.0\nM4,EQ1,overhaul,4.0\n"
        )
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)
        result = execute_traversal(db, gid, pid, path, uid)
        assert result["row_count"] == 4

    #  limit / offset 

    def test_limit_offset(self, monkeypatch):
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        tgt_csv = (
            "maint_id,equipment_id,type,hours\n"
            "M1,EQ1,preventive,1.0\nM2,EQ1,corrective,2.0\n"
            "M3,EQ1,inspection,3.0\n"
        )
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        r1 = execute_traversal(db, gid, pid, path, uid, offset=1, limit=1)
        assert r1["row_count"] == 1
        r2 = execute_traversal(db, gid, pid, path, uid, offset=0, limit=2)
        assert r2["row_count"] == 2

    #  explain 

    def test_explain_only(self, monkeypatch):
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(
            db, gid, pid, path, uid, explain_only=True,
        )
        assert result["row_count"] is None
        assert result["rows"] == []
        explain = result["explain"]
        assert explain["path"] == ["equipment", "maintenance"]
        hop = explain["hops"][0]
        assert hop["link_type_api_name"] == "equipment_maintenance"
        assert hop["source_fk_column"] == "eq_id"
        assert hop["target_pk_column"] == "equipment_id"

    def test_explain_includes_scan_info(self, monkeypatch):
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\nEQ2,Motor-B,inactive\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)

        result = execute_traversal(db, gid, pid, path, uid)
        explain = result["explain"]
        assert explain["scanned_rows"]["equipment"] == 2
        assert explain["scanned_rows"]["maintenance"] == 1
        assert explain["matched_before_paging"] >= 1

    #  type conversion 

    def test_integer_fk_pk_join(self, monkeypatch):
        """FK and PK as integers join correctly after type conversion."""
        src_csv = "eq_id,eq_name,status\n101,Pump-A,active\n102,Motor-B,inactive\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,101,preventive,2.5\nM2,102,corrective,8.0\n"
        db, gid, pid, path, uid = self._setup(
            monkeypatch, src_csv, tgt_csv,
            ctx_overrides={
                "prop_map": {
                    "equipment_id": {"object_type": "equipment",
                                     "value_type": "integer", "required": True},
                    "equipment_fk": {"object_type": "maintenance",
                                     "value_type": "integer", "required": True},
                },
            },
        )
        result = execute_traversal(db, gid, pid, path, uid)
        assert result["row_count"] == 2

    def test_null_fk_skipped(self, monkeypatch):
        """Source row with null FK is skipped (inner join)."""
        src_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n,Orphan,active\n"
        tgt_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        db, gid, pid, path, uid = self._setup(monkeypatch, src_csv, tgt_csv)
        result = execute_traversal(db, gid, pid, path, uid)
        assert result["row_count"] == 1


# Error cases.
# 

class TestTraversalErrors:
    def _patch_basics(self, monkeypatch, ctx=None):
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_get_latest_project_package",
            lambda db, gid, pid: _mock_package(),
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_build_contract_context",
            lambda pkg: ctx or _contract_context(),
        )

    def test_path_length_not_two(self, monkeypatch):
        self._patch_basics(monkeypatch)
        db = MagicMock()
        with pytest.raises(ValueError, match="must have 2"):
            execute_traversal(db, "g1", "p1", ["equipment"], "u1")
        with pytest.raises(ValueError, match="must have 2"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "maintenance", "extra", "fourth"], "u1")

    def test_no_link_type_connects(self, monkeypatch):
        self._patch_basics(monkeypatch)
        db = MagicMock()
        with pytest.raises(ValueError, match="No link_type connects"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "nonexistent"], "u1")

    def test_link_without_fk_property(self, monkeypatch):
        ctx = _contract_context()
        ctx["link_map"]["equipment_maintenance"]["source_fk_property"] = ""
        self._patch_basics(monkeypatch, ctx)
        db = MagicMock()
        with pytest.raises(ValueError, match="no source_fk_property"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "maintenance"], "u1")

    def test_link_without_pk_property(self, monkeypatch):
        ctx = _contract_context()
        ctx["link_map"]["equipment_maintenance"]["target_pk_property"] = ""
        ctx["ot_map"]["maintenance"]["primary_key"] = ""
        self._patch_basics(monkeypatch, ctx)
        db = MagicMock()
        with pytest.raises(ValueError, match="no target_pk_property"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "maintenance"], "u1")

    def test_no_package(self, monkeypatch):
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_get_latest_project_package",
            lambda db, gid, pid: None,
        )
        db = MagicMock()
        with pytest.raises(ValueError, match="No project package"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "maintenance"], "u1")

    def test_contract_compilation_fails(self, monkeypatch):
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_get_latest_project_package",
            lambda db, gid, pid: _mock_package(),
        )
        def _fail(*args, **kwargs):
            raise Exception("boom")
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_build_contract_context",
            _fail,
        )
        db = MagicMock()
        with pytest.raises(ValueError, match="contract compilation failed"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "maintenance"], "u1")

    def test_no_active_binding(self, monkeypatch):
        """No active binding for source OT raises an error."""
        pkg = _mock_package()
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_get_latest_project_package",
            lambda db, gid, pid: pkg,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_build_contract_context",
            lambda pkg: _contract_context(),
        )
        db = MagicMock()
        db.scalar = MagicMock(return_value=None)  # no binding found
        with pytest.raises(ValueError, match="No active binding"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "maintenance"], "u1")


# Provenance safety.
# 

class TestTraverseExplainSafety:
    def _setup(self, monkeypatch, src_csv=None, tgt_csv=None):
        tmp = tempfile.mkdtemp()
        src_path = os.path.join(tmp, "src.csv")
        tgt_path = os.path.join(tmp, "tgt.csv")
        _write_csv(src_path, src_csv or "eq_id,eq_name,status\nEQ1,Pump-A,active\n")
        _write_csv(tgt_path, tgt_csv or "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n")

        pkg = _mock_package()
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_get_latest_project_package",
            lambda db, gid, pid: pkg,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_build_contract_context",
            lambda pkg: _contract_context(),
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse."
            "_validate_dataset_path",
            lambda sp, gid, pid: Path(sp),
        )

        src_b = _mock_binding(
            "bind-src", pkg.id, "ds-src", "equipment",
            {"equipment_id": "eq_id", "equipment_name": "eq_name",
             "status": "status"},
        )
        tgt_b = _mock_binding(
            "bind-tgt", pkg.id, "ds-tgt", "maintenance",
            {"maintenance_id": "maint_id", "equipment_fk": "equipment_id",
             "maint_type": "type", "downtime_hours": "hours"},
        )
        src_ds = _mock_dataset("ds-src", src_path)
        tgt_ds = _mock_dataset("ds-tgt", tgt_path)

        db = MagicMock()
        import itertools
        _scalar_cycle = itertools.cycle([src_b, tgt_b])
        db.scalar = MagicMock(side_effect=lambda stmt: next(_scalar_cycle))
        db.get = MagicMock(side_effect=lambda model, ds_id:
                           {"ds-src": src_ds, "ds-tgt": tgt_ds}.get(ds_id))
        return db, "g1", "p1", ["equipment", "maintenance"], "u1"

    def test_explain_no_storage_path(self, monkeypatch):
        db, gid, pid, path, uid = self._setup(monkeypatch)
        result = execute_traversal(db, gid, pid, path, uid)
        explain_str = str(result["explain"]).lower()
        assert "storage_path" not in explain_str
        assert "dataset-storage" not in explain_str

    def test_explain_no_filter_values(self, monkeypatch):
        db, gid, pid, path, uid = self._setup(monkeypatch)
        result = execute_traversal(
            db, gid, pid, path, uid, filters={"status": "active"},
        )
        explain_str = str(result["explain"]).lower()
        assert "active" not in explain_str

    def test_explain_no_fk_pk_data_values(self, monkeypatch):
        db, gid, pid, path, uid = self._setup(monkeypatch)
        result = execute_traversal(db, gid, pid, path, uid)
        explain_str = str(result["explain"]).lower()
        assert "eq1" not in explain_str
        assert "pump-a" not in explain_str

    def test_result_no_storage_path(self, monkeypatch):
        db, gid, pid, path, uid = self._setup(monkeypatch)
        result = execute_traversal(db, gid, pid, path, uid)
        result_str = str(result).lower()
        assert "storage_path" not in result_str

    def test_explain_package_and_binding_ids(self, monkeypatch):
        db, gid, pid, path, uid = self._setup(monkeypatch)
        result = execute_traversal(db, gid, pid, path, uid)
        explain = result["explain"]
        assert explain["package_id"] == "pkg-1"
        hop = explain["hops"][0]
        assert hop["source_binding_id"] == "bind-src"
        assert hop["target_binding_id"] == "bind-tgt"
        assert hop["source_dataset_id"] == "ds-src"
        assert hop["target_dataset_id"] == "ds-tgt"

    def test_explain_semantic_hash_from_contract(self, monkeypatch):
        db, gid, pid, path, uid = self._setup(monkeypatch)
        result = execute_traversal(db, gid, pid, path, uid)
        assert result["explain"]["package_semantic_hash"] == "sha256:abc123"


# R2D integration tests: router-level FastAPI TestClient.


def _mock_traverse_success(**overrides):
    """Return a valid execute_traversal result dict for router tests."""
    result = {
        "rows": [
            {
                "equipment__name": "Pump-A",
                "equipment__status": "active",
                "maintenance__type": "preventive",
                "maintenance__hours": 2.5,
            },
        ],
        "row_count": 1,
        "explain": {
            "package_id": "pkg-test",
            "package_version": 1,
            "package_semantic_hash": "sha256:deadbeef",
            "path": ["equipment", "maintenance"],
            "hops": [
                {
                    "hop_index": 0,
                    "link_type_api_name": "equipment_maintenance",
                    "source_object_type": "equipment",
                    "target_object_type": "maintenance",
                    "cardinality": "one_to_many",
                    "source_binding_id": "bind-src",
                    "target_binding_id": "bind-tgt",
                    "source_dataset_id": "ds-src",
                    "target_dataset_id": "ds-tgt",
                    "source_fk_property": "equipment_id",
                    "target_pk_property": "equipment_fk",
                    "source_fk_column": "eq_id",
                    "target_pk_column": "equipment_id",
                },
            ],
            "selected_fields_by_ot": {
                "equipment": ["name", "status"],
                "maintenance": ["type", "hours"],
            },
            "filter_field_names_by_ot": {"equipment": []},
            "limit": 20,
            "offset": 0,
            "scanned_rows": {"equipment": 5, "maintenance": 20},
            "scan_limit": 10000,
            "scan_truncated": {"equipment": False, "maintenance": False},
            "matched_before_paging": 1,
        },
    }
    result.update(overrides)
    return result


def _mock_traverse_explain_only():
    """Return an explain_only result."""
    return {
        "rows": [],
        "row_count": None,
        "explain": {
            "package_id": "pkg-test",
            "package_version": 1,
            "package_semantic_hash": "sha256:deadbeef",
            "path": ["equipment", "maintenance"],
            "hops": [
                {
                    "hop_index": 0,
                    "link_type_api_name": "equipment_maintenance",
                    "source_object_type": "equipment",
                    "target_object_type": "maintenance",
                    "cardinality": "one_to_many",
                    "source_binding_id": "bind-src",
                    "target_binding_id": "bind-tgt",
                    "source_dataset_id": "ds-src",
                    "target_dataset_id": "ds-tgt",
                    "source_fk_property": "equipment_id",
                    "target_pk_property": "equipment_fk",
                    "source_fk_column": "eq_id",
                    "target_pk_column": "equipment_id",
                },
            ],
            "selected_fields_by_ot": {
                "equipment": ["name", "status"],
                "maintenance": ["type", "hours"],
            },
            "filter_field_names_by_ot": {"equipment": []},
            "limit": 20,
            "offset": 0,
        },
    }


def _setup_traverse_project(client):
    """Create group + project + member user. Returns (gid, pid, owner_h, member_h)."""
    from conftest import register_and_login

    _, _, owner_h = register_and_login(client, "r2d-own@test.com")
    _, mem_resp, mem_h = register_and_login(client, "r2d-mem@test.com")
    gid = None
    r = client.post("/groups", json={"name": "R2D Traverse Test"}, headers=owner_h)
    assert r.status_code == 201, r.text
    gid = r.json()["id"]

    # Invite + join member
    inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
    assert inv.status_code == 201
    r = client.post(
        "/groups/join-by-invite",
        json={"invite_code": inv.json()["invite_code"]},
        headers=mem_h,
    )
    assert r.status_code == 200

    # Create project
    r = client.post(
        f"/groups/{gid}/projects",
        json={"name": "Traverse Project", "entry_mode": "problem_first"},
        headers=owner_h,
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    return gid, pid, owner_h, mem_h


# Permissions.


class TestTraverseRouterPermissions:
    def test_member_can_traverse(self, client, monkeypatch):
        """Member can call POST /runtime/traverse and get a 200."""
        gid, pid, _owner_h, mem_h = _setup_traverse_project(client)

        mock_result = _mock_traverse_success()
        monkeypatch.setattr(
            "semantic_lighthouse.routers.runtime.execute_traversal",
            lambda *args, **kwargs: mock_result,
        )

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={
                "path": ["equipment", "maintenance"],
                "fields": {"equipment": ["name"], "maintenance": ["type"]},
            },
            headers=mem_h,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["row_count"] == 1
        assert len(data["rows"]) == 1
        assert "explain" in data

    def test_non_member_rejected_403(self, client):
        """User not in group gets 403."""
        from conftest import register_and_login

        _, _, owner_h = register_and_login(client, "r2d-nm-own@test.com")
        _, _, outsider_h = register_and_login(client, "r2d-nm-out@test.com")

        r = client.post("/groups", json={"name": "NM Group"}, headers=owner_h)
        assert r.status_code == 201
        gid = r.json()["id"]

        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "NM Project", "entry_mode": "problem_first"},
            headers=owner_h,
        )
        assert r.status_code == 201
        pid = r.json()["id"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"]},
            headers=outsider_h,
        )
        assert r.status_code == 403, r.text

    def test_outsider_rejected_403(self, client):
        """Unrelated user gets 403 on all runtime traverse operations."""
        from conftest import register_and_login

        _, _, owner_h = register_and_login(client, "r2d-out-own@test.com")
        _, _, outsider_h = register_and_login(client, "r2d-out-x@test.com")

        r = client.post("/groups", json={"name": "Outsider Group"}, headers=owner_h)
        assert r.status_code == 201
        gid = r.json()["id"]

        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "Out Project", "entry_mode": "problem_first"},
            headers=owner_h,
        )
        assert r.status_code == 201
        pid = r.json()["id"]

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"]},
            headers=outsider_h,
        )
        assert r.status_code == 403

    def test_project_from_another_group_404(self, client):
        """Project that doesn't belong to the URL group returns 404."""
        from conftest import register_and_login

        _, _, h1 = register_and_login(client, "r2d-cg-1@test.com")
        _, _, h2 = register_and_login(client, "r2d-cg-2@test.com")

        r = client.post("/groups", json={"name": "CG Group 1"}, headers=h1)
        assert r.status_code == 201
        gid1 = r.json()["id"]

        r = client.post("/groups", json={"name": "CG Group 2"}, headers=h2)
        assert r.status_code == 201
        gid2 = r.json()["id"]

        r = client.post(
            f"/groups/{gid1}/projects",
            json={"name": "CG Project", "entry_mode": "problem_first"},
            headers=h1,
        )
        assert r.status_code == 201
        pid = r.json()["id"]

        # Access group 1's project under group 2's URL
        r = client.post(
            f"/groups/{gid2}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"]},
            headers=h2,
        )
        assert r.status_code == 404

    def test_archived_project_rejected_409(self, client, db_session):
        """Archived project returns 409 even for members."""
        from conftest import register_and_login
        from semantic_lighthouse.models import BusinessProject

        _, _, owner_h = register_and_login(client, "r2d-arch-own@test.com")
        _, _, mem_h = register_and_login(client, "r2d-arch-mem@test.com")

        r = client.post("/groups", json={"name": "Archive Group"}, headers=owner_h)
        assert r.status_code == 201
        gid = r.json()["id"]

        inv = client.post(f"/groups/{gid}/invites", headers=owner_h)
        assert inv.status_code == 201
        r = client.post(
            "/groups/join-by-invite",
            json={"invite_code": inv.json()["invite_code"]},
            headers=mem_h,
        )
        assert r.status_code == 200

        r = client.post(
            f"/groups/{gid}/projects",
            json={"name": "Archive Project", "entry_mode": "problem_first"},
            headers=owner_h,
        )
        assert r.status_code == 201
        pid = r.json()["id"]

        # Archive the project directly in DB
        project = db_session.get(BusinessProject, pid)
        assert project is not None
        project.status = "archived"
        db_session.commit()

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"]},
            headers=mem_h,
        )
        assert r.status_code == 409, r.text
        assert "archived" in r.json()["detail"].lower()


# Error mapping.


class TestTraverseRouterErrors:
    def _setup_with_mock(self, client, monkeypatch, mock_fn):
        """Create group + project + member, install mock, return (gid, pid, mem_h)."""
        gid, pid, _owner_h, mem_h = _setup_traverse_project(client)
        monkeypatch.setattr(
            "semantic_lighthouse.routers.runtime.execute_traversal",
            mock_fn,
        )
        return gid, pid, mem_h

    def test_no_link_type_returns_422(self, client, monkeypatch):
        """ValueError with 'No link_type connects' maps to 422."""
        def _fail(*args, **kwargs):
            raise ValueError("No link_type connects 'equipment' -> 'nonexistent'")
        gid, pid, mem_h = self._setup_with_mock(client, monkeypatch, _fail)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "nonexistent"]},
            headers=mem_h,
        )
        assert r.status_code == 422, r.text
        assert "No link_type connects" in r.json()["detail"]

    def test_invalid_fields_returns_422(self, client, monkeypatch):
        """ValueError about invalid fields maps to 422."""
        def _fail(*args, **kwargs):
            raise ValueError(
                "Fields not in contract for 'equipment': bad_field"
            )
        gid, pid, mem_h = self._setup_with_mock(client, monkeypatch, _fail)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={
                "path": ["equipment", "maintenance"],
                "fields": {"equipment": ["bad_field"]},
            },
            headers=mem_h,
        )
        assert r.status_code == 422, r.text
        assert "bad_field" in r.json()["detail"]

    def test_no_package_returns_422(self, client, monkeypatch):
        """ValueError about missing package maps to 422."""
        def _fail(*args, **kwargs):
            raise ValueError("No project package found for this project")
        gid, pid, mem_h = self._setup_with_mock(client, monkeypatch, _fail)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"]},
            headers=mem_h,
        )
        assert r.status_code == 422, r.text
        assert "No project package" in r.json()["detail"]

    def test_path_too_short_pydantic_422(self, client):
        """Path with < 2 elements rejected by Pydantic validation."""
        gid, pid, _owner_h, mem_h = _setup_traverse_project(client)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment"]},
            headers=mem_h,
        )
        assert r.status_code == 422, r.text

    def test_path_too_long_pydantic_422(self, client):
        """Path with > 3 elements rejected by Pydantic validation."""
        gid, pid, _owner_h, mem_h = _setup_traverse_project(client)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["a", "b", "c", "d"]},
            headers=mem_h,
        )
        assert r.status_code == 422, r.text

    def test_limit_exceeds_max_pydantic_422(self, client):
        """Limit > 100 rejected by Pydantic."""
        gid, pid, _owner_h, mem_h = _setup_traverse_project(client)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"], "limit": 101},
            headers=mem_h,
        )
        assert r.status_code == 422, r.text

    def test_non_root_filter_rejected_422(self, client, monkeypatch):
        """Filters on non-root object_types are rejected, not ignored."""
        gid, pid, mem_h = self._setup_with_mock(
            client,
            monkeypatch,
            lambda *args, **kwargs: _mock_traverse_success(),
        )

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={
                "path": ["equipment", "maintenance"],
                "filters": {"maintenance": {"type": "preventive"}},
            },
            headers=mem_h,
        )
        assert r.status_code == 422, r.text
        assert "root object_type" in r.json()["detail"]


# Response shape and provenance safety.


class TestTraverseRouterResponse:
    def _setup_with_success_mock(self, client, monkeypatch, mock_result=None):
        """Create project + install success mock. Returns (gid, pid, mem_h)."""
        gid, pid, _owner_h, mem_h = _setup_traverse_project(client)
        monkeypatch.setattr(
            "semantic_lighthouse.routers.runtime.execute_traversal",
            lambda *args, **kwargs: mock_result or _mock_traverse_success(),
        )
        return gid, pid, mem_h

    def test_explain_only_works(self, client, monkeypatch):
        """explain_only=True returns empty rows and full explain."""
        gid, pid, mem_h = self._setup_with_success_mock(
            client, monkeypatch, _mock_traverse_explain_only(),
        )

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={
                "path": ["equipment", "maintenance"],
                "explain_only": True,
            },
            headers=mem_h,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["row_count"] is None
        assert data["rows"] == []
        explain = data["explain"]
        assert explain["path"] == ["equipment", "maintenance"]
        assert len(explain["hops"]) == 1
        assert explain["hops"][0]["link_type_api_name"] == "equipment_maintenance"

    def test_response_no_storage_path(self, client, monkeypatch):
        """API response must not contain storage_path."""
        gid, pid, mem_h = self._setup_with_success_mock(client, monkeypatch)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"]},
            headers=mem_h,
        )
        assert r.status_code == 200, r.text
        response_str = r.text.lower()
        assert "storage_path" not in response_str
        assert "dataset-storage" not in response_str

    def test_response_no_filter_values(self, client, monkeypatch):
        """API response explain must not leak filter values."""
        gid, pid, mem_h = self._setup_with_success_mock(client, monkeypatch)

        # Use filters with a value that should NOT appear in explain
        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={
                "path": ["equipment", "maintenance"],
                "filters": {"equipment": {"status": "active"}},
            },
            headers=mem_h,
        )
        assert r.status_code == 200, r.text
        explain_str = str(r.json()["explain"]).lower()
        # "active" is a filter value; it must not appear in explain.
        assert "active" not in explain_str

    def test_response_no_fk_pk_data_values(self, client, monkeypatch):
        """API response explain must not leak FK/PK data values."""
        gid, pid, mem_h = self._setup_with_success_mock(client, monkeypatch)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={
                "path": ["equipment", "maintenance"],
                "fields": {"equipment": ["name"], "maintenance": ["type"]},
            },
            headers=mem_h,
        )
        assert r.status_code == 200, r.text
        explain_str = str(r.json()["explain"]).lower()
        # FK/PK column *names* (metadata) are OK; data *values* like "eq1" are NOT
        assert "eq1" not in explain_str
        assert "pump-a" not in explain_str

    def test_response_includes_package_and_binding_ids(self, client, monkeypatch):
        """Response explain includes package and binding metadata."""
        gid, pid, mem_h = self._setup_with_success_mock(client, monkeypatch)

        r = client.post(
            f"/groups/{gid}/projects/{pid}/runtime/traverse",
            json={"path": ["equipment", "maintenance"]},
            headers=mem_h,
        )
        assert r.status_code == 200, r.text
        explain = r.json()["explain"]
        assert explain["package_id"] == "pkg-test"
        hop = explain["hops"][0]
        assert hop["source_binding_id"] == "bind-src"
        assert hop["target_binding_id"] == "bind-tgt"
        assert hop["source_dataset_id"] == "ds-src"
        assert hop["target_dataset_id"] == "ds-tgt"


# R2E audit tests: service-level real DB session with mocked file IO.


def _audit_rows(db_session, operation="traverse"):
    """Query OntologyRuntimeAudit from the test DB."""
    from sqlalchemy import select as sa_select

    from semantic_lighthouse.models import OntologyRuntimeAudit

    stmt = sa_select(OntologyRuntimeAudit).where(
        OntologyRuntimeAudit.operation == operation,
    ).order_by(OntologyRuntimeAudit.created_at)
    return db_session.scalars(stmt).all()


def _mk_audit_setup(monkeypatch, tmp_dir, pkg, ctx, src_b, tgt_b, src_ds, tgt_ds):
    """Create temp CSVs and install common mocks for audit tests."""
    import os as _os

    src_path = _os.path.join(tmp_dir, "src.csv")
    tgt_path = _os.path.join(tmp_dir, "tgt.csv")
    _write_csv(src_path, "eq_id,eq_name,status\nEQ1,Pump-A,active\n")
    _write_csv(tgt_path, "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n")

    from pathlib import Path as _Path

    monkeypatch.setattr(
        "semantic_lighthouse.services.runtime_traverse._get_latest_project_package",
        lambda db, gid, pid: pkg,
    )
    monkeypatch.setattr(
        "semantic_lighthouse.services.runtime_traverse._build_contract_context",
        lambda pkg: ctx,
    )
    monkeypatch.setattr(
        "semantic_lighthouse.services.runtime_traverse._validate_dataset_path",
        lambda sp, gid, pid: _Path(sp),
    )
    monkeypatch.setattr(
        "semantic_lighthouse.services.runtime_traverse._resolve_binding",
        lambda db, pkg_id, gid, pid, ot: (
            src_b if ot == "equipment" else tgt_b
        ),
    )
    monkeypatch.setattr(
        "semantic_lighthouse.services.runtime_traverse._resolve_dataset_and_path",
        lambda db, binding, gid, pid, ot: (
            (src_ds, src_path) if ot == "equipment"
            else (tgt_ds, tgt_path)
        ),
    )


def _make_audit_mocks():
    """Build standard mock objects for audit success tests."""
    pkg = _mock_package()
    ctx = _contract_context()
    src_b = _mock_binding("bind-src", pkg.id, "ds-src", "equipment",
                          {"equipment_id": "eq_id", "equipment_name": "eq_name",
                           "status": "status"})
    tgt_b = _mock_binding("bind-tgt", pkg.id, "ds-tgt", "maintenance",
                          {"maintenance_id": "maint_id",
                           "equipment_fk": "equipment_id",
                           "maint_type": "type", "downtime_hours": "hours"})
    src_ds = _mock_dataset("ds-src", "dummy.csv")
    tgt_ds = _mock_dataset("ds-tgt", "dummy.csv")
    return pkg, ctx, src_b, tgt_b, src_ds, tgt_ds


class TestTraverseAudit:
    """Verify OntologyRuntimeAudit records for traverse operations."""

    def test_success_audit_has_all_traverse_fields(self, db_session, monkeypatch):
        """Successful traversal writes audit with path, hop_count, etc."""
        pkg, ctx, src_b, tgt_b, src_ds, tgt_ds = _make_audit_mocks()
        tmp_dir = tempfile.mkdtemp()
        _mk_audit_setup(monkeypatch, tmp_dir, pkg, ctx, src_b, tgt_b, src_ds, tgt_ds)

        result = execute_traversal(
            db_session, "g1", "p1", ["equipment", "maintenance"], "user-1",
            fields={"equipment": ["equipment_name"], "maintenance": ["maint_type"]},
        )
        assert result["row_count"] >= 1

        audits = _audit_rows(db_session)
        assert len(audits) >= 1
        a = audits[-1]
        assert a.operation == "traverse"
        assert a.outcome == "success"
        assert a.group_id == "g1"
        assert a.project_id == "p1"
        assert a.path == ["equipment", "maintenance"]
        assert a.hop_count == 1
        assert a.link_type_api_names == ["equipment_maintenance"]
        assert a.binding_ids == ["bind-src", "bind-tgt"]
        assert a.dataset_ids == ["ds-src", "ds-tgt"]
        assert a.limit_val == 20
        assert a.offset_val == 0
        assert a.field_names is not None
        assert "equipment__equipment_name" in a.field_names
        assert "maintenance__maint_type" in a.field_names
        assert a.row_count == 1

    def test_empty_traversal_audit_outcome_empty(self, db_session, monkeypatch):
        """Traversal with 0 matching rows writes audit outcome='empty'."""
        pkg, ctx, src_b, tgt_b, src_ds, tgt_ds = _make_audit_mocks()
        tmp_dir = tempfile.mkdtemp()
        _mk_audit_setup(monkeypatch, tmp_dir, pkg, ctx, src_b, tgt_b, src_ds, tgt_ds)

        result = execute_traversal(
            db_session, "g1", "p1", ["equipment", "maintenance"], "user-1",
            filters={"status": "nonexistent"},
        )
        assert result["row_count"] == 0

        audits = _audit_rows(db_session)
        a = audits[-1]
        assert a.outcome == "empty"
        assert a.row_count == 0
        assert a.path == ["equipment", "maintenance"]

    def test_explain_only_audit_has_metadata(self, db_session, monkeypatch):
        """explain_only writes audit with path info and row_count=0."""
        pkg, ctx, src_b, tgt_b, src_ds, tgt_ds = _make_audit_mocks()
        tmp_dir = tempfile.mkdtemp()
        _mk_audit_setup(monkeypatch, tmp_dir, pkg, ctx, src_b, tgt_b, src_ds, tgt_ds)

        result = execute_traversal(
            db_session, "g1", "p1", ["equipment", "maintenance"], "user-1",
            explain_only=True,
        )
        assert result["row_count"] is None
        assert result["rows"] == []

        audits = _audit_rows(db_session)
        a = audits[-1]
        assert a.outcome == "success"
        assert a.row_count == 0
        assert a.path == ["equipment", "maintenance"]
        assert a.link_type_api_names == ["equipment_maintenance"]
        assert a.binding_ids == ["bind-src", "bind-tgt"]
        assert a.dataset_ids == ["ds-src", "ds-tgt"]
        assert a.field_names is not None
        assert len(a.field_names) >= 2

    def test_failure_audit_no_package(self, db_session, monkeypatch):
        """Missing package writes failure audit with error_code."""
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._get_latest_project_package",
            lambda db, gid, pid: None,
        )
        with pytest.raises(ValueError, match="No project package"):
            execute_traversal(db_session, "g1", "p1",
                              ["equipment", "maintenance"], "user-1")

        audits = _audit_rows(db_session)
        assert len(audits) >= 1
        a = audits[-1]
        assert a.outcome == "failure"
        assert a.error_code == "no_project_package"
        assert a.path == ["equipment", "maintenance"]
        assert a.hop_count == 1

    def test_failure_audit_invalid_path_length(self, db_session):
        """Invalid service-level path length writes failure audit."""
        with pytest.raises(ValueError, match="must have 2"):
            execute_traversal(db_session, "g1", "p1", ["equipment"], "user-1")

        audits = _audit_rows(db_session)
        a = audits[-1]
        assert a.outcome == "failure"
        assert a.error_code == "max_path_length_exceeded"
        assert a.path == ["equipment"]
        assert a.hop_count == 0

    def test_failure_audit_no_link_type(self, db_session, monkeypatch):
        """No link_type writes failure audit with correct error_code."""
        pkg = _mock_package()
        ctx = _contract_context()
        # Keep the link_type but query a path that doesn't match
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._get_latest_project_package",
            lambda db, gid, pid: pkg,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._build_contract_context",
            lambda pkg: ctx,
        )

        with pytest.raises(ValueError, match="No link_type connects"):
            execute_traversal(db_session, "g1", "p1",
                              ["equipment", "nonexistent"], "user-1")

        audits = _audit_rows(db_session)
        a = audits[-1]
        assert a.outcome == "failure"
        assert a.error_code == "no_link_type"
        assert a.path == ["equipment", "nonexistent"]
        assert a.link_type_api_names is None

    def test_failure_audit_no_binding(self, db_session, monkeypatch):
        """No binding writes failure audit with no_binding_for_hop."""
        pkg = _mock_package()
        ctx = _contract_context()
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._get_latest_project_package",
            lambda db, gid, pid: pkg,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._build_contract_context",
            lambda pkg: ctx,
        )

        with pytest.raises(ValueError, match="No active binding"):
            execute_traversal(db_session, "g1", "p1",
                              ["equipment", "maintenance"], "user-1")

        audits = _audit_rows(db_session)
        a = audits[-1]
        assert a.outcome == "failure"
        assert a.error_code == "no_binding_for_hop"
        assert a.link_type_api_names == ["equipment_maintenance"]

    def test_audit_no_storage_path(self, db_session, monkeypatch):
        """Audit record must never contain storage_path."""
        pkg, ctx, src_b, tgt_b, src_ds, tgt_ds = _make_audit_mocks()
        tmp_dir = tempfile.mkdtemp()
        _mk_audit_setup(monkeypatch, tmp_dir, pkg, ctx, src_b, tgt_b, src_ds, tgt_ds)

        execute_traversal(
            db_session, "g1", "p1", ["equipment", "maintenance"], "user-1",
        )

        audits = _audit_rows(db_session)
        a = audits[-1]
        for col_name in ("error_summary", "error_code"):
            val = getattr(a, col_name, None)
            if val:
                assert "dataset-storage" not in str(val).lower()
                assert "storage_path" not in str(val).lower()
        for col_name in ("field_names", "filter_field_names", "path",
                         "link_type_api_names", "binding_ids", "dataset_ids"):
            val = getattr(a, col_name, None)
            if val:
                val_str = str(val).lower()
                assert "dataset-storage" not in val_str
                assert "storage_path" not in val_str

    def test_audit_no_filter_values(self, db_session, monkeypatch):
        """Audit must never contain filter values, only filter field names."""
        pkg, ctx, src_b, tgt_b, src_ds, tgt_ds = _make_audit_mocks()
        tmp_dir = tempfile.mkdtemp()
        _mk_audit_setup(monkeypatch, tmp_dir, pkg, ctx, src_b, tgt_b, src_ds, tgt_ds)

        execute_traversal(
            db_session, "g1", "p1", ["equipment", "maintenance"], "user-1",
            filters={"status": "active"},
        )

        audits = _audit_rows(db_session)
        a = audits[-1]
        assert a.filter_field_names is not None
        audit_str = str({
            "field_names": a.field_names,
            "filter_field_names": a.filter_field_names,
            "error_summary": a.error_summary,
            "error_code": a.error_code,
        }).lower()
        assert "active" not in audit_str


class TestTraverseAuditFailClosed:
    """Prove that audit persistence failure prevents data exposure."""

    def test_audit_commit_failure_does_not_return_data(
        self, db_session, monkeypatch,
    ):
        """If audit write fails, an exception propagates and data is not returned."""
        from semantic_lighthouse.models import OntologyRuntimeAudit

        pkg, ctx, src_b, tgt_b, src_ds, tgt_ds = _make_audit_mocks()
        tmp_dir = tempfile.mkdtemp()
        _mk_audit_setup(monkeypatch, tmp_dir, pkg, ctx, src_b, tgt_b, src_ds, tgt_ds)

        _orig_init = OntologyRuntimeAudit.__init__

        def _failing_init(self, **kw):
            if kw.get("operation") == "traverse" and kw.get("outcome") == "success":
                raise RuntimeError("Simulated audit persistence failure")
            return _orig_init(self, **kw)

        monkeypatch.setattr(OntologyRuntimeAudit, "__init__", _failing_init)

        errored = False
        try:
            result = execute_traversal(
                db_session, "g1", "p1", ["equipment", "maintenance"], "user-1",
            )
            assert False, (
                f"Expected exception on audit failure, got rows={result.get('row_count')}"
            )
        except (RuntimeError, ValueError):
            errored = True
        assert errored, "Audit persistence failure should prevent data return"


# R2F two-hop traversal tests: equipment -> maintenance -> work_orders.




def _two_hop_context(**overrides):
    """Build a contract context for equipment -> maintenance -> work_orders."""
    ctx = {
        "manifest": {"semantic_hash": "sha256:2hop"},
        "semantic_hash": "sha256:2hop",
        "ot_map": {
            "equipment": {"primary_key": "equipment_id", "display_name": "Equipment"},
            "maintenance": {"primary_key": "maintenance_id", "display_name": "Maintenance"},
            "work_orders": {"primary_key": "work_order_id", "display_name": "Work Orders"},
        },
        "prop_map": {
            "equipment_id": {"object_type": "equipment", "value_type": "string", "required": True},
            "equipment_name": {"object_type": "equipment", "value_type": "string", "required": True},
            "status": {"object_type": "equipment", "value_type": "string", "required": False},
            "maintenance_id": {"object_type": "maintenance", "value_type": "string", "required": True},
            "equipment_fk": {"object_type": "maintenance", "value_type": "string", "required": True},
            "maint_type": {"object_type": "maintenance", "value_type": "string", "required": True},
            "downtime_hours": {"object_type": "maintenance", "value_type": "number", "required": False},
            "work_order_id": {"object_type": "work_orders", "value_type": "string", "required": True},
            "maintenance_fk": {"object_type": "work_orders", "value_type": "string", "required": True},
            "wo_description": {"object_type": "work_orders", "value_type": "string", "required": True},
            "priority": {"object_type": "work_orders", "value_type": "string", "required": False},
        },
        "fields_by_ot": {
            "equipment": ["equipment_id", "equipment_name", "status"],
            "maintenance": ["maintenance_id", "equipment_fk", "maint_type", "downtime_hours"],
            "work_orders": ["work_order_id", "maintenance_fk", "wo_description", "priority"],
        },
        "link_types": [
            {
                "entity_type": "link_type",
                "api_name": "equipment_maintenance",
                "source_object_type": "equipment",
                "target_object_type": "maintenance",
                "cardinality": "one_to_many",
                "source_fk_property": "equipment_id",
                "target_pk_property": "equipment_fk",
            },
            {
                "entity_type": "link_type",
                "api_name": "maintenance_work_orders",
                "source_object_type": "maintenance",
                "target_object_type": "work_orders",
                "cardinality": "one_to_many",
                "source_fk_property": "maintenance_id",
                "target_pk_property": "maintenance_fk",
            },
        ],
        "link_map": {
            "equipment_maintenance": {
                "api_name": "equipment_maintenance",
                "source_object_type": "equipment",
                "target_object_type": "maintenance",
                "cardinality": "one_to_many",
                "source_fk_property": "equipment_id",
                "target_pk_property": "equipment_fk",
            },
            "maintenance_work_orders": {
                "api_name": "maintenance_work_orders",
                "source_object_type": "maintenance",
                "target_object_type": "work_orders",
                "cardinality": "one_to_many",
                "source_fk_property": "maintenance_id",
                "target_pk_property": "maintenance_fk",
            },
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(ctx.get(k), dict):
            ctx[k].update(v)
        else:
            ctx[k] = v
    return ctx


class TestTwoHopTraversal:
    """Equipment -> Maintenance -> Work Orders two-hop traversal."""

    def _setup(self, monkeypatch, eq_csv, maint_csv, wo_csv, ctx_overrides=None):
        """Create 3 temp CSVs, patch DB/services, return args tuple."""
        tmp = tempfile.mkdtemp()
        eq_path = os.path.join(tmp, "equipment.csv")
        maint_path = os.path.join(tmp, "maintenance.csv")
        wo_path = os.path.join(tmp, "work_orders.csv")
        _write_csv(eq_path, eq_csv)
        _write_csv(maint_path, maint_csv)
        _write_csv(wo_path, wo_csv)

        pkg = _mock_package(pkg_id="pkg-2h", version=1)
        ctx = _two_hop_context(**(ctx_overrides or {}))

        # Bindings
        eq_b = _mock_binding("b-eq", pkg.id, "ds-eq", "equipment",
                             {"equipment_id": "eq_id", "equipment_name": "eq_name", "status": "status"})
        m_b = _mock_binding("b-m", pkg.id, "ds-m", "maintenance",
                            {"maintenance_id": "maint_id", "equipment_fk": "equipment_id",
                             "maint_type": "type", "downtime_hours": "hours"})
        wo_b = _mock_binding("b-wo", pkg.id, "ds-wo", "work_orders",
                             {"work_order_id": "wo_id", "maintenance_fk": "maint_ref",
                              "wo_description": "description", "priority": "priority"})

        # Datasets
        eq_ds = _mock_dataset("ds-eq", eq_path)
        m_ds = _mock_dataset("ds-m", maint_path)
        wo_ds = _mock_dataset("ds-wo", wo_path)

        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._get_latest_project_package",
            lambda db, gid, pid: pkg,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._build_contract_context",
            lambda pkg: ctx,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._validate_dataset_path",
            lambda sp, gid, pid: Path(sp),
        )

        import itertools
        _scalar_cycle = itertools.cycle([eq_b, m_b, wo_b])
        db = MagicMock()
        db.scalar = MagicMock(side_effect=lambda stmt: next(_scalar_cycle))
        db.get = MagicMock(side_effect=lambda model, ds_id:
                           {"ds-eq": eq_ds, "ds-m": m_ds, "ds-wo": wo_ds}.get(ds_id))

        return db, "g1", "p1", ["equipment", "maintenance", "work_orders"], "user-1"

    def test_basic_two_hop_returns_joined_rows(self, monkeypatch):
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\nEQ2,Motor-B,inactive\n"
        maint_csv = ("maint_id,equipment_id,type,hours\n"
                     "M1,EQ1,preventive,2.5\nM2,EQ1,corrective,8.0\nM3,EQ2,preventive,1.0\n")
        wo_csv = ("wo_id,maint_ref,description,priority\n"
                  "W1,M1,Replace bearing,high\nW2,M1,Inspect seal,low\nW3,M3,Lubricate,medium\n")

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        result = execute_traversal(
            db, gid, pid, path, uid,
            fields={"equipment": ["equipment_name"],
                    "maintenance": ["maint_type"],
                    "work_orders": ["wo_description"]},
        )
        assert result["row_count"] == 3
        # EQ1 -> M1 -> W1, W2  (2 rows)
        eq1 = [r for r in result["rows"] if r["equipment__equipment_name"] == "Pump-A"]
        assert len(eq1) == 2
        # EQ2 -> M3 -> W3  (1 row)
        eq2 = [r for r in result["rows"] if r["equipment__equipment_name"] == "Motor-B"]
        assert len(eq2) == 1

        for r in result["rows"]:
            assert "equipment__equipment_name" in r
            assert "maintenance__maint_type" in r
            assert "work_orders__wo_description" in r
            # No unprefixed leak
            assert "equipment_name" not in r
            assert "maint_type" not in r

    def test_two_hop_field_whitelist_per_ot(self, monkeypatch):
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M1,Replace bearing,high\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        result = execute_traversal(
            db, gid, pid, path, uid,
            fields={"equipment": ["equipment_name"],
                    "maintenance": ["maint_type"],
                    "work_orders": ["wo_description"]},
        )
        row = result["rows"][0]
        assert "equipment__equipment_name" in row
        assert "equipment__status" not in row
        assert "maintenance__maint_type" in row
        assert "maintenance__downtime_hours" not in row
        assert "work_orders__wo_description" in row
        assert "work_orders__priority" not in row

    def test_two_hop_root_filter(self, monkeypatch):
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\nEQ2,Motor-B,inactive\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\nM2,EQ2,preventive,1.0\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M1,Replace,high\nW2,M2,Lube,low\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        result = execute_traversal(
            db, gid, pid, path, uid,
            fields={"equipment": ["equipment_name"],
                    "maintenance": ["maint_type"],
                    "work_orders": ["wo_description"]},
            filters={"status": "active"},
        )
        assert result["row_count"] == 1
        assert result["rows"][0]["equipment__equipment_name"] == "Pump-A"

    def test_two_hop_explain_has_two_hops(self, monkeypatch):
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M1,Replace,high\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        result = execute_traversal(db, gid, pid, path, uid)
        explain = result["explain"]
        assert explain["path"] == ["equipment", "maintenance", "work_orders"]
        assert len(explain["hops"]) == 2
        hop0 = explain["hops"][0]
        assert hop0["hop_index"] == 0
        assert hop0["link_type_api_name"] == "equipment_maintenance"
        hop1 = explain["hops"][1]
        assert hop1["hop_index"] == 1
        assert hop1["link_type_api_name"] == "maintenance_work_orders"
        assert "scanned_rows" in explain
        assert "equipment" in explain["scanned_rows"]
        assert "maintenance" in explain["scanned_rows"]
        assert "work_orders" in explain["scanned_rows"]

    def test_two_hop_explain_only(self, monkeypatch):
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M1,Replace,high\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        result = execute_traversal(db, gid, pid, path, uid, explain_only=True)
        assert result["row_count"] is None
        assert result["rows"] == []
        assert len(result["explain"]["hops"]) == 2

    def test_two_hop_limit_offset(self, monkeypatch):
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        wo_csv = ("wo_id,maint_ref,description,priority\n"
                  "W1,M1,A,high\nW2,M1,B,low\nW3,M1,C,medium\n")

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        r1 = execute_traversal(db, gid, pid, path, uid, offset=1, limit=1)
        assert r1["row_count"] == 1
        r2 = execute_traversal(db, gid, pid, path, uid, offset=0, limit=2)
        assert r2["row_count"] == 2

    def test_two_hop_empty_intermediate_yields_empty(self, monkeypatch):
        """If hop 0 produces no matches, result is empty (inner join semantics)."""
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ999,preventive,2.5\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M1,Replace,high\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        result = execute_traversal(db, gid, pid, path, uid)
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_two_hop_empty_final_yields_empty(self, monkeypatch):
        """If hop 1 produces no matches, result is empty."""
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M999,Replace,high\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        result = execute_traversal(db, gid, pid, path, uid)
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_two_hop_no_link_type_rejected(self, monkeypatch):
        """Invalid second hop maps to no_link_type."""
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M1,Replace,high\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv)

        with pytest.raises(ValueError, match="No link_type connects"):
            execute_traversal(db, gid, pid,
                              ["equipment", "maintenance", "nonexistent"], uid)

    def test_two_hop_missing_fk_property_rejected(self, monkeypatch):
        """Link without FK property maps to fk_property_not_in_contract."""
        ctx = _two_hop_context()
        ctx["link_map"]["maintenance_work_orders"]["source_fk_property"] = ""
        eq_csv = "eq_id,eq_name,status\nEQ1,Pump-A,active\n"
        maint_csv = "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n"
        wo_csv = "wo_id,maint_ref,description,priority\nW1,M1,Replace,high\n"

        db, gid, pid, path, uid = self._setup(monkeypatch, eq_csv, maint_csv, wo_csv,
                                              ctx_overrides=ctx)
        with pytest.raises(ValueError, match="no source_fk_property"):
            execute_traversal(db, gid, pid, path, uid)

    def test_two_hop_audit_has_two_hop_metadata(self, db_session, monkeypatch):
        """Two-hop success audit records 2 link_types, 3 bindings, 3 datasets."""
        pkg = _mock_package(pkg_id="pkg-2h")
        ctx = _two_hop_context()

        # Bindings
        eq_b = _mock_binding("b-eq", pkg.id, "ds-eq", "equipment",
                             {"equipment_id": "eq_id", "equipment_name": "eq_name", "status": "status"})
        m_b = _mock_binding("b-m", pkg.id, "ds-m", "maintenance",
                            {"maintenance_id": "maint_id", "equipment_fk": "equipment_id",
                             "maint_type": "type", "downtime_hours": "hours"})
        wo_b = _mock_binding("b-wo", pkg.id, "ds-wo", "work_orders",
                             {"work_order_id": "wo_id", "maintenance_fk": "maint_ref",
                              "wo_description": "description", "priority": "priority"})

        # Datasets
        eq_ds = _mock_dataset("ds-eq", "dummy.csv")
        m_ds = _mock_dataset("ds-m", "dummy.csv")
        wo_ds = _mock_dataset("ds-wo", "dummy.csv")

        tmp_dir = tempfile.mkdtemp()
        eq_path = os.path.join(tmp_dir, "equipment.csv")
        maint_path = os.path.join(tmp_dir, "maintenance.csv")
        wo_path = os.path.join(tmp_dir, "work_orders.csv")
        _write_csv(eq_path, "eq_id,eq_name,status\nEQ1,Pump-A,active\n")
        _write_csv(maint_path, "maint_id,equipment_id,type,hours\nM1,EQ1,preventive,2.5\n")
        _write_csv(wo_path, "wo_id,maint_ref,description,priority\nW1,M1,Replace,high\n")

        from pathlib import Path as _Path

        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._get_latest_project_package",
            lambda db, gid, pid: pkg,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._build_contract_context",
            lambda pkg: ctx,
        )
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._validate_dataset_path",
            lambda sp, gid, pid: _Path(sp),
        )
        _ot_bindings = {"equipment": eq_b, "maintenance": m_b, "work_orders": wo_b}
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._resolve_binding",
            lambda db, pkg_id, gid, pid, ot: _ot_bindings[ot],
        )
        _ot_paths = {"equipment": eq_path, "maintenance": maint_path, "work_orders": wo_path}
        _ot_ds = {"equipment": eq_ds, "maintenance": m_ds, "work_orders": wo_ds}
        monkeypatch.setattr(
            "semantic_lighthouse.services.runtime_traverse._resolve_dataset_and_path",
            lambda db, binding, gid, pid, ot: (_ot_ds[ot], _ot_paths[ot]),
        )

        result = execute_traversal(
            db_session, "g1", "p1",
            ["equipment", "maintenance", "work_orders"], "user-1",
            fields={"equipment": ["equipment_name"],
                    "maintenance": ["maint_type"],
                    "work_orders": ["wo_description"]},
        )
        assert result["row_count"] >= 1

        audits = _audit_rows(db_session)
        a = audits[-1]
        assert a.outcome == "success"
        assert a.path == ["equipment", "maintenance", "work_orders"]
        assert a.hop_count == 2
        assert a.link_type_api_names == ["equipment_maintenance", "maintenance_work_orders"]
        assert a.binding_ids == ["b-eq", "b-m", "b-wo"]
        assert a.dataset_ids == ["ds-eq", "ds-m", "ds-wo"]
        assert a.field_names is not None
        assert "equipment__equipment_name" in a.field_names
        assert "maintenance__maint_type" in a.field_names
        assert "work_orders__wo_description" in a.field_names
