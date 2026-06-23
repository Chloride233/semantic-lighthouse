"""Runtime audit helpers — immutable audit record creation and sanitized error codes.

Extracted from services/runtime.py per R1B.
No API, permission, migration, or query semantic changes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from semantic_lighthouse.models import OntologyRuntimeAudit


def _record_audit(
    db: Session,
    user_id: str,
    group_id: str,
    project_id: str,
    operation: str,
    *,
    object_type: str | None = None,
    field_names: list[str] | None = None,
    filter_field_names: list[str] | None = None,
    limit_val: int | None = None,
    offset_val: int | None = None,
    outcome: str,
    row_count: int | None = None,
    error_code: str | None = None,
    error_summary: str | None = None,
) -> OntologyRuntimeAudit:
    """Write an immutable runtime audit record.

    Never records filter values, raw data, storage_path, PII, or secrets.
    """
    record = OntologyRuntimeAudit(
        user_id=user_id,
        group_id=group_id,
        project_id=project_id,
        operation=operation,
        object_type=object_type,
        field_names=field_names,
        filter_field_names=filter_field_names,
        limit_val=limit_val,
        offset_val=offset_val,
        outcome=outcome,
        row_count=row_count,
        error_code=error_code,
        error_summary=error_summary,
    )
    db.add(record)
    return record


_SANITIZED_ERROR_CODES = {
    "path_outside_root": "dataset_path_outside_root",
    "path_outside_project": "dataset_path_outside_project",
    "file_not_found": "dataset_file_not_found",
    "no_package": "no_project_package",
    "no_binding": "no_active_binding",
    "dataset_not_ready": "dataset_not_ready",
    "read_error": "file_read_error",
    "type_conversion": "type_conversion_error",
    "binding_missing": "missing_binding",
    "smoke_failed": "smoke_query_failed",
    "archive": "project_archived",
    "stage": "stage_not_allowed",
}


def _sanitized_code(error_type: str) -> str:
    """Map internal error type to stable, non-leaking error code."""
    return _SANITIZED_ERROR_CODES.get(error_type, "internal_error")
