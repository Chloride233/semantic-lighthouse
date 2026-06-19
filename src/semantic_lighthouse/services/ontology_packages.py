"""Ontology model package builder — immutable contract snapshots from accepted drafts.

Phase 12.3b: creates a versioned, content-hashed, immutable package from
currently accepted modeling drafts. No API, no Agent, no external KB.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    OntologyModelPackage,
    OntologyModelingDraft,
)
from semantic_lighthouse.services.ontology_draft_quality import (
    validate_modeling_drafts,
)


class PackageBuildError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def build_model_package(
    db: Session, group_id: str, created_by: str
) -> tuple[OntologyModelPackage, bool]:
    """Build an immutable model package from accepted drafts.

    Returns (package, created). created=False if identical package exists.

    Raises PackageBuildError if:
    - No accepted drafts exist
    - Accepted drafts have quality errors
    - Accepted property/link references missing accepted object_type
    """
    # ── Accepted drafts only ──────────────────────────────────────────
    accepted = list(
        db.scalars(
            select(OntologyModelingDraft).where(
                OntologyModelingDraft.group_id == group_id,
                OntologyModelingDraft.status == "accepted",
            )
        ).all()
    )
    if not accepted:
        raise PackageBuildError(
            code="no_accepted_drafts",
            message="No accepted drafts in this group",
        )

    accepted_ids = {d.id for d in accepted}

    # ── Quality gate ──────────────────────────────────────────────────
    qr = validate_modeling_drafts(db, group_id)
    accepted_errors = [
        i for i in qr["issues"]
        if i["severity"] == "error" and i["draft_id"] in accepted_ids
    ]
    if accepted_errors:
        codes = sorted({e["code"] for e in accepted_errors})
        raise PackageBuildError(
            code="quality_errors",
            message=f"Accepted drafts have quality errors: {', '.join(codes)}",
        )

    accepted_warnings = [
        i for i in qr["issues"]
        if i["severity"] == "warning" and i["draft_id"] in accepted_ids
    ]
    warning_codes: dict[str, int] = {}
    for w in accepted_warnings:
        c = w["code"]
        warning_codes[c] = warning_codes.get(c, 0) + 1

    quality_status = "WARN" if accepted_warnings else "PASS"

    # ── Accepted-only dependency gate ─────────────────────────────────
    obj_type_names = {
        d.name.strip().casefold()
        for d in accepted if d.draft_type == "object_type"
    }

    for d in accepted:
        payload = d.payload or {}
        if d.draft_type == "property":
            ot_raw = payload.get("object_type")
            if not isinstance(ot_raw, str) or not ot_raw.strip():
                raise PackageBuildError(
                    code="missing_dependency",
                    message=f"Property '{d.name}' missing or empty "
                    f"payload.object_type — required for package contract",
                )
            ot = ot_raw.strip().casefold()
            if ot not in obj_type_names:
                raise PackageBuildError(
                    code="missing_dependency",
                    message=f"Property '{d.name}' object_type '{ot_raw.strip()}' "
                    f"not in accepted object_type drafts",
                )
        if d.draft_type == "link_type":
            for field, label in [
                ("source_object_type", "source"),
                ("target_object_type", "target"),
            ]:
                ot_raw = payload.get(field)
                if not isinstance(ot_raw, str) or not ot_raw.strip():
                    raise PackageBuildError(
                        code="missing_dependency",
                        message=f"Link '{d.name}' missing or empty "
                        f"payload.{field} — required for package contract",
                    )
                ot = ot_raw.strip().casefold()
                if ot not in obj_type_names:
                    raise PackageBuildError(
                        code="missing_dependency",
                        message=f"Link '{d.name}' {label}_object_type "
                        f"'{ot_raw.strip()}' not in accepted object_type drafts",
                    )

    # ── Stable contract snapshot ──────────────────────────────────────
    contract: dict = {
        "schema_version": "1.0",
        "object_types": [],
        "properties": [],
        "link_types": [],
        "action_types": [],
    }

    def _draft_snapshot(d: OntologyModelingDraft) -> dict:
        return {
            "id": d.id,
            "draft_type": d.draft_type,
            "name": d.name,
            "description": d.description,
            "payload": d.payload or {},
            "evidence_refs": d.evidence_refs or [],
            "reviewed_by": d.reviewed_by,
            "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
            "review_note": d.review_note,
        }

    type_key = {
        "object_type": "object_types",
        "property": "properties",
        "link_type": "link_types",
        "action_type": "action_types",
    }
    for d in accepted:
        key = type_key.get(d.draft_type)
        if key is not None:
            contract[key].append(_draft_snapshot(d))

    # Stable sort by normalized name + id
    for key in contract:
        if isinstance(contract[key], list):
            contract[key].sort(
                key=lambda x: (
                    (x.get("name", "") or "").strip().casefold(),
                    x.get("id", ""),
                )
            )

    # source_draft_ids in same stable order
    all_ids: list[str] = []
    for key in ("object_types", "properties", "link_types", "action_types"):
        for item in contract[key]:
            all_ids.append(item["id"])

    # ── Content hash ──────────────────────────────────────────────────
    canonical = json.dumps(
        contract, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ── Version / idempotency ─────────────────────────────────────────
    existing = db.scalar(
        select(OntologyModelPackage).where(
            OntologyModelPackage.group_id == group_id,
            OntologyModelPackage.content_hash == content_hash,
        )
    )
    if existing is not None:
        return existing, False

    max_ver = db.scalar(
        select(func.max(OntologyModelPackage.version)).where(
            OntologyModelPackage.group_id == group_id,
        )
    ) or 0
    version = max_ver + 1

    quality_summary = {
        "status": quality_status,
        "error_count": 0,
        "warning_count": len(accepted_warnings),
        "warning_codes": warning_codes,
        "accepted_draft_count": len(accepted),
    }

    pkg = OntologyModelPackage(
        group_id=group_id,
        version=version,
        content_hash=content_hash,
        contract_json=contract,
        source_draft_ids=all_ids,
        draft_count=len(accepted),
        quality_status=quality_status,
        quality_summary=quality_summary,
        created_by=created_by,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg, True
