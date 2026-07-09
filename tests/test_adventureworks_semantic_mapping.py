"""Tests for AdventureWorks raw export to Semantic CI data pack mapping."""

import csv
import importlib.util
import json
import sys
from pathlib import Path

from scripts.validate_manufacturing_data_pack import validate_data_pack


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "map_adventureworks_to_semantic_pack.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "map_adventureworks_to_semantic_pack", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_tiny_raw_adventureworks_pack(raw_dir: Path) -> None:
    tables = {
        "Production_ProductCategory.csv": [
            {"ProductCategoryID": 1, "Name": "Components"},
            {"ProductCategoryID": 2, "Name": "Bikes"},
        ],
        "Production_ProductSubcategory.csv": [
            {"ProductSubcategoryID": 10, "ProductCategoryID": 1, "Name": "Wheels"},
            {"ProductSubcategoryID": 20, "ProductCategoryID": 2, "Name": "Road Bikes"},
        ],
        "Production_Product.csv": [
            {
                "ProductID": 100,
                "Name": "Front Wheel",
                "ProductNumber": "FW-100",
                "MakeFlag": 1,
                "FinishedGoodsFlag": 0,
                "StandardCost": 12.5,
                "ListPrice": 0,
                "SafetyStockLevel": 50,
                "ReorderPoint": 10,
                "DaysToManufacture": 2,
                "ProductSubcategoryID": 10,
                "SellStartDate": "2011-05-31T00:00:00",
                "ModifiedDate": "2014-02-08T10:00:00",
            },
            {
                "ProductID": 200,
                "Name": "Road-150 Red",
                "ProductNumber": "BK-R93R-62",
                "MakeFlag": 1,
                "FinishedGoodsFlag": 1,
                "StandardCost": 2171.2942,
                "ListPrice": 3578.27,
                "SafetyStockLevel": 100,
                "ReorderPoint": 20,
                "DaysToManufacture": 4,
                "ProductSubcategoryID": 20,
                "SellStartDate": "2011-05-31T00:00:00",
                "ModifiedDate": "2014-02-08T10:00:00",
            },
        ],
        "Production_WorkOrder.csv": [
            {
                "WorkOrderID": 9000,
                "ProductID": 200,
                "OrderQty": 10,
                "StockedQty": 8,
                "ScrappedQty": 1,
                "StartDate": "2013-06-03T00:00:00",
                "EndDate": "2013-06-13T00:00:00",
                "DueDate": "2013-06-14T00:00:00",
                "ScrapReasonID": "",
                "ModifiedDate": "2013-06-13T00:00:00",
            }
        ],
        "Production_WorkOrderRouting.csv": [
            {
                "WorkOrderID": 9000,
                "ProductID": 200,
                "OperationSequence": 1,
                "LocationID": 1,
                "ScheduledStartDate": "2013-06-03T08:00:00",
                "ScheduledEndDate": "2013-06-03T10:00:00",
                "ActualStartDate": "2013-06-03T08:05:00",
                "ActualEndDate": "2013-06-03T10:15:00",
                "ActualResourceHrs": 2.2,
                "PlannedCost": 25,
                "ActualCost": 30,
                "ModifiedDate": "2013-06-03T10:15:00",
            }
        ],
        "Production_BillOfMaterials.csv": [
            {
                "BillOfMaterialsID": 700,
                "ProductAssemblyID": 200,
                "ComponentID": 100,
                "UnitMeasureCode": "EA",
                "BOMLevel": 1,
                "PerAssemblyQty": 2,
                "StartDate": "2011-05-31T00:00:00",
                "EndDate": "",
                "ModifiedDate": "2011-05-31T00:00:00",
            }
        ],
        "Production_Location.csv": [
            {
                "LocationID": 1,
                "Name": "Frame Forming",
                "CostRate": 12.25,
                "Availability": 96,
                "ModifiedDate": "2014-02-08T10:00:00",
            }
        ],
        "Production_ProductInventory.csv": [
            {
                "ProductID": 100,
                "LocationID": 1,
                "Shelf": "A",
                "Bin": 1,
                "Quantity": 40,
                "ModifiedDate": "2014-02-08T10:00:00",
            }
        ],
        "Purchasing_Vendor.csv": [
            {
                "BusinessEntityID": 500,
                "AccountNumber": "AW0000500",
                "Name": "Contoso Components",
                "CreditRating": 1,
                "PreferredVendorStatus": 1,
                "ActiveFlag": 1,
                "ModifiedDate": "2014-02-08T10:00:00",
            }
        ],
        "Purchasing_ProductVendor.csv": [
            {
                "ProductID": 100,
                "BusinessEntityID": 500,
                "AverageLeadTime": 7,
                "StandardPrice": 11.2,
                "LastReceiptCost": 11,
                "MinOrderQty": 1,
                "MaxOrderQty": 100,
                "OnOrderQty": 12,
                "UnitMeasureCode": "EA",
                "ModifiedDate": "2014-02-08T10:00:00",
            }
        ],
    }
    for filename, rows in tables.items():
        _write_csv(raw_dir / filename, rows)
    manifest = {
        "manifest_version": "1.0",
        "data_pack": "adventureworks",
        "preset": "tiny",
        "seed": None,
        "generated_at": "2026-07-09T00:00:00+00:00",
        "table_count": len(tables),
        "total_rows": sum(len(rows) for rows in tables.values()),
        "tables": [
            {"table_name": filename.removesuffix(".csv"), "csv_file": filename}
            for filename in tables
        ],
    }
    (raw_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def test_maps_tiny_adventureworks_pack_to_valid_semantic_ci_pack(tmp_path):
    mod = _load_module()
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "semantic"
    _write_tiny_raw_adventureworks_pack(raw_dir)

    summary = mod.map_data_pack(raw_dir, output_dir)

    expected_tables = {
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
    }
    for table in expected_tables:
        assert (output_dir / f"{table}.csv").is_file()

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_pack"] == "manufacturing"
    assert manifest["preset"] == "adventureworks_semantic_v1"
    assert manifest["table_count"] == 13
    assert summary["total_rows"] == manifest["total_rows"]

    materials = _read_csv(output_dir / "materials.csv")
    suppliers = _read_csv(output_dir / "suppliers.csv")
    products = _read_csv(output_dir / "products.csv")
    boms = _read_csv(output_dir / "bills_of_materials.csv")
    wo_ops = _read_csv(output_dir / "work_order_operations.csv")
    routing_ops = _read_csv(output_dir / "routing_operations.csv")
    inventory = _read_csv(output_dir / "inventory.csv")

    supplier_ids = {row["supplier_id"] for row in suppliers}
    product_ids = {row["product_id"] for row in products}
    material_ids = {row["material_id"] for row in materials}
    routing_operation_ids = {
        row["routing_operation_id"] for row in routing_ops
    }

    assert {row["supplier_id"] for row in materials} <= supplier_ids
    assert {row["product_id"] for row in boms} <= product_ids
    assert {row["material_id"] for row in boms} <= material_ids
    assert {row["material_id"] for row in inventory} <= material_ids
    assert {row["routing_operation_id"] for row in wo_ops} <= routing_operation_ids

    result = validate_data_pack(output_dir)
    assert not result.has_fail, result.summary()
