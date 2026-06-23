"""Tests for R2C runtime relationship traversal core.

Covers: single-hop hash join, FK/PK column resolution, field whitelist,
root filters, limit/offset, explain_only, error cases (no link_type,
no binding, no FK column, missing FK/PK annotation, path length),
provenance safety (no storage_path, no FK values, no filter values).
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
        with pytest.raises(ValueError, match="exactly 2"):
            execute_traversal(db, "g1", "p1", ["equipment"], "u1")
        with pytest.raises(ValueError, match="exactly 2"):
            execute_traversal(db, "g1", "p1",
                              ["equipment", "maintenance", "extra"], "u1")

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


