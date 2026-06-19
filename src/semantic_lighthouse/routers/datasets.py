"""Phase 14.2 — dataset asset upload, list, detail, archive API.

Permissions: member read, owner/admin upload/archive.
Metadata-first: files stored on disk, profile in DB.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from semantic_lighthouse.config import get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import (
    get_current_user,
    get_membership_or_404,
    require_group_role,
)
from semantic_lighthouse.models import BusinessProject, DatasetAsset, User, utc_now
from semantic_lighthouse.schemas_dataset import (
    DatasetAssetListResponse,
    DatasetAssetResponse,
    DatasetAssetUploadResponse,
)
from semantic_lighthouse.services import projects as projects_service
from semantic_lighthouse.services.dataset_profiling import (
    compute_content_hash,
    profile_csv,
    profile_xlsx,
    suggest_foreign_keys,
)

router = APIRouter(
    prefix="/groups/{group_id}/projects/{project_id}/datasets",
    tags=["datasets"],
)

_ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


def _get_project_or_404(
    db: Session, project_id: str, group_id: str
) -> BusinessProject:
    """Fetch project and enforce group_id match (404 on mismatch)."""
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def _asset_response(asset: DatasetAsset) -> DatasetAssetResponse:
    return DatasetAssetResponse(
        id=asset.id,
        group_id=asset.group_id,
        project_id=asset.project_id,
        original_name=asset.original_name,
        file_format=asset.file_format,
        file_size=asset.file_size,
        content_hash=asset.content_hash,
        status=asset.status,
        row_count=asset.row_count,
        column_count=asset.column_count,
        profile_json=asset.profile_json,
        created_by=asset.created_by,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _sanitize_name(original: str) -> str:
    """Produce a filesystem-safe filename. Preserve extension."""
    stem = Path(original).stem
    ext = Path(original).suffix.lower()
    safe_stem = "".join(c for c in stem if c.isalnum() or c in "._-")[:100]
    safe_stem = safe_stem.strip("._-")
    if not safe_stem:
        safe_stem = "dataset"
    return f"{safe_stem}{ext}"


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_dataset(
    group_id: str,
    project_id: str,
    file: UploadFile = File(...),
    include_sample_values: bool = Form(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetAssetUploadResponse:
    """Upload a CSV or XLSX dataset for profiling.

    Owner/admin only. Deduplicates by content hash.
    Does not store raw rows in the database.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    project = _get_project_or_404(db, project_id, group_id)

    if project.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot upload to an archived project",
        )

    # Validate filename
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename is required",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file format: {ext}. Allowed: .csv, .xlsx",
        )

    if ext == ".xls" and not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=".xls format is not supported. Use .xlsx instead.",
        )

    settings = get_settings()
    max_bytes = settings.max_document_upload_bytes

    # Read with bounded size to prevent unbounded memory allocation
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {max_bytes} bytes",
        )

    # Ensure storage directory exists
    storage_root = Path(settings.dataset_storage_path).resolve()
    storage_dir = storage_root / group_id / project_id
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Write to temp file
    safe_name = _sanitize_name(file.filename)
    dataset_id: str | None = None
    final_path: Path | None = None

    from uuid import uuid4

    tmp_name = f".tmp_{uuid4().hex}_{safe_name}"
    tmp_path = storage_dir / tmp_name

    try:
        # Write temp file
        with open(tmp_path, "wb") as f:
            f.write(content)

        # Compute hash
        content_hash = compute_content_hash(str(tmp_path))

        # Check for duplicate in same project
        existing = db.scalar(
            select(DatasetAsset).where(
                DatasetAsset.project_id == project_id,
                DatasetAsset.content_hash == content_hash,
            )
        )
        if existing is not None:
            # Clean up temp file
            tmp_path.unlink(missing_ok=True)
            return DatasetAssetUploadResponse(
                id=existing.id,
                group_id=existing.group_id,
                project_id=existing.project_id,
                original_name=existing.original_name,
                file_format=existing.file_format,
                file_size=existing.file_size,
                content_hash=existing.content_hash,
                status=existing.status,
                row_count=existing.row_count,
                column_count=existing.column_count,
                profile_json=existing.profile_json,
                created_by=existing.created_by,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
                deduplicated=True,
            )

        # Profile the file
        fmt = ext.lstrip(".")
        if fmt == "csv":
            result = profile_csv(str(tmp_path), include_samples=include_sample_values)
        else:
            result = profile_xlsx(str(tmp_path), include_samples=include_sample_values)

        if result.error is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Profile error: {result.error}",
            )

        # Create asset ID and move to final location
        dataset_id = uuid4().hex
        final_path = storage_dir / f"{dataset_id}_{safe_name}"
        tmp_path.rename(final_path)

        # Compute FK suggestions within the same project
        existing_datasets = db.scalars(
            select(DatasetAsset).where(
                DatasetAsset.project_id == project_id,
                DatasetAsset.status == "ready",
            )
        ).all()

        fk_suggestions = suggest_foreign_keys(
            result.columns,
            [
                {
                    "id": d.id,
                    "original_name": d.original_name,
                    "profile_json": d.profile_json,
                }
                for d in existing_datasets
            ],
        )
        result.foreign_key_suggestions = fk_suggestions

        profile_dict = result.to_dict()

        asset = DatasetAsset(
            id=dataset_id,
            group_id=group_id,
            project_id=project_id,
            original_name=safe_name,
            storage_path=str(final_path),
            file_format=fmt,
            file_size=len(content),
            content_hash=content_hash,
            status="ready",
            row_count=result.rows_scanned,
            column_count=len(result.columns),
            profile_json=profile_dict,
            created_by=current_user.id,
        )
        db.add(asset)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Race: another upload with same content won. Return theirs.
            final_path.unlink(missing_ok=True)
            existing = db.scalar(
                select(DatasetAsset).where(
                    DatasetAsset.project_id == project_id,
                    DatasetAsset.content_hash == content_hash,
                )
            )
            if existing is not None:
                return DatasetAssetUploadResponse(
                    id=existing.id,
                    group_id=existing.group_id,
                    project_id=existing.project_id,
                    original_name=existing.original_name,
                    file_format=existing.file_format,
                    file_size=existing.file_size,
                    content_hash=existing.content_hash,
                    status=existing.status,
                    row_count=existing.row_count,
                    column_count=existing.column_count,
                    profile_json=existing.profile_json,
                    created_by=existing.created_by,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                    deduplicated=True,
                )
            raise

        db.refresh(asset)

        # Advance project stage if this is the first ready asset
        if project.stage == "goal":
            ready_count = db.scalar(
                select(func.count()).select_from(
                    select(DatasetAsset).where(
                        DatasetAsset.project_id == project_id,
                        DatasetAsset.status == "ready",
                    ).subquery()
                )
            )
            if ready_count and ready_count > 0:
                projects_service.advance_stage("goal", "data")
                project.stage = "data"
                db.commit()
                db.refresh(project)

        return DatasetAssetUploadResponse(
            id=asset.id,
            group_id=asset.group_id,
            project_id=asset.project_id,
            original_name=asset.original_name,
            file_format=asset.file_format,
            file_size=asset.file_size,
            content_hash=asset.content_hash,
            status=asset.status,
            row_count=asset.row_count,
            column_count=asset.column_count,
            profile_json=asset.profile_json,
            created_by=asset.created_by,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            deduplicated=False,
        )

    except HTTPException:
        # Clean up temp file on any HTTP error
        tmp_path.unlink(missing_ok=True)
        raise
    except ValueError as e:
        # Profile validation errors → 422
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        # Unexpected error — clean up temp file
        tmp_path.unlink(missing_ok=True)
        if final_path:
            final_path.unlink(missing_ok=True)
        raise


