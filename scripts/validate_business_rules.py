"""Validate business rules against a manufacturing data pack.

Reads manifest.json, mapping_contract.json, and CSV files from a data pack
directory, then runs deterministic offline rule checks. Produces a
rule_validation_report.json. No database writes, no API calls, no UI.

Rule categories (v1):
  required_field   — null_strategy=forbid columns must be non-null
  pk_unique        — primary key values must be unique and non-null
  fk_integrity     — foreign key values must reference existing rows
  enum_allowed     — enum columns must contain only allowed values
  numeric_range    — quantity/cost/rate/downtime/lead_time must be >= 0
  date_order       — start date must be <= end date
  derived_class    — identify derived/high-value entities (INFO only)
  row_count_range  — each table must have > 0 rows

Usage:
  .venv/Scripts/python scripts/validate_business_rules.py \\
      --data-pack .tmp/phase19-manufacturing

  .venv/Scripts/python scripts/validate_business_rules.py \\
      --data-pack .tmp/phase19-manufacturing --fail-on-warn

Exit: 0 = PASS (all rules pass, or only WARN without --fail-on-warn).
      1 = one or more FAIL rules (or WARN with --fail-on-warn).
Dependencies: stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPORT_VERSION = "1.0"

# ── Hardcoded enum allowed values (derived from generator deterministic schema)
# Keys are "table_name.column_name". Only columns in this map get enum checks.
# ─────────────────────────────────────────────────────────────────────────────

ENUM_ALLOWED_MAP: dict[str, set[str]] = {
    # suppliers
    "suppliers.country": {
        "US", "CN", "DE", "JP", "KR", "TW", "IN", "MX",
    },
    # materials
    "materials.unit_of_measure": {
        "kg", "m", "pcs", "L", "m²", "roll", "tube", "sheet",
    },
    "materials.abc_class": {"A", "B", "C"},
    # products
    "products.product_family": {
        "Hydraulic", "Electronic", "Mechanical", "Structural", "Aerospace",
    },
    # work_centers
    "work_centers.work_center_type": {
        "CNC Machining", "Manual Lathe", "Welding Station",
        "Assembly Line", "Quality Inspection", "Surface Treatment",
        "PCB Assembly", "Test & Calibration", "EDM Machining",
        "Powder Coating", "Heat Treatment", "Laser Cutting",
    },
    # equipment
    "equipment.status": {"operational", "degraded", "down"},
    # equipment_maintenance
    "equipment_maintenance.maintenance_type": {
        "preventive", "corrective", "predictive", "calibration", "overhaul",
    },
    "equipment_maintenance.status": {
        "scheduled", "in_progress", "completed",
    },
    # work_orders
    "work_orders.status": {
        "planned", "released", "in_progress", "completed",
        "on_hold", "rejected",
    },
    "work_orders.priority": {"high", "medium", "low"},
    # work_order_operations
    "work_order_operations.status": {
        "pending", "in_progress", "completed",
    },
    # routing_operations
    "routing_operations.operation_name": {
        "Rough Cut", "Finish Cut", "Drill", "Tap", "Weld",
        "Assemble", "Inspect", "Test", "Deburr", "Polish",
        "Coat", "Heat Treat", "Solder", "Calibrate", "Pack",
        "Sandblast", "Press Fit", "Torque", "Seal", "Label",
    },
    # quality_inspections
    "quality_inspections.result": {
        "pending", "in_progress", "passed", "failed", "conditional_accept",
    },
    "quality_inspections.inspection_type": {"final", "in_process"},
    # inventory
    "inventory.location_code": {"WH-A", "WH-B", "PROD", "RAW", "FG"},
    "inventory.location_name": {
        "Warehouse A", "Warehouse B", "Production Floor",
        "Raw Material Yard", "Finished Goods Store",
    },
}

# ── Date-order pairs: (table, start_col, end_col, allow_null_end)
# ═══════════════════════════════════════════════════════════════════════════════

DATE_ORDER_PAIRS: list[tuple[str, str, str, bool]] = [
    ("work_orders", "scheduled_start", "scheduled_end", False),
    ("work_orders", "actual_start", "actual_end", True),
    ("work_order_operations", "planned_start", "planned_end", False),
    ("work_order_operations", "actual_start", "actual_end", True),
    ("equipment_maintenance", "scheduled_date", "completed_date", True),
]

# ── Derived class rules: (table, condition_fn_key, class_name)
# These are INFO-only and never cause failure.
# ─────────────────────────────────────────────────────────────────────────────

DERIVED_CLASS_RULES: list[dict] = [
    {
        "class_name": "critical_work_order",
        "table": "work_orders",
        "description": (
            "High-priority work orders that are released or in progress"
        ),
        "condition": lambda row: (
            row.get("priority") == "high"
            and row.get("status") in ("released", "in_progress")
        ),
    },
    {
        "class_name": "at_risk_equipment",
        "table": "equipment",
        "description": (
            "Equipment with degraded or down status requiring attention"
        ),
        "condition": lambda row: (
            row.get("status") in ("degraded", "down")
        ),
    },
    {
        "class_name": "high_value_material",
        "table": "materials",
        "description": (
            "Class A materials with high inventory value"
        ),
        "condition": lambda row: (
            row.get("abc_class") == "A"
        ),
    },
    {
        "class_name": "high_scrap_work_order",
        "table": "work_orders",
        "description": (
            "Work orders with > 10% scrap rate (scrapped / ordered)"
        ),
        "condition": lambda row: (
            int(row.get("quantity_ordered", "1") or "1") > 0
            and int(row.get("quantity_scrapped", "0") or "0")
            / max(1, int(row.get("quantity_ordered", "1") or "1"))
            > 0.1
        ),
    },
]

# ── Numeric non-negative columns (table.column)
# ═══════════════════════════════════════════════════════════════════════════════

NUMERIC_NON_NEGATIVE: set[str] = {
    "suppliers.lead_time_days",
    "suppliers.min_order_qty",
    "suppliers.quality_rating",
    "materials.unit_cost",
    "materials.lead_time_days",
    "materials.safety_stock_qty",
    "materials.reorder_point",
    "products.unit_cost",
    "products.unit_price",
    "products.lead_time_days",
    "products.min_lot_size",
    "work_centers.hourly_rate",
    "work_centers.capacity_hours_per_day",
    "work_centers.setup_time_minutes",
    "work_centers.efficiency_pct",
    "bills_of_materials.quantity_per_unit",
    "bills_of_materials.scrap_rate_pct",
    "bills_of_materials.sequence",
    "routing_operations.sequence",
    "routing_operations.standard_time_minutes",
    "routing_operations.setup_time_minutes",
    "equipment_maintenance.downtime_hours",
    "equipment_maintenance.cost",
    "work_orders.quantity_ordered",
    "work_orders.quantity_completed",
    "work_orders.quantity_scrapped",
    "work_order_operations.sequence",
    "work_order_operations.setup_time_minutes",
    "work_order_operations.run_time_minutes",
    "inventory.quantity_on_hand",
    "inventory.quantity_allocated",
    "inventory.quantity_on_order",
    "quality_inspections.defect_count",
    "quality_inspections.measured_value",
    "quality_inspections.spec_lower",
    "quality_inspections.spec_upper",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read CSV and return list of dicts with original row numbers."""
    if not csv_path.is_file():
        return []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        rows = []
        for i, row in enumerate(csv.DictReader(f), 1):
            row["__row__"] = str(i)
            rows.append(row)
        return rows


