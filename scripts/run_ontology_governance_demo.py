"""Phase 9 real KB governance demo runner.

Usage:
  DATABASE_URL=sqlite+pysqlite:///.tmp/phase9-real-kb-demo.db \\
  .venv/Scripts/python scripts/run_ontology_governance_demo.py

Pre-requisite: alembic upgrade head must have been run against DATABASE_URL.
Does NOT modify F:\\ontology-kb\\knowledge-graph.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
from sqlalchemy import select

DEFAULT_KB = Path("F:/ontology-kb/knowledge-graph")
DEFAULT_REPORT = Path("docs/ontology-governance-demo-report.md")


def main() -> int:
    p = argparse.ArgumentParser(description="Ontology governance demo")
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
        print("Creating demo user and group...")
        uid, gid = str(uuid4()), str(uuid4())
        db.add(User(id=uid, email="demo@onto.local", password_hash="x", display_name="Demo"))
        db.add(Group(id=gid, name="Ontology Demo", created_by=uid))
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
        print(f"Scan: {sr['scanned_count']} docs, {sr['entity_count']} entities, {sr['relation_count']} relations, {sr['issue_count']} issues")

        ee = db.scalars(select(OntologyEntity).where(OntologyEntity.group_id == gid)).all()
        rr = db.scalars(select(OntologyRelation).where(OntologyRelation.group_id == gid)).all()
        ii = db.scalars(select(OntologyValidationIssue).where(OntologyValidationIssue.group_id == gid)).all()

        et_cnt: dict[str, int] = {}
        for e in ee:
            et_cnt[e.entity_type] = et_cnt.get(e.entity_type, 0) + 1
        rel_ok = sum(1 for r in rr if r.status == "resolved")
        rel_bad = sum(1 for r in rr if r.status == "unresolved")
        ic_cnt: dict[str, int] = {}
        severity_by_code: dict[str, str] = {}
        for i in ii:
            ic_cnt[i.code] = ic_cnt.get(i.code, 0) + 1
            severity_by_code[i.code] = i.severity

        un_samples = [r for r in rr if r.status == "unresolved"][:5]
        dup_t = [i for i in ii if i.code == "duplicate_title"][:3]
        dup_a = [i for i in ii if i.code == "duplicate_alias"][:3]
        stale = [i for i in ii if i.code == "stale_eval_gold_doc_id"][:5]

        summary = {
            "kb_path": str(kb_root), "imported": imported, "skipped": skipped,
            "scanned": sr["scanned_count"], "entities": len(ee), "relations": len(rr),
            "issues": len(ii), "entities_by_type": et_cnt,
            "resolved_relations": rel_ok, "unresolved_relations": rel_bad,
            "issues_by_code": ic_cnt,
        }
        print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))

        lines = [
            "# Ontology Governance Demo Report", "",
            "**Date**: 2026-06-18", f"**KB**: {kb_root}",
            f"**DB**: temporary SQLite (`{os.environ.get('DATABASE_URL', 'N/A')}`)", "",
            "## Import & Scan", "",
            "| Metric | Count |", "|--------|-------|",
            f"| Imported | {imported} |", f"| Skipped | {skipped} |",
            f"| Scanned (ready) | {sr['scanned_count']} |",
            f"| Entities | {len(ee)} |", f"| Relations | {len(rr)} |",
            f"| Issues | {len(ii)} |", "",
            "## Entities by Type", "",
            "| entityType | Count |", "|------------|-------|",
            *[f"| {t} | {c} |" for t, c in sorted(et_cnt.items(), key=lambda x: -x[1])],
            "", "## Relations by Status", "",
            "| Status | Count |", "|--------|-------|",
            f"| resolved | {rel_ok} |", f"| unresolved | {rel_bad} |", "",
            "## Issues by Code", "",
            "| Code | Count | Severity |", "|------|-------|----------|",
            *[f"| {c} | {n} | {severity_by_code.get(c, '?')} |" for c, n in sorted(ic_cnt.items(), key=lambda x: -x[1])],
        ]

        if un_samples:
            lines += ["", "### Unresolved Wikilinks (sample)", ""]
            for r in un_samples:
                src = next((e for e in ee if e.id == r.source_entity_id), None)
                lines.append(f"- `{r.target_path}` ← `{src.title if src else '?'}`{f' ({r.target_label})' if r.target_label else ''}")
        if dup_t:
            lines += ["", "### Duplicate Titles", ""]
            for i in dup_t:
                lines.append(f"- {i.message} (`{i.source_path}`)")
        if dup_a:
            lines += ["", "### Duplicate Aliases", ""]
            for i in dup_a:
                lines.append(f"- {i.message} (`{i.source_path}`)")
        if stale:
            lines += ["", "### Stale Eval Gold Doc IDs", ""]
            for i in stale:
                lines.append(f"- `{i.details.get('expected_doc_id', '?')}` → questions: {', '.join(i.details.get('question_ids', []))}")

        lines += ["", "## Boundaries", "",
                   "- ✅ External KB not modified",
                   "- ✅ No Graph RAG / graph DB",
                   "- ✅ No modeling studio / editor",
                   "- ✅ Agent cannot auto-write ontology",
                   "- ✅ All read models are group-scoped, permission-aware", "",
                   "## Next Steps", "",
                   "- Phase 10 planning",
                   "- Polish demo scripts for portfolio",
                   "- Consider KB content curation from governance findings"]

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nReport: {report_path}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
