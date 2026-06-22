"""Validate a manufacturing data pack against the Phase 19.1 contract.

Usage:
  .venv/Scripts/python scripts/validate_manufacturing_data_pack.py <data-pack-dir>

Checks:
  1. All 13 tables present (CSV files exist)
  2. manifest.json exists with complete fields
  3. Per-table row_count matches actual CSV row count
  4. Primary key non-null and unique
  5. Foreign keys point to existing values
  6. core_pilot subset exists with >= 4 tables
  7. No obvious future dates or negative value anomalies

Exit 0 = PASS. Exit 1 = one or more checks FAIL.
Dependencies: stdlib only.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Expected 13-table schema (from generate_manufacturing_dataset.py) ─────

EXPECTED_TABLES = [
    "suppliers",
    "materials",
    "products",
    "work_centers",
    "bills_of_materials",
    "routings",
    "routing_operations",
    "equipment",
    "equipment_maintenance",
    "work_orders",
    "work_order_operations",
    "inventory",
    "quality_inspections",
]

MIN_CORE_PILOT_TABLES = 4

# Columns that are expected to be non-negative
NON_NEGATIVE_COLUMNS: dict[str, list[str]] = {
    "suppliers": ["lead_time_days", "min_order_qty", "quality_rating"],
    "materials": ["unit_cost", "lead_time_days", "safety_stock_qty", "reorder_point"],
    "products": ["unit_cost", "unit_price", "lead_time_days", "min_lot_size"],
    "work_centers": ["hourly_rate", "capacity_hours_per_day", "setup_time_minutes",
                     "efficiency_pct"],
    "bills_of_materials": ["quantity_per_unit", "scrap_rate_pct"],
    "routing_operations": ["sequence", "standard_time_minutes", "setup_time_minutes"],
    "equipment_maintenance": ["downtime_hours", "cost"],
    "work_orders": ["quantity_ordered", "quantity_completed", "quantity_scrapped"],
    "work_order_operations": ["sequence", "setup_time_minutes", "run_time_minutes"],
    "inventory": ["quantity_on_hand", "quantity_allocated", "quantity_on_order"],
    "quality_inspections": ["defect_count", "measured_value",
                            "spec_lower", "spec_upper"],
}

# Date-like columns (Y-m-d or ISO format) to check for future anomalies
DATE_COLUMNS: dict[str, list[str]] = {
    "suppliers": ["created_at"],
    "products": ["created_at"],
    "equipment": ["install_date", "last_calibration"],
    "equipment_maintenance": ["scheduled_date", "completed_date"],
    "work_orders": ["scheduled_start", "scheduled_end",
                    "actual_start", "actual_end", "created_at"],
    "work_order_operations": ["planned_start", "planned_end",
                              "actual_start", "actual_end"],
    "inventory": ["last_count_date", "last_transaction_date"],
    "quality_inspections": ["inspection_date"],
}


# ── Validator ──────────────────────────────────────────────────────────────


class ValidationResult:
    """Collects findings and emits a final PASS/FAIL verdict."""

    def __init__(self) -> None:
        self.findings: list[tuple[str, str]] = []  # (level, message)
        self.stats: dict[str, Any] = {}

    def ok(self, msg: str) -> None:
        self.findings.append(("OK", msg))

    def fail(self, msg: str) -> None:
        self.findings.append(("FAIL", msg))

    def warn(self, msg: str) -> None:
        self.findings.append(("WARN", msg))

    @property
    def has_fail(self) -> bool:
        return any(level == "FAIL" for level, _ in self.findings)

    def summary(self) -> str:
        n_ok = sum(1 for level, _ in self.findings if level == "OK")
        n_fail = sum(1 for level, _ in self.findings if level == "FAIL")
        n_warn = sum(1 for level, _ in self.findings if level == "WARN")
        lines: list[str] = []
        for level, msg in self.findings:
            prefix = f"  [{level}]" if level != "OK" else "  [OK] "
            lines.append(f"{prefix} {msg}")
        lines.append("")
        lines.append(f"  OK: {n_ok}  FAIL: {n_fail}  WARN: {n_warn}")
        return "\n".join(lines)


def _actually_read_csv(csv_path: Path) -> list[dict[str, str]]:
    """Real CSV reader, used at runtime."""
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _parse_date(val: str) -> datetime | None:
    """Try to parse a date/datetime string. Returns None on failure."""
    if not val or not val.strip():
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S+00:00"):
        try:
            dt = datetime.strptime(val.strip(), fmt)
            if fmt.endswith("%z") or "+00:00" in fmt:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def validate_data_pack(data_dir: Path) -> ValidationResult:
    """Run all validation checks on a manufacturing data pack directory."""
    r = ValidationResult()

    if not data_dir.is_dir():
        r.fail(f"Data pack directory not found: {data_dir}")
        return r

    # ── 1. Manifest exists and has complete fields ─────────────────────
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        r.fail("manifest.json not found")
        return r

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        r.fail(f"manifest.json is not valid JSON: {e}")
        return r

    required_manifest_fields = [
        "manifest_version", "data_pack", "generator", "seed",
        "generated_at", "table_count", "tables",
    ]
    for field in required_manifest_fields:
        if field not in manifest:
            r.fail(f"manifest.json missing required field: {field}")

    if manifest.get("manifest_version") != "1.0":
        r.fail(f"Unsupported manifest_version: {manifest.get('manifest_version')}")

    manifest_tables = manifest.get("tables", [])
    if not isinstance(manifest_tables, list) or len(manifest_tables) == 0:
        r.fail("manifest.tables is empty or not a list")
    else:
        # Check each table entry has required fields
        required_table_fields = [
            "table_name", "csv_file", "row_count", "primary_key",
            "foreign_keys", "core_pilot", "business_meaning",
        ]
        for t in manifest_tables:
            for rf in required_table_fields:
                if rf not in t:
                    r.fail(
                        f"Table '{t.get('table_name', '?')}' missing "
                        f"field '{rf}' in manifest"
                    )

    r.ok(f"manifest.json loaded: {manifest.get('data_pack')} v"
         f"{manifest.get('manifest_version')}, "
         f"{len(manifest_tables)} tables declared")

    # ── 2. All 13 tables present ───────────────────────────────────────
    manifest_table_names = {t["table_name"] for t in manifest_tables}
    expected_set = set(EXPECTED_TABLES)

    for tname in sorted(expected_set):
        csv_file = data_dir / f"{tname}.csv"
        if csv_file.is_file():
            r.ok(f"CSV present: {tname}.csv")
        else:
            r.fail(f"Missing CSV: {tname}.csv")

    extra_in_manifest = manifest_table_names - expected_set
    if extra_in_manifest:
        r.warn(f"Tables in manifest but not in expected 13: "
               f"{', '.join(sorted(extra_in_manifest))}")

    # ── 3. Per-table row_count matches CSV ─────────────────────────────
    csv_data: dict[str, list[dict[str, str]]] = {}
    for t in manifest_tables:
        tname = t["table_name"]
        csv_path = data_dir / t["csv_file"]
        if not csv_path.is_file():
            continue
        rows = _actually_read_csv(csv_path)
        csv_data[tname] = rows
        actual = len(rows)
        declared = t.get("row_count", -1)
        if actual == declared:
            r.ok(f"{tname}: row_count {actual} matches manifest")
        else:
            r.fail(
                f"{tname}: manifest row_count={declared} but CSV has "
                f"{actual} rows"
            )

    r.stats["total_csv_rows"] = sum(len(v) for v in csv_data.values())

    # ── 4. PK non-null and unique ──────────────────────────────────────
    for t in manifest_tables:
        tname = t["table_name"]
        rows = csv_data.get(tname)
        if rows is None:
            continue
        pk_cols = t.get("primary_key", [])
        if not pk_cols:
            r.warn(f"{tname}: no primary_key declared in manifest")
            continue

        pk_values: list[tuple] = []
        null_found = False
        for i, row in enumerate(rows, 1):
            pk_tuple = tuple(row.get(col) for col in pk_cols)
            if any(v is None or v.strip() == "" for v in pk_tuple):
                if not null_found:
                    r.fail(
                        f"{tname}: null/empty PK value at row {i} "
                        f"(columns: {pk_cols})"
                    )
                    null_found = True
            pk_values.append(pk_tuple)

        if not null_found:
            # Check uniqueness
            seen: set[tuple] = set()
            dupes: set[tuple] = set()
            for pv in pk_values:
                if pv in seen:
                    dupes.add(pv)
                seen.add(pv)
            if dupes:
                r.fail(
                    f"{tname}: duplicate PK values found: "
                    f"{len(dupes)} duplicate(s) "
                    f"(sample: {list(dupes)[:3]})"
                )
            else:
                r.ok(f"{tname}: PK unique ({len(seen)} rows)")

    # ── 5. FK referential integrity ────────────────────────────────────
    for t in manifest_tables:
        tname = t["table_name"]
        fks = t.get("foreign_keys", [])
        if not fks:
            continue
        rows = csv_data.get(tname)
        if not rows:
            continue

        for fk in fks:
            fk_cols = fk.get("columns", [])
            ref = fk.get("references", {})
            ref_table = ref.get("table")
            ref_cols = ref.get("columns", [])

            if not ref_table or not ref_cols:
                continue

            ref_rows = csv_data.get(ref_table)
            if ref_rows is None:
                continue  # referenced table missing, reported above

            # Build set of valid FK target values
            ref_values: set[tuple] = set()
            for rr in ref_rows:
                ref_values.add(tuple(rr.get(c) for c in ref_cols))

            # Check each FK value exists in the referenced table
            missing_count = 0
            missing_samples: list[tuple] = []
            nullable_fk = False
            for i, row in enumerate(rows, 1):
                fk_val = tuple(row.get(c) for c in fk_cols)
                if any(v is None or v.strip() == "" for v in fk_val):
                    nullable_fk = True
                    continue
                if fk_val not in ref_values:
                    missing_count += 1
                    if len(missing_samples) < 3:
                        missing_samples.append(fk_val)

            if missing_count > 0:
                r.fail(
                    f"{tname}.{','.join(fk_cols)} -> "
                    f"{ref_table}.{','.join(ref_cols)}: "
                    f"{missing_count} FK value(s) not found "
                    f"(samples: {missing_samples})"
                )
            elif nullable_fk:
                r.ok(
                    f"{tname}.{','.join(fk_cols)} -> "
                    f"{ref_table}.{','.join(ref_cols)}: all non-null "
                    f"FKs valid (some nulls OK)"
                )
            else:
                r.ok(
                    f"{tname}.{','.join(fk_cols)} -> "
                    f"{ref_table}.{','.join(ref_cols)}: all valid"
                )

    # ── 6. core_pilot subset exists with >= MIN_CORE_PILOT_TABLES ─────
    core_tables = [t for t in manifest_tables if t.get("core_pilot")]
    core_count = len(core_tables)
    if core_count >= MIN_CORE_PILOT_TABLES:
        r.ok(
            f"core_pilot subset: {core_count} tables "
            f"(min {MIN_CORE_PILOT_TABLES}): "
            f"{', '.join(t['table_name'] for t in core_tables)}"
        )
    else:
        r.fail(
            f"core_pilot subset: only {core_count} tables, "
            f"minimum {MIN_CORE_PILOT_TABLES} required"
        )

    # ── 7. No future dates or negative values ──────────────────────────
    now_utc = datetime.now(tz=timezone.utc)
    future_buffer_days = 7  # allow small clock skew or near-future dates

    for t in manifest_tables:
        tname = t["table_name"]
        rows = csv_data.get(tname)
        if not rows:
            continue

        # Check future dates
        date_cols = DATE_COLUMNS.get(tname, [])
        for dc in date_cols:
            future_count = 0
            for i, row in enumerate(rows, 1):
                val = row.get(dc)
                dt = _parse_date(val)
                if dt is not None:
                    # Make naive datetimes timezone-aware for comparison
                    if dt.tzinfo is None:
                        dt_aware = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt_aware = dt
                    if dt_aware > now_utc + timedelta(
                        days=future_buffer_days
                    ):
                        future_count += 1
            if future_count > 0:
                r.warn(
                    f"{tname}.{dc}: {future_count} row(s) with future "
                    f"dates (> {future_buffer_days}d from now)"
                )

        # Check negative values
        neg_cols = NON_NEGATIVE_COLUMNS.get(tname, [])
        for nc in neg_cols:
            neg_count = 0
            neg_samples: list[str] = []
            for row in rows:
                val = row.get(nc, "")
                if val and val.strip():
                    try:
                        if float(val) < 0:
                            neg_count += 1
                            if len(neg_samples) < 3:
                                neg_samples.append(val)
                    except ValueError:
                        pass  # non-numeric, skip
            if neg_count > 0:
                r.fail(
                    f"{tname}.{nc}: {neg_count} negative value(s) "
                    f"(samples: {neg_samples})"
                )

    r.ok("anomaly scan complete (future dates, negative values)")

    return r


# ── CLI ────────────────────────────────────────────────────────────────────


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <data-pack-dir>", file=sys.stderr)
        return 2

    data_dir = Path(sys.argv[1])
    print("=== Manufacturing Data Pack Validator (Phase 19.1) ===\n")
    print("Data pack:", data_dir, "\n")

    result = validate_data_pack(data_dir)
    print(result.summary())

    if result.has_fail:
        print("\nResult: FAIL")
        return 1
    else:
        print("\nResult: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