def _parse_date(val: str | None) -> datetime | None:
    """Parse a date/datetime string. Returns None on failure."""
    if not val or not val.strip():
        return None
    clean = val.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S+00:00",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def _pk_cols(manifest: dict, table_name: str) -> list[str]:
    """Get primary key columns for a table from manifest."""
    for t in manifest.get("tables", []):
        if t["table_name"] == table_name:
            return t.get("primary_key", [])
    return []


def _read_manifest(data_dir: Path) -> dict:
    return json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))


def _read_contract(data_dir: Path) -> dict:
    return json.loads(
        (data_dir / "mapping_contract.json").read_text(encoding="utf-8")
    )


# ── Rule implementations ─────────────────────────────────────────────────────


def _check_required_field(
    data: dict[str, list[dict[str, str]]], contract: dict,
) -> tuple[str, list[dict]]:
    """Check null_strategy=forbid columns have no null/empty values."""
    findings = []
    checks = 0
    for ot in contract.get("object_type_mappings", []):
        tbl = ot["source_table"]
        rows = data.get(tbl)
        if rows is None:
            continue
        for cm in ot.get("column_mappings", []):
            if cm.get("null_strategy") != "forbid":
                continue
            col = cm["source_column"]
            checks += len(rows)
            for row in rows:
                val = row.get(col, "")
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    findings.append({
                        "rule_id": "required_field",
                        "status": "FAIL",
                        "table": tbl,
                        "column": col,
                        "row": row.get("__row__"),
                        "primary_key": _row_pk(row, tbl, data, _load_manifest(contract)),
                        "message": (
                            f"Column '{col}' has null_strategy=forbid "
                            f"but value is null/empty"
                        ),
                        "evidence": {
                            "column": col,
                            "null_strategy": "forbid",
                            "value_null": True,
                        },
                    })
    status = "PASS" if not findings else "FAIL"
    return status, {"rule_id": "required_field",
                    "rule_name": "Required Field Non-Null",
                    "status": status, "checks_performed": checks,
                    "violations_found": len(findings),
                    "findings": findings}


