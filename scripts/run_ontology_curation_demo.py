"""Phase 10.2 real KB curation demo runner.

Usage:
  DATABASE_URL=sqlite+pysqlite:///.tmp/phase10-curation-demo.db \\
  .venv/Scripts/python scripts/run_ontology_curation_demo.py

Pre-requisite: alembic upgrade head must have been run against DATABASE_URL.
Does NOT modify the external knowledge base.
Does NOT call web, LLM, or Agent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semantic_lighthouse.database import SessionLocal
from semantic_lighthouse.models import (
    Group,
    GroupMembership,
    OntologyEntity,
    OntologyRelation,
    OntologyValidationIssue,
    User,
)
from semantic_lighthouse.services.document_ingestion import ingest_markdown, should_import_markdown
from semantic_lighthouse.services.ontology import scan_group
from semantic_lighthouse.services.ontology_drafts import determine_action_type
from sqlalchemy import select

DEFAULT_KB = Path(os.environ.get("KNOWLEDGE_BASE_PATH", "./knowledge-graph"))
DEFAULT_REPORT = Path("docs/ontology-curation-demo-report.md")

KB_ENTITY_DIRS = {
    "concepts", "vendors", "products", "methodologies",
    "cases", "persons", "proposals", "faqs",
}


# ── Pure helper functions (testable without DB/KB) ─────────────────────


def classify_unresolved_wikilink(target_path: str) -> str:
    """Classify an unresolved wikilink by its target_path prefix.

    Returns triage_note string.
    """
    if target_path.startswith("research/"):
        return "missing_research_doc_or_directory"
    first_dir = target_path.split("/")[0] if "/" in target_path else ""
    if first_dir in KB_ENTITY_DIRS:
        return "missing_or_renamed_entity_doc"
    return "review_link_target"


def calculate_priority(code: str, affected_count: int = 1) -> str:
    """Calculate backlog priority from issue code and affected count."""
    if code in ("stale_eval_gold_doc_id", "duplicate_title", "duplicate_alias"):
        return "high"
    if code == "unresolved_wikilink":
        if affected_count >= 3:
            return "high"
        return "medium"
    return "medium"


def aggregate_backlog(issues: list[dict]) -> list[dict]:
    """Aggregate confirmed/triaged issues into curation backlog entries.

    Each issue dict should have: code, triage_note, source_path, details.

    Grouping:
      - unresolved_wikilink: by target_path
      - stale_eval_gold_doc_id: by expected_doc_id
      - duplicate_title: by normalized_title
      - duplicate_alias: by normalized_alias

    Returns list of backlog entry dicts sorted by priority then affected_count desc.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)

    for issue in issues:
        code = issue.get("code", "")
        details = issue.get("details", {}) or {}
        source_path = issue.get("source_path", "")

        if code == "unresolved_wikilink":
            key = (code, details.get("target_path", ""))
        elif code == "stale_eval_gold_doc_id":
            key = (code, details.get("expected_doc_id", ""))
        elif code == "duplicate_title":
            key = (code, details.get("normalized_title", ""))
        elif code == "duplicate_alias":
            key = (code, details.get("normalized_alias", ""))
        else:
            key = (code, source_path)

        groups[key].append(issue)

    backlog: list[dict] = []
    for (code, target), items in groups.items():
        action_type = determine_action_type(code, items[0].get("triage_note", ""))
        priority = calculate_priority(code, len(items))
        examples = [i.get("source_path", "") for i in items[:5]]

        suggested = _suggested_action(action_type, target, len(items))

        entry = {
            "action_type": action_type,
            "priority": priority,
            "issue_code": code,
            "target": target,
            "source_path": items[0].get("source_path", ""),
            "affected_count": len(items),
            "examples": examples,
            "suggested_human_action": suggested,
        }
        backlog.append(entry)

    priority_order = {"high": 0, "medium": 1, "low": 2}
    backlog.sort(key=lambda e: (priority_order.get(e["priority"], 2), -e["affected_count"]))
    return backlog


