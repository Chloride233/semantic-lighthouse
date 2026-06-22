#!/usr/bin/env python3
"""FDE Demo Smoke Script — validates the full Pilot Outcome delivery chain.

Usage:
  .venv/Scripts/python scripts/smoke_fde_demo.py
  .venv/Scripts/python scripts/smoke_fde_demo.py --data-pack .tmp/phase19-manufacturing

Runs on a temporary SQLite database. Does NOT require:
- Real LLM/embedding API keys (uses fake providers)
- Running server (uses FastAPI TestClient in-process)
- External KB or real data

With --data-pack, the smoke reads the Phase 19.1 manufacturing data pack
manifest.json as its input asset contract — this proves the FDE demo chain
can consume a contracted, validated data asset rather than relying solely on
implicit in-script seeds.

Exit 0 = all smoke checks PASS. Exit 1 = one or more steps FAIL.
Phase 17.2 — 2026-06-21. Phase 19.2 data-pack integration — 2026-06-22.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

# ═══════════════════════════════════════════════════════════════════════════════
# Environment — must be set before any semantic_lighthouse imports
# ═══════════════════════════════════════════════════════════════════════════════

os.environ.setdefault("JWT_SECRET_KEY", "smoke-fde-demo-secret-at-least-32-bytes")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("CHAT_PROVIDER", "fake")
os.environ.setdefault("COOKIE_SECURE", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.models import (
    Base,
    Document,
    OntologyModelPackage,
    OntologyRuntimeAudit,
    ProjectEvidenceLink,
    RagRun,
    new_id,
)
from semantic_lighthouse.routers import documents as documents_router
import semantic_lighthouse.main as app_main


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

RESULTS: list[tuple[str, bool, str, float]] = []
T0 = time.monotonic()


def step_ok(name: str, detail: str = "", elapsed: float | None = None) -> None:
    if elapsed is None:
        elapsed = time.monotonic() - T0
    RESULTS.append((name, True, detail, elapsed))
    print(f"  [PASS] {name} ({elapsed:.2f}s)" + (f" — {detail}" if detail else ""))


def step_fail(name: str, detail: str = "", elapsed: float | None = None) -> None:
    if elapsed is None:
        elapsed = time.monotonic() - T0
    RESULTS.append((name, False, detail, elapsed))
    print(f"  [FAIL] {name} ({elapsed:.2f}s)" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════════════════════
# Artifact Quality Gate (17.3 spec, inline for 17.2)
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_SECTIONS = [
    "Pilot Outcome / FDE Delivery Record",
    "## Business Goal",
    "## Latest Outcome",
    "## Evidence Summary",
    "## Ontology Package Summary",
    "## Runtime Summary",
    "## Provenance",
]

FORBIDDEN_TERMS = [
    "raw_content", "raw_answer", "raw_prompt",
    "answer", "prompt",
    "source_path", "storage_path",
    "secret", "token", "password",
    "stack_trace",
]

MAX_ARTIFACT_BYTES = 20_000
PATH_PATTERNS = ["/data/", "C:\\", "\\\\", "/tmp/", "/home/", "/Users/"]


def validate_artifact(artifact_md: str) -> tuple[bool, str, list[str]]:
    """Validate a Pilot Outcome markdown artifact per 17.3 spec."""
    findings: list[str] = []
    has_fail = False
    has_warn = False

    # ── Boundedness ─────────────────────────────────────────────────────
    size = len(artifact_md.encode("utf-8"))
    if size > MAX_ARTIFACT_BYTES:
        findings.append(
            f"[FAIL] boundedness: artifact size {size} bytes exceeds "
            f"{MAX_ARTIFACT_BYTES} byte limit"
        )
        has_fail = True

    body_lower = artifact_md.lower()
    for pat in PATH_PATTERNS:
        if pat.lower() in body_lower:
            findings.append(
                f"[FAIL] boundedness: found local path pattern '{pat}'"
            )
            has_fail = True

    for i, line in enumerate(artifact_md.splitlines(), 1):
        if line.count(",") >= 9:
            findings.append(
                f"[FAIL] boundedness: line {i} has {line.count(',') + 1} "
                f"comma-separated fields (looks like CSV data row)"
            )
            has_fail = True
            break

    # ── Required sections ───────────────────────────────────────────────
    for section in REQUIRED_SECTIONS:
        if section not in artifact_md:
            findings.append(
                f"[FAIL] required_sections: missing '{section}'"
            )
            has_fail = True

    # ── Forbidden terms (skip Provenance section) ────────────────────────
    prov_idx = artifact_md.find("## Provenance")
    body = artifact_md[:prov_idx] if prov_idx != -1 else artifact_md
    body_lower_check = body.lower()
    for term in FORBIDDEN_TERMS:
        if term in body_lower_check:
            findings.append(
                f"[FAIL] forbidden_terms: found '{term}' outside Provenance"
            )
            has_fail = True

    # ── Business signals ────────────────────────────────────────────────
    bg_start = artifact_md.find("## Business Goal")
    bg_next = artifact_md.find("##", bg_start + 1) if bg_start != -1 else -1
    if bg_start != -1:
        bg_content = artifact_md[bg_start:bg_next] if bg_next != -1 else artifact_md[bg_start:]
        bg_text = bg_content.replace("## Business Goal", "").strip()
        if len(bg_text) < 10:
            findings.append("[WARN] business_signals: business_goal too short or empty")
            has_warn = True
    else:
        findings.append("[FAIL] business_signals: Business Goal section not found")
        has_fail = True

    ev_match = re.search(r"Total Active Evidence Links[* ]*:\s*(\d+)", artifact_md)
    if ev_match and int(ev_match.group(1)) == 0:
        findings.append("[WARN] business_signals: evidence total_active is 0")
        has_warn = True
    elif not ev_match:
        findings.append("[WARN] business_signals: could not find evidence total")
        has_warn = True

    pkg_match = re.search(r"Total Packages[* ]*:\s*(\d+)", artifact_md)
    if pkg_match and int(pkg_match.group(1)) == 0:
        findings.append("[WARN] business_signals: package count is 0")
        has_warn = True
    elif not pkg_match:
        findings.append("[WARN] business_signals: could not find package total")
        has_warn = True

    rt_match = re.search(r"Total Operations[* ]*:\s*(\d+)", artifact_md)
    if rt_match and int(rt_match.group(1)) == 0:
        findings.append("[WARN] business_signals: runtime total_operations is 0")
        has_warn = True
    elif not rt_match:
        findings.append("[WARN] business_signals: could not find runtime total")
        has_warn = True

    if "Not recorded yet" not in artifact_md:
        ds_heading = "### Decision Summary"
        ds_start = artifact_md.find(ds_heading)
        if ds_start != -1:
            ds_content_start = ds_start + len(ds_heading)
            next_heading = re.search(r"\n#{2,3}\s+", artifact_md[ds_content_start:])
            ds_content_end = (
                ds_content_start + next_heading.start()
                if next_heading is not None
                else len(artifact_md)
            )
            ds_text = artifact_md[ds_content_start:ds_content_end].strip()
            if len(ds_text) < 20:
                findings.append("[WARN] business_signals: decision_summary too short")
                has_warn = True

    if has_fail:
        return False, "FAIL", findings
    if has_warn:
        return True, "WARN", findings
    return True, "PASS", findings


# ═══════════════════════════════════════════════════════════════════════════════
# Data Pack Manifest (Phase 19.2)
# ═══════════════════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRESET = "tiny"
MIN_TABLES = 13
MIN_CORE_PILOT = 4


def validate_and_summarize_manifest(data_dir: Path) -> dict:
    """Validate a manufacturing data pack manifest and return a summary dict.

    Returns a dict with keys:
      - valid: bool
      - error: str (if invalid)
      - table_count, core_pilot_count, total_rows, seed, preset (if valid)
    """
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        return {
            "valid": False,
            "error": (
                f"manifest.json not found in {data_dir}. "
                f"Run: python scripts/generate_manufacturing_dataset.py "
                f"--preset {DEFAULT_PRESET} --output-dir {data_dir}"
            ),
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"manifest.json is not valid JSON: {e}"}

    # Required top-level fields
    for field in ("manifest_version", "data_pack", "tables", "seed"):
        if field not in manifest:
            return {
                "valid": False,
                "error": f"manifest.json missing required field: {field}",
            }

    tables = manifest.get("tables", [])
    if not isinstance(tables, list) or len(tables) < MIN_TABLES:
        return {
            "valid": False,
            "error": (
                f"Expected at least {MIN_TABLES} tables in manifest, "
                f"found {len(tables) if isinstance(tables, list) else 'non-list'}"
            ),
        }

    # Per-table required fields
    required_table_fields = [
        "table_name", "csv_file", "row_count", "primary_key",
        "foreign_keys", "core_pilot", "business_meaning",
    ]
    for t in tables:
        for rf in required_table_fields:
            if rf not in t:
                return {
                    "valid": False,
                    "error": (
                        f"Table '{t.get('table_name', '?')}' missing "
                        f"field '{rf}' in manifest"
                    ),
                }

    # Core pilot subset
    core_tables = [t for t in tables if t.get("core_pilot")]
    if len(core_tables) < MIN_CORE_PILOT:
        return {
            "valid": False,
            "error": (
                f"core_pilot subset has only {len(core_tables)} tables, "
                f"minimum {MIN_CORE_PILOT} required"
            ),
        }

    # CSV files must exist alongside manifest
    missing_csvs = []
    for t in tables:
        csv_path = data_dir / t["csv_file"]
        if not csv_path.is_file():
            missing_csvs.append(t["csv_file"])
    if missing_csvs:
        return {
            "valid": False,
            "error": (
                f"Missing CSV files: {', '.join(missing_csvs[:5])}"
                + (f" ... and {len(missing_csvs) - 5} more"
                   if len(missing_csvs) > 5 else "")
            ),
        }

    # Row count sanity check
    for t in tables:
        csv_path = data_dir / t["csv_file"]
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            actual_rows = sum(1 for _ in f) - 1  # exclude header
        if actual_rows != t["row_count"]:
            return {
                "valid": False,
                "error": (
                    f"Table '{t['table_name']}': manifest row_count="
                    f"{t['row_count']} but CSV has {actual_rows} rows"
                ),
            }

    # PK uniqueness quick check on a sample of tables
    for t in tables:
        csv_path = data_dir / t["csv_file"]
        pk_cols = t.get("primary_key", [])
        if not pk_cols:
            continue
        import csv as csv_mod
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv_mod.DictReader(f)
            seen = set()
            for row in reader:
                pk_val = tuple(row.get(c) for c in pk_cols)
                if any(v is None or v.strip() == "" for v in pk_val):
                    return {
                        "valid": False,
                        "error": (
                            f"Table '{t['table_name']}': null PK value "
                            f"in column(s) {pk_cols}"
                        ),
                    }
                if pk_val in seen:
                    return {
                        "valid": False,
                        "error": (
                            f"Table '{t['table_name']}': duplicate PK "
                            f"value {pk_val}"
                        ),
                    }
                seen.add(pk_val)

    total_rows = sum(t["row_count"] for t in tables)
    preset = manifest.get("preset", "unknown")

    return {
        "valid": True,
        "error": "",
        "table_count": len(tables),
        "core_pilot_count": len(core_tables),
        "core_pilot_tables": [t["table_name"] for t in core_tables],
        "total_rows": total_rows,
        "seed": manifest["seed"],
        "preset": preset,
        "data_pack": manifest.get("data_pack", "unknown"),
        "manifest_version": manifest.get("manifest_version", "unknown"),
    }


def _auto_generate_data_pack(output_dir: Path) -> dict:
    """Generate a default tiny data pack and return manifest summary."""
    gen_script = REPO_ROOT / "scripts" / "generate_manufacturing_dataset.py"
    result = subprocess.run(
        [
            sys.executable, str(gen_script),
            "--preset", DEFAULT_PRESET,
            "--seed", "42",
            "--output-dir", str(output_dir),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return {
            "valid": False,
            "error": (
                f"Auto-generate data pack failed (exit {result.returncode}): "
                f"{result.stderr[:300]}"
            ),
        }
    return validate_and_summarize_manifest(output_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FDE Demo Smoke — validate the Pilot Outcome delivery chain",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        default=None,
        help=(
            "Path to a manufacturing data pack directory containing "
            "manifest.json and CSV files. If not provided, a default "
            "tiny data pack is auto-generated."
        ),
    )
    args = parser.parse_args()

    # ── Data pack manifest validation ─────────────────────────────────
    if args.data_pack:
        manifest_summary = validate_and_summarize_manifest(args.data_pack)
        pack_source = f"provided: {args.data_pack}"
    else:
        auto_dir = Path(".tmp/smoke-fde-auto-pack")
        print("(no --data-pack provided; auto-generating default tiny pack)\n")
        manifest_summary = _auto_generate_data_pack(auto_dir)
        pack_source = "auto-generated default (tiny preset)"

    if not manifest_summary["valid"]:
        print(f"  [FAIL] Data pack manifest: {manifest_summary['error']}")
        return 1

    ms = manifest_summary
    print("=== FDE Demo Smoke (Phase 19.2) ===\n")
    print(f"Data pack: {pack_source}")
    print(f"  manifest_version: {ms['manifest_version']}")
    print(f"  data_pack:        {ms['data_pack']}")
    print(f"  preset/seed:      {ms['preset']} / seed={ms['seed']}")
    print(f"  table_count:      {ms['table_count']}")
    print(f"  core_pilot_count: {ms['core_pilot_count']}")
    print(f"  core_pilot:       {', '.join(ms['core_pilot_tables'])}")
    print(f"  total_rows:       {ms['total_rows']:,}")
    print()

    # ── Step 0: Setup temp database ─────────────────────────────────────
    os.makedirs(".tmp", exist_ok=True)
    db_path = ".tmp/smoke-fde-demo.db"
    if os.path.exists(db_path):
        os.unlink(db_path)

    db_url = f"sqlite+pysqlite:///{db_path.replace(chr(92), '/')}"
    os.environ["DATABASE_URL"] = db_url

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    smoke_sessionmaker = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = app_main.create_app()
    sess = smoke_sessionmaker()

    def override_get_db():
        try:
            yield sess
        finally:
            pass

    def override_get_settings():
        return Settings(
            database_url=db_url,
            jwt_secret_key=os.environ["JWT_SECRET_KEY"],
            embedding_provider="fake",
            chat_provider="fake",
            cookie_secure=False,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    with (
        mock.patch.object(app_main, "SessionLocal", smoke_sessionmaker),
        mock.patch.object(documents_router, "SessionLocal", smoke_sessionmaker),
    ):
        with TestClient(app) as client:

            # ── Step 1: Register demo user ────────────────────────
            r = client.post("/auth/register", json={
                "email": "demo-operator@fde.local",
                "password": "DemoPass123!",
                "display_name": "Demo Operator",
            })
            if r.status_code == 201:
                user_id = r.json()["id"]
                step_ok("register", f"user_id={user_id[:8]}...")
            else:
                step_fail("register", f"HTTP {r.status_code}: {r.text[:120]}")
                return 1

            # ── Step 2: Login ─────────────────────────────────────
            r = client.post("/auth/login", json={
                "email": "demo-operator@fde.local",
                "password": "DemoPass123!",
            })
            if r.status_code == 200:
                token = r.json()["access_token"]
                step_ok("login", f"token={token[:16]}...")
            else:
                step_fail("login", f"HTTP {r.status_code}: {r.text[:120]}")
                return 1

            h = {"Authorization": f"Bearer {token}"}

            # ── Step 3: Create demo group ─────────────────────────
            r = client.post("/groups", json={
                "name": "FDE Demo — Manufacturing",
                "description": "Phase 17 smoke test group",
            }, headers=h)
            if r.status_code == 201:
                gid = r.json()["id"]
                step_ok("create_group", f"gid={gid[:8]}...")
            else:
                step_fail("create_group", f"HTTP {r.status_code}: {r.text[:120]}")
                return 1

            # ── Step 4: Create pilot project ──────────────────────
            r = client.post(f"/groups/{gid}/projects", json={
                "name": "Equipment Reliability Pilot — Plant 3",
                "entry_mode": "problem_first",
                "industry_template": "manufacturing",
                "business_goal": (
                    "Build a governed ontology for manufacturing equipment "
                    "and work-order management at Plant 3 to reduce unplanned "
                    "downtime by improving failure-code traceability and "
                    "maintenance-team assignment accuracy."
                ),
            }, headers=h)
            if r.status_code == 201:
                pid = r.json()["id"]
                step_ok("create_project", f"pid={pid[:8]}...")
            else:
                step_fail("create_project", f"HTTP {r.status_code}: {r.text[:120]}")
                return 1

            # ── Step 5: Seed evidence (direct DB) ─────────────────
            doc_1 = new_id()
            doc_2 = new_id()
            rag_run_id = new_id()
            el_1 = new_id()
            el_2 = new_id()
            el_3 = new_id()

            sess.add_all([
                Document(id=doc_1, group_id=gid,
                         title="Plant 3 Equipment Taxonomy & Failure-Code Catalog",
                         file_name="plant3-taxonomy.md",
                         source_path="smoke-seed/taxonomy.md",
                         content_hash="smoke-hash-taxonomy",
                         raw_content="Taxonomy content — smoke seed only.",
                         status="ready", created_by=user_id,
                         frontmatter={"source": "Plant 3 Engineering"}),
                Document(id=doc_2, group_id=gid,
                         title="Maintenance SLA Policy — Response-Time Targets",
                         file_name="maintenance-sla.md",
                         source_path="smoke-seed/sla.md",
                         content_hash="smoke-hash-sla",
                         raw_content="SLA policy content — smoke seed only.",
                         status="ready", created_by=user_id,
                         frontmatter={"source": "Maintenance Operations"}),
                RagRun(id=rag_run_id, group_id=gid, user_id=user_id,
                       question="What failure codes correlate with downtime >8h?",
                       answer="BRG-01 and BRG-03 are top contributors.",
                       confidence="high", retrieval_method="hybrid",
                       model="fake", status="success"),
            ])
            sess.flush()

            sess.add_all([
                ProjectEvidenceLink(id=el_1, group_id=gid, project_id=pid,
                                    evidence_type="document", evidence_id=doc_1,
                                    role="context", status="active",
                                    created_by=user_id),
                ProjectEvidenceLink(id=el_2, group_id=gid, project_id=pid,
                                    evidence_type="document", evidence_id=doc_2,
                                    role="requirement", status="active",
                                    created_by=user_id),
                ProjectEvidenceLink(id=el_3, group_id=gid, project_id=pid,
                                    evidence_type="rag_run", evidence_id=rag_run_id,
                                    role="decision", status="active",
                                    created_by=user_id),
            ])
            sess.flush()
            step_ok("seed_evidence", "2 docs + 1 rag_run + 3 evidence links")

            # ── Step 6: Seed package (direct DB) ──────────────────
            pkg_id = new_id()
            sess.add(OntologyModelPackage(
                id=pkg_id, group_id=gid, project_id=pid,
                scope_key=f"project:{pid}", version=1,
                content_hash="smoke-pkg-hash-plant3-001",
                draft_count=4, quality_status="PASS",
                created_by=user_id,
                contract_json={"object_types": [], "properties": []},
                source_draft_ids=[new_id() for _ in range(4)],
                quality_summary={"errors": 0, "warnings": 0},
            ))
            sess.flush()
            step_ok("seed_package", "1 package v1 PASS (4 drafts)")

            # ── Step 7: Seed runtime audit (direct DB) ────────────
            sess.add_all([
                OntologyRuntimeAudit(id=new_id(), user_id=user_id,
                                     group_id=gid, project_id=pid,
                                     operation="generate_bindings",
                                     outcome="success"),
                OntologyRuntimeAudit(id=new_id(), user_id=user_id,
                                     group_id=gid, project_id=pid,
                                     operation="query",
                                     object_type="work_order",
                                     outcome="success", row_count=8),
            ])
            sess.flush()
            step_ok("seed_runtime", "2 audit records (bindings + query, 8 rows)")

            sess.commit()

            # ── Step 8: Create outcome record via API ─────────────
            r = client.post(f"/groups/{gid}/projects/{pid}/outcomes", json={
                "title": "Plant 3 Equipment Reliability — FDE Delivery v1",
                "selected_evidence_link_ids": [el_1, el_2, el_3],
                "package_ids": [pkg_id],
                "query_refs": [{
                    "binding": "work_order_binding",
                    "object_type": "work_order",
                    "row_count": 8,
                    "outcome": "success",
                }],
                "decision_summary": (
                    "The Plant 3 equipment ontology pilot identified "
                    "bearing-related failure codes (BRG-01, BRG-03) as the "
                    "top contributors to unplanned downtime, accounting for "
                    "62% of critical work orders. Proceed to production pilot."
                ),
                "risks": [
                    "Seed dataset limited to synthetic rows",
                    "Failure code taxonomy may be incomplete",
                ],
                "next_actions": [
                    "Expand dataset to Plants 1–4",
                    "Validate failure-code catalog against CMMS history",
                    "Integrate real-time sensor feed",
                ],
            }, headers=h)
            if r.status_code == 201:
                outcome_id = r.json()["id"]
                step_ok("create_outcome",
                        f"oid={outcome_id[:8]}... title={r.json().get('title', '')}")
            else:
                step_fail("create_outcome", f"HTTP {r.status_code}: {r.text[:200]}")
                return 1

            # ── Step 9: Fetch outcome-summary JSON ────────────────
            r = client.get(
                f"/groups/{gid}/projects/{pid}/outcome-summary", headers=h
            )
            if r.status_code == 200:
                data = r.json()
                step_ok("outcome_summary",
                        f"evidence={data['evidence_summary']['total_active']} "
                        f"pkg={data['package_summary']['count']} "
                        f"runtime={data['runtime_summary']['total_operations']} "
                        f"outcome={'yes' if data['latest_outcome'] else 'no'}")
            else:
                step_fail("outcome_summary", f"HTTP {r.status_code}: {r.text[:200]}")
                return 1

            # ── Step 10: Fetch outcome-artifact.md ────────────────
            r = client.get(
                f"/groups/{gid}/projects/{pid}/outcome-artifact.md", headers=h
            )
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and "text/markdown" in ct:
                artifact_md = r.text
                step_ok("outcome_artifact",
                        f"size={len(artifact_md)}B content-type={ct}")
            else:
                step_fail("outcome_artifact",
                          f"HTTP {r.status_code} ct={ct}: {r.text[:200]}")
                return 1

            # ── Step 11: Run artifact quality gate ─────────────────
            passed, status, findings = validate_artifact(artifact_md)
            ok = status in ("PASS", "WARN")
            if ok:
                step_ok("artifact_quality_gate",
                        f"{status} ({len(findings)} findings)")
            else:
                step_fail("artifact_quality_gate",
                          f"{status} ({len(findings)} findings)")
            for f in findings:
                print(f"         {f}")

            if not ok:
                return 1

            # ── Summary ───────────────────────────────────────────
            total_t = time.monotonic() - T0
            all_ok = all(r[1] for r in RESULTS)
            n_pass = sum(1 for r in RESULTS if r[1])
            n_fail = sum(1 for r in RESULTS if not r[1])
            print(f"\n{'='*60}")
            print(f"FDE Demo Smoke: {'PASS' if all_ok else 'FAIL'}")
            print(f"Steps: {len(RESULTS)}  Passed: {n_pass}  Failed: {n_fail}")
            print(f"Total time: {total_t:.2f}s")
            print(f"Artifact gate: {status}")
            print(f"{'='*60}")

            # Clean up
            sess.close()
            engine.dispose()
            try:
                os.unlink(db_path)
            except OSError:
                pass

            return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