def _check_pk_unique(
    data: dict[str, list[dict[str, str]]], manifest: dict,
) -> tuple[str, list[dict]]:
    """Check primary keys are unique and non-null."""
    findings = []
    checks = 0
    for t in manifest.get("tables", []):
        tbl = t["table_name"]
        rows = data.get(tbl)
        if rows is None:
            continue
        pk_cols = t.get("primary_key", [])
        if not pk_cols:
            continue
        checks += len(rows)
        seen: dict[tuple, int] = {}
        for row in rows:
            pk_val = tuple(row.get(c, "") for c in pk_cols)
            if any(v is None or v.strip() == "" for v in pk_val):
                findings.append({
                    "rule_id": "pk_unique",
                    "status": "FAIL",
                    "table": tbl,
                    "column": ",".join(pk_cols),
                    "row": row.get("__row__"),
                    "primary_key": {c: row.get(c) for c in pk_cols},
                    "message": (
                        f"Primary key has null/empty value in column(s) "
                        f"{pk_cols}"
                    ),
                    "evidence": {"pk_columns": pk_cols, "value_null": True},
                })
            else:
                if pk_val in seen:
                    findings.append({
                        "rule_id": "pk_unique",
                        "status": "FAIL",
                        "table": tbl,
                        "column": ",".join(pk_cols),
                        "row": row.get("__row__"),
                        "primary_key": {c: row.get(c) for c in pk_cols},
                        "message": (
                            f"Duplicate primary key (first seen at row "
                            f"{seen[pk_val]})"
                        ),
                        "evidence": {
                            "pk_columns": pk_cols,
                            "duplicate_value": list(pk_val),
                            "first_row": seen[pk_val],
                        },
                    })
                else:
                    seen[pk_val] = int(row.get("__row__", "0"))
    status = "PASS" if not findings else "FAIL"
    return status, {"rule_id": "pk_unique",
                    "rule_name": "Primary Key Unique",
                    "status": status, "checks_performed": checks,
                    "violations_found": len(findings),
                    "findings": findings}


def _check_fk_integrity(
    data: dict[str, list[dict[str, str]]], manifest: dict,
) -> tuple[str, list[dict]]:
    """Check foreign key values reference existing rows."""
    findings = []
    checks = 0
    for t in manifest.get("tables", []):
        tbl = t["table_name"]
        rows = data.get(tbl)
        if rows is None:
            continue
        for fk in t.get("foreign_keys", []):
            fk_cols = fk.get("columns", [])
            ref = fk.get("references", {})
            ref_table = ref.get("table")
            ref_cols = ref.get("columns", [])
            if not ref_table or not ref_cols:
                continue
            ref_rows = data.get(ref_table)
            if ref_rows is None:
                continue
            # Build set of valid FK targets
            ref_values: set[tuple] = set()
            for rr in ref_rows:
                ref_values.add(tuple(rr.get(c) for c in ref_cols))
            checks += len(rows)
            for row in rows:
                fk_val = tuple(row.get(c) for c in fk_cols)
                if any(v is None or v.strip() == "" for v in fk_val):
                    continue  # nullable FK, skip
                if fk_val not in ref_values:
                    findings.append({
                        "rule_id": "fk_integrity",
                        "status": "FAIL",
                        "table": tbl,
                        "column": ",".join(fk_cols),
                        "row": row.get("__row__"),
                        "primary_key": {c: row.get(c) for c in _pk_cols(manifest, tbl)},
                        "message": (
                            f"FK {','.join(fk_cols)}={list(fk_val)} "
                            f"not found in {ref_table}.{','.join(ref_cols)}"
                        ),
                        "evidence": {
                            "fk_columns": fk_cols,
                            "fk_value": list(fk_val),
                            "referenced_table": ref_table,
                            "referenced_columns": ref_cols,
                        },
                    })
    status = "PASS" if not findings else "FAIL"
    return status, {"rule_id": "fk_integrity",
                    "rule_name": "Foreign Key Integrity",
                    "status": status, "checks_performed": checks,
                    "violations_found": len(findings),
                    "findings": findings}