def _suggested_action(action_type: str, target: str, count: int) -> str:
    """Generate human-readable suggested action for a backlog entry."""
    entity_count = f"{count} referencing document{'s' if count > 1 else ''}"
    if action_type == "create_missing_research_doc":
        return (
            f"Create the missing research document `{target}`. "
            f"{entity_count} link to this path. "
            f"If the research directory was intentionally excluded from KB, "
            f"update wikilinks to point to existing concept documents instead."
        )
    if action_type == "create_or_rename_entity_doc":
        return (
            f"Create or rename the entity document `{target}`. "
            f"{entity_count} wikilink to this path. "
            f"Verify whether the document was renamed, moved to a different directory, "
            f"or never created — then fix wikilinks or create the missing file."
        )
    if action_type == "update_eval_gold_doc_id":
        return (
            f"Update eval gold document ID `{target}` in "
            f"`docs/eval/rag-queries-ontology.json`. "
            f"Either the document does not exist in the current KB, or the "
            f"expected_doc_id is stale. Review the referenced questions and "
            f"correct the doc ID to match an available KB document."
        )
    if action_type == "resolve_identity_conflict":
        return (
            f"Resolve identity conflict for `{target}`. "
            f"Multiple entities share this title or alias. "
            f"Determine whether they represent the same concept (merge) or "
            f"different concepts (rename to disambiguate). "
            f"{entity_count} affected."
        )
    if action_type == "review_link_target":
        return (
            f"Review wikilink target `{target}`. "
            f"{entity_count} wikilink to this path but it does not resolve. "
            f"Determine whether a new document is needed, the link should be "
            f"updated to point to an existing entity, or the link should be removed."
        )
    return f"Review issue: {action_type} for target {target}"


