"""Phase 14.2 — dataset asset profiling service.

Metadata-first: profile_json stores column statistics, never raw rows.
Supports CSV (stdlib csv) and XLSX (openpyxl read_only/data_only).

Privacy: sample values are opt-in, PII-masked, and capped at 3 per column.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from semantic_lighthouse.config import get_settings

_PROFILE_SCHEMA_VERSION = "1.0"
_MAX_SAMPLE_VALUES = 3

# ── PII patterns for masking sample values ──────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^(\+?86)?1[3-9]\d{9}$")
_ID_CARD_RE = re.compile(r"^\d{15}$|^\d{17}[\dXx]$")


def _mask_pii(value: str) -> str:
    """Mask PII-like values in sample output."""
    stripped = value.strip()
    if _EMAIL_RE.match(stripped):
        parts = stripped.split("@")
        return f"{parts[0][:2]}***@{parts[1]}"
    if _PHONE_RE.match(stripped):
        if stripped.startswith("+86"):
            return "+86" + stripped[-11:-8] + "****" + stripped[-4:]
        return stripped[:3] + "****" + stripped[-4:]
    if _ID_CARD_RE.match(stripped):
        return stripped[:3] + "***********" + stripped[-2:]
    return value


# ── type inference ──────────────────────────────────────────────────────

_INT_RE = re.compile(r"^-?\d+$")
_NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")
_BOOL_RE = re.compile(r"^(?i:true|false|0|1|yes|no)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")

_FK_NAMES = {"_id", "_code", "_key", "_ref", "_fk"}
_PK_NAMES = {"id", "uuid", "uid", "pk", "key", "code"}


def _infer_type(values: list[str | None]) -> str:
    """Infer column type from non-null sample values."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "string"

    # Check from most specific to least
    if all(_INT_RE.match(v) for v in non_null):
        return "integer"
    if all(_NUMBER_RE.match(v) for v in non_null):
        return "number"
    if all(_BOOL_RE.match(v) for v in non_null):
        return "boolean"
    if all(_DATE_RE.match(v) for v in non_null):
        return "date"
    if all(_DATETIME_RE.match(v) for v in non_null):
        return "datetime"
    return "string"


def _pk_confidence(col_name: str, inferred_type: str) -> tuple[str, str]:
    """Return (confidence, reason) for a PK candidate column."""
    name_lower = col_name.lower().strip()
    is_pk_name = name_lower in _PK_NAMES or any(
        name_lower.endswith(suffix) for suffix in _FK_NAMES
    )
    is_numeric = inferred_type in ("integer", "number")

    if is_pk_name and is_numeric:
        return "high", f"name matches primary/foreign key pattern, type is {inferred_type}"
    if is_pk_name:
        return "medium", f"name matches primary/foreign key pattern but type is {inferred_type}"
    if is_numeric:
        return "low", f"type is {inferred_type} but name does not match key pattern"
    return "low", "non-key name and non-numeric type"


# ── profiling result types ──────────────────────────────────────────────


@dataclass
class ColumnProfile:
    name: str
    position: int
    inferred_type: str = "string"
    nullable: bool = True
    null_count: int = 0
    non_null_count: int = 0
    distinct_count: int = 0
    distinct_count_capped: bool = False
    primary_key_candidate: bool = False
    pk_confidence: str = "low"
    pk_reason: str = ""
    sample_values: list[str] | None = None


@dataclass
class FKMatch:
    source_column: str
    target_dataset_id: str
    target_column: str
    target_dataset_name: str | None = None
    confidence: str = "low"
    reason: str = ""
    overlap_ratio: float = 0.0