def _check_enum_allowed(
    data: dict[str, list[dict[str, str]]],
) -> tuple[str, list[dict]]:
    """Check enum columns contain only allowed values."""
    findings = []
    checks = 0
    for key, allowed in ENUM_ALLOWED_MAP.items():
        tbl, col = key.split(".", 1)
        rows = data.get(tbl)
        if rows is None:
            continue
        checks += len(rows)
        for row in rows:
            val = row.get(col, "")
            if val is None or val.strip() == "":
                continue  # nullable, not an enum violation here
            if val.strip() not in allowed:
                findings.append({
                    "rule_id": "enum_allowed",
                    "status": "FAIL",
                    "table": tbl,
                    "column": col,
                    "row": row.get("__row__"),
                    "primary_key": {c: row.get(c) for c in _pk_cols(
                        _load_manifest_from_data(data), tbl
                    )} if _load_manifest_from_data(data) else {},
                    "message": (
                        f"Value '{val}' not in allowed set: "
                        f"{sorted(allowed)[:10]}"
                    ),
                    "evidence": {
                        "column": col,
                        "value": val,
                        "allowed_values": sorted(allowed),
                    },
                })
    status = "PASS" if not findings else "FAIL"
    return status, {"rule_id": "enum_allowed",
                    "rule_name": "Enum Allowed Values",
                    "status": status, "checks_performed": checks,
                    "violations_found": len(findings),
                    "findings": findings}


def _check_numeric_range(
    data: dict[str, list[dict[str, str]]],
) -> tuple[str, list[dict]]:
    """Check numeric columns for non-negative values."""
    findings = []
    checks = 0
    for key in sorted(NUMERIC_NON_NEGATIVE):
        tbl, col = key.split(".", 1)
        rows = data.get(tbl)
        if rows is None:
            continue
        checks += len(rows)
        for row in rows:
            val = row.get(col, "")
            if val is None or val.strip() == "":
                continue
            try:
                fv = float(val)
                if fv < 0:
                    findings.append({
                        "rule_id": "numeric_range",
                        "status": "FAIL",
                        "table": tbl,
                        "column": col,
                        "row": row.get("__row__"),
                        "primary_key": {},
                        "message": (
                            f"Column '{col}' has negative value: {fv}"
                        ),
                        "evidence": {
                            "column": col,
                            "value": fv,
                            "expected": ">= 0",
                        },
                    })
            except ValueError:
                pass  # non-numeric, skip
    status = "PASS" if not findings else "FAIL"
    return status, {"rule_id": "numeric_range",
                    "rule_name": "Numeric Range (Non-Negative)",
                    "status": status, "checks_performed": checks,
                    "violations_found": len(findings),
                    "findings": findings}


def _check_date_order(
    data: dict[str, list[dict[str, str]]],
) -> tuple[str, list[dict]]:
    """Check date columns where start must be <= end."""
    findings = []
    checks = 0
    for tbl, start_col, end_col, allow_null_end in DATE_ORDER_PAIRS:
        rows = data.get(tbl)
        if rows is None:
            continue
        checks += len(rows)
        for row in rows:
            start_val = row.get(start_col)
            end_val = row.get(end_col)
            start_dt = _parse_date(start_val)
            end_dt = _parse_date(end_val)
            if start_dt is None:
                continue  # can't compare if start is unparseable
            if end_dt is None:
                if allow_null_end:
                    continue  # null end is allowed
                else:
                    findings.append({
                        "rule_id": "date_order",
                        "status": "FAIL",
                        "table": tbl,
                        "column": f"{start_col} <= {end_col}",
                        "row": row.get("__row__"),
                        "primary_key": {},
                        "message": (
                            f"'{end_col}' is null/empty but "
                            f"null end is not allowed"
                        ),
                        "evidence": {
                            "start_column": start_col,
                            "end_column": end_col,
                            "start_value": start_val,
                            "end_value": end_val,
                        },
                    })
                    continue
            if start_dt > end_dt:
                findings.append({
                    "rule_id": "date_order",
                    "status": "FAIL",
                    "table": tbl,
                    "column": f"{start_col} <= {end_col}",
                    "row": row.get("__row__"),
                    "primary_key": {},
                    "message": (
                        f"'{start_col}' ({start_val}) > "
                        f"'{end_col}' ({end_val})"
                    ),
                    "evidence": {
                        "start_column": start_col,
                        "end_column": end_col,
                        "start_value": start_val,
                        "end_value": end_val,
                    },
                })
    status = "PASS" if not findings else "FAIL"
    return status, {"rule_id": "date_order",
                    "rule_name": "Date Order (Start <= End)",
                    "status": status, "checks_performed": checks,
                    "violations_found": len(findings),
                    "findings": findings}