@router.get("", response_model=DatasetAssetListResponse)
def list_datasets(
    group_id: str,
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetAssetListResponse:
    """List datasets for a project (member+)."""
    get_membership_or_404(db, current_user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    base = select(DatasetAsset).where(
        DatasetAsset.project_id == project_id,
        DatasetAsset.group_id == group_id,
    )
    if status_filter:
        base = base.where(DatasetAsset.status == status_filter)

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    datasets = db.scalars(
        base.order_by(DatasetAsset.created_at.desc()).offset(offset).limit(limit)
    ).all()

    return DatasetAssetListResponse(
        datasets=[_asset_response(d) for d in datasets],
        total=total or 0,
    )


@router.get("/{dataset_id}", response_model=DatasetAssetResponse)
def get_dataset(
    dataset_id: str,
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetAssetResponse:
    """Get a single dataset detail (member+)."""
    get_membership_or_404(db, current_user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    asset = db.get(DatasetAsset, dataset_id)
    if asset is None or asset.project_id != project_id or asset.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        )
    return _asset_response(asset)


@router.post("/{dataset_id}/archive", response_model=DatasetAssetResponse)
def archive_dataset(
    dataset_id: str,
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetAssetResponse:
    """Archive a dataset (owner/admin only). Idempotent."""
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    _get_project_or_404(db, project_id, group_id)

    asset = db.get(DatasetAsset, dataset_id)
    if asset is None or asset.project_id != project_id or asset.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        )

    asset.status = "archived"
    asset.updated_at = utc_now()
    db.commit()
    db.refresh(asset)
    return _asset_response(asset)