@dataclass
class ProfileResult:
    schema_version: str = _PROFILE_SCHEMA_VERSION
    sheet_name: str | None = None
    rows_scanned: int = 0
    truncated: bool = False
    columns: list[ColumnProfile] = field(default_factory=list)
    primary_key_candidates: list[dict] = field(default_factory=list)
    foreign_key_suggestions: list[dict] = field(default_factory=list)
    sample_policy: str = "none"
    error: str | None = None

    def to_dict(self) -> dict:
        cols = []
        for c in self.columns:
            cd: dict = {
                "name": c.name,
                "position": c.position,
                "inferred_type": c.inferred_type,
                "nullable": c.nullable,
                "null_count": c.null_count,
                "non_null_count": c.non_null_count,
                "distinct_count": c.distinct_count,
                "distinct_count_capped": c.distinct_count_capped,
                "primary_key_candidate": c.primary_key_candidate,
                "sample_values": c.sample_values,
            }
            if c.primary_key_candidate:
                cd["pk_confidence"] = c.pk_confidence
                cd["pk_reason"] = c.pk_reason
            cols.append(cd)

        pks = [p for p in self.primary_key_candidates]
        fks = [f for f in self.foreign_key_suggestions]

        result: dict = {
            "schema_version": self.schema_version,
            "sheet_name": self.sheet_name,
            "rows_scanned": self.rows_scanned,
            "truncated": self.truncated,
            "columns": cols,
            "primary_key_candidates": pks,
            "foreign_key_suggestions": fks,
            "sample_policy": self.sample_policy,
        }
        if self.error:
            result["error"] = self.error
        return result


# ── profiling engine ────────────────────────────────────────────────────


def _safe_name(original: str) -> str:
    """Return a filesystem-safe stem from an original filename."""
    stem = Path(original).stem
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", stem)[:100]
    return safe if safe else "dataset"


def profile_csv(
    file_path: str,
    include_samples: bool = False,
) -> ProfileResult:
    """Profile a CSV file using stdlib csv module.

    Args:
        file_path: Path to the CSV file.
        include_samples: If True, include up to 3 masked sample values per column.

    Returns:
        ProfileResult with column statistics.

    Raises:
        ValueError: On empty file, duplicate columns, or parse errors.
    """
    settings = get_settings()
    max_rows = settings.dataset_max_scan_rows
    max_distinct = settings.dataset_max_distinct_values

    # Detect encoding: try UTF-8-SIG first (handles BOM), then UTF-8
    raw_bytes = Path(file_path).read_bytes()
    if not raw_bytes.strip():
        raise ValueError("Empty CSV file")

    text: str
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"CSV encoding not supported (expected UTF-8): {e}") from e

    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("CSV file has no rows")
    except csv.Error as e:
        raise ValueError(f"CSV parse error at header: {e}") from e

    if not header or all(h == "" for h in header):
        raise ValueError("CSV file has no valid header row")

    # Deduplicate headers
    header = [h.strip() for h in header]
    seen: set[str] = set()
    for h in header:
        if not h:
            raise ValueError("CSV header contains empty column name")
        if h in seen:
            raise ValueError(f"Duplicate column name: {h!r}")
        seen.add(h)

    # Initialize column trackers
    col_data: list[list[str | None]] = [[] for _ in header]
    distinct_sets: list[set[str]] = [set() for _ in header]
    distinct_capped: list[bool] = [False] * len(header)
    null_counts: list[int] = [0] * len(header)

    row_count = 0
    truncated = False

    for row in reader:
        if row_count >= max_rows:
            truncated = True
            break
        row_count += 1

        for i in range(len(header)):
            if i >= len(row) or row[i].strip() == "":
                col_data[i].append(None)
                null_counts[i] += 1
            else:
                val = row[i].strip()
                col_data[i].append(val)
                if not distinct_capped[i]:
                    if len(distinct_sets[i]) < max_distinct:
                        distinct_sets[i].add(val)
                    else:
                        distinct_capped[i] = True

    # Build column profiles
    columns: list[ColumnProfile] = []
    for i, name in enumerate(header):
        non_null = row_count - null_counts[i]
        distinct = len(distinct_sets[i])
        inferred = _infer_type(col_data[i])

        col = ColumnProfile(
            name=name,
            position=i,
            inferred_type=inferred,
            nullable=null_counts[i] > 0,
            null_count=null_counts[i],
            non_null_count=non_null,
            distinct_count=distinct,
            distinct_count_capped=distinct_capped[i],
        )

        if include_samples:
            samples: list[str] = []
            sample_seen: set[str] = set()
            for v in col_data[i]:
                if v is None:
                    continue
                if v not in sample_seen:
                    sample_seen.add(v)
                    samples.append(_mask_pii(v))
                if len(samples) >= _MAX_SAMPLE_VALUES:
                    break
            col.sample_values = samples if samples else None
        else:
            col.sample_values = None

        columns.append(col)

    result = ProfileResult(
        sheet_name=None,
        rows_scanned=row_count,
        truncated=truncated,
        columns=columns,
        sample_policy="none" if not include_samples else "opt-in-masked",
    )

    # Compute PK candidates
    result.primary_key_candidates = _find_pk_candidates(columns, row_count)

    return result


