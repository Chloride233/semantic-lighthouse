"""Export a focused AdventureWorks benchmark data pack.

The exporter is intentionally offline and dependency-light. It connects to a
remote SQL Server container through SSH, asks sqlcmd for JSON, then writes CSV
files plus a manifest.json compatible with the Phase 19 data-pack shape.

Example:
  .venv/Scripts/python scripts/export_adventureworks.py \
      --ssh-target ubuntu@<server-ip> \
      --identity-file ~/.ssh/<key-name> \
      --output .tmp/adventureworks
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GENERATOR_VERSION = "1.0"


@dataclass(frozen=True)
class TableSpec:
    table_name: str
    csv_file: str
    primary_key: list[str]
    foreign_keys: list[dict[str, Any]]
    core_pilot: bool
    business_meaning: str
    order_by: list[str]


@dataclass(frozen=True)
class ExportedTable:
    table_name: str
    csv_file: str
    columns: list[str]
    rows: list[dict[str, Any]]


TABLE_SPECS: list[TableSpec] = [
    TableSpec(
        table_name="Production.ProductCategory",
        csv_file="Production_ProductCategory.csv",
        primary_key=["ProductCategoryID"],
        foreign_keys=[],
        core_pilot=True,
        business_meaning="Product category hierarchy roots.",
        order_by=["ProductCategoryID"],
    ),
    TableSpec(
        table_name="Production.ProductSubcategory",
        csv_file="Production_ProductSubcategory.csv",
        primary_key=["ProductSubcategoryID"],
        foreign_keys=[
            {
                "columns": ["ProductCategoryID"],
                "references": {
                    "table": "Production.ProductCategory",
                    "columns": ["ProductCategoryID"],
                },
            }
        ],
        core_pilot=True,
        business_meaning="Product subcategory hierarchy under categories.",
        order_by=["ProductSubcategoryID"],
    ),
    TableSpec(
        table_name="Production.Product",
        csv_file="Production_Product.csv",
        primary_key=["ProductID"],
        foreign_keys=[
            {
                "columns": ["ProductSubcategoryID"],
                "references": {
                    "table": "Production.ProductSubcategory",
                    "columns": ["ProductSubcategoryID"],
                },
            }
        ],
        core_pilot=True,
        business_meaning="Sellable and manufacturable products.",
        order_by=["ProductID"],
    ),
    TableSpec(
        table_name="Production.WorkOrder",
        csv_file="Production_WorkOrder.csv",
        primary_key=["WorkOrderID"],
        foreign_keys=[
            {
                "columns": ["ProductID"],
                "references": {
                    "table": "Production.Product",
                    "columns": ["ProductID"],
                },
            }
        ],
        core_pilot=True,
        business_meaning="Manufacturing work orders for products.",
        order_by=["WorkOrderID"],
    ),
    TableSpec(
        table_name="Production.WorkOrderRouting",
        csv_file="Production_WorkOrderRouting.csv",
        primary_key=["WorkOrderID", "ProductID", "OperationSequence"],
        foreign_keys=[
            {
                "columns": ["WorkOrderID"],
                "references": {
                    "table": "Production.WorkOrder",
                    "columns": ["WorkOrderID"],
                },
            },
            {
                "columns": ["ProductID"],
                "references": {
                    "table": "Production.Product",
                    "columns": ["ProductID"],
                },
            },
        ],
        core_pilot=True,
        business_meaning="Routing operations and actual manufacturing hours.",
        order_by=["WorkOrderID", "ProductID", "OperationSequence"],
    ),
    TableSpec(
        table_name="Production.BillOfMaterials",
        csv_file="Production_BillOfMaterials.csv",
        primary_key=["BillOfMaterialsID"],
        foreign_keys=[
            {
                "columns": ["ProductAssemblyID"],
                "references": {
                    "table": "Production.Product",
                    "columns": ["ProductID"],
                },
            },
            {
                "columns": ["ComponentID"],
                "references": {
                    "table": "Production.Product",
                    "columns": ["ProductID"],
                },
            },
        ],
        core_pilot=True,
        business_meaning="Bill of materials product-component structure.",
        order_by=["BillOfMaterialsID"],
    ),
    TableSpec(
        table_name="Production.Location",
        csv_file="Production_Location.csv",
        primary_key=["LocationID"],
        foreign_keys=[],
        core_pilot=True,
        business_meaning="Manufacturing and inventory locations.",
        order_by=["LocationID"],
    ),
    TableSpec(
        table_name="Production.ProductInventory",
        csv_file="Production_ProductInventory.csv",
        primary_key=["ProductID", "LocationID"],
        foreign_keys=[
            {
                "columns": ["ProductID"],
                "references": {
                    "table": "Production.Product",
                    "columns": ["ProductID"],
                },
            },
            {
                "columns": ["LocationID"],
                "references": {
                    "table": "Production.Location",
                    "columns": ["LocationID"],
                },
            },
        ],
        core_pilot=True,
        business_meaning="Inventory quantity by product and location.",
        order_by=["ProductID", "LocationID"],
    ),
    TableSpec(
        table_name="Purchasing.Vendor",
        csv_file="Purchasing_Vendor.csv",
        primary_key=["BusinessEntityID"],
        foreign_keys=[],
        core_pilot=True,
        business_meaning="Vendors and supplier credit attributes.",
        order_by=["BusinessEntityID"],
    ),
    TableSpec(
        table_name="Purchasing.ProductVendor",
        csv_file="Purchasing_ProductVendor.csv",
        primary_key=["ProductID", "BusinessEntityID"],
        foreign_keys=[
            {
                "columns": ["ProductID"],
                "references": {
                    "table": "Production.Product",
                    "columns": ["ProductID"],
                },
            },
            {
                "columns": ["BusinessEntityID"],
                "references": {
                    "table": "Purchasing.Vendor",
                    "columns": ["BusinessEntityID"],
                },
            },
        ],
        core_pilot=True,
        business_meaning="Approved vendor sourcing options for products.",
        order_by=["ProductID", "BusinessEntityID"],
    ),
]


TABLE_SPEC_BY_NAME = {spec.table_name: spec for spec in TABLE_SPECS}


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_manifest(exported_tables: list[ExportedTable]) -> dict[str, Any]:
    tables = []
    for exported in exported_tables:
        spec = TABLE_SPEC_BY_NAME[exported.table_name]
        tables.append(
            {
                "table_name": exported.table_name,
                "csv_file": exported.csv_file,
                "row_count": len(exported.rows),
                "primary_key": spec.primary_key,
                "foreign_keys": spec.foreign_keys,
                "core_pilot": spec.core_pilot,
                "business_meaning": spec.business_meaning,
                "columns": exported.columns,
            }
        )

    return {
        "manifest_version": "1.0",
        "data_pack": "adventureworks",
        "generator": {
            "name": "export_adventureworks.py",
            "version": GENERATOR_VERSION,
        },
        "preset": "recommended_minimum",
        "seed": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "table_count": len(tables),
        "total_rows": sum(t["row_count"] for t in tables),
        "core_pilot_table_count": sum(1 for t in tables if t["core_pilot"]),
        "tables": tables,
    }


def write_data_pack(output_dir: Path, exported_tables: list[ExportedTable]) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    for exported in exported_tables:
        csv_path = output_dir / exported.csv_file
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=exported.columns)
            writer.writeheader()
            for row in exported.rows:
                writer.writerow(
                    {column: _normalize_value(row.get(column)) for column in exported.columns}
                )

    manifest = build_manifest(exported_tables)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def _split_table_name(table_name: str) -> tuple[str, str]:
    schema, name = table_name.split(".", 1)
    return schema, name


def _select_query(spec: TableSpec, row_limit: int | None) -> str:
    schema, name = _split_table_name(spec.table_name)
    top = f"TOP ({row_limit}) " if row_limit else ""
    order = ", ".join(f"[{col}]" for col in spec.order_by)
    return (
        "SET NOCOUNT ON; "
        f"SELECT {top}* FROM [{schema}].[{name}] "
        f"ORDER BY {order} "
        "FOR JSON PATH, INCLUDE_NULL_VALUES;"
    )


def _run_remote_sqlcmd(
    *,
    ssh_target: str,
    identity_file: Path | None,
    container: str,
    database: str,
    user: str,
    password_file: str,
    query: str,
    timeout: int,
) -> str:
    remote_sql = (
        f"password=$(sudo cat {shlex.quote(password_file)}); "
        f"sudo docker exec {shlex.quote(container)} "
        "/opt/mssql-tools18/bin/sqlcmd "
        f"-S localhost -U {shlex.quote(user)} -P \"$password\" -C "
        f"-d {shlex.quote(database)} -y 0 -Y 0 -w 65535 "
        f"-Q {shlex.quote(query)}"
    )
    cmd = ["ssh"]
    if identity_file is not None:
        cmd.extend(["-i", str(identity_file)])
    cmd.extend([
        "-o",
        "BatchMode=yes",
        ssh_target,
        f"bash -lc {shlex.quote(remote_sql)}",
    ])
    result = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def _parse_sqlcmd_json(output: str) -> list[dict[str, Any]]:
    compact = "".join(line.strip() for line in output.splitlines() if line.strip())
    start = compact.find("[")
    end = compact.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("sqlcmd output did not contain a JSON array")
    json_text = compact[start : end + 1]
    if not json_text:
        return []
    return json.loads(json_text)


def export_tables(
    *,
    ssh_target: str,
    identity_file: Path | None,
    container: str,
    database: str,
    user: str,
    password_file: str,
    row_limit: int | None,
    timeout: int,
) -> list[ExportedTable]:
    exported_tables: list[ExportedTable] = []
    for spec in TABLE_SPECS:
        print(f"Exporting {spec.table_name} -> {spec.csv_file}")
        output = _run_remote_sqlcmd(
            ssh_target=ssh_target,
            identity_file=identity_file,
            container=container,
            database=database,
            user=user,
            password_file=password_file,
            query=_select_query(spec, row_limit),
            timeout=timeout,
        )
        rows = _parse_sqlcmd_json(output)
        columns = list(rows[0].keys()) if rows else []
        exported_tables.append(
            ExportedTable(
                table_name=spec.table_name,
                csv_file=spec.csv_file,
                columns=columns,
                rows=rows,
            )
        )
    return exported_tables


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a focused AdventureWorks data pack through SSH/sqlcmd",
    )
    parser.add_argument(
        "--ssh-target",
        default=os.environ.get("AW_SSH_TARGET"),
        help="SSH target, for example ubuntu@<server-ip>",
    )
    parser.add_argument(
        "--identity-file",
        type=Path,
        default=os.environ.get("AW_SSH_IDENTITY_FILE"),
        help="SSH private key path",
    )
    parser.add_argument("--container", default="aw-sql")
    parser.add_argument("--database", default="AdventureWorks2022")
    parser.add_argument("--user", default="aw_reader")
    parser.add_argument(
        "--password-file",
        default="/opt/adventureworks/.aw_reader_password",
        help="Remote file readable through sudo that contains the sqlcmd password",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tmp") / "adventureworks",
        help="Output data-pack directory",
    )
    parser.add_argument(
        "--row-limit",
        type=int,
        default=None,
        help="Optional TOP N limit per table for smoke exports",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    if not args.ssh_target:
        print("ERROR: --ssh-target is required", file=sys.stderr)
        return 2
    if args.row_limit is not None and args.row_limit < 1:
        print("ERROR: --row-limit must be >= 1 when provided", file=sys.stderr)
        return 2

    try:
        exported = export_tables(
            ssh_target=args.ssh_target,
            identity_file=args.identity_file,
            container=args.container,
            database=args.database,
            user=args.user,
            password_file=args.password_file,
            row_limit=args.row_limit,
            timeout=args.timeout,
        )
        manifest = write_data_pack(args.output, exported)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] data pack: {args.output}")
    print(f"  tables: {manifest['table_count']}")
    print(f"  rows: {manifest['total_rows']}")
    print(f"  manifest: {args.output / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
