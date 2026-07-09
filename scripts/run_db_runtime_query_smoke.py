"""Run a DB-backed runtime query smoke from offline data-pack artifacts.

This script promotes offline query plans into a temporary SQLite runtime smoke.
It seeds only a local throwaway database and dataset-storage copy, then calls
the existing runtime execute_query path so row reads and audit writes are real.

It does not write the application database, create governance issues, publish a
package, or activate runtime.

Usage:
  .venv/Scripts/python scripts/run_db_runtime_query_smoke.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from semantic_lighthouse.config import get_settings  # noqa: E402
from semantic_lighthouse.models import (  # noqa: E402
    Base,
    BusinessProject,
    DatasetAsset,
    Group,
    GroupMembership,
    OntologyDatasetBinding,
    OntologyModelPackage,
    OntologyRuntimeAudit,
    User,
)
from semantic_lighthouse.services.runtime_query import execute_query  # noqa: E402


REPORT_VERSION = "1.0"
GROUP_ID = "runtime-smoke-group"
PROJECT_ID = "runtime-smoke-project"
USER_ID = "runtime-smoke-user"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _artifact(path: Path) -> dict[str, str | None]:
    return {
        "path": path.name if path.is_file() else None,
        "sha256": _sha256(path) if path.is_file() else None,
    }


def _data_pack_summary(data_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    tables = manifest.get("tables", [])
    return {
        "path": data_dir.name,
        "preset": manifest.get("preset"),
        "seed": manifest.get("seed"),
        "table_count": manifest.get("table_count", len(tables)),
        "total_rows": manifest.get(
            "total_rows",
            sum(int(table.get("row_count", 0) or 0) for table in tables),
        ),
    }


def _value_type(value_type: str | None) -> str:
    mapping = {
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
        "date": "date",
        "datetime": "datetime",
        "enum": "string",
        "string": "string",
        "text": "string",
    }
    return mapping.get(str(value_type or "string").casefold(), "string")


def _mapping_index(mapping_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(mapping.get("source_table")): mapping
        for mapping in mapping_contract.get("object_type_mappings", [])
        if mapping.get("source_table")
    }


def _table_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(table.get("table_name")): table
        for table in manifest.get("tables", [])
        if table.get("table_name")
    }


def _contract_item(
    *,
    item_id: str,
    draft_type: str,
    description: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload = {"contract_profile": "business_v1", **payload}
    return {
        "id": item_id,
        "draft_type": draft_type,
        "description": description,
        "payload": payload,
    }


def _contract_for_plans(
    plans: list[dict[str, Any]],
    mappings: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    object_types: list[dict[str, Any]] = []
    properties: list[dict[str, Any]] = []
    property_mappings: dict[str, dict[str, str]] = {}
    seen_object_types: set[str] = set()
    seen_properties: set[tuple[str, str]] = set()

    for plan in plans:
        source_table = str(plan.get("source_table"))
        mapping = mappings[source_table]
        object_type = str(mapping.get("object_type") or plan.get("object_type"))
        primary_key = str((mapping.get("primary_key") or [""])[0])
        if object_type not in seen_object_types:
            object_types.append(
                _contract_item(
                    item_id=f"runtime-smoke-ot-{object_type}",
                    draft_type="object_type",
                    description=mapping.get("description")
                    or f"Runtime smoke Object Type for {object_type}",
                    payload={
                        "api_name": object_type,
                        "display_name": object_type,
                        "primary_key": primary_key,
                    },
                )
            )
            seen_object_types.add(object_type)

        property_mappings.setdefault(object_type, {})
        for column in mapping.get("column_mappings", []):
            source_column = str(column.get("source_column") or "")
            target_property = str(
                column.get("target_property") or source_column
            )
            if not source_column or not target_property:
                continue
            property_mappings[object_type][target_property] = source_column
            key = (object_type, target_property)
            if key in seen_properties:
                continue
            properties.append(
                _contract_item(
                    item_id=f"runtime-smoke-prop-{object_type}-{target_property}",
                    draft_type="property",
                    description=f"{object_type}.{target_property}",
                    payload={
                        "api_name": target_property,
                        "display_name": target_property,
                        "object_type": object_type,
                        "value_type": _value_type(column.get("value_type")),
                        "required": target_property == primary_key,
                    },
                )
            )
            seen_properties.add(key)

    return {
        "object_types": object_types,
        "properties": properties,
        "link_types": [],
        "action_types": [],
    }, property_mappings


def _content_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _prepare_storage(
    data_dir: Path,
    smoke_dir: Path,
    manifest: dict[str, Any],
    table_names: set[str],
) -> dict[str, Path]:
    root = smoke_dir / "dataset-storage"
    project_root = root / GROUP_ID / PROJECT_ID
    if root.exists():
        shutil.rmtree(root)
    project_root.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for table in manifest.get("tables", []):
        table_name = str(table.get("table_name"))
        if table_name not in table_names:
            continue
        csv_file = str(table.get("csv_file"))
        source = data_dir / csv_file
        target = project_root / csv_file
        shutil.copyfile(source, target)
        copied[table_name] = target
    return copied


def _seed_database(
    db,
    *,
    manifest: dict[str, Any],
    contract: dict[str, Any],
    property_mappings: dict[str, dict[str, str]],
    table_paths: dict[str, Path],
    mappings: dict[str, dict[str, Any]],
) -> None:
    db.add(User(id=USER_ID, email="runtime-smoke@local", password_hash="x", display_name="Runtime Smoke"))
    db.add(Group(id=GROUP_ID, name="Runtime Smoke", created_by=USER_ID))
    db.add(GroupMembership(group_id=GROUP_ID, user_id=USER_ID, role="owner"))
    db.add(
        BusinessProject(
            id=PROJECT_ID,
            group_id=GROUP_ID,
            name="Runtime Smoke",
            business_goal="Temporary DB-backed runtime query smoke.",
            entry_mode="data_first",
            stage="validate",
            status="active",
            created_by=USER_ID,
        )
    )
    package_id = "runtime-smoke-package"
    db.add(
        OntologyModelPackage(
            id=package_id,
            group_id=GROUP_ID,
            project_id=PROJECT_ID,
            scope_key=f"project:{PROJECT_ID}",
            version=1,
            schema_version="1.0",
            content_hash=_content_hash(contract),
            contract_json=contract,
            source_draft_ids=[],
            draft_count=len(contract["object_types"]) + len(contract["properties"]),
            quality_status="PASS",
            quality_summary={"status": "PASS", "runtime_smoke": True},
            created_by=USER_ID,
        )
    )

    tables = _table_index(manifest)
    for table_name, path in table_paths.items():
        table = tables[table_name]
        mapping = mappings[table_name]
        object_type = str(mapping.get("object_type"))
        dataset_id = f"runtime-smoke-dataset-{table_name}"
        db.add(
            DatasetAsset(
                id=dataset_id,
                group_id=GROUP_ID,
                project_id=PROJECT_ID,
                original_name=str(table.get("csv_file")),
                storage_path=str(path),
                file_format="csv",
                file_size=path.stat().st_size,
                content_hash=_sha256(path),
                status="ready",
                row_count=int(table.get("row_count", 0) or 0),
                column_count=len(mapping.get("column_mappings", [])),
                profile_json={
                    "columns": [
                        {"name": col.get("source_column")}
                        for col in mapping.get("column_mappings", [])
                    ]
                },
                created_by=USER_ID,
            )
        )
        db.add(
            OntologyDatasetBinding(
                group_id=GROUP_ID,
                project_id=PROJECT_ID,
                package_id=package_id,
                dataset_id=dataset_id,
                object_type_api_name=object_type,
                primary_key_column=str((mapping.get("primary_key") or [""])[0]),
                property_mappings=property_mappings[object_type],
                status="active",
                created_by=USER_ID,
            )
        )
    db.commit()


def _blocked_report(
    data_dir: Path,
    manifest: dict[str, Any],
    query_plan: dict[str, Any],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "report_version": REPORT_VERSION,
        "pipeline": "db_runtime_query_smoke",
        "generated_at": _utc_now(),
        "data_pack": _data_pack_summary(data_dir, manifest),
        "source_artifacts": {
            "manifest": _artifact(data_dir / "manifest.json"),
            "mapping_contract": _artifact(data_dir / "mapping_contract.json"),
            "offline_runtime_query_plan": _artifact(
                data_dir / "offline_runtime_query_plan.json"
            ),
        },
        "summary": {
            "runtime_execution_status": "BLOCKED",
            "query_plan_count": int(
                query_plan.get("summary", {}).get("query_plan_count", 0) or 0
            ),
            "executed_query_count": 0,
            "returned_row_count": 0,
            "audit_record_count": 0,
            "executes_runtime_query": False,
            "reads_dataset_rows": False,
            "creates_audit_records": False,
            "writes_to_application_database": False,
            "database_scope": "temporary_sqlite_smoke",
        },
        "readiness_issues": issues,
        "query_results": [],
        "boundaries": _boundaries(False),
    }


def _boundaries(executed: bool) -> dict[str, bool]:
    return {
        "temporary_sqlite_only": True,
        "writes_to_application_database": False,
        "creates_real_governance_issues": False,
        "publishes_model_package": False,
        "activates_runtime": False,
        "executes_runtime_query": executed,
        "reads_dataset_rows": executed,
        "creates_audit_records": executed,
    }


def run_db_runtime_query_smoke(
    data_dir: Path,
    *,
    max_plans: int = 5,
) -> dict[str, Any]:
    manifest = _read_json(data_dir / "manifest.json", "manifest.json")
    mapping_contract = _read_json(
        data_dir / "mapping_contract.json",
        "mapping_contract.json",
    )
    query_plan = _read_json(
        data_dir / "offline_runtime_query_plan.json",
        "offline_runtime_query_plan.json",
    )
    if query_plan.get("summary", {}).get("query_status") != "QUERY_PLANNED":
        return _blocked_report(
            data_dir,
            manifest,
            query_plan,
            [
                {
                    "code": "offline_query_not_ready",
                    "severity": "error",
                    "message": "offline_runtime_query_plan.json is not QUERY_PLANNED.",
                }
            ],
        )

    plans = query_plan.get("query_plans", [])[:max(1, max_plans)]
    if not plans:
        return _blocked_report(
            data_dir,
            manifest,
            query_plan,
            [
                {
                    "code": "no_query_plans",
                    "severity": "error",
                    "message": "No offline query plans are available.",
                }
            ],
        )

    mappings = _mapping_index(mapping_contract)
    missing_mappings = [
        str(plan.get("source_table"))
        for plan in plans
        if str(plan.get("source_table")) not in mappings
    ]
    if missing_mappings:
        return _blocked_report(
            data_dir,
            manifest,
            query_plan,
            [
                {
                    "code": "missing_mapping",
                    "severity": "error",
                    "message": f"Missing mapping for: {', '.join(missing_mappings)}",
                }
            ],
        )

    smoke_dir = REPO_ROOT / ".tmp" / "db-runtime-query-smoke" / (
        "run-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    )
    smoke_dir.mkdir(parents=True, exist_ok=True)
    contract, property_mappings = _contract_for_plans(plans, mappings)
    old_storage = os.environ.get("DATASET_STORAGE_PATH")
    os.environ["DATASET_STORAGE_PATH"] = str(smoke_dir / "dataset-storage")
    get_settings.cache_clear()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_local()
    try:
        table_paths = _prepare_storage(
            data_dir,
            smoke_dir,
            manifest,
            {str(plan.get("source_table")) for plan in plans},
        )
        _seed_database(
            db,
            manifest=manifest,
            contract=contract,
            property_mappings=property_mappings,
            table_paths=table_paths,
            mappings=mappings,
        )
        query_results = []
        returned_rows = 0
        for plan in plans:
            request = plan.get("query_request", {})
            result = execute_query(
                db,
                group_id=GROUP_ID,
                project_id=PROJECT_ID,
                object_type=str(request.get("object_type") or plan.get("object_type")),
                user_id=USER_ID,
                fields=list(request.get("fields") or []),
                filters=dict(request.get("filters") or {}),
                limit=int(request.get("limit", 20) or 20),
                offset=int(request.get("offset", 0) or 0),
                explain_only=False,
            )
            row_count = int(result.get("row_count", 0) or 0)
            returned_rows += row_count
            query_results.append(
                {
                    "plan_id": plan.get("plan_id"),
                    "object_type": plan.get("object_type"),
                    "source_table": plan.get("source_table"),
                    "row_count": row_count,
                    "selected_fields": result.get("explain", {}).get(
                        "selected_fields", []
                    ),
                    "audit_outcome": "success" if row_count else "empty",
                    "row_preview": result.get("rows", [])[:2],
                    "row_preview_truncated": row_count > 2,
                }
            )
        audits = db.scalars(
            select(OntologyRuntimeAudit).where(
                OntologyRuntimeAudit.operation == "query"
            )
        ).all()
    finally:
        db.close()
        engine.dispose()
        if old_storage is None:
            os.environ.pop("DATASET_STORAGE_PATH", None)
        else:
            os.environ["DATASET_STORAGE_PATH"] = old_storage
        get_settings.cache_clear()

    return {
        "report_version": REPORT_VERSION,
        "pipeline": "db_runtime_query_smoke",
        "generated_at": _utc_now(),
        "data_pack": _data_pack_summary(data_dir, manifest),
        "source_artifacts": {
            "manifest": _artifact(data_dir / "manifest.json"),
            "mapping_contract": _artifact(data_dir / "mapping_contract.json"),
            "offline_runtime_query_plan": _artifact(
                data_dir / "offline_runtime_query_plan.json"
            ),
        },
        "summary": {
            "runtime_execution_status": "PASS",
            "query_plan_count": int(
                query_plan.get("summary", {}).get("query_plan_count", len(plans))
                or len(plans)
            ),
            "executed_query_count": len(query_results),
            "returned_row_count": returned_rows,
            "audit_record_count": len(audits),
            "executes_runtime_query": True,
            "reads_dataset_rows": True,
            "creates_audit_records": len(audits) >= len(query_results),
            "writes_to_application_database": False,
            "database_scope": "temporary_sqlite_smoke",
        },
        "readiness_issues": [],
        "query_results": query_results,
        "boundaries": _boundaries(True),
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# DB Runtime Query Smoke",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Runtime execution status: `{summary['runtime_execution_status']}`",
        f"- Executed queries: `{summary['executed_query_count']}`",
        f"- Returned rows: `{summary['returned_row_count']}`",
        f"- Audit records: `{summary['audit_record_count']}`",
        "- Writes to application database: `false`",
        "",
        "## Query Results",
        "",
        "| Plan | Object type | Source table | Rows | Audit |",
        "|---|---|---|---|---|",
    ]
    for item in result["query_results"]:
        lines.append(
            "| "
            f"{item.get('plan_id')} | "
            f"{item.get('object_type')} | "
            f"{item.get('source_table')} | "
            f"{item.get('row_count')} | "
            f"{item.get('audit_outcome')} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Temporary SQLite only: `true`",
            "- Writes to application database: `false`",
            "- Creates real governance issues: `false`",
            "- Publishes model package: `false`",
            "- Activates runtime: `false`",
            "",
        ]
    )
    return "\n".join(lines)


def write_db_runtime_query_smoke(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
    *,
    max_plans: int = 5,
) -> dict[str, Any]:
    result = run_db_runtime_query_smoke(data_dir, max_plans=max_plans)
    _write_json(output_path, result)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(render_markdown(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DB-backed runtime query smoke from offline artifacts",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing offline_runtime_query_plan.json",
    )
    parser.add_argument(
        "--max-plans",
        type=int,
        default=5,
        help="Maximum offline query plans to execute in the temporary smoke DB",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/db_runtime_query_smoke_report.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/db_runtime_query_smoke_report.md)"
        ),
    )
    args = parser.parse_args()
    output = args.output or (args.data_pack / "db_runtime_query_smoke_report.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "db_runtime_query_smoke_report.md"
    )
    try:
        result = write_db_runtime_query_smoke(
            args.data_pack,
            output,
            markdown_output,
            max_plans=args.max_plans,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== DB Runtime Query Smoke ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Runtime execution status: {summary['runtime_execution_status']}")
    print(f"Executed queries: {summary['executed_query_count']}")
    print(f"Returned rows: {summary['returned_row_count']}")
    print(f"Audit records: {summary['audit_record_count']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0 if summary["runtime_execution_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
