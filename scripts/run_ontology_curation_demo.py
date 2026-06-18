"""Phase 10.2 real KB curation demo — deterministic triage + backlog.

Usage:
  DATABASE_URL=sqlite+pysqlite:///.tmp/phase10-curation-demo.db \\
  .venv/Scripts/python scripts/run_ontology_curation_demo.py

Does NOT modify F:\\ontology-kb\\knowledge-graph.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semantic_lighthouse.database import SessionLocal
from semantic_lighthouse.models import (
    Group, GroupMembership, OntologyEntity,
    OntologyValidationIssue, User, utc_now,
)
from semantic_lighthouse.services.document_ingestion import ingest_markdown, should_import_markdown
from semantic_lighthouse.services.ontology import scan_group
from sqlalchemy import select

DEFAULT_KB = Path("F:/ontology-kb/knowledge-graph")
DEFAULT_REPORT = Path("docs/ontology-curation-demo-report.md")
KB_DIRS = {"concepts", "vendors", "products", "methodologies", "cases", "persons", "research", "proposals", "faqs"}


def classify_wikilink(target_path: str) -> str:
    if target_path.startswith("research/"):
        return "missing_research_doc_or_directory"
    for d in KB_DIRS:
        if target_path.startswith(d + "/") or target_path == d + ".md":
            return "missing_or_renamed_entity_doc"
    return "review_link_target"


def action_for_wikilink(target_path: str) -> str:
    if target_path.startswith("research/"):
        return "create_missing_research_doc"
    for d in KB_DIRS:
        if target_path.startswith(d + "/") or target_path == d + ".md":
            return "create_or_rename_entity_doc"
    return "review_link_target"


def priority_for_backlog(action_type: str, affected_count: int) -> str:
    if action_type in ("update_eval_gold_doc_id", "resolve_identity_conflict"):
        return "high"
    if affected_count >= 3:
        return "high"
    return "medium"


def build_backlog(issues: list) -> list[dict]:
    """Aggregate confirmed issues into curation backlog entries."""
    wikilink: dict[str, list] = defaultdict(list)
    stale: dict[str, list] = defaultdict(list)
    dt: dict[str, list] = defaultdict(list)
    da: dict[str, list] = defaultdict(list)
    for i in issues:
        if i.triage_status != "confirmed":
            continue
        d = i.details or {}
        if i.code == "unresolved_wikilink":
            wikilink[d.get("target_path", "?")].append(i)
        elif i.code == "stale_eval_gold_doc_id":
            stale[d.get("expected_doc_id", "?")].append(i)
        elif i.code == "duplicate_title":
            dt[d.get("normalized_title", "?")].append(i)
        elif i.code == "duplicate_alias":
            da[d.get("normalized_alias", "?")].append(i)
    result = []
    for tp, g in wikilink.items():
        a = action_for_wikilink(tp)
        sps = list({i.source_path for i in g})
        result.append({"action_type": a, "priority": priority_for_backlog(a, len(g)),
                       "issue_code": "unresolved_wikilink", "target": tp,
                       "source_path": sps[0] if len(sps) == 1 else f"{len(sps)} sources",
                       "affected_count": len(g),
                       "examples": [i.message for i in g[:3]],
                       "suggested_human_action": f"Verify whether '{tp}' should exist."})
    for eid, g in stale.items():
        qs = [q for i in g for q in (i.details.get("question_ids", []) if i.details else [])]
        result.append({"action_type": "update_eval_gold_doc_id", "priority": "high",
                       "issue_code": "stale_eval_gold_doc_id", "target": eid,
                       "source_path": "docs/eval/rag-queries-ontology.json",
                       "affected_count": len(g),
                       "examples": [f"Questions: {', '.join(sorted(set(qs)))}"],
                       "suggested_human_action": f"Add '{eid}.md' or update eval gold IDs."})
    for nt, g in dt.items():
        sps = list({i.source_path for i in g})
        result.append({"action_type": "resolve_identity_conflict", "priority": "high",
                       "issue_code": "duplicate_title", "target": nt,
                       "source_path": ", ".join(sps[:5]), "affected_count": len(g),
                       "examples": [i.message for i in g[:3]],
                       "suggested_human_action": f"Title '{nt}' has duplicates. Rename."})
    for na, g in da.items():
        sps = list({i.source_path for i in g})
        result.append({"action_type": "resolve_identity_conflict", "priority": "high",
                       "issue_code": "duplicate_alias", "target": na,
                       "source_path": ", ".join(sps[:5]), "affected_count": len(g),
                       "examples": [i.message for i in g[:3]],
                       "suggested_human_action": f"Alias '{na}' conflicts. Fix."})
    result.sort(key=lambda b: (-1 if b["priority"] == "high" else 0, -b["affected_count"]))
    return result


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
        print("Setup...")
        uid, gid = str(uuid4()), str(uuid4())
        db.add(User(id=uid, email="c@o.local", password_hash="x", display_name="C"))
        db.add(Group(id=gid, name="Curation", created_by=uid))
        db.add(GroupMembership(group_id=gid, user_id=uid, role="admin"))
        db.flush()
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
        sr = scan_group(db, gid)
        issues = db.scalars(select(OntologyValidationIssue).where(OntologyValidationIssue.group_id == gid)).all()
        confirmed = 0
        for iss in issues:
            d = iss.details or {}
            if iss.code == "unresolved_wikilink":
                iss.triage_status = "confirmed"
                iss.triage_note = classify_wikilink(d.get("target_path") or "")
                iss.triaged_by = uid
                iss.triaged_at = utc_now()
                confirmed += 1
            elif iss.code == "stale_eval_gold_doc_id":
                iss.triage_status = "confirmed"
                iss.triage_note = "update_eval_gold_or_add_missing_doc"
                iss.triaged_by = uid
                iss.triaged_at = utc_now()
                confirmed += 1
            elif iss.code in ("duplicate_title", "duplicate_alias"):
                iss.triage_status = "confirmed"
                iss.triage_note = "resolve_identity_conflict"
                iss.triaged_by = uid
                iss.triaged_at = utc_now()
                confirmed += 1
        db.commit()
        print(f"Triaged: {confirmed} confirmed")
        entities = db.scalars(select(OntologyEntity).where(OntologyEntity.group_id == gid)).all()
        backlog = build_backlog(issues)
        sr2 = scan_group(db, gid)
        issues2 = db.scalars(select(OntologyValidationIssue).where(OntologyValidationIssue.group_id == gid)).all()
        c2 = sum(1 for i in issues2 if i.triage_status == "confirmed")
        p2 = sum(1 for i in issues2 if i.triage_status == "pending")
        print(f"Rescan: {sr2['issue_count']} issues, {c2} confirmed, {p2} pending — persisted={'YES' if c2 == confirmed else 'NO'}")
        ic: dict[str, int] = {}
        tr: dict[str, int] = {}
        for i in issues2:
            ic[i.code] = ic.get(i.code, 0) + 1
            tr[i.triage_status] = tr.get(i.triage_status, 0) + 1
        ac: dict[str, int] = {}
        for b in backlog:
            ac[b["action_type"]] = ac.get(b["action_type"], 0) + 1
        summary = {"imported": imported, "entities": len(entities), "issues": len(issues2),
                   "triage": tr, "issues_by_code": ic, "backlog": len(backlog),
                   "by_action": ac, "persisted": c2 == confirmed}
        print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))
        lines = ["# Ontology Curation Demo Report", "", "**Date**: 2026-06-18", f"**KB**: {kb_root}",
                 "**DB**: temporary SQLite", "", "## Import & Scan", "",
                 "| Metric | Count |", "|--------|-------|", f"| Imported | {imported} |",
                 f"| Entities | {len(entities)} |", f"| Relations | {sr['relation_count']} |",
                 f"| Issues | {len(issues2)} |", "", "## Triage", "",
                 "| Status | Count |", "|--------|-------|"]
        for s, c in sorted(tr.items()):
            lines.append(f"| {s} | {c} |")
        lines += ["", "### Issues by Code", "", "| Code | Count |", "|------|-------|"]
        for c, n in sorted(ic.items(), key=lambda x: -x[1]):
            lines.append(f"| {c} | {n} |")
        lines += ["", "## Curation Backlog", "", f"### Top {min(15, len(backlog))} Items", ""]
        for i, b in enumerate(backlog[:15]):
            lines.append(f"### {i + 1}. [{b['priority'].upper()}] {b['action_type']}")
            lines.append(f"- **Target**: `{b['target']}` — {b['affected_count']} issues")
            if b["examples"]:
                lines.append(f"- Example: {b['examples'][0]}")
            lines.append(f"- Action: {b['suggested_human_action']}")
            lines.append("")
        lines += ["### By Action", "", "| Action | Count |", "|--------|-------|"]
        for a, c in sorted(ac.items(), key=lambda x: -x[1]):
            lines.append(f"| {a} | {c} |")
        lines += ["", "## Persistence", "",
                  f"- Rescan: {c2} confirmed, {p2} pending — triage persisted: {'✅' if c2 == confirmed else '❌'}",
                  "", "## Boundaries", "",
                  "- ✅ External KB not modified", "- ✅ No auto-fix of KB files",
                  "- ✅ No Graph RAG / graph DB", "- ✅ No Agent auto-write",
                  "- ✅ Curation backlog is human action guidance only",
                  "", "## Next", "", "- Phase 10.3 Ontology graph UX polish"]
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nReport: {report_path}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
