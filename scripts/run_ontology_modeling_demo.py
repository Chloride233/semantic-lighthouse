"""Phase 12.1 real KB modeling draft demo runner.

Usage:
  DATABASE_URL=sqlite+pysqlite:///.tmp/phase12-modeling-demo.db \\
  .venv/Scripts/python scripts/run_ontology_modeling_demo.py

Pre-requisites:
  1. alembic upgrade head against DATABASE_URL.
  2. scripts/run_ontology_curation_demo.py has been run against the same DB
     (creates "Ontology Curation Demo" group with scanned/triaged data).
  3. Does NOT modify F:\\ontology-kb\\knowledge-graph.
  4. Does NOT call web, LLM, or Agent.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date as date_type
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semantic_lighthouse.database import SessionLocal
from semantic_lighthouse.models import (
    Group,
    OntologyEntity,
    OntologyModelingDraft,
    OntologyRelation,
    OntologyValidationIssue,
)
from semantic_lighthouse.services.ontology_drafts import generate_modeling_drafts
from sqlalchemy import func, select

DEFAULT_GROUP_NAME = "Ontology Curation Demo"
DEFAULT_REPORT = Path("docs/ontology-modeling-draft-demo-report.md")

# ── Pure helpers (testable without DB) ──────────────────────────────────


def count_missing_generation_keys(drafts: list[dict]) -> int:
    return sum(1 for d in drafts if not (d.get("payload") or {}).get("generation_key"))


def count_missing_source_pointers(drafts: list[dict]) -> int:
    return sum(
        1
        for d in drafts
        if not any(
            d.get(k)
            for k in (
                "source_entity_id",
                "source_relation_id",
                "source_issue_id",
                "source_rag_run_id",
            )
        )
    )


def count_empty_evidence(drafts: list[dict]) -> int:
    return sum(1 for d in drafts if not d.get("evidence_refs"))


def count_duplicate_type_names(drafts: list[dict]) -> int:
    seen: dict[tuple[str, str], int] = {}
    for d in drafts:
        key = (d.get("draft_type", ""), (d.get("name", "") or "").strip().casefold())
        seen[key] = seen.get(key, 0) + 1
    return sum(v - 1 for v in seen.values() if v > 1)


def count_single_entity_properties(drafts: list[dict]) -> int:
    """Property candidates backed by exactly 1 entity."""
    return sum(
        1
        for d in drafts
        if d.get("draft_type") == "property"
        and (d.get("payload") or {}).get("entity_count") == 1
    )


def count_single_relation_links(drafts: list[dict]) -> int:
    """Link candidates with exactly 1 relation evidence."""
    return sum(
        1
        for d in drafts
        if d.get("draft_type") == "link_type"
        and (d.get("payload") or {}).get("relation_count") == 1
    )


def count_single_issue_actions(drafts: list[dict]) -> int:
    """Action candidates with exactly 1 issue evidence."""
    return sum(
        1
        for d in drafts
        if d.get("draft_type") == "action_type"
        and (d.get("payload") or {}).get("issue_count") == 1
    )


def count_properties_per_object_type(drafts: list[dict]) -> dict[str, int]:
    """Count property drafts per object_type (from payload)."""
    counts: dict[str, int] = defaultdict(int)
    for d in drafts:
        if d.get("draft_type") != "property":
            continue
        ot = (d.get("payload") or {}).get("object_type", "unknown")
        counts[ot] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Ontology modeling draft demo")
    p.add_argument("--group-name", default=DEFAULT_GROUP_NAME)
    p.add_argument("--group-id", default=None)
    p.add_argument("--report-path", default=str(DEFAULT_REPORT))
    args = p.parse_args()

    report_path = Path.cwd() / args.report_path
    db = SessionLocal()

    try:
        # ── Find group ────────────────────────────────────────────────
        if args.group_id:
            g = db.get(Group, args.group_id)
        else:
            g = db.scalar(
                select(Group).where(Group.name == args.group_name)
            )

        if g is None:
            print(
                f"ERROR: Group not found. Run scripts/run_ontology_curation_demo.py "
                f"first to create the '{args.group_name}' group with ontology data.",
                file=sys.stderr,
            )
            return 1

        gid = g.id

        # ── Verify entities exist ──────────────────────────────────────
        entity_count = db.scalar(
            select(func.count()).select_from(
                select(OntologyEntity).where(OntologyEntity.group_id == gid).subquery()
            )
        ) or 0

        if entity_count == 0:
            print(
                f"ERROR: No ontology entities in group '{g.name}' (id={gid}). "
                f"Run scripts/run_ontology_curation_demo.py first.",
                file=sys.stderr,
            )
            return 2

        relation_count = db.scalar(
            select(func.count()).select_from(
                select(OntologyRelation).where(OntologyRelation.group_id == gid).subquery()
            )
        ) or 0

        issue_count = db.scalar(
            select(func.count()).select_from(
                select(OntologyValidationIssue).where(
                    OntologyValidationIssue.group_id == gid,
                ).subquery()
            )
        ) or 0

        confirmed_issue_count = db.scalar(
            select(func.count()).select_from(
                select(OntologyValidationIssue).where(
                    OntologyValidationIssue.group_id == gid,
                    OntologyValidationIssue.triage_status == "confirmed",
                ).subquery()
            )
        ) or 0

        print(
            f"Group: {g.name} (id={gid})\n"
            f"Source: {entity_count} entities, {relation_count} relations, "
            f"{issue_count} issues ({confirmed_issue_count} confirmed)"
        )

        # ── First generation ──────────────────────────────────────────
        print("\n--- First generation ---")
        r1 = generate_modeling_drafts(db, gid, g.created_by)
        print(
            f"  Generated: {r1['generated_count']}, "
            f"Existing: {r1['existing_count']}, "
            f"Skipped: {r1['skipped_count']}"
        )
        for dtype in ("object_type", "property", "link_type", "action_type"):
            print(f"  {dtype}: {r1['counts_by_type'][dtype]}")

        # ── Second generation (idempotency check) ──────────────────────
        print("\n--- Second generation (idempotency) ---")
        r2 = generate_modeling_drafts(db, gid, g.created_by)
        idempotent = r2["generated_count"] == 0
        print(
            f"  Generated: {r2['generated_count']} (idempotent={'YES' if idempotent else 'NO'}), "
            f"Existing: {r2['existing_count']}"
        )

        # ── Fetch all drafts ───────────────────────────────────────────
        all_drafts = list(
            db.scalars(
                select(OntologyModelingDraft).where(
                    OntologyModelingDraft.group_id == gid,
                )
            ).all()
        )

        drafts_json: list[dict] = []
        for d in all_drafts:
            drafts_json.append({
                "id": d.id,
                "draft_type": d.draft_type,
                "name": d.name,
                "description": d.description,
                "status": d.status,
                "source_entity_id": d.source_entity_id,
                "source_relation_id": d.source_relation_id,
                "source_issue_id": d.source_issue_id,
                "source_rag_run_id": d.source_rag_run_id,
                "evidence_refs": d.evidence_refs or [],
                "payload": d.payload or {},
            })

        # ── Quality checks ─────────────────────────────────────────────
        total = len(drafts_json)
        dt_counts: dict[str, int] = defaultdict(int)
        for d in drafts_json:
            dt_counts[d["draft_type"]] += 1

        missing_keys = count_missing_generation_keys(drafts_json)
        missing_source = count_missing_source_pointers(drafts_json)
        empty_evidence = count_empty_evidence(drafts_json)
        dup_names = count_duplicate_type_names(drafts_json)

        single_props = count_single_entity_properties(drafts_json)
        single_links = count_single_relation_links(drafts_json)
        single_actions = count_single_issue_actions(drafts_json)
        props_per_ot = count_properties_per_object_type(drafts_json)

        hard_pass = (missing_keys == 0 and missing_source == 0
                     and empty_evidence == 0 and dup_names == 0 and idempotent)

        # ── Quality validator ────────────────────────────────────────────
        from semantic_lighthouse.services.ontology_draft_quality import (
            validate_modeling_drafts,
        )

        qr = validate_modeling_drafts(db, gid)
        warning_codes: dict[str, int] = {}
        for i in qr["issues"]:
            if i["severity"] == "warning":
                c = i["code"]
                warning_codes[c] = warning_codes.get(c, 0) + 1
        print(
            f"  Validator: status={qr['status']}, "
            f"errors={qr['error_count']}, warnings={qr['warning_count']}"
        )

        # ── Candidate samples ──────────────────────────────────────────
        samples: dict[str, list[dict]] = {}
        for dtype in ("object_type", "property", "link_type", "action_type"):
            typed = [d for d in drafts_json if d["draft_type"] == dtype]
            typed.sort(key=lambda d: len(d.get("evidence_refs", [])), reverse=True)
            samples[dtype] = typed[:10]

        # ── Build report ───────────────────────────────────────────────
        lines = _build_report(
            group_name=g.name,
            group_id=gid,
            entity_count=entity_count,
            relation_count=relation_count,
            issue_count=issue_count,
            confirmed_issue_count=confirmed_issue_count,
            total=total,
            dt_counts=dict(dt_counts),
            r1=r1,
            idempotent=idempotent,
            missing_keys=missing_keys,
            missing_source=missing_source,
            empty_evidence=empty_evidence,
            dup_names=dup_names,
            hard_pass=hard_pass,
            single_props=single_props,
            single_links=single_links,
            single_actions=single_actions,
            props_per_ot=props_per_ot,
            samples=samples,
            db_url=os.environ.get("DATABASE_URL", "N/A"),
            validator_status=qr["status"],
            validator_errors=qr["error_count"],
            validator_warnings=qr["warning_count"],
            warning_codes=warning_codes,
        )

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nReport: {report_path}")
        print(f"Technical integrity: {'PASS' if hard_pass else 'ISSUES FOUND'}")
    finally:
        db.close()

    return 0


# ── Report builder ──────────────────────────────────────────────────────


def _build_report(
    group_name: str,
    group_id: str,
    entity_count: int,
    relation_count: int,
    issue_count: int,
    confirmed_issue_count: int,
    total: int,
    dt_counts: dict[str, int],
    r1: dict,
    idempotent: bool,
    missing_keys: int,
    missing_source: int,
    empty_evidence: int,
    dup_names: int,
    hard_pass: bool,
    single_props: int,
    single_links: int,
    single_actions: int,
    props_per_ot: dict[str, int],
    samples: dict[str, list[dict]],
    db_url: str,
    validator_status: str = "N/A",
    validator_errors: int = 0,
    validator_warnings: int = 0,
    warning_codes: dict[str, int] | None = None,
) -> list[str]:
    today = date_type.today().isoformat()

    lines: list[str] = [
        "# Ontology Modeling Draft Demo Report",
        "",
        f"**Date**: {today}",
        "**Phase**: 12.1 real KB modeling draft demo",
        f"**DB**: `{db_url}`",
        f"**Group**: `{group_name}` (`{group_id}`)",
        "",
        "## 1. Source Baseline",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Entities | {entity_count} |",
        f"| Relations | {relation_count} |",
        f"| Issues (total) | {issue_count} |",
        f"| Issues (confirmed) | {confirmed_issue_count} |",
        "",
        "## 2. Draft Counts",
        "",
        "| Draft Type | Count |",
        "|------------|-------|",
        f"| object_type | {dt_counts.get('object_type', 0)} |",
        f"| property | {dt_counts.get('property', 0)} |",
        f"| link_type | {dt_counts.get('link_type', 0)} |",
        f"| action_type | {dt_counts.get('action_type', 0)} |",
        f"| **Total** | **{total}** |",
        "",
        f"First generation: {r1['generated_count']} generated, "
        f"{r1['existing_count']} existing, {r1['skipped_count']} skipped.",
        "",
        "## 3. Hard Quality Checks",
        "",
        "| Check | Count | Gate |",
        "|-------|-------|------|",
        f"| Missing generation_key | {missing_keys} | must be 0 |",
        f"| Missing source pointer | {missing_source} | must be 0 |",
        f"| Empty evidence_refs | {empty_evidence} | must be 0 |",
        f"| Duplicate (type, name) | {dup_names} | must be 0 |",
        f"| Second generation idempotent | {'YES' if idempotent else 'NO'} | must be YES |",
        "",
        f"**Technical integrity**: {'**PASS**' if hard_pass else '**ISSUES FOUND**'}",
        "",
        "### 3.5 Quality Validator (Phase 12.2b)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Validator status | **{validator_status}** |",
        f"| Error count | {validator_errors} |",
        f"| Warning count | {validator_warnings} |",
        "",
    ]

    if warning_codes:
        lines.append("**Warning code distribution**:")
        lines.append("")
        lines.append("| Code | Count |")
        lines.append("|------|-------|")
        for c, n in sorted(warning_codes.items(), key=lambda x: -x[1]):
            lines.append(f"| {c} | {n} |")
        lines.append("")

    lines += [
        "",
        "## 4. Noise Indicators",
        "",
        "| Indicator | Count | Note |",
        "|-----------|-------|------|",
        f"| Property candidates with 1 entity | {single_props} | single-entity candidates carry less signal |",
        f"| Link candidates with 1 relation evidence | {single_links} | single-relation candidates carry less signal |",
        f"| Action candidates with 1 issue evidence | {single_actions} | single-issue candidates carry less signal |",
        "",
        "### Properties per Object Type",
        "",
        "| Object Type | Property Count |",
        "|-------------|---------------|",
        *[f"| {ot} | {c} |" for ot, c in props_per_ot.items()],
        "",
        "## 5. Candidate Samples",
        "",
    ]

    dtype_labels = {
        "object_type": "Object Type",
        "property": "Property",
        "link_type": "Link Type",
        "action_type": "Action Type",
    }

    for dtype in ("object_type", "property", "link_type", "action_type"):
        items = samples.get(dtype, [])
        lines.append(f"### {dtype_labels.get(dtype, dtype)} (showing {len(items)} of {dt_counts.get(dtype, 0)})")
        lines.append("")
        if items:
            lines.append("| Name | Source | Evidence | Key Payload |")
            lines.append("|------|--------|----------|-------------|")
            for d in items:
                src = (
                    d.get("source_entity_id") or d.get("source_relation_id")
                    or d.get("source_issue_id") or d.get("source_rag_run_id")
                    or "—"
                )
                ev_count = len(d.get("evidence_refs", []))
                p = d.get("payload", {})
                pk = (p.get("generation_key", "") or "")[:50]
                extra = ""
                if dtype == "object_type":
                    extra = f"entities={p.get('entity_count', '?')}"
                elif dtype == "property":
                    extra = f"types={p.get('observed_value_types', [])}"
                elif dtype == "link_type":
                    extra = f"rels={p.get('relation_count', '?')}"
                elif dtype == "action_type":
                    extra = f"issues={p.get('issue_count', '?')}"
                lines.append(
                    f"| {d['name'][:60]} | {src[:8]}... | {ev_count} | "
                    f"key={pk}, {extra} |"
                )
            lines.append("")
        else:
            lines.append("*No candidates of this type.*")
            lines.append("")

    lines += [
        "## 6. Interpretation",
        "",
        "### What These Candidates Are",
        "",
        "- **Object Type candidates** are derived from knowledge base `entityType` values "
        "(Concept, Vendor, Product, Methodology, Case, Person, Proposal, FAQ). "
        "They are **knowledge meta-model candidates** — they describe how the KB is structured, "
        "not necessarily customer business objects. A `Concept` object type should not be "
        "confused with a customer-facing business object type.",
        "- **Property candidates** are derived from frontmatter fields per entity type. "
        "They describe KB metadata conventions (e.g., `Concept.tags`, `Vendor.created`), "
        "not necessarily business object properties.",
        "- **Link Type candidates** are derived from `[[wikilink]]` relations between entities. "
        "They represent **knowledge association patterns**, not business semantic relationships. "
        "A `Concept -> Concept (wikilink)` link type means two KB concept documents reference "
        "each other; it does not imply a business domain relationship.",
        "- **Action Type candidates** are derived from governance issue codes and triage rules. "
        "They are **human governance action suggestions**, not automatically executable "
        "business actions. `review_link_target` means a human should review a broken wikilink; "
        "it does not trigger an automated workflow.",
        "",
        "### Important Distinctions",
        "",
        "- **proposed ≠ accepted ≠ production**. All drafts here are `proposed` — none have "
        "been reviewed by a human owner/admin.",
        "- **Knowledge meta-model ≠ business ontology**. The current KB entityType taxonomy "
        "(Concept/Vendor/Product/etc.) is a document classification system. Direct 1:1 mapping "
        "to business object types requires domain modeling from a human expert.",
        "- **wikilink ≠ business relation**. Wikilinks express navigational/document "
        "connections, not typed business relationships with cardinality, direction, and "
        "lifecycle semantics.",
        "- **governance action ≠ executable action**. Action type drafts describe what "
        "governance tasks exist; they do not define automated business operations with "
        "roles, inputs, outputs, and side effects.",
        "",
        "## 7. Quality Conclusion",
        "",
    ]

    if hard_pass:
        lines += [
            "**Technical integrity: PASS** — all hard checks are 0, generation is idempotent.",
            "",
            f"Noise indicators: {single_props} single-entity properties, "
            f"{single_links} single-relation links, {single_actions} single-issue actions. "
            "These are risk flags, not failures — they indicate candidates with weaker "
            "evidence that a human reviewer should scrutinize more carefully.",
            "",
            "**Recommendation**: Proceed to Phase 12.2 (draft quality gates). "
            "The deterministic generation pipeline is producing structurally valid, "
            "idempotent, evidence-backed candidates. Quality gates in 12.2 should "
            "add per-draft validation before accepting any draft for package assembly.",
        ]
    else:
        lines += [
            "**Technical integrity: ISSUES FOUND** — one or more hard checks failed.",
            "",
            "Review the failed checks above. If any draft is missing generation_key or "
            "source pointer, inspect the generation rules in "
            "`src/semantic_lighthouse/services/ontology_drafts.py`.",
        ]

    lines += [
        "",
        "## 8. Boundaries",
        "",
        "- ✅ No drafts accepted or rejected — all remain `proposed`",
        "- ✅ No external KB modified",
        "- ✅ No Agent, no LLM, no web calls",
        "- ✅ No new migration, no API changes",
        "- ✅ Generation is deterministic and idempotent",
        "- ✅ Accepted ≠ production — this demo does not publish anything",
        "",
    ]

    return lines


if __name__ == "__main__":
    sys.exit(main())