def _check_derived_class(
    data: dict[str, list[dict[str, str]]],
) -> tuple[str, list[dict]]:
    """Identify derived/high-value entities (INFO only)."""
    findings = []
    checks = 0
    for rule in DERIVED_CLASS_RULES:
        tbl = rule["table"]
        rows = data.get(tbl)
        if rows is None:
            continue
        checks += len(rows)
        for row in rows:
            try:
                if rule["condition"](row):
                    findings.append({
                        "rule_id": "derived_class",
                        "status": "INFO",
                        "table": tbl,
                        "column": None,
                        "row": row.get("__row__"),
                        "primary_key": {},
                        "message": (
                            f"Entity classified as '{rule['class_name']}': "
                            f"{rule['description']}"
                        ),
                        "evidence": {
                            "derived_class": rule["class_name"],
                            "description": rule["description"],
                        },
                    })
            except (ValueError, TypeError, ZeroDivisionError):
                pass  # skip malformed rows in derived checks
    status = "PASS"  # derived_class is always INFO, never FAIL
    return status, {"rule_id": "derived_class",
                    "rule_name": "Derived Class Identification",
                    "status": status, "checks_performed": checks,
                    "entities_classified": len(findings),
                    "findings": findings}


def _check_row_count_range(
    data: dict[str, list[dict[str, str]]], manifest: dict,
) -> tuple[str, list[dict]]:
    """Check each table has at least 1 row."""
    findings = []
    checks = 0
    for t in manifest.get("tables", []):
        tbl = t["table_name"]
        rows = data.get(tbl)
        checks += 1
        count = len(rows) if rows else 0
        if count == 0:
            findings.append({
                "rule_id": "row_count_range",
                "status": "FAIL",
                "table": tbl,
                "column": None,
                "row": None,
                "primary_key": {},
                "message": f"Table '{tbl}' has 0 rows",
                "evidence": {"table": tbl, "row_count": 0},
            })
    status = "PASS" if not findings else "FAIL"
    return status, {"rule_id": "row_count_range",
                    "rule_name": "Row Count Range",
                    "status": status, "checks_performed": checks,
                    "violations_found": len(findings),
                    "findings": findings}


# ── Shared helpers for _row_pk ───────────────────────────────────────────────

_MANIFEST_CACHE: dict[str, dict] = {}


def _load_manifest_from_data(
    data: dict[str, list[dict[str, str]]],
) -> dict:
    """Minimal fallback — returns empty manifest. Used only when manifest
    is not directly available to _row_pk."""
    return {}


def _load_manifest(contract: dict) -> dict:
    """Not used at runtime; provided for caller compatibility."""
    return {}


def _row_pk(
    row: dict[str, str], table: str,
    data: dict[str, list[dict[str, str]]],
    manifest: dict,
) -> dict[str, str]:
    """Extract primary key values from a row."""
    pk_cols = _pk_cols(manifest, table)
    return {c: row.get(c, "") for c in pk_cols} if pk_cols else {}


# ── Orchestration ────────────────────────────────────────────────────────────


def _make_finding_id(prefix: str, idx: int) -> str:
    return f"{prefix}-{idx:04d}"


def _assign_finding_ids(rule_results: list[dict]) -> list[dict]:
    """Assign stable finding IDs to each finding."""
    for rule in rule_results:
        for i, f in enumerate(rule.get("findings", []), 1):
            f["finding_id"] = _make_finding_id(rule["rule_id"], i)
    return rule_results


