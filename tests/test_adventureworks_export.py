"""Tests for the AdventureWorks offline benchmark exporter."""

import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "export_adventureworks.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "export_adventureworks", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_adventureworks_manifest_contains_required_contract_fields(tmp_path):
    mod = _load_module()
    exported = [
        mod.ExportedTable(
            table_name="Production.Product",
            csv_file="Production_Product.csv",
            columns=["ProductID", "Name", "ProductNumber"],
            rows=[
                {
                    "ProductID": 1,
                    "Name": "Adjustable Race",
                    "ProductNumber": "AR-5381",
                }
            ],
        )
    ]

    manifest = mod.build_manifest(exported)

    assert manifest["manifest_version"] == "1.0"
    assert manifest["data_pack"] == "adventureworks"
    assert manifest["generator"]["name"] == "export_adventureworks.py"
    assert manifest["table_count"] == 1
    assert manifest["total_rows"] == 1
    table = manifest["tables"][0]
    for field in (
        "table_name",
        "csv_file",
        "row_count",
        "primary_key",
        "foreign_keys",
        "core_pilot",
        "business_meaning",
    ):
        assert field in table
    assert table["primary_key"] == ["ProductID"]
    assert table["core_pilot"] is True


def test_write_data_pack_writes_csv_and_manifest(tmp_path):
    mod = _load_module()
    exported = [
        mod.ExportedTable(
            table_name="Purchasing.Vendor",
            csv_file="Purchasing_Vendor.csv",
            columns=["BusinessEntityID", "Name", "CreditRating"],
            rows=[
                {
                    "BusinessEntityID": 1492,
                    "Name": "Australia Bike Retailer",
                    "CreditRating": 1,
                }
            ],
        )
    ]

    mod.write_data_pack(tmp_path, exported)

    csv_path = tmp_path / "Purchasing_Vendor.csv"
    manifest_path = tmp_path / "manifest.json"
    assert csv_path.is_file()
    assert manifest_path.is_file()

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == [
        {
            "BusinessEntityID": "1492",
            "Name": "Australia Bike Retailer",
            "CreditRating": "1",
        }
    ]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["tables"][0]["table_name"] == "Purchasing.Vendor"
    assert manifest["tables"][0]["csv_file"] == "Purchasing_Vendor.csv"
    assert manifest["tables"][0]["row_count"] == 1
