"""Phase 14.3 — deterministic dataset-to-modeling bridge.

Reads DatasetAsset profiles within a pilot project and generates
project-scoped, dataset-grounded, human-reviewable business_v1
Ontology Modeling Drafts.

No LLM. No auto-accept. No Action Type generation.
Evidence never includes sample values, raw rows, or storage paths.
"""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    BusinessProject,
    DatasetAsset,
    OntologyModelingDraft,
)

# ── type mapping: profile inferred_type → business_v1 value_type ──────────

_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "date",
    "datetime": "datetime",
}

def _snake_case(name: str) -> str:
    """Normalize a name to snake_case for use as an api_name."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s if s else "unnamed"


def _title_case(name: str) -> str:
    """Safe, deterministic title-case from a snake_case or filename stem."""
    parts = _snake_case(name).split("_")
    return " ".join(p.strip().title() for p in parts if p.strip())


def _build_evidence(
    dataset: DatasetAsset, column_name: str | None = None,
    is_pk: bool = False, is_fk: bool = False, extra: dict | None = None,
) -> list[dict]:
    """Build evidence_refs for a draft — never includes sample_values or raw rows."""
    evidence: dict = {
        "dataset_id": dataset.id,
        "content_hash": dataset.content_hash,
        "original_name": dataset.original_name,
        "profile_schema_version": (
            dataset.profile_json.get("schema_version", "1.0")
        ),
    }
    if column_name:
        evidence["column"] = column_name
    if is_pk:
        evidence["role"] = "primary_key"
    if is_fk:
        evidence["role"] = "foreign_key"
    if extra:
        evidence.update(extra)
    return [evidence]


def _dataset_stems(datasets: list[DatasetAsset]) -> dict[str, list[str]]:
    """Group datasets by normalized stem; return collisions."""
    stem_map: dict[str, list[str]] = defaultdict(list)
    for ds in datasets:
        stem = _snake_case(ds.original_name)
        stem_map[stem].append(ds.id)
    return dict(stem_map)


def generate_dataset_drafts(
    db: Session,
    group_id: str,
    project_id: str,
    created_by: str,
) -> dict:
    """Generate proposed business_v1 drafts from project dataset profiles.

    Returns dict with generated_count, existing_count, skipped_count,
    counts_by_type, and issues list.

    Idempotent: re-running with the same data produces no duplicates.
    Never modifies existing drafts.
    """
    # ── Load project and datasets ───────────────────────────────────────
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise ValueError("Project not found or group mismatch")

    datasets = sorted(
        db.scalars(
            select(DatasetAsset).where(
                DatasetAsset.project_id == project_id,
                DatasetAsset.group_id == group_id,
                DatasetAsset.status == "ready",
            )
        ).all(),
        key=lambda d: (d.original_name, d.id),
    )

    # ── Load existing project-scoped drafts ─────────────────────────────
    existing_drafts = db.scalars(
        select(OntologyModelingDraft).where(
            OntologyModelingDraft.project_id == project_id,
            OntologyModelingDraft.group_id == group_id,
        )
    ).all()

    existing_keys: set[str] = set()
    existing_type_names: set[tuple[str, str]] = set()
    for d in existing_drafts:
        gen_key = (d.payload or {}).get("generation_key")
        if gen_key:
            existing_keys.add(gen_key)
        existing_type_names.add((d.draft_type, (d.name or "").strip().casefold()))

    new_drafts: list[OntologyModelingDraft] = []
    counts: dict[str, int] = {"object_type": 0, "property": 0, "link_type": 0, "action_type": 0}
    existing = 0
    skipped = 0
    issues: list[dict] = []

    # ── Check stem collisions ───────────────────────────────────────────
    stem_collisions = _dataset_stems(datasets)
    collided_stems = {stem for stem, ids in stem_collisions.items() if len(ids) > 1}

    # ── Dataset → Object Type index (for property / link type referencing) ──
    dataset_object_type: dict[str, str] = {}  # dataset_id → api_name

    # ══════════════════════════════════════════════════════════════════════
    #  Object Type drafts — one per dataset with a valid PK
    # ══════════════════════════════════════════════════════════════════════
    for ds in datasets:
        stem = _snake_case(ds.original_name)
        if stem in collided_stems:
            issues.append({
                "code": "object_type_stem_collision",
                "severity": "error",
                "dataset_id": ds.id,
                "column": None,
                "message": (
                    f"Dataset stem '{stem}' collides with another dataset "
                    f"in the same project. Object Type not generated."
                ),
            })
            skipped += 1
            continue

        pk_candidates = ds.profile_json.get("primary_key_candidates", [])
        if not pk_candidates:
            issues.append({
                "code": "no_primary_key_candidate",
                "severity": "warning",
                "dataset_id": ds.id,
                "column": None,
                "message": (
                    f"No primary key candidate found in dataset "
                    f"'{ds.original_name}'. Object Type not generated."
                ),
            })
            skipped += 1
            continue

        # Select best PK: highest confidence, then earliest position
        best_pk = sorted(
            pk_candidates,
            key=lambda p: (
                {"high": 0, "medium": 1, "low": 2}.get(p.get("confidence", "low"), 3),
                next(
                    (c["position"] for c in ds.profile_json.get("columns", [])
                     if c["name"] == p["column"]),
                    999,
                ),
            ),
        )[0]
        pk_col_name = best_pk["column"]

        api_name = stem
        display_name = _title_case(ds.original_name)

        gen_key = (
            f"dataset_object_type:{project_id}:{ds.id}:{api_name}"
        )
        normalized_name = display_name.strip().casefold()

        if gen_key in existing_keys or ("object_type", normalized_name) in existing_type_names:
            existing += 1
            dataset_object_type[ds.id] = api_name
            continue

        evidence = _build_evidence(ds, column_name=pk_col_name, is_pk=True)

        # Find the PK column profile for type info
        pk_col = next(
            (c for c in ds.profile_json.get("columns", []) if c["name"] == pk_col_name),
            None,
        )

        pk_api_name = f"{api_name}_{_snake_case(pk_col_name)}"

        payload = {
            "contract_profile": "business_v1",
            "generator": "dataset_deterministic_v1",
            "generation_key": gen_key,
            "project_id": project_id,
            "source_dataset_id": ds.id,
            "api_name": api_name,
            "display_name": display_name,
            "primary_key": pk_api_name,
            "primary_key_type": pk_col.get("inferred_type", "string") if pk_col else "string",
        }

        description = (
            f"Proposed Object Type from dataset '{ds.original_name}'. "
            f"Primary key: {pk_col_name} (confidence: {best_pk.get('confidence', 'low')}). "
            f"This is a human-reviewable proposal, NOT a published Object Type."
        )

        new_drafts.append(OntologyModelingDraft(
            group_id=group_id,
            draft_type="object_type",
            name=display_name,
            description=description,
            status="proposed",
            project_id=project_id,
            source_dataset_id=ds.id,
            evidence_refs=evidence,
            payload=payload,
            created_by=created_by,
        ))
        existing_keys.add(gen_key)
        existing_type_names.add(("object_type", normalized_name))
        counts["object_type"] += 1
        dataset_object_type[ds.id] = api_name

    # ══════════════════════════════════════════════════════════════════════
    #  Property drafts — one per column in each modeled dataset
    # ══════════════════════════════════════════════════════════════════════
    for ds in datasets:
        obj_api_name = dataset_object_type.get(ds.id)
        if obj_api_name is None:
            continue  # Object Type was not generated for this dataset

        columns = ds.profile_json.get("columns", [])
        if not columns:
            continue

        for col in columns:
            col_name = col["name"]
            inferred = col.get("inferred_type", "string")
            value_type = _TYPE_MAP.get(inferred, "string")
            required = not col.get("nullable", True)
            col_position = col.get("position", 0)
            is_pk = col_name in {
                p["column"] for p in ds.profile_json.get("primary_key_candidates", [])
            }

            prop_name = f"{obj_api_name}.{_snake_case(col_name)}"
            gen_key = (
                f"dataset_property:{project_id}:{ds.id}:"
                f"{_snake_case(col_name)}"
            )
            normalized_name = prop_name.strip().casefold()

            if gen_key in existing_keys or ("property", normalized_name) in existing_type_names:
                existing += 1
                continue

            evidence = _build_evidence(
                ds, column_name=col_name, is_pk=is_pk,
            )

            api_name_prop = f"{obj_api_name}_{_snake_case(col_name)}"
            display_name_prop = f"{_title_case(ds.original_name)} {col_name}"

            payload = {
                "contract_profile": "business_v1",
                "generator": "dataset_deterministic_v1",
                "generation_key": gen_key,
                "project_id": project_id,
                "source_dataset_id": ds.id,
                "api_name": api_name_prop,
                "display_name": display_name_prop,
                "object_type": obj_api_name,
                "property_name": col_name,
                "value_type": value_type,
                "required": required,
                "position": col_position,
            }

            description = (
                f"Proposed Property '{col_name}' on Object Type '{obj_api_name}' "
                f"from dataset '{ds.original_name}'. "
                f"Inferred type: {inferred}, required: {required}. "
                f"This is a human-reviewable proposal, NOT a published Property."
            )

            new_drafts.append(OntologyModelingDraft(
                group_id=group_id,
                draft_type="property",
                name=prop_name,
                description=description,
                status="proposed",
                project_id=project_id,
                source_dataset_id=ds.id,
                evidence_refs=evidence,
                payload=payload,
                created_by=created_by,
            ))
            existing_keys.add(gen_key)
            existing_type_names.add(("property", normalized_name))
            counts["property"] += 1

    # ══════════════════════════════════════════════════════════════════════
    #  Link Type drafts — from FK suggestions within the project
    # ══════════════════════════════════════════════════════════════════════
    for ds in datasets:
        src_api_name = dataset_object_type.get(ds.id)
        if src_api_name is None:
            continue

        fk_suggestions = ds.profile_json.get("foreign_key_suggestions", [])
        for fk in fk_suggestions:
            target_ds_id = fk.get("target_dataset_id")
            if not target_ds_id:
                continue

            tgt_api_name = dataset_object_type.get(target_ds_id)
            if tgt_api_name is None:
                issues.append({
                    "code": "link_target_not_modeled",
                    "severity": "warning",
                    "dataset_id": ds.id,
                    "column": fk.get("source_column"),
                    "message": (
                        f"FK target dataset '{fk.get('target_dataset_name', target_ds_id)}' "
                        f"has no Object Type draft. Link not generated."
                    ),
                })
                skipped += 1
                continue

            source_col = fk.get("source_column", "")
            target_col = fk.get("target_column", "")
            link_name = f"{src_api_name}.{_snake_case(source_col)} → {tgt_api_name}.{_snake_case(target_col)}"

            gen_key = (
                f"dataset_link_type:{project_id}:{ds.id}:{target_ds_id}:"
                f"{_snake_case(source_col)}:{_snake_case(target_col)}"
            )
            normalized_name = link_name.strip().casefold()

            if gen_key in existing_keys or ("link_type", normalized_name) in existing_type_names:
                existing += 1
                continue

            evidence = _build_evidence(
                ds, column_name=source_col, is_fk=True,
            )

            api_name_link = (
                f"{src_api_name}_{_snake_case(source_col)}_to_"
                f"{tgt_api_name}_{_snake_case(target_col)}"
            )

            payload = {
                "contract_profile": "business_v1",
                "generator": "dataset_deterministic_v1",
                "generation_key": gen_key,
                "project_id": project_id,
                "source_dataset_id": ds.id,
                "api_name": api_name_link,
                "display_name": link_name,
                "source_object_type": src_api_name,
                "source_property": source_col,
                "target_object_type": tgt_api_name,
                "target_property": target_col,
                "cardinality": "many_to_one",
            }

            description = (
                f"Proposed Link Type from FK suggestion: "
                f"{src_api_name}.{source_col} → {tgt_api_name}.{target_col}. "
                f"Cardinality: many_to_one. "
                f"This is a human-reviewable proposal, NOT a published Link Type."
            )

            new_drafts.append(OntologyModelingDraft(
                group_id=group_id,
                draft_type="link_type",
                name=link_name,
                description=description,
                status="proposed",
                project_id=project_id,
                source_dataset_id=ds.id,
                evidence_refs=evidence,
                payload=payload,
                created_by=created_by,
            ))
            existing_keys.add(gen_key)
            existing_type_names.add(("link_type", normalized_name))
            counts["link_type"] += 1

    # ══════════════════════════════════════════════════════════════════════
    #  Action Type — explicitly NOT generated from datasets
    # ══════════════════════════════════════════════════════════════════════
    # counts["action_type"] is always 0 — no action type generation from data

    # ── Persist ─────────────────────────────────────────────────────────
    for draft in new_drafts:
        db.add(draft)
    db.commit()

    return {
        "generated_count": sum(counts.values()),
        "existing_count": existing,
        "skipped_count": skipped,
        "counts_by_type": counts,
        "issues": issues,
    }
