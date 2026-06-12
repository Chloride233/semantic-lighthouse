"""Retrieval evaluation CLI.

Usage:
  python scripts/eval/evaluate.py [--dataset docs/eval/queries.json]

Loads gold-standard queries, runs keyword / semantic / hybrid search,
computes Recall@K and MRR, and writes a markdown report.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings
from semantic_lighthouse.database import SessionLocal
from semantic_lighthouse.models import Document, DocumentChunk
from semantic_lighthouse.services.retrieval import hybrid_search

SETTINGS = Settings(
    database_url="sqlite+pysqlite:///:memory:",
    jwt_secret_key="eval-key-32-bytes-minimum",
    embedding_provider="fake",
    chat_provider="fake",
)

HEADERS = ["Query", "Method", "Results", "Recall@1", "Recall@3", "Recall@5", "MRR", "Zero", "Lat(ms)"]


def load_queries(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def kw_search(db: Session, gid: str, q: str, limit: int) -> list[str]:
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.group_id == gid, Document.group_id == gid,
            Document.status == "ready", DocumentChunk.content.ilike(f"%{q}%"),
        )
        .order_by(Document.created_at.desc(), DocumentChunk.chunk_index.asc())
        .limit(limit)
    ).all()
    seen: set[str] = set()
    return [d for d in (doc.id for _, doc in rows) if not (d in seen or seen.add(d))]


def sem_search(db: Session, gid: str, q: str, limit: int) -> list[str]:
    from semantic_lighthouse.services.embeddings import cosine_similarity, create_embedding_client

    try:
        qv = create_embedding_client(SETTINGS).embed_texts([q]).vectors[0]
    except Exception:
        return []
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.group_id == gid, Document.group_id == gid,
               Document.status == "ready", DocumentChunk.embedding.is_not(None))
    ).all()
    scored = [(cosine_similarity(qv, c.embedding or []), doc.id) for c, doc in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    return [d for d in (doc_id for _, doc_id in scored) if not (d in seen or seen.add(d))][:limit]


def hyb_search(db: Session, gid: str, q: str, limit: int) -> list[str]:
    results = hybrid_search(db, gid, q, limit, keyword_weight=0.3, settings=SETTINGS)
    seen: set[str] = set()
    return [d for d in (r.document.id for r in results) if not (d in seen or seen.add(d))]


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant:
        return 1.0
    return len(set(retrieved[:k]) & set(relevant)) / len(relevant)


def mean_reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    if not relevant:
        return 1.0
    rel = set(relevant)
    for i, doc_id in enumerate(retrieved, 1):
        if doc_id in rel:
            return 1.0 / i
    return 0.0


def run(queries_path: str = "docs/eval/queries.json", output_path: str | None = None) -> None:
    queries = load_queries(queries_path)
    if not output_path:
        output_path = f"docs/eval/report-{time.strftime('%Y-%m-%d')}.md"

    db: Session = SessionLocal()
    rows: list[list[str]] = []

    for q in queries:
        qid, qtext = q["id"], q["query"]
        if not qtext.strip():
            rows.append([qid, "—", "—", "—", "—", "—", "—", "—", "—"])
            continue
        relevant = q.get("relevant_document_ids", [])

        for name, fn in [("keyword", kw_search), ("semantic", sem_search), ("hybrid", hyb_search)]:
            t0 = time.perf_counter()
            doc_ids = fn(db, "eval", qtext, limit=5)
            lat = int((time.perf_counter() - t0) * 1000)

            rows.append([
                qid, name, str(len(doc_ids)),
                f"{recall_at_k(doc_ids, relevant, 1):.2f}",
                f"{recall_at_k(doc_ids, relevant, 3):.2f}",
                f"{recall_at_k(doc_ids, relevant, 5):.2f}",
                f"{mean_reciprocal_rank(doc_ids, relevant):.2f}",
                "yes" if len(doc_ids) == 0 else "no",
                str(lat),
            ])

    db.close()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Retrieval Evaluation Report\n\n")
        f.write(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Queries**: {len(queries)}  \n\n")
        f.write("| " + " | ".join(HEADERS) + " |\n")
        f.write("|" + "|".join(["---"] * len(HEADERS)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(row) + " |\n")

    print(f"Report: {output_path}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="docs/eval/queries.json")
    p.add_argument("--output", default=None)
    a = p.parse_args()
    run(a.dataset, a.output)
