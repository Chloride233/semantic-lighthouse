"""Map an AdventureWorks raw export into a Semantic CI manufacturing data pack.

The raw AdventureWorks export keeps source table names and columns.  Semantic CI
currently expects the Phase 19 manufacturing contract: 13 fixed CSV tables plus
manifest.json.  This adapter performs a deterministic offline projection from
the focused AdventureWorks export to that contract.

Example:
  .venv/Scripts/python scripts/map_adventureworks_to_semantic_pack.py \
      --input .tmp/adventureworks \
      --output .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_manufacturing_dataset import Config, ManufacturingGenerator  # noqa: E402


GENERATOR_VERSION = "1.0"
PRESET_NAME = "adventureworks_semantic_v1"

RAW_FILES = {
    "categories": "Production_ProductCategory.csv",
    "subcategories": "Production_ProductSubcategory.csv",
    "products": "Production_Product.csv",
    "work_orders": "Production_WorkOrder.csv",
    "work_order_routings": "Production_WorkOrderRouting.csv",
    "boms": "Production_BillOfMaterials.csv",
    "locations": "Production_Location.csv",
    "inventory": "Production_ProductInventory.csv",
    "vendors": "Purchasing_Vendor.csv",
    "product_vendors": "Purchasing_ProductVendor.csv",
}

TARGET_COLUMNS = {
    "suppliers": [
        "supplier_id",
        "supplier_name",
        "supplier_code",
        "country",
        "lead_time_days",
        "min_order_qty",
        "quality_rating",
        "is_active",
        "created_at",
    ],
    "materials": [
        "material_id",
        "material_name",
        "material_code",
        "supplier_id",
        "unit_of_measure",
        "unit_cost",
        "lead_time_days",
        "safety_stock_qty",
        "reorder_point",
        "abc_class",
        "is_batch_tracked",
    ],
    "products": [
        "product_id",
        "product_name",
        "product_code",
        "product_family",
        "revision",
        "unit_cost",
        "unit_price",
        "lead_time_days",
        "min_lot_size",
        "is_make_to_order",
        "created_at",
    ],
    "work_centers": [
        "work_center_id",
        "work_center_name",
        "work_center_code",
        "work_center_type",
        "hourly_rate",
        "capacity_hours_per_day",
        "setup_time_minutes",
        "efficiency_pct",
        "is_bottleneck",
    ],
    "bills_of_materials": [
        "bom_id",
        "product_id",
        "material_id",
        "sequence",
        "quantity_per_unit",
        "scrap_rate_pct",
        "is_critical",
    ],
    "routings": [
        "routing_id",
        "product_id",
        "routing_name",
        "revision",
        "is_active",
    ],
    "routing_operations": [
        "routing_operation_id",
        "routing_id",
        "sequence",
        "operation_name",
        "work_center_id",
        "standard_time_minutes",
        "setup_time_minutes",
        "sequence_dependent",
    ],
    "equipment": [
        "equipment_id",
        "work_center_id",
        "equipment_name",
        "serial_number",
        "install_date",
        "last_calibration",
        "status",
    ],
    "equipment_maintenance": [
        "maintenance_id",
        "equipment_id",
        "maintenance_type",
        "scheduled_date",
        "completed_date",
        "downtime_hours",
        "cost",
        "technician",
        "status",
    ],
    "work_orders": [
        "work_order_id",
        "work_order_number",
        "product_id",
        "quantity_ordered",
        "quantity_completed",
        "quantity_scrapped",
        "status",
        "priority",
        "scheduled_start",
        "scheduled_end",
        "actual_start",
        "actual_end",
        "released_by",
        "rejection_reason",
        "created_at",
    ],
    "work_order_operations": [
        "wo_operation_id",
        "work_order_id",
        "routing_operation_id",
        "sequence",
        "work_center_id",
        "status",
        "planned_start",
        "planned_end",
        "actual_start",
        "actual_end",
        "setup_time_minutes",
        "run_time_minutes",
        "operator_id",
    ],
    "inventory": [
        "inventory_id",
        "material_id",
        "location_code",
        "location_name",
        "quantity_on_hand",
        "quantity_allocated",
        "quantity_on_order",
        "last_count_date",
        "last_transaction_date",
    ],
    "quality_inspections": [
        "inspection_id",
        "work_order_id",
        "wo_operation_id",
        "inspection_type",
        "inspection_date",
        "result",
        "defect_count",
        "measured_value",
        "spec_lower",
        "spec_upper",
        "inspector_id",
        "notes",
    ],
}

PRODUCT_FAMILIES = [
    "Hydraulic",
    "Electronic",
    "Mechanical",
    "Structural",
    "Aerospace",
]
WORK_CENTER_TYPES = [
    "CNC Machining",
    "Manual Lathe",
    "Welding Station",
    "Assembly Line",
    "Quality Inspection",
    "Surface Treatment",
    "PCB Assembly",
    "Test & Calibration",
    "EDM Machining",
    "Powder Coating",
    "Heat Treatment",
    "Laser Cutting",
]
OPERATION_NAMES = [
    "Rough Cut",
    "Finish Cut",
    "Drill",
    "Tap",
    "Weld",
    "Assemble",
    "Inspect",
    "Test",
    "Deburr",
    "Polish",
    "Coat",
    "Heat Treat",
    "Solder",
    "Calibrate",
    "Pack",
    "Sandblast",
    "Press Fit",
    "Torque",
    "Seal",
    "Label",
]
INVENTORY_LOCATIONS = [
    ("WH-A", "Warehouse A"),
    ("WH-B", "Warehouse B"),
    ("PROD", "Production Floor"),
    ("RAW", "Raw Material Yard"),
    ("FG", "Finished Goods Store"),
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required AdventureWorks CSV missing: {path.name}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _index(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key, "")}


def _to_int(value: str | None, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _to_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _date(value: str | None, fallback: str = "2014-01-01") -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return fallback
    return dt.strftime("%Y-%m-%d")


def _datetime(value: str | None, fallback: str = "2014-01-01T00:00:00+00:00") -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return fallback
    return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    clean = value.strip().replace("Z", "+00:00")
    if "." in clean:
        prefix, suffix = clean.split(".", 1)
        tz_suffix = ""
        if "+" in suffix:
            tz_suffix = "+" + suffix.split("+", 1)[1]
        clean = prefix + tz_suffix
    if " " in clean:
        clean = clean.replace(" ", "T", 1)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def _add_minutes(value: str, minutes: int) -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return value
    return (dt + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _id(prefix: str, value: str | int) -> str:
    return f"{prefix}-{value}"


def _family_for_product(
    product: dict[str, str],
    subcategories_by_id: dict[str, dict[str, str]],
    categories_by_id: dict[str, dict[str, str]],
) -> str:
    subcategory = subcategories_by_id.get(product.get("ProductSubcategoryID", ""))
    category = categories_by_id.get(
        subcategory.get("ProductCategoryID", "") if subcategory else ""
    )
    name = f"{category.get('Name', '') if category else ''} {product.get('Name', '')}"
    lowered = name.lower()
    if "electric" in lowered or "cable" in lowered or "sensor" in lowered:
        return "Electronic"
    if "tube" in lowered or "frame" in lowered or "fork" in lowered:
        return "Structural"
    if "aero" in lowered:
        return "Aerospace"
    if "hydraulic" in lowered:
        return "Hydraulic"
    return "Mechanical"


def _unit(raw_unit: str | None) -> str:
    normalized = str(raw_unit or "").strip().upper()
    if normalized in {"KG", "G"}:
        return "kg"
    if normalized in {"M", "CM", "MM"}:
        return "m"
    if normalized in {"L"}:
        return "L"
    return "pcs"


def _abc_class(standard_cost: float) -> str:
    if standard_cost >= 1000:
        return "A"
    if standard_cost >= 100:
        return "B"
    return "C"


def _priority(order_qty: int) -> str:
    if order_qty >= 500:
        return "high"
    if order_qty >= 50:
        return "medium"
    return "low"


def _work_order_status(row: dict[str, str]) -> str:
    if row.get("EndDate"):
        return "completed"
    if row.get("StartDate"):
        return "in_progress"
    return "planned"


def _operation_status(row: dict[str, str]) -> str:
    if row.get("ActualEndDate"):
        return "completed"
    if row.get("ActualStartDate"):
        return "in_progress"
    return "pending"


def _build_suppliers(vendors: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for vendor in vendors:
        vendor_id = vendor["BusinessEntityID"]
        rating = 6 - max(1, min(5, _to_int(vendor.get("CreditRating"), 3)))
        rows.append({
            "supplier_id": _id("SUP", vendor_id),
            "supplier_name": vendor.get("Name") or f"Vendor {vendor_id}",
            "supplier_code": vendor.get("AccountNumber") or f"V-{vendor_id}",
            "country": "US",
            "lead_time_days": 7,
            "min_order_qty": 1,
            "quality_rating": round(float(rating), 1),
            "is_active": _truthy(vendor.get("ActiveFlag")),
            "created_at": _date(vendor.get("ModifiedDate")),
        })
    if not rows:
        rows.append({
            "supplier_id": "SUP-UNKNOWN",
            "supplier_name": "Unknown Supplier",
            "supplier_code": "UNKNOWN",
            "country": "US",
            "lead_time_days": 7,
            "min_order_qty": 1,
            "quality_rating": 3.0,
            "is_active": True,
            "created_at": "2014-01-01",
        })
    return rows


def _build_materials(
    products: list[dict[str, str]],
    product_vendors: list[dict[str, str]],
    suppliers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    supplier_by_product = {
        row["ProductID"]: row for row in product_vendors if row.get("ProductID")
    }
    fallback_supplier_id = suppliers[0]["supplier_id"]
    rows = []
    for product in products:
        product_id = product["ProductID"]
        pv = supplier_by_product.get(product_id)
        supplier_id = (
            _id("SUP", pv["BusinessEntityID"])
            if pv and pv.get("BusinessEntityID")
            else fallback_supplier_id
        )
        standard_cost = _to_float(product.get("StandardCost"))
        rows.append({
            "material_id": _id("MAT", product_id),
            "material_name": product.get("Name") or f"Material {product_id}",
            "material_code": product.get("ProductNumber") or f"M-{product_id}",
            "supplier_id": supplier_id,
            "unit_of_measure": _unit(pv.get("UnitMeasureCode") if pv else None),
            "unit_cost": round(standard_cost, 4),
            "lead_time_days": _to_int(
                pv.get("AverageLeadTime") if pv else None,
                _to_int(product.get("DaysToManufacture"), 1),
            ),
            "safety_stock_qty": _to_float(product.get("SafetyStockLevel")),
            "reorder_point": _to_float(product.get("ReorderPoint")),
            "abc_class": _abc_class(standard_cost),
            "is_batch_tracked": not _truthy(product.get("FinishedGoodsFlag")),
        })
    return rows


def _build_products(
    products: list[dict[str, str]],
    subcategories_by_id: dict[str, dict[str, str]],
    categories_by_id: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    for product in products:
        product_id = product["ProductID"]
        cost = _to_float(product.get("StandardCost"))
        price = _to_float(product.get("ListPrice"), cost)
        rows.append({
            "product_id": _id("PRD", product_id),
            "product_name": product.get("Name") or f"Product {product_id}",
            "product_code": product.get("ProductNumber") or f"P-{product_id}",
            "product_family": _family_for_product(
                product,
                subcategories_by_id,
                categories_by_id,
            ),
            "revision": "A",
            "unit_cost": round(cost, 2),
            "unit_price": round(price, 2),
            "lead_time_days": _to_int(product.get("DaysToManufacture"), 1),
            "min_lot_size": max(1, _to_int(product.get("ReorderPoint"), 1)),
            "is_make_to_order": _truthy(product.get("MakeFlag")),
            "created_at": _date(product.get("SellStartDate")),
        })
    return rows


def _build_work_centers(locations: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for idx, location in enumerate(locations):
        location_id = location["LocationID"]
        wc_type = WORK_CENTER_TYPES[idx % len(WORK_CENTER_TYPES)]
        rows.append({
            "work_center_id": _id("WC", location_id),
            "work_center_name": location.get("Name") or f"Location {location_id}",
            "work_center_code": f"AW-{location_id}",
            "work_center_type": wc_type,
            "hourly_rate": round(_to_float(location.get("CostRate"), 1.0), 2),
            "capacity_hours_per_day": 8,
            "setup_time_minutes": 15,
            "efficiency_pct": round(_to_float(location.get("Availability"), 90), 1),
            "is_bottleneck": _to_float(location.get("Availability"), 90) < 80,
        })
    return rows


def _build_boms(
    boms: list[dict[str, str]],
    product_ids: set[str],
    material_ids: set[str],
) -> list[dict[str, Any]]:
    rows = []
    sequence_by_product: dict[str, int] = {}
    for bom in boms:
        assembly_id = bom.get("ProductAssemblyID", "")
        component_id = bom.get("ComponentID", "")
        product_id = _id("PRD", assembly_id)
        material_id = _id("MAT", component_id)
        if product_id not in product_ids or material_id not in material_ids:
            continue
        sequence_by_product[product_id] = sequence_by_product.get(product_id, 0) + 1
        rows.append({
            "bom_id": _id("BOM", bom.get("BillOfMaterialsID") or len(rows) + 1),
            "product_id": product_id,
            "material_id": material_id,
            "sequence": sequence_by_product[product_id],
            "quantity_per_unit": max(0.001, _to_float(bom.get("PerAssemblyQty"), 1.0)),
            "scrap_rate_pct": 0.0,
            "is_critical": _to_int(bom.get("BOMLevel"), 1) <= 1,
        })
    return rows


def _build_routings_and_operations(
    routing_rows: list[dict[str, str]],
    products_by_id: dict[str, dict[str, str]],
    work_center_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str, str], str]]:
    product_ids = sorted({row["ProductID"] for row in routing_rows if row.get("ProductID")})
    routings = []
    for product_id in product_ids:
        product = products_by_id.get(product_id, {})
        routings.append({
            "routing_id": _id("RTG", product_id),
            "product_id": _id("PRD", product_id),
            "routing_name": f"Routing for {product.get('Name') or product_id}",
            "revision": "A",
            "is_active": True,
        })

    seen_ops: set[tuple[str, str, str]] = set()
    operation_id_by_key: dict[tuple[str, str, str], str] = {}
    operations = []
    for row in routing_rows:
        product_id = row.get("ProductID", "")
        sequence = str(_to_int(row.get("OperationSequence"), 1))
        location_id = row.get("LocationID", "")
        work_center_id = _id("WC", location_id)
        key = (product_id, sequence, location_id)
        if (
            not product_id
            or key in seen_ops
            or _id("PRD", product_id) not in {_id("PRD", p) for p in product_ids}
            or work_center_id not in work_center_ids
        ):
            continue
        seen_ops.add(key)
        operation_id = f"ROP-{product_id}-{sequence}-{location_id}"
        operation_id_by_key[key] = operation_id
        operations.append({
            "routing_operation_id": operation_id,
            "routing_id": _id("RTG", product_id),
            "sequence": _to_int(sequence, 1),
            "operation_name": OPERATION_NAMES[
                (max(1, _to_int(sequence, 1)) - 1) % len(OPERATION_NAMES)
            ],
            "work_center_id": work_center_id,
            "standard_time_minutes": round(
                max(1.0, _to_float(row.get("ActualResourceHrs"), 1.0) * 60),
                1,
            ),
            "setup_time_minutes": 15.0,
            "sequence_dependent": True,
        })
    return routings, operations, operation_id_by_key


def _build_equipment(work_centers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for idx, work_center in enumerate(work_centers, 1):
        status = "degraded" if work_center["is_bottleneck"] else "operational"
        rows.append({
            "equipment_id": _id("EQP", idx),
            "work_center_id": work_center["work_center_id"],
            "equipment_name": f"{work_center['work_center_type']} Asset",
            "serial_number": f"AW-EQP-{idx:05d}",
            "install_date": "2011-01-01",
            "last_calibration": "2014-01-01",
            "status": status,
        })
    return rows


def _build_maintenance(equipment: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for idx, item in enumerate(equipment, 1):
        rows.append({
            "maintenance_id": _id("MNT", idx),
            "equipment_id": item["equipment_id"],
            "maintenance_type": "calibration",
            "scheduled_date": "2014-01-01",
            "completed_date": "2014-01-02",
            "downtime_hours": 1.0,
            "cost": 100.0,
            "technician": f"TECH-{idx:03d}",
            "status": "completed",
        })
    return rows


def _build_work_orders(
    work_orders: list[dict[str, str]],
    product_ids: set[str],
    work_order_limit: int | None,
) -> list[dict[str, Any]]:
    rows = []
    for source in work_orders:
        if work_order_limit is not None and len(rows) >= work_order_limit:
            break
        product_id = _id("PRD", source.get("ProductID", ""))
        if product_id not in product_ids:
            continue
        order_qty = max(1, _to_int(source.get("OrderQty"), 1))
        scrapped_qty = max(0, _to_int(source.get("ScrappedQty"), 0))
        completed_qty = _to_int(source.get("StockedQty"), order_qty - scrapped_qty)
        status = _work_order_status(source)
        scheduled_start = _datetime(source.get("StartDate"))
        scheduled_end = _datetime(source.get("DueDate") or source.get("EndDate"))
        if scheduled_start > scheduled_end:
            scheduled_end = _add_minutes(scheduled_start, 60)
        actual_start = _datetime(source.get("StartDate")) if source.get("StartDate") else ""
        actual_end = _datetime(source.get("EndDate")) if source.get("EndDate") else ""
        rows.append({
            "work_order_id": _id("WO", source.get("WorkOrderID", len(rows) + 1)),
            "work_order_number": f"AW-WO-{source.get('WorkOrderID', len(rows) + 1)}",
            "product_id": product_id,
            "quantity_ordered": order_qty,
            "quantity_completed": max(0, completed_qty),
            "quantity_scrapped": scrapped_qty,
            "status": status,
            "priority": _priority(order_qty),
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "actual_start": actual_start,
            "actual_end": actual_end,
            "released_by": "adventureworks",
            "rejection_reason": "scrap recorded" if status == "rejected" else "",
            "created_at": _datetime(source.get("ModifiedDate") or source.get("StartDate")),
        })
    return rows


def _build_work_order_operations(
    routing_rows: list[dict[str, str]],
    work_order_ids: set[str],
    operation_id_by_key: dict[tuple[str, str, str], str],
) -> list[dict[str, Any]]:
    rows = []
    for source in routing_rows:
        work_order_id = _id("WO", source.get("WorkOrderID", ""))
        sequence = str(_to_int(source.get("OperationSequence"), 1))
        key = (source.get("ProductID", ""), sequence, source.get("LocationID", ""))
        routing_operation_id = operation_id_by_key.get(key)
        if work_order_id not in work_order_ids or not routing_operation_id:
            continue
        planned_start = _datetime(source.get("ScheduledStartDate"))
        planned_end = _datetime(source.get("ScheduledEndDate"))
        if planned_start > planned_end:
            planned_end = _add_minutes(planned_start, 60)
        actual_start = (
            _datetime(source.get("ActualStartDate"))
            if source.get("ActualStartDate")
            else ""
        )
        actual_end = (
            _datetime(source.get("ActualEndDate"))
            if source.get("ActualEndDate")
            else ""
        )
        rows.append({
            "wo_operation_id": f"WOO-{source.get('WorkOrderID')}-{sequence}",
            "work_order_id": work_order_id,
            "routing_operation_id": routing_operation_id,
            "sequence": _to_int(sequence, 1),
            "work_center_id": _id("WC", source.get("LocationID", "")),
            "status": _operation_status(source),
            "planned_start": planned_start,
            "planned_end": planned_end,
            "actual_start": actual_start,
            "actual_end": actual_end,
            "setup_time_minutes": 15.0,
            "run_time_minutes": round(
                max(0.0, _to_float(source.get("ActualResourceHrs"), 0.0) * 60),
                1,
            ),
            "operator_id": "AW-OPERATOR",
        })
    return rows


def _build_inventory(
    inventory: list[dict[str, str]],
    material_ids: set[str],
) -> list[dict[str, Any]]:
    rows = []
    for source in inventory:
        material_id = _id("MAT", source.get("ProductID", ""))
        if material_id not in material_ids:
            continue
        loc_code, loc_name = INVENTORY_LOCATIONS[
            _to_int(source.get("LocationID"), 0) % len(INVENTORY_LOCATIONS)
        ]
        on_hand = max(0.0, _to_float(source.get("Quantity"), 0.0))
        rows.append({
            "inventory_id": f"INV-{source.get('ProductID')}-{source.get('LocationID')}",
            "material_id": material_id,
            "location_code": loc_code,
            "location_name": loc_name,
            "quantity_on_hand": on_hand,
            "quantity_allocated": 0.0,
            "quantity_on_order": 0.0,
            "last_count_date": _date(source.get("ModifiedDate")),
            "last_transaction_date": _date(source.get("ModifiedDate")),
        })
    return rows


def _build_quality_inspections(
    work_orders: list[dict[str, Any]],
    work_order_operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    operation_by_work_order = {
        row["work_order_id"]: row for row in work_order_operations
    }
    rows = []
    for idx, work_order in enumerate(work_orders, 1):
        operation = operation_by_work_order.get(work_order["work_order_id"])
        if operation is None:
            continue
        defect_count = min(99, int(work_order["quantity_scrapped"]))
        result = "failed" if defect_count > 0 else "passed"
        inspection_date = operation.get("actual_end") or operation["planned_end"]
        rows.append({
            "inspection_id": _id("QIN", idx),
            "work_order_id": work_order["work_order_id"],
            "wo_operation_id": operation["wo_operation_id"],
            "inspection_type": "final",
            "inspection_date": inspection_date,
            "result": result,
            "defect_count": defect_count,
            "measured_value": 95.0 - defect_count,
            "spec_lower": 1.0,
            "spec_upper": 99.0,
            "inspector_id": f"INSP-{idx % 20 + 1:03d}",
            "notes": "Derived from AdventureWorks work order scrap quantity",
        })
    return rows


def _build_manifest(output_dir: Path, row_counts: dict[str, int]) -> dict[str, Any]:
    cfg = Config(seed=20260709)
    cfg._preset_name = PRESET_NAME
    generator = ManufacturingGenerator(cfg, output_dir)
    manifest = generator._build_manifest({
        "suppliers": row_counts["suppliers"],
        "materials": row_counts["materials"],
        "products": row_counts["products"],
        "work_centers": row_counts["work_centers"],
        "bom_items": row_counts["bills_of_materials"],
        "routings": row_counts["routings"],
        "routing_operations": row_counts["routing_operations"],
        "equipment": row_counts["equipment"],
        "maintenance": row_counts["equipment_maintenance"],
        "work_orders": row_counts["work_orders"],
        "wo_operations": row_counts["work_order_operations"],
        "inventory": row_counts["inventory"],
        "quality_inspections": row_counts["quality_inspections"],
    })
    manifest["generator"] = {
        "name": "map_adventureworks_to_semantic_pack.py",
        "version": GENERATOR_VERSION,
        "source": "AdventureWorks focused raw export",
    }
    manifest["seed"] = None
    return manifest


def map_data_pack(
    input_dir: Path,
    output_dir: Path,
    *,
    work_order_limit: int | None = None,
) -> dict[str, Any]:
    raw = {name: _read_csv(input_dir / filename) for name, filename in RAW_FILES.items()}

    categories_by_id = _index(raw["categories"], "ProductCategoryID")
    subcategories_by_id = _index(raw["subcategories"], "ProductSubcategoryID")
    products_by_id = _index(raw["products"], "ProductID")

    suppliers = _build_suppliers(raw["vendors"])
    materials = _build_materials(raw["products"], raw["product_vendors"], suppliers)
    products = _build_products(
        raw["products"],
        subcategories_by_id,
        categories_by_id,
    )
    work_centers = _build_work_centers(raw["locations"])

    product_ids = {row["product_id"] for row in products}
    material_ids = {row["material_id"] for row in materials}
    work_center_ids = {row["work_center_id"] for row in work_centers}

    bills_of_materials = _build_boms(raw["boms"], product_ids, material_ids)
    routings, routing_operations, operation_id_by_key = _build_routings_and_operations(
        raw["work_order_routings"],
        products_by_id,
        work_center_ids,
    )
    equipment = _build_equipment(work_centers)
    equipment_maintenance = _build_maintenance(equipment)
    work_orders = _build_work_orders(raw["work_orders"], product_ids, work_order_limit)
    work_order_ids = {row["work_order_id"] for row in work_orders}
    work_order_operations = _build_work_order_operations(
        raw["work_order_routings"],
        work_order_ids,
        operation_id_by_key,
    )
    inventory = _build_inventory(raw["inventory"], material_ids)
    quality_inspections = _build_quality_inspections(
        work_orders,
        work_order_operations,
    )

    tables = {
        "suppliers": suppliers,
        "materials": materials,
        "products": products,
        "work_centers": work_centers,
        "bills_of_materials": bills_of_materials,
        "routings": routings,
        "routing_operations": routing_operations,
        "equipment": equipment,
        "equipment_maintenance": equipment_maintenance,
        "work_orders": work_orders,
        "work_order_operations": work_order_operations,
        "inventory": inventory,
        "quality_inspections": quality_inspections,
    }

    for table_name, rows in tables.items():
        _write_csv(
            output_dir / f"{table_name}.csv",
            TARGET_COLUMNS[table_name],
            rows,
        )

    row_counts = {name: len(rows) for name, rows in tables.items()}
    manifest = _build_manifest(output_dir, row_counts)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "table_count": len(tables),
        "total_rows": sum(row_counts.values()),
        "row_counts": row_counts,
        "output": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map AdventureWorks raw export to Semantic CI manufacturing pack",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(".tmp") / "adventureworks",
        help="AdventureWorks raw export directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tmp") / "adventureworks-semantic",
        help="Output Semantic CI data pack directory",
    )
    parser.add_argument(
        "--work-order-limit",
        type=int,
        default=None,
        help="Optional cap for work orders when creating smaller benchmark packs",
    )
    args = parser.parse_args()

    if args.work_order_limit is not None and args.work_order_limit < 1:
        print("ERROR: --work-order-limit must be >= 1 when provided", file=sys.stderr)
        return 2

    try:
        summary = map_data_pack(
            args.input,
            args.output,
            work_order_limit=args.work_order_limit,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] semantic data pack: {args.output}")
    print(f"  tables: {summary['table_count']}")
    print(f"  rows: {summary['total_rows']}")
    print(f"  manifest: {args.output / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