def profile_xlsx(
    file_path: str,
    include_samples: bool = False,
) -> ProfileResult:
    """Profile an XLSX file using openpyxl read_only/data_only mode.

    Only the first visible worksheet is analyzed. Formulas, macros,
    and external links are not executed.

    Args:
        file_path: Path to the XLSX file.
        include_samples: If True, include up to 3 masked sample values per column.

    Returns:
        ProfileResult with column statistics.

    Raises:
        ValueError: On empty file, duplicate columns, or corrupt workbook.
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ImportError("openpyxl is required for XLSX profiling") from None

    settings = get_settings()
    max_rows = settings.dataset_max_scan_rows
    max_distinct = settings.dataset_max_distinct_values

    try:
        wb = load_workbook(file_path, read_only=True, data_only=True, keep_links=False)
    except Exception as e:
        raise ValueError(f"Cannot open XLSX file (corrupt or unsupported): {e}") from e

    try:
        # First visible sheet
        sheet_name: str | None = None
        ws = None
        for name in wb.sheetnames:
            ws = wb[name]
            if ws and ws.sheet_state == "visible":
                sheet_name = name
                break

        if ws is None:
            raise ValueError("XLSX file has no visible worksheets")

        # Read header row
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if header_row is None or all(v is None or str(v).strip() == "" for v in header_row):
            raise ValueError("XLSX file has no valid header row")

        header = [str(v).strip() if v is not None else "" for v in header_row]
        # Truncate trailing empty columns
        while header and header[-1] == "":
            header.pop()

        if not header:
            raise ValueError("XLSX file has no valid header row")

        seen: set[str] = set()
        for h in header:
            if not h:
                raise ValueError("XLSX header contains empty column name")
            if h in seen:
                raise ValueError(f"Duplicate column name: {h!r}")
            seen.add(h)

        # Initialize trackers
        col_data: list[list[str | None]] = [[] for _ in header]
        distinct_sets: list[set[str]] = [set() for _ in header]
        distinct_capped: list[bool] = [False] * len(header)
        null_counts: list[int] = [0] * len(header)

        row_count = 0
        truncated = False

        for row in ws.iter_rows(min_row=2, values_only=True):
            if row_count >= max_rows:
                truncated = True
                break
            if all(v is None or str(v).strip() == "" for v in row):
                continue  # skip fully empty rows
            row_count += 1

            for i in range(len(header)):
                if i >= len(row) or row[i] is None or str(row[i]).strip() == "":
                    col_data[i].append(None)
                    null_counts[i] += 1
                else:
                    val = str(row[i]).strip()
                    col_data[i].append(val)
                    if not distinct_capped[i]:
                        if len(distinct_sets[i]) < max_distinct:
                            distinct_sets[i].add(val)
                        else:
                            distinct_capped[i] = True

        columns: list[ColumnProfile] = []
        for i, name in enumerate(header):
            non_null = row_count - null_counts[i]
            distinct = len(distinct_sets[i])
            inferred = _infer_type(col_data[i])

            col = ColumnProfile(
                name=name,
                position=i,
                inferred_type=inferred,
                nullable=null_counts[i] > 0,
                null_count=null_counts[i],
                non_null_count=non_null,
                distinct_count=distinct,
                distinct_count_capped=distinct_capped[i],
            )

            if include_samples:
                samples: list[str] = []
                sample_seen: set[str] = set()
                for v in col_data[i]:
                    if v is None:
                        continue
                    if v not in sample_seen:
                        sample_seen.add(v)
                        samples.append(_mask_pii(v))
                    if len(samples) >= _MAX_SAMPLE_VALUES:
                        break
                col.sample_values = samples if samples else None
            else:
                col.sample_values = None

            columns.append(col)

        result = ProfileResult(
            sheet_name=sheet_name,
            rows_scanned=row_count,
            truncated=truncated,
            columns=columns,
            sample_policy="none" if not include_samples else "opt-in-masked",
        )

        result.primary_key_candidates = _find_pk_candidates(columns, row_count)
        return result

    finally:
        wb.close()


def _find_pk_candidates(columns: list[ColumnProfile], row_count: int) -> list[dict]:
    """Find primary key candidates from column profiles."""
    if row_count == 0:
        return []
    candidates: list[dict] = []
    for col in columns:
        is_unique = (
            not col.nullable
            and col.non_null_count == row_count
            and col.distinct_count == col.non_null_count
            and not col.distinct_count_capped
        )
        if not is_unique:
            continue
        confidence, reason = _pk_confidence(col.name, col.inferred_type)
        candidates.append({
            "column": col.name,
            "confidence": confidence,
            "reason": reason,
        })
    return candidates


def compute_content_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def suggest_foreign_keys(
    new_columns: list[ColumnProfile],
    existing_datasets: list[dict],
) -> list[dict]:
    """Suggest foreign key relationships within the same project.

    Args:
        new_columns: Column profiles from the newly uploaded dataset.
        existing_datasets: List of dicts with keys: id, original_name, profile_json.
            Each profile_json must have a 'columns' list.

    Returns:
        List of FK suggestion dicts.
    """
    if not existing_datasets:
        return []

    suggestions: list[dict] = []

    for col in new_columns:
        col_lower = col.name.lower().strip()

        # Only consider columns whose names suggest FK potential
        is_fk_name = col_lower.endswith(tuple(_FK_NAMES)) or col_lower in _PK_NAMES
        if not is_fk_name:
            continue

        col_base = col_lower
        for suffix in _FK_NAMES:
            if col_lower.endswith(suffix):
                col_base = col_lower[:-len(suffix)]
                break

        for ds in existing_datasets:
            pk_candidates = (
                ds.get("profile_json", {}).get("primary_key_candidates", [])
            )
            for pk in pk_candidates:
                target_col = pk.get("column", "")
                target_lower = target_col.lower().strip()

                # Name similarity check: handle patterns like customer_id → id
                name_match = (
                    col_lower == target_lower
                    or col_base == target_lower
                    or target_lower in col_lower
                    or (col_base and col_base.rstrip("_") == target_lower)
                )

                if not name_match:
                    continue

                confidence = "low"
                reason_parts = []

                if pk.get("confidence") == "high":
                    confidence = "medium"
                    reason_parts.append("target is high-confidence PK candidate")
                elif pk.get("confidence") == "medium":
                    confidence = "low"
                    reason_parts.append("target is medium-confidence PK candidate")
                else:
                    reason_parts.append("name-based match only")

                if col.inferred_type in ("integer", "number"):
                    reason_parts.append("source type is numeric")
                    if confidence == "medium":
                        confidence = "medium"

                reason = ". ".join(reason_parts) + "."

                suggestions.append({
                    "source_column": col.name,
                    "target_dataset_id": ds["id"],
                    "target_column": target_col,
                    "target_dataset_name": ds.get("original_name"),
                    "confidence": confidence,
                    "reason": reason,
                })

    return suggestions