# ── Main demo runner ────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Ontology curation demo")
    p.add_argument("--kb-path", default=str(DEFAULT_KB))
    p.add_argument("--report-path", default=str(DEFAULT_REPORT))
    args = p.parse_args()
    kb_root = Path(args.kb_path).resolve()
    report_path = Path.cwd() / args.report_path

    if not kb_root.exists():
        print(f"SKIP: KB path not found: {kb_root}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        # ── Setup ──────────────────────────────────────────────────
        print("Creating demo user and group...")
        uid, gid = str(uuid4()), str(uuid4())
        db.add(User(id=uid, email="curation-demo@onto.local", password_hash="x", display_name="Curation Demo"))
        db.add(Group(id=gid, name="Ontology Curation Demo", created_by=uid))
        db.add(GroupMembership(group_id=gid, user_id=uid, role="admin"))
        db.flush()

        # ── Import ─────────────────────────────────────────────────
        imported, skipped = 0, 0
        for fp in sorted(kb_root.rglob("*.md")):
            if not should_import_markdown(fp):
                skipped += 1
                continue
            try:
                rel = fp.relative_to(kb_root).as_posix()
            except ValueError:
                rel = fp.name
            md = fp.read_text(encoding="utf-8")
            r = ingest_markdown(db, group_id=gid, created_by=uid, file_name=fp.name, source_path=rel, markdown=md)
            if r.created:
                imported += 1
            else:
                skipped += 1

        print(f"Imported: {imported}, skipped: {skipped}")

        # ── Initial scan ───────────────────────────────────────────
        sr = scan_group(db, gid)
        print(
            f"Scan: {sr['scanned_count']} docs, {sr['entity_count']} entities, "
            f"{sr['relation_count']} relations, {sr['issue_count']} issues"
        )

        # ── Deterministic triage ───────────────────────────────────
        all_issues = db.scalars(
            select(OntologyValidationIssue).where(
                OntologyValidationIssue.group_id == gid,
            )
        ).all()

        now = datetime.now(UTC)
        triaged_count = 0
        pending_count = 0

        for issue in all_issues:
            if issue.code == "unresolved_wikilink":
                target_path = (issue.details or {}).get("target_path", "")
                issue.triage_status = "confirmed"
                issue.triage_note = classify_unresolved_wikilink(target_path)
                issue.triaged_by = uid
                issue.triaged_at = now
                triaged_count += 1
            elif issue.code == "stale_eval_gold_doc_id":
                issue.triage_status = "confirmed"
                issue.triage_note = "update_eval_gold_or_add_missing_doc"
                issue.triaged_by = uid
                issue.triaged_at = now
                triaged_count += 1
            elif issue.code in ("duplicate_title", "duplicate_alias"):
                issue.triage_status = "confirmed"
                issue.triage_note = "resolve_identity_conflict"
                issue.triaged_by = uid
                issue.triaged_at = now
                triaged_count += 1
            else:
                pending_count += 1

        db.commit()
        print(f"Triaged: {triaged_count} confirmed, {pending_count} pending")

        # ── Re-scan to verify triage persistence ───────────────────
        sr2 = scan_group(db, gid)
        print(
            f"Re-scan: {sr2['scanned_count']} docs, {sr2['entity_count']} entities, "
            f"{sr2['relation_count']} relations, {sr2['issue_count']} issues"
        )

        issues_after = db.scalars(
            select(OntologyValidationIssue).where(
                OntologyValidationIssue.group_id == gid,
            )
        ).all()
        confirmed_after = sum(1 for i in issues_after if i.triage_status == "confirmed")
        pending_after = sum(1 for i in issues_after if i.triage_status == "pending")
        triage_persisted = confirmed_after == triaged_count
        print(f"After rescan: {confirmed_after} confirmed, {pending_after} pending")

        # ── Collect stats ──────────────────────────────────────────
        ee = db.scalars(select(OntologyEntity).where(OntologyEntity.group_id == gid)).all()
        rr = db.scalars(select(OntologyRelation).where(OntologyRelation.group_id == gid)).all()

        et_cnt: dict[str, int] = {}
        for e in ee:
            et_cnt[e.entity_type] = et_cnt.get(e.entity_type, 0) + 1

        rel_ok = sum(1 for r in rr if r.status == "resolved")
        rel_bad = sum(1 for r in rr if r.status == "unresolved")

        ic_cnt: dict[str, int] = {}
        ic_confirmed: dict[str, int] = {}
        for i in issues_after:
            ic_cnt[i.code] = ic_cnt.get(i.code, 0) + 1
            if i.triage_status == "confirmed":
                ic_confirmed[i.code] = ic_confirmed.get(i.code, 0) + 1

        # ── Build backlog from confirmed issues ────────────────────
        confirmed_issues: list[dict] = []
        for i in issues_after:
            if i.triage_status == "confirmed":
                confirmed_issues.append({
                    "code": i.code,
                    "triage_note": i.triage_note or "",
                    "source_path": i.source_path,
                    "details": i.details or {},
                })

        backlog = aggregate_backlog(confirmed_issues)

        at_dist: dict[str, int] = {}
        priority_dist: dict[str, int] = {}
        for b in backlog:
            at_dist[b["action_type"]] = at_dist.get(b["action_type"], 0) + 1
            priority_dist[b["priority"]] = priority_dist.get(b["priority"], 0) + 1

        # ── JSON summary ───────────────────────────────────────────
        summary = {
            "kb_path": str(kb_root),
            "imported": imported,
            "skipped": skipped,
            "scanned": sr["scanned_count"],
            "entities": len(ee),
            "relations": len(rr),
            "resolved_relations": rel_ok,
            "unresolved_relations": rel_bad,
            "issues_total": len(issues_after),
            "issues_by_code": ic_cnt,
            "triage": {
                "confirmed": triaged_count,
                "pending": pending_count,
                "confirmed_by_code": ic_confirmed,
            },
            "triage_persisted_across_rescan": triage_persisted,
            "backlog": {
                "total_entries": len(backlog),
                "action_type_distribution": at_dist,
                "priority_distribution": priority_dist,
            },
        }
        print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))

        # ── Markdown report ────────────────────────────────────────
        lines = _build_report(
            kb_root=kb_root,
            db_url=os.environ.get("DATABASE_URL", "N/A"),
            imported=imported,
            skipped=skipped,
            scanned=sr["scanned_count"],
            entities=len(ee),
            relations=len(rr),
            rel_ok=rel_ok,
            rel_bad=rel_bad,
            issues_total=len(issues_after),
            et_cnt=et_cnt,
            ic_cnt=ic_cnt,
            triaged_count=triaged_count,
            pending_count=pending_count,
            confirmed_count=confirmed_after,
            triage_persisted=triage_persisted,
            backlog=backlog,
            at_dist=at_dist,
            priority_dist=priority_dist,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nReport: {report_path}")
    finally:
        db.close()
    return 0


def _build_report(
    kb_root: Path,
    db_url: str,
    imported: int,
    skipped: int,
    scanned: int,
    entities: int,
    relations: int,
    rel_ok: int,
    rel_bad: int,
    issues_total: int,
    et_cnt: dict[str, int],
    ic_cnt: dict[str, int],
    triaged_count: int,
    pending_count: int,
    confirmed_count: int,
    triage_persisted: bool,
    backlog: list[dict],
    at_dist: dict[str, int],
    priority_dist: dict[str, int],
) -> list[str]:
    """Build Markdown report lines."""
    from datetime import date as date_type

    today = date_type.today().isoformat()

    lines = [
        "# Ontology Curation Demo Report",
        "",
        f"**Date**: {today}",
        f"**KB**: {kb_root}",
        f"**DB**: temporary SQLite (`{db_url}`)",
        "",
        "## Import & Scan",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Imported | {imported} |",
        f"| Skipped | {skipped} |",
        f"| Scanned (ready) | {scanned} |",
        f"| Entities | {entities} |",
        f"| Relations | {relations} |",
        f"| Issues | {issues_total} |",
        "",
        "## Entities by Type",
        "",
        "| entityType | Count |",
        "|------------|-------|",
        *[f"| {t} | {c} |" for t, c in sorted(et_cnt.items(), key=lambda x: -x[1])],
        "",
        "## Relations by Status",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| resolved | {rel_ok} |",
        f"| unresolved | {rel_bad} |",
        "",
        "## Issues by Code",
        "",
        "| Code | Count |",
        "|------|-------|",
        *[f"| {c} | {n} |" for c, n in sorted(ic_cnt.items(), key=lambda x: -x[1])],
        "",
        "## Triage Summary",
        "",
        "Triage is **deterministic rule-based**, not LLM-driven.",
        "All recognized issue codes are marked `confirmed` (no automated ignoring).",
        "",
        "| State | Count |",
        "|-------|-------|",
        f"| confirmed | {confirmed_count} |",
        f"| pending | {pending_count} |",
        "",
        "### Triage Rules Applied",
        "",
        "- `unresolved_wikilink` → classified by `target_path`:",
        "  - `research/*` → `missing_research_doc_or_directory`",
        "  - `concepts/*`, `vendors/*`, `products/*`, `methodologies/*`, `cases/*`, `persons/*`, `proposals/*`, `faqs/*` → `missing_or_renamed_entity_doc`",
        "  - other → `review_link_target`",
        "- `stale_eval_gold_doc_id` → `update_eval_gold_or_add_missing_doc`",
        "- `duplicate_title` / `duplicate_alias` → `resolve_identity_conflict`",
        "- Other codes → left `pending`",
        "",
        "### Scan Persistence Check",
        "",
        f"Re-scan after triage: triage persisted = **{'YES' if triage_persisted else 'NO'}**",
        f"(confirmed before = {triaged_count}, confirmed after = {confirmed_count})",
        "",
        "## Curation Backlog",
        "",
        f"**{len(backlog)} backlog entries** generated from {confirmed_count} confirmed issues.",
        "",
        "### Action Type Distribution",
        "",
        "| Action Type | Count |",
        "|-------------|-------|",
        *[f"| {a} | {c} |" for a, c in sorted(at_dist.items(), key=lambda x: -x[1])],
        "",
        "### Priority Distribution",
        "",
        "| Priority | Count |",
        "|----------|-------|",
        *[f"| {p} | {c} |" for p, c in sorted(priority_dist.items(), key=lambda x: -x[1])],
        "",
        "### Top Backlog Items",
        "",
    ]

    for i, entry in enumerate(backlog[:20]):
        lines += [
            f"#### {i + 1}. [{entry['priority'].upper()}] {entry['action_type']}",
            "",
            f"- **Target**: `{entry['target']}`",
            f"- **Issue code**: `{entry['issue_code']}`",
            f"- **Affected**: {entry['affected_count']} document(s)",
            f"- **Examples**: {', '.join(f'`{e}`' for e in entry['examples'][:5])}",
            f"- **Suggested action**: {entry['suggested_human_action']}",
            "",
        ]

    if len(backlog) > 20:
        lines += [f"*({len(backlog) - 20} more entries not shown)*", ""]

    lines += [
        "## Boundaries",
        "",
        "- ✅ External KB not modified",
        "- ✅ No Graph RAG / graph DB",
        "- ✅ No modeling studio / editor",
        "- ✅ Agent cannot auto-write ontology",
        "- ✅ Curation backlog is human action guidance only — no automated KB fix",
        "- ✅ Triage is deterministic (rule-based), not LLM-driven",
        "- ✅ All read models are group-scoped, permission-aware",
        "",
        "## Next Steps",
        "",
        "- Phase 10.3: Ontology graph UX polish (filterable graph, improved labels, edge hover, mobile)",
        "- Optional: portfolio demo script polish",
        "- Human curator reviews and acts on backlog items at their discretion",
    ]

    return lines


if __name__ == "__main__":
    sys.exit(main())