def validate_business_rules(
    data_dir: Path,
    manifest: dict,
    contract: dict,
    data: dict[str, list[dict[str, str]]],
) -> dict:
    """Run all business rule checks and return the report dict."""
    rule_results = []

    # Run each rule
    for check_fn in [
        (_check_required_field, (data, contract)),
        (_check_pk_unique, (data, manifest)),
        (_check_fk_integrity, (data, manifest)),
        (_check_enum_allowed, (data,)),
        (_check_numeric_range, (data,)),
        (_check_date_order, (data,)),
        (_check_derived_class, (data,)),
        (_check_row_count_range, (data, manifest)),
    ]:
        fn, args = check_fn
        status, result = fn(*args)
        rule_results.append(result)

    # Assign finding IDs
    rule_results = _assign_finding_ids(rule_results)

    # Compute summary
    total = sum(r["checks_performed"] for r in rule_results)
    passed = sum(1 for r in rule_results if r["status"] == "PASS")
    failed = sum(1 for r in rule_results if r["status"] == "FAIL")
    warned = sum(1 for r in rule_results if r["status"] == "WARN")

    all_findings = []
    for r in rule_results:
        all_findings.extend(r.get("findings", []))

    return {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_pack": manifest.get("data_pack", "unknown"),
        "source_manifest": "manifest.json",
        "source_mapping_contract": "mapping_contract.json",
        "summary": {
            "total_rules": len(rule_results),
            "rules_passed": passed,
            "rules_warned": warned,
            "rules_failed": failed,
            "total_checks": total,
            "total_findings": len(all_findings),
        },
        "rule_results": rule_results,
        "findings": all_findings,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_governance_issues": False,
        },
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate business rules against a manufacturing data pack",
    )
    parser.add_argument(
        "--data-pack", type=Path, required=True,
        help="Path to manufacturing data pack directory",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path for rule_validation_report.json "
             "(default: <data-pack>/rule_validation_report.json)",
    )
    parser.add_argument(
        "--fail-on-warn", action="store_true",
        help="Treat WARN as failure (exit 1)",
    )
    args = parser.parse_args()

    data_dir = args.data_pack
    manifest_path = data_dir / "manifest.json"
    contract_path = data_dir / "mapping_contract.json"

    if not manifest_path.is_file():
        print(f"ERROR: manifest.json not found in {data_dir}", file=sys.stderr)
        return 1
    if not contract_path.is_file():
        print(f"ERROR: mapping_contract.json not found in {data_dir}. "
              f"Run generate_mapping_contract.py first.", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    print("=== Business Rule Validation (Phase 19.4) ===\n")
    print(f"Data pack: {data_dir}")
    print(f"Tables: {len(manifest.get('tables', []))}")

    # Load all CSV data
    data: dict[str, list[dict[str, str]]] = {}
    for t in manifest.get("tables", []):
        csv_path = data_dir / t["csv_file"]
        if csv_path.is_file():
            data[t["table_name"]] = _read_csv_rows(csv_path)

    report = validate_business_rules(data_dir, manifest, contract, data)

    # Print summary
    s = report["summary"]
    print(f"\nRules: {s['total_rules']}  "
          f"PASS: {s['rules_passed']}  "
          f"WARN: {s['rules_warned']}  "
          f"FAIL: {s['rules_failed']}")
    print(f"Checks: {s['total_checks']:,}  "
          f"Findings: {s['total_findings']}")

    for r in report["rule_results"]:
        flag = "PASS" if r["status"] == "PASS" else r["status"]
        extra = ""
        if r["rule_id"] == "derived_class":
            extra = f" ({r.get('entities_classified', 0)} classified)"
        print(f"  [{flag}] {r['rule_name']}{extra}"
              + (f" — {r['violations_found']} violations"
                 if r.get('violations_found') else ""))

    # Write report
    output_path = args.output or (data_dir / "rule_validation_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  [OK] Report -> {output_path}")

    # Determine exit code
    has_fail = any(r["status"] == "FAIL" for r in report["rule_results"])
    has_warn = any(r["status"] == "WARN" for r in report["rule_results"])

    if has_fail:
        print("\nResult: FAIL")
        return 1
    elif has_warn and args.fail_on_warn:
        print("\nResult: FAIL (--fail-on-warn)")
        return 1
    elif has_warn:
        print("\nResult: WARN (use --fail-on-warn to treat as failure)")
        return 0
    else:
        print("\nResult: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
