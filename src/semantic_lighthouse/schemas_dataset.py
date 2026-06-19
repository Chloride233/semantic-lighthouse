"""Phase 14.2 — dataset asset schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DatasetAssetResponse(BaseModel):
    id: str
    group_id: str
    project_id: str
    original_name: str
    file_format: str
    file_size: int
    content_hash: str
    status: str
    row_count: int
    column_count: int
    profile_json: dict = Field(default_factory=dict)
    created_by: str
    created_at: datetime
    updated_at: datetime


class DatasetAssetListResponse(BaseModel):
    datasets: list[DatasetAssetResponse]
    total: int


class DatasetAssetUploadResponse(DatasetAssetResponse):
    deduplicated: bool = False
