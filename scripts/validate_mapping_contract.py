"""Validate a Mapping Contract against the Phase 19.3 contract spec.

Usage:
  .venv/Scripts/python scripts/validate_mapping_contract.py <mapping_contract.json>
  .venv/Scripts/python scripts/validate_mapping_contract.py \\
      --data-pack .tmp/phase19-manufacturing \\
      --manifest manifest.json

When --data-pack is provided, cross-validates against the manifest
(CSV headers, PK/FK consistency). When only a contract path is given,
validates the contract JSON structure alone.

Exit 0 = PASS. Exit 1 = one or more checks FAIL.
Dependencies: stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# ── Controlled vocabularies (must match generate_mapping_contract.py) ──────

VALID_VALUE_TYPES = frozenset({
    "string", "int", "float", "date", "datetime", "bool", "enum",
})

VALID_SEMANTIC_ROLES = frozenset({
    "primary_key", "foreign_key", "identifier", "label", "measure",
    "status_flag", "date_field", "category", "enumeration",
    "description", "reference",
})

VALID_NULL_STRATEGIES = frozenset({
    "allow", "forbid", "default", "unknown",
})

MIN_CORE_PILOT_OBJECT_TYPES = 4


# ── Validation result ────────────────────────────────────────────────────────


class ValidationResult:
    def __init__(self) -> None:
        self.findings: list[tuple[str, str]] = []

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
        lines = []
        for level, msg in self.findings:
            prefix = f"  [{level}]" if level != "OK" else "  [OK] "
            lines.append(f"{prefix} {msg}")
        lines.append("")
        lines.append(f"  OK: {n_ok}  FAIL: {n_fail}  WARN: {n_warn}")
        return "\n".join(lines)


# ── Validator ────────────────────────────────────────────────────────────────


def _read_csv_headers(data_dir: Path, csv_file: str) -> set[str] | None:
    """Read CSV headers. Returns None if file missing."""
    csv_path = data_dir / csv_file
    if not csv_path.is_file():
        return None
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            return set(next(reader))
        except StopIteration:
            return set()


def validate_contract(
    contract: dict,
    manifest: dict | None = None,
    data_dir: Path | None = None,
) -> ValidationResult:
    """Validate a mapping contract."""
    r = ValidationResult()

    # ── 1. Top-level fields ────────────────────────────────────────────
    required_top = [
        "contract_version", "generated_at", "data_pack",
        "object_type_mappings", "relationship_mappings",
    ]
    for field in required_top:
        if field not in contract:
            r.fail(f"Missing required top-level field: {field}")

    if contract.get("contract_version") != "1.0":
        r.fail(
            f"Unsupported contract_version: "
            f"{contract.get('contract_version')}"
        )
    else:
        r.ok(f"contract_version: {contract['contract_version']}")

    obj_mappings = contract.get("object_type_mappings", [])
    if not isinstance(obj_mappings, list) or len(obj_mappings) == 0:
        r.fail("object_type_mappings is empty or not a list")
        return r

    rel_mappings = contract.get("relationship_mappings", [])
    if not isinstance(rel_mappings, list):
        r.fail("relationship_mappings is not a list")
        rel_mappings = []

    r.ok(
        f"Loaded: {len(obj_mappings)} object_types, "
        f"{len(rel_mappings)} relationships"
    )

    # ── 2. Core pilot object type count ────────────────────────────────
    core_obj_types = [o for o in obj_mappings if o.get("core_pilot")]
    if len(core_obj_types) >= MIN_CORE_PILOT_OBJECT_TYPES:
        r.ok(
            f"core_pilot object_types: {len(core_obj_types)} "
            f"(min {MIN_CORE_PILOT_OBJECT_TYPES})"
        )
    else:
        r.fail(
            f"core_pilot object_types: only {len(core_obj_types)}, "
            f"minimum {MIN_CORE_PILOT_OBJECT_TYPES} required"
        )

    # ── 3. Per-object-type validation ──────────────────────────────────
    for ot in obj_mappings:
        obj_name = ot.get("object_type", "?")
        tbl = ot.get("source_table", "?")

        # Required fields on each object type mapping
        for field in ("object_type", "source_table", "primary_key",
                      "column_mappings"):
            if field not in ot:
                r.fail(
                    f"Object type '{obj_name}': missing field '{field}'"
                )

        pk = ot.get("primary_key", [])
        if not pk:
            r.fail(f"Object type '{obj_name}': primary_key is empty")
        elif manifest is not None:
            # Cross-validate PK with manifest
            manifest_tables = {
                t["table_name"]: t for t in manifest.get("tables", [])
            }
            mt = manifest_tables.get(tbl)
            if mt and pk != mt.get("primary_key", []):
                r.fail(
                    f"Object type '{obj_name}': primary_key {pk} "
                    f"does not match manifest {mt.get('primary_key')}"
                )
            elif mt:
                r.ok(
                    f"'{obj_name}': primary_key {pk} matches manifest"
                )

        col_mappings = ot.get("column_mappings", [])
        if not isinstance(col_mappings, list) or len(col_mappings) == 0:
            r.fail(
                f"Object type '{obj_name}': column_mappings is empty"
            )
            continue

        # ── 3a. Column mapping field validation ──────────────────────
        has_pk_mapping = False
        for cm in col_mappings:
            src_col = cm.get("source_column", "?")
            prefix = f"'{obj_name}.{src_col}'"

            for field in ("source_column", "target_property", "value_type",
                          "semantic_role", "null_strategy", "evidence_source"):
                if field not in cm:
                    r.fail(f"{prefix}: missing field '{field}'")

            vt = cm.get("value_type", "")
            if vt and vt not in VALID_VALUE_TYPES:
                r.fail(
                    f"{prefix}: invalid value_type '{vt}' "
                    f"(allowed: {sorted(VALID_VALUE_TYPES)})"
                )

            sr = cm.get("semantic_role", "")
            if sr and sr not in VALID_SEMANTIC_ROLES:
                r.fail(
                    f"{prefix}: invalid semantic_role '{sr}' "
                    f"(allowed: {sorted(VALID_SEMANTIC_ROLES)})"
                )

            ns = cm.get("null_strategy", "")
            if ns and ns not in VALID_NULL_STRATEGIES:
                r.fail(
                    f"{prefix}: invalid null_strategy '{ns}' "
                    f"(allowed: {sorted(VALID_NULL_STRATEGIES)})"
                )

            es = cm.get("evidence_source", "")
            if not es or not es.strip():
                r.fail(f"{prefix}: evidence_source is empty")

            if sr == "primary_key":
                has_pk_mapping = True

        if not has_pk_mapping and pk:
            r.warn(
                f"'{obj_name}': no column with semantic_role=primary_key "
                f"(expected for PK {pk})"
            )

        # ── 3b. CSV header cross-validation ──────────────────────────
        if data_dir is not None:
            csv_headers = _read_csv_headers(
                data_dir, f"{tbl}.csv"
            )
            if csv_headers is None:
                r.warn(f"'{obj_name}': CSV file not found for cross-check")
            else:
                for cm in col_mappings:
                    src_col = cm.get("source_column", "")
                    if src_col and src_col not in csv_headers:
                        r.fail(
                            f"'{obj_name}.{src_col}': column not found "
                            f"in {tbl}.csv headers"
                        )
                # Check no important CSV columns are unmapped
                mapped_cols = {cm.get("source_column") for cm in col_mappings}
                unmapped = csv_headers - mapped_cols - {""}
                if unmapped:
                    r.warn(
                        f"'{obj_name}': {len(unmapped)} CSV column(s) "
                        f"not mapped: {sorted(unmapped)[:5]}"
                    )

    # ── 4. Relationship validation ────────────────────────────────────
    if manifest is not None:
        manifest_tables = {
            t["table_name"]: t for t in manifest.get("tables", [])
        }
        # Build manifest FK set
        manifest_fks: set[tuple] = set()
        for t in manifest.get("tables", []):
            for fk in t.get("foreign_keys", []):
                manifest_fks.add((
                    t["table_name"],
                    tuple(fk.get("columns", [])),
                    fk.get("references", {}).get("table"),
                    tuple(fk.get("references", {}).get("columns", [])),
                ))

        for rel in rel_mappings:
            rname = rel.get("relationship_name", "?")
            src_tbl = rel.get("source_table", "")
            src_cols = tuple(rel.get("source_columns", []))
            tgt_tbl = rel.get("target_table", "")
            tgt_cols = tuple(rel.get("target_columns", []))

            # Check required fields
            for field in ("relationship_name", "source_table",
                          "source_columns", "target_table",
                          "target_columns", "cardinality"):
                if field not in rel:
                    r.fail(
                        f"Relationship '{rname}': missing field '{field}'"
                    )

            # Cross-validate with manifest FKs
            rel_key = (src_tbl, src_cols, tgt_tbl, tgt_cols)
            if rel_key not in manifest_fks:
                r.fail(
                    f"Relationship '{rname}': "
                    f"{src_tbl}.{list(src_cols)} -> "
                    f"{tgt_tbl}.{list(tgt_cols)} "
                    f"not found in manifest foreign_keys"
                )
            else:
                r.ok(
                    f"Relationship '{rname}': matches manifest FK"
                )
    else:
        # Structural-only validation of relationships
        for rel in rel_mappings:
            rname = rel.get("relationship_name", "?")
            for field in ("relationship_name", "source_table",
                          "source_columns", "target_table",
                          "target_columns", "cardinality"):
                if field not in rel:
                    r.fail(
                        f"Relationship '{rname}': missing field '{field}'"
                    )
        if rel_mappings:
            r.ok(f"{len(rel_mappings)} relationships structurally valid")

    r.ok("validation complete")
    return r


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Mapping Contract (Phase 19.3)",
    )
    parser.add_argument(
        "contract_path", type=Path, nargs="?",
        help="Path to mapping_contract.json",
    )
    parser.add_argument(
        "--data-pack", type=Path, default=None,
        help="Data pack directory for CSV header and manifest cross-validation",
    )
    parser.add_argument(
        "--manifest", type=str, default="manifest.json",
        help="Manifest filename within data-pack dir (default: manifest.json)",
    )
    args = parser.parse_args()

    if args.contract_path is None and args.data_pack is None:
        print(
            "ERROR: provide either <contract_path> or --data-pack",
            file=sys.stderr,
        )
        return 2

    # Resolve contract path
    if args.contract_path:
        contract_path = args.contract_path
    else:
        contract_path = args.data_pack / "mapping_contract.json"  # type: ignore[operator]

    if not contract_path.is_file():
        print(f"ERROR: contract not found: {contract_path}", file=sys.stderr)
        return 1

    print("=== Mapping Contract Validator (Phase 19.3) ===\n")
    print(f"Contract: {contract_path}")

    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    # Load manifest if data-pack provided
    manifest = None
    data_dir = None
    if args.data_pack:
        data_dir = args.data_pack
        manifest_path = data_dir / args.manifest
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            print(f"Manifest: {manifest_path}")
        else:
            print(f"Manifest not found at {manifest_path} — "
                  f"cross-validation skipped")
    print()

    result = validate_contract(contract, manifest, data_dir)
    print(result.summary())

    if result.has_fail:
        print("\nResult: FAIL")
        return 1
    else:
        print("\nResult: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
