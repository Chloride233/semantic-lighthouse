"""Generate a Mapping Contract from a manufacturing data pack manifest.

Produces mapping_contract.json — an offline artifact that declares how each
CSV source column maps to an Ontology business property.  Deterministic
rules + generator metadata only; no LLM, no human interaction, no DB.

Usage:
  .venv/Scripts/python scripts/generate_mapping_contract.py \\
      --data-pack .tmp/phase19-manufacturing

  # Custom output path
  .venv/Scripts/python scripts/generate_mapping_contract.py \\
      --data-pack .tmp/phase19-manufacturing \\
      --output .tmp/my-contract.json

Dependencies: stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CONTRACT_VERSION = "1.0"

# ── Controlled vocabularies ──────────────────────────────────────────────────

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

# ── Deterministic table schemas ─────────────────────────────────────────────
#
# Each entry maps a table name to:
#   - object_type: the Ontology object type name
#   - description: short business description
#   - columns: ordered list of column mappings
#
# Columns that exist in the CSV but lack an explicit mapping are omitted
# from the contract (v1 rule: only explicit columns are declared).
# ─────────────────────────────────────────────────────────────────────────────

TABLE_SCHEMAS: dict[str, dict] = {
    "suppliers": {
        "object_type": "supplier",
        "description": "Raw material and component supplier",
        "columns": [
            ("supplier_id",   "supplier_id",   "string", "primary_key",  "forbid"),
            ("supplier_name", "supplier_name", "string", "label",        "forbid"),
            ("supplier_code", "supplier_code", "string", "identifier",   "forbid"),
            ("country",       "country",       "enum",   "category",     "forbid"),
            ("lead_time_days","lead_time_days","int",    "measure",      "forbid"),
            ("min_order_qty", "min_order_qty", "int",    "measure",      "forbid"),
            ("quality_rating","quality_rating","float",  "measure",      "forbid"),
            ("is_active",     "is_active",     "bool",   "status_flag",  "forbid"),
            ("created_at",    "created_at",    "date",   "date_field",   "forbid"),
        ],
    },
    "materials": {
        "object_type": "material",
        "description": "Raw material, component, or sub-assembly",
        "columns": [
            ("material_id",      "material_id",      "string", "primary_key",  "forbid"),
            ("material_name",    "material_name",    "string", "label",        "forbid"),
            ("material_code",    "material_code",    "string", "identifier",   "forbid"),
            ("supplier_id",      "supplier_id",      "string", "foreign_key",  "forbid"),
            ("unit_of_measure",  "unit_of_measure",  "enum",   "category",     "forbid"),
            ("unit_cost",        "unit_cost",        "float",  "measure",      "forbid"),
            ("lead_time_days",   "lead_time_days",   "int",    "measure",      "forbid"),
            ("safety_stock_qty", "safety_stock_qty", "float",  "measure",      "forbid"),
            ("reorder_point",    "reorder_point",    "float",  "measure",      "forbid"),
            ("abc_class",        "abc_class",        "enum",   "category",     "forbid"),
            ("is_batch_tracked", "is_batch_tracked", "bool",   "status_flag",  "forbid"),
        ],
    },
    "products": {
        "object_type": "product",
        "description": "Finished product with family, revision, and cost",
        "columns": [
            ("product_id",      "product_id",      "string", "primary_key",  "forbid"),
            ("product_name",    "product_name",    "string", "label",        "forbid"),
            ("product_code",    "product_code",    "string", "identifier",   "forbid"),
            ("product_family",  "product_family",  "enum",   "category",     "forbid"),
            ("revision",        "revision",        "string", "identifier",   "forbid"),
            ("unit_cost",       "unit_cost",       "float",  "measure",      "forbid"),
            ("unit_price",      "unit_price",      "float",  "measure",      "forbid"),
            ("lead_time_days",  "lead_time_days",  "int",    "measure",      "forbid"),
            ("min_lot_size",    "min_lot_size",    "int",    "measure",      "forbid"),
            ("is_make_to_order","is_make_to_order","bool",   "status_flag",  "forbid"),
            ("created_at",      "created_at",      "date",   "date_field",   "forbid"),
        ],
    },
    "work_centers": {
        "object_type": "work_center",
        "description": "Production work center / line with capacity and cost",
        "columns": [
            ("work_center_id",       "work_center_id",       "string", "primary_key",  "forbid"),
            ("work_center_name",     "work_center_name",     "string", "label",        "forbid"),
            ("work_center_code",     "work_center_code",     "string", "identifier",   "forbid"),
            ("work_center_type",     "work_center_type",     "enum",   "category",     "forbid"),
            ("hourly_rate",          "hourly_rate",          "float",  "measure",      "forbid"),
            ("capacity_hours_per_day","capacity_hours_per_day","int",   "measure",      "forbid"),
            ("setup_time_minutes",   "setup_time_minutes",   "int",    "measure",      "forbid"),
            ("efficiency_pct",       "efficiency_pct",       "float",  "measure",      "forbid"),
            ("is_bottleneck",        "is_bottleneck",        "bool",   "status_flag",  "forbid"),
        ],
    },
    "bills_of_materials": {
        "object_type": "bill_of_material",
        "description": "Bill of Materials item: product-material composition",
        "columns": [
            ("bom_id",           "bom_id",           "string", "primary_key",  "forbid"),
            ("product_id",       "product_id",       "string", "foreign_key",  "forbid"),
            ("material_id",      "material_id",      "string", "foreign_key",  "forbid"),
            ("sequence",         "sequence",         "int",    "measure",      "forbid"),
            ("quantity_per_unit","quantity_per_unit","float",  "measure",      "forbid"),
            ("scrap_rate_pct",   "scrap_rate_pct",   "float",  "measure",      "forbid"),
            ("is_critical",      "is_critical",      "bool",   "status_flag",  "forbid"),
        ],
    },
    "routings": {
        "object_type": "routing",
        "description": "Manufacturing routing: production recipe per product",
        "columns": [
            ("routing_id",   "routing_id",   "string", "primary_key",  "forbid"),
            ("product_id",   "product_id",   "string", "foreign_key",  "forbid"),
            ("routing_name", "routing_name", "string", "label",        "forbid"),
            ("revision",     "revision",     "string", "identifier",   "forbid"),
            ("is_active",    "is_active",    "bool",   "status_flag",  "forbid"),
        ],
    },
    "routing_operations": {
        "object_type": "routing_operation",
        "description": "Individual step within a manufacturing routing",
        "columns": [
            ("routing_operation_id", "routing_operation_id", "string", "primary_key",  "forbid"),
            ("routing_id",           "routing_id",           "string", "foreign_key",  "forbid"),
            ("sequence",             "sequence",             "int",    "measure",      "forbid"),
            ("operation_name",       "operation_name",       "enum",   "category",     "forbid"),
            ("work_center_id",       "work_center_id",       "string", "foreign_key",  "forbid"),
            ("standard_time_minutes","standard_time_minutes","float",  "measure",      "forbid"),
            ("setup_time_minutes",   "setup_time_minutes",   "float",  "measure",      "forbid"),
            ("sequence_dependent",   "sequence_dependent",   "bool",   "status_flag",  "forbid"),
        ],
    },
    "equipment": {
        "object_type": "equipment",
        "description": "Physical equipment asset with calibration and status",
        "columns": [
            ("equipment_id",     "equipment_id",     "string", "primary_key",  "forbid"),
            ("work_center_id",   "work_center_id",   "string", "foreign_key",  "forbid"),
            ("equipment_name",   "equipment_name",   "string", "label",        "forbid"),
            ("serial_number",    "serial_number",    "string", "identifier",   "forbid"),
            ("install_date",     "install_date",     "date",   "date_field",   "forbid"),
            ("last_calibration", "last_calibration", "date",   "date_field",   "allow"),
            ("status",           "status",           "enum",   "status_flag",  "forbid"),
        ],
    },
    "equipment_maintenance": {
        "object_type": "equipment_maintenance",
        "description": "Maintenance record per equipment asset",
        "columns": [
            ("maintenance_id",  "maintenance_id",  "string", "primary_key",  "forbid"),
            ("equipment_id",    "equipment_id",    "string", "foreign_key",  "forbid"),
            ("maintenance_type","maintenance_type","enum",   "category",     "forbid"),
            ("scheduled_date",  "scheduled_date",  "date",   "date_field",   "forbid"),
            ("completed_date",  "completed_date",  "date",   "date_field",   "allow"),
            ("downtime_hours",  "downtime_hours",  "float",  "measure",      "forbid"),
            ("cost",            "cost",            "float",  "measure",      "forbid"),
            ("technician",      "technician",      "string", "identifier",   "forbid"),
            ("status",          "status",          "enum",   "status_flag",  "forbid"),
        ],
    },
    "work_orders": {
        "object_type": "work_order",
        "description": "Production work order with status state machine",
        "columns": [
            ("work_order_id",      "work_order_id",      "string", "primary_key",  "forbid"),
            ("work_order_number",  "work_order_number",  "string", "identifier",   "forbid"),
            ("product_id",         "product_id",         "string", "foreign_key",  "forbid"),
            ("quantity_ordered",   "quantity_ordered",   "int",    "measure",      "forbid"),
            ("quantity_completed", "quantity_completed", "int",    "measure",      "forbid"),
            ("quantity_scrapped",  "quantity_scrapped",  "int",    "measure",      "forbid"),
            ("status",             "status",             "enum",   "status_flag",  "forbid"),
            ("priority",           "priority",           "enum",   "category",     "forbid"),
            ("scheduled_start",    "scheduled_start",    "datetime","date_field",  "forbid"),
            ("scheduled_end",      "scheduled_end",      "datetime","date_field",  "forbid"),
            ("actual_start",       "actual_start",       "datetime","date_field",  "allow"),
            ("actual_end",         "actual_end",         "datetime","date_field",  "allow"),
            ("released_by",        "released_by",        "string", "reference",    "allow"),
            ("rejection_reason",   "rejection_reason",   "string", "description",  "allow"),
            ("created_at",         "created_at",         "datetime","date_field",  "forbid"),
        ],
    },
    "work_order_operations": {
        "object_type": "work_order_operation",
        "description": "Per-work-order operation instance with timing",
        "columns": [
            ("wo_operation_id",     "wo_operation_id",     "string", "primary_key",  "forbid"),
            ("work_order_id",       "work_order_id",       "string", "foreign_key",  "forbid"),
            ("routing_operation_id","routing_operation_id","string", "foreign_key",  "forbid"),
            ("sequence",            "sequence",            "int",    "measure",      "forbid"),
            ("work_center_id",      "work_center_id",      "string", "foreign_key",  "forbid"),
            ("status",              "status",              "enum",   "status_flag",  "forbid"),
            ("planned_start",       "planned_start",       "datetime","date_field",  "forbid"),
            ("planned_end",         "planned_end",         "datetime","date_field",  "forbid"),
            ("actual_start",        "actual_start",        "datetime","date_field",  "allow"),
            ("actual_end",          "actual_end",          "datetime","date_field",  "allow"),
            ("setup_time_minutes",  "setup_time_minutes",  "float",  "measure",      "forbid"),
            ("run_time_minutes",    "run_time_minutes",    "float",  "measure",      "forbid"),
            ("operator_id",         "operator_id",         "string", "reference",    "forbid"),
        ],
    },
    "inventory": {
        "object_type": "inventory_record",
        "description": "Per-location inventory record for a material",
        "columns": [
            ("inventory_id",         "inventory_id",         "string", "primary_key",  "forbid"),
            ("material_id",          "material_id",          "string", "foreign_key",  "forbid"),
            ("location_code",        "location_code",        "string", "identifier",   "forbid"),
            ("location_name",        "location_name",        "string", "label",        "forbid"),
            ("quantity_on_hand",     "quantity_on_hand",     "float",  "measure",      "forbid"),
            ("quantity_allocated",   "quantity_allocated",   "float",  "measure",      "forbid"),
            ("quantity_on_order",    "quantity_on_order",    "float",  "measure",      "forbid"),
            ("last_count_date",      "last_count_date",      "date",   "date_field",   "allow"),
            ("last_transaction_date","last_transaction_date","date",   "date_field",   "allow"),
        ],
    },
    "quality_inspections": {
        "object_type": "quality_inspection",
        "description": "Quality inspection record: final or in-process check",
        "columns": [
            ("inspection_id",   "inspection_id",   "string", "primary_key",  "forbid"),
            ("work_order_id",   "work_order_id",   "string", "foreign_key",  "forbid"),
            ("wo_operation_id", "wo_operation_id", "string", "foreign_key",  "allow"),
            ("inspection_type", "inspection_type", "enum",   "category",     "forbid"),
            ("inspection_date", "inspection_date", "datetime","date_field",  "forbid"),
            ("result",          "result",          "enum",   "status_flag",  "forbid"),
            ("defect_count",    "defect_count",    "int",    "measure",      "forbid"),
            ("measured_value",  "measured_value",  "float",  "measure",      "forbid"),
            ("spec_lower",      "spec_lower",      "float",  "measure",      "forbid"),
            ("spec_upper",      "spec_upper",      "float",  "measure",      "forbid"),
            ("inspector_id",    "inspector_id",    "string", "reference",    "forbid"),
            ("notes",           "notes",           "string", "description",  "allow"),
        ],
    },
}

# ── Builder ─────────────────────────────────────────────────────────────────


def build_relationship_mappings(manifest: dict) -> list[dict]:
    """Derive relationship mappings from manifest foreign_keys + table schemas.

    Each FK in the manifest becomes a relationship_mapping entry.
    """
    relationships = []
    core_pilot_tables = {
        t["table_name"] for t in manifest.get("tables", []) if t.get("core_pilot")
    }

    for table_entry in manifest.get("tables", []):
        source_table = table_entry["table_name"]
        for fk in table_entry.get("foreign_keys", []):
            fk_cols = fk.get("columns", [])
            ref = fk.get("references", {})
            target_table = ref.get("table")
            target_cols = ref.get("columns", [])

            if not target_table or not fk_cols:
                continue

            # Build a readable relationship name
            source_obj = source_table.rstrip("s")
            target_obj = target_table.rstrip("s")
            rel_name = f"{source_obj}_to_{target_obj}"

            # Derive cardinality: if there's a UNIQUE constraint it's one_to_one,
            # otherwise default to many_to_one (child → parent direction)
            # v1: deterministic rule — FK on child table → many_to_one
            cardinality = "many_to_one"

            # Check if both sides are core_pilot
            both_core = (
                source_table in core_pilot_tables
                and target_table in core_pilot_tables
            )

            relationships.append({
                "relationship_name": rel_name,
                "source_table": source_table,
                "source_columns": fk_cols,
                "target_table": target_table,
                "target_columns": target_cols,
                "cardinality": cardinality,
                "core_pilot": both_core,
                "evidence_source": (
                    "manufacturing data pack manifest foreign_keys"
                ),
            })

    return relationships


def build_mapping_contract(manifest: dict) -> dict:
    """Build a complete mapping_contract from a manifest and TABLE_SCHEMAS."""
    core_pilot_tables = {
        t["table_name"] for t in manifest.get("tables", []) if t.get("core_pilot")
    }

    object_type_mappings = []
    evidence_source = "manufacturing data pack generator v1 — deterministic column schema"

    for table_entry in manifest.get("tables", []):
        tname = table_entry["table_name"]
        schema = TABLE_SCHEMAS.get(tname)
        if schema is None:
            print(f"  [WARN] No schema defined for table '{tname}', skipping")
            continue

        is_core = tname in core_pilot_tables

        column_mappings = []
        for (src_col, tgt_prop, val_type,
             sem_role, null_strat) in schema["columns"]:
            column_mappings.append({
                "source_column": src_col,
                "target_property": tgt_prop,
                "value_type": val_type,
                "semantic_role": sem_role,
                "null_strategy": null_strat,
                "evidence_source": evidence_source,
            })

        # Extract PK columns from manifest
        manifest_pk = table_entry.get("primary_key", [])

        object_type_mappings.append({
            "object_type": schema["object_type"],
            "source_table": tname,
            "description": schema["description"],
            "core_pilot": is_core,
            "primary_key": manifest_pk,
            "column_mappings": column_mappings,
        })

    relationship_mappings = build_relationship_mappings(manifest)

    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": "manifest.json",
        "data_pack": manifest.get("data_pack", "unknown"),
        "preset": manifest.get("preset", "unknown"),
        "seed": manifest.get("seed"),
        "object_type_count": len(object_type_mappings),
        "core_pilot_object_type_count": sum(
            1 for o in object_type_mappings if o["core_pilot"]
        ),
        "relationship_count": len(relationship_mappings),
        "core_pilot_relationship_count": sum(
            1 for r in relationship_mappings if r["core_pilot"]
        ),
        "object_type_mappings": object_type_mappings,
        "relationship_mappings": relationship_mappings,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Mapping Contract from manufacturing data pack",
    )
    parser.add_argument(
        "--data-pack", type=Path, required=True,
        help="Path to manufacturing data pack directory containing manifest.json",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path for mapping_contract.json (default: <data-pack>/mapping_contract.json)",
    )
    args = parser.parse_args()

    data_dir = args.data_pack
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        print(f"ERROR: manifest.json not found in {data_dir}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print(f"Generating mapping contract from: {data_dir}")
    print(f"  tables in manifest: {len(manifest.get('tables', []))}")
    print(f"  core_pilot: {manifest.get('core_pilot_table_count', '?')}")

    contract = build_mapping_contract(manifest)

    output_path = args.output or (data_dir / "mapping_contract.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2, ensure_ascii=False)

    print(f"  [OK] mapping_contract.json -> {output_path}")
    print(f"       object_types: {contract['object_type_count']} "
          f"({contract['core_pilot_object_type_count']} core_pilot)")
    print(f"       relationships: {contract['relationship_count']} "
          f"({contract['core_pilot_relationship_count']} core_pilot)")
    print(f"       contract_version: {CONTRACT_VERSION}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
