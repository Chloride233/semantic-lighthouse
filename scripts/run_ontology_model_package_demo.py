"""Phase 12.6 real model package demo.

Usage:
  DATABASE_URL=sqlite+pysqlite:///.tmp/phase12-realdemo.db \\
  .venv/Scripts/python scripts/run_ontology_model_package_demo.py

Verifies: accept → quality → package → hash → idempotency → audit chain.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semantic_lighthouse.database import SessionLocal
from semantic_lighthouse.dependencies import require_group_role
from semantic_lighthouse.models import Group, OntologyModelingDraft
from semantic_lighthouse.services.ontology_draft_quality import (
    validate_modeling_drafts,
)
from semantic_lighthouse.services.ontology_draft_reviews import review_modeling_drafts
from semantic_lighthouse.services.ontology_packages import build_model_package
from sqlalchemy import select

DEFAULT_GROUP = "Ontology Curation Demo"
REPORT_PATH = Path("docs/ontology-model-package-demo-report.md")

WHITELIST_KEYS = [
    "object_type:concept",
    "object_type:case",
    "property:concept:tags",
    "link_type:concept:wikilink:case",
    "action_type:review_link_target",
]


def main() -> int:
    db = SessionLocal()
    try:
        g = db.scalar(select(Group).where(Group.name == DEFAULT_GROUP))
        if g is None:
            print(f"ERROR: Group '{DEFAULT_GROUP}' not found", file=sys.stderr)
            return 1
        gid = g.id
        reviewer_id = g.created_by

        # ── Find target drafts by generation_key ──────────────────────
        all_drafts = list(
            db.scalars(
                select(OntologyModelingDraft).where(
                    OntologyModelingDraft.group_id == gid,
                )
            ).all()
        )
        targets = []
        for key in WHITELIST_KEYS:
            found = [d for d in all_drafts
                     if (d.payload or {}).get("generation_key") == key]
            if found:
                targets.append(found[0])
            else:
                print(f"ERROR: key '{key}' not found among {len(all_drafts)} drafts",
                      file=sys.stderr)
                return 2

        print(f"Selected {len(targets)} drafts:")
        for d in targets:
            print(f"  {d.draft_type}: {d.name}")

        # ── Accept selected drafts ────────────────────────────────────
        note = "Phase 12.6 demo review — scripted, not production auto-accept"
        require_group_role(db, reviewer_id, gid, {"owner", "admin"})
        targets, _ = review_modeling_drafts(
            db=db,
            group_id=gid,
            draft_ids=[d.id for d in targets],
            decision="accepted",
            reviewer_id=reviewer_id,
            review_note=note,
        )
        print(f"\nAccepted {len(targets)} drafts (reviewer={reviewer_id})")

        # ── Quality gate ──────────────────────────────────────────────
        qr = validate_modeling_drafts(db, gid)
        accepted_ids = {d.id for d in targets}
        errors = [i for i in qr["issues"]
                  if i["severity"] == "error" and i["draft_id"] in accepted_ids]
        warnings = [i for i in qr["issues"]
                    if i["severity"] == "warning" and i["draft_id"] in accepted_ids]
        wc: dict[str, int] = {}
        for w in warnings:
            wc[w["code"]] = wc.get(w["code"], 0) + 1

        print(f"Quality: errors={len(errors)}, warnings={len(warnings)}")
        assert len(errors) == 0, f"Unexpected quality errors: {errors}"

        # ── Build package ─────────────────────────────────────────────
        pkg, created = build_model_package(db, gid, reviewer_id)
        assert created, "Expected new package"
        c = pkg.contract_json
        print(f"Package v{pkg.version}: hash={pkg.content_hash[:16]}..., "
              f"drafts={pkg.draft_count}, quality={pkg.quality_status}")
        print(f"  types: OT={len(c['object_types'])} "
              f"Prop={len(c['properties'])} "
              f"Link={len(c['link_types'])} "
              f"Action={len(c['action_types'])}")
        assert len(c["action_types"]) == 1
        action_contract = c["action_types"][0].get("action_contract", {})
        assert action_contract == {
            "required_role": "admin",
            "confirmation_requirement": "always",
            "evidence_requirement": ["ontology_validation_issue"],
        }
        print(f"  action_contract: {action_contract['required_role']}/"
              f"{action_contract['confirmation_requirement']}/"
              f"{action_contract['evidence_requirement']}")

        # ── Source draft IDs match ────────────────────────────────────
        assert set(pkg.source_draft_ids) == accepted_ids

        # ── Idempotency ───────────────────────────────────────────────
        pkg2, c2 = build_model_package(db, gid, reviewer_id)
        assert not c2 and pkg2.id == pkg.id and pkg2.version == pkg.version
        print("Idempotent: same package returned")

        # ── Hash verification ─────────────────────────────────────────
        canonical = json.dumps(
            c, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert computed == pkg.content_hash, "Content hash mismatch"
        print("Hash: SHA-256 verified")

        # ── Audit chain ───────────────────────────────────────────────
        for d in targets:
            db.refresh(d)
            assert d.status == "accepted"
            assert d.reviewed_by == reviewer_id and d.reviewed_at is not None
        assert pkg.created_by == reviewer_id and pkg.created_at is not None
        print("Audit: all drafts + package have reviewer/creator metadata")

        other = [d for d in all_drafts if d.id not in accepted_ids]
        for d in other:
            assert d.status == "proposed", f"{d.name} changed to {d.status}"

        # ── Report ────────────────────────────────────────────────────
        lines = [
            "# Ontology Model Package Demo Report",
            "",
            f"**Date**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
            f"**Group**: {DEFAULT_GROUP} ({gid})",
            "",
            "## Selected Drafts",
            "",
            "| Type | Name |",
            "|------|------|",
            *[f"| {d.draft_type} | {d.name} |" for d in targets],
            "",
            "## Quality Gate",
            f"  Errors: {len(errors)}, Warnings: {len(warnings)}",
            *([""] + ["| Code | Count |", "|------|-------|"]
              + [f"| {c} | {n} |" for c, n in sorted(wc.items())]
              if wc else []),
            "",
            "## Package",
            f"- Version: {pkg.version}, Hash: `{pkg.content_hash}`",
            f"- Drafts: {pkg.draft_count}, Quality: {pkg.quality_status}",
            f"- OT={len(c['object_types'])}, Prop={len(c['properties'])}, "
            f"Link={len(c['link_types'])}, Action={len(c['action_types'])}",
            f"- Action contract: required_role={action_contract['required_role']}, "
            f"confirmation={action_contract['confirmation_requirement']}, "
            f"evidence={action_contract['evidence_requirement']}",
            "",
            "## Idempotency & Hash",
            "- Same accepted set → same package (idempotent)",
            "- SHA-256 matches stored content_hash",
            "",
            "## Audit Chain",
            f"- Shared review service accepted all {len(targets)} drafts",
            "- All accepted drafts: reviewed_by, reviewed_at, review_note",
            "- Package: created_by, created_at",
            f"- {len(other)} unselected drafts unchanged",
            "",
            "## Boundaries",
            "- No external KB modification / Agent / LLM / publish / execution",
            "- Accepted ≠ production; package is immutable snapshot",
            "",
        ]
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(f"Report: {REPORT_PATH}")
        print("\nPASS: all assertions passed")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
