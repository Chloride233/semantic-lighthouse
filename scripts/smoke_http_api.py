#!/usr/bin/env python3
"""HTTP API Smoke Script — validates the API layer with real HTTP calls.

Usage:
  Local mode (starts uvicorn):
    .venv/Scripts/python scripts/smoke_http_api.py

  Deployment mode (target existing server):
    .venv/Scripts/python scripts/smoke_http_api.py --base-url http://HOST:PORT
    .venv/Scripts/python scripts/smoke_http_api.py --base-url http://127.0.0.1:8000 \\
        --email-prefix deploy-smoke --password DeployPass1! --timeout-seconds 10

Phase 18.3/18.4 — 2026-06-21.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

RESULTS: list[tuple[str, bool, str, float]] = []
T0 = time.monotonic()


def ok(name: str, detail: str = "") -> None:
    RESULTS.append((name, True, detail, time.monotonic() - T0))
    print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))


def fail(name: str, detail: str = "") -> None:
    RESULTS.append((name, False, detail, time.monotonic() - T0))
    print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def http(method: str, url: str, *,
         json_body: dict | None = None,
         headers: dict | None = None,
         timeout: int = 10) -> tuple[int, str, dict]:
    """Make an HTTP request. Returns (status_code, body_text, parsed_json)."""
    data = None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {}
            return resp.status, body, parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return e.code, body, {}
    except Exception as e:
        return 0, str(e), {}


# ═══════════════════════════════════════════════════════════════════════════════
# Artifact checks (inline, bounded)
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_SECTIONS = [
    "Pilot Outcome / FDE Delivery Record",
    "## Business Goal",
    "## Evidence Summary",
    "## Ontology Package Summary",
    "## Runtime Summary",
    "## Provenance",
]

FORBIDDEN_TERMS = [
    "raw_content", "raw_answer", "raw_prompt",
    "source_path", "storage_path",
    "secret", "token", "password",
    "stack_trace",
]


def check_artifact(md: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    for s in REQUIRED_SECTIONS:
        if s not in md:
            issues.append(f"missing section: {s}")
    prov = md.find("## Provenance")
    body = md[:prov] if prov != -1 else md
    bl = body.lower()
    for t in FORBIDDEN_TERMS:
        if t in bl:
            issues.append(f"forbidden term: {t}")
    return len(issues) == 0, issues


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    p = argparse.ArgumentParser(description="HTTP API Smoke")
    p.add_argument("--base-url", default=None, help="Remote API base URL")
    p.add_argument("--email-prefix", default="smoke-http-api", help="Email prefix")
    p.add_argument("--password", default="SmokePass1!", help="Password")
    p.add_argument("--timeout-seconds", type=int, default=10, help="HTTP timeout")
    args = p.parse_args()

    base_url = args.base_url
    email = f"{args.email_prefix}-{int(time.time())}@smoke.local"
    password = args.password
    timeout = args.timeout_seconds

    # ═══════════════════════════════════════════════════════════════════════
    # Local mode: start uvicorn
    # ═══════════════════════════════════════════════════════════════════════
    proc = None
    db_path = None

    if base_url is None:
        # Temp SQLite DB
        os.makedirs(".tmp", exist_ok=True)
        db_path = ".tmp/smoke-http-api.db"
        if os.path.exists(db_path):
            os.unlink(db_path)
        abs_db = str(Path(db_path).resolve()).replace("\\", "/")

        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite+pysqlite:///{abs_db}"
        env["JWT_SECRET_KEY"] = "smoke-http-secret-at-least-32-bytes"
        env["EMBEDDING_PROVIDER"] = "fake"
        env["CHAT_PROVIDER"] = "fake"
        env["COOKIE_SECURE"] = "false"

        port = 8018
        base_url = f"http://127.0.0.1:{port}"

        # Init DB schema (alembic needs DATABASE_URL; use create_all for speed)
        from sqlalchemy import create_engine
        from semantic_lighthouse.models import Base
        engine = create_engine(f"sqlite+pysqlite:///{abs_db}")
        Base.metadata.create_all(bind=engine)
        engine.dispose()

        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "semantic_lighthouse.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for /health
        deadline = time.monotonic() + 15
        healthy = False
        while time.monotonic() < deadline:
            try:
                code, _, _ = http("GET", f"{base_url}/health", timeout=2)
                if code == 200:
                    healthy = True
                    break
            except Exception:
                pass
            time.sleep(0.3)

        if not healthy:
            print("  [FAIL] uvicorn_start — /health did not return 200 within 15s")
            proc.terminate()
            proc.wait()
            return 1

        ok("uvicorn_start", f"port={port}")

    # ═══════════════════════════════════════════════════════════════════════
    # Step 1: Health check
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http("GET", f"{base_url}/health", timeout=timeout)
    if code == 200 and data.get("status") == "ok":
        ok("health", f"status={data.get('status')} db={data.get('database','?')}")
    else:
        fail("health", f"HTTP {code}: {body[:120]}")
        return _cleanup(proc, db_path, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # Step 2: Register
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http("POST", f"{base_url}/auth/register", json_body={
        "email": email,
        "password": password,
        "display_name": "Smoke HTTP Tester",
    }, timeout=timeout)
    if code == 201:
        user_id = data.get("id", "?")
        ok("register", f"uid={user_id[:8]}...")
    else:
        fail("register", f"HTTP {code}: {body[:120]}")
        return _cleanup(proc, db_path, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # Step 3: Login
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http("POST", f"{base_url}/auth/login", json_body={
        "email": email, "password": password,
    }, timeout=timeout)
    if code == 200 and "access_token" in data:
        token = data["access_token"]
        ok("login", f"token={token[:16]}...")
    else:
        fail("login", f"HTTP {code}: {body[:120]}")
        return _cleanup(proc, db_path, 1)

    h = {"Authorization": f"Bearer {token}"}

    # ═══════════════════════════════════════════════════════════════════════
    # Step 4: Create group
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http("POST", f"{base_url}/groups", json_body={
        "name": "Smoke HTTP API Group",
        "description": "Phase 18.3 smoke test",
    }, headers=h, timeout=timeout)
    if code == 201:
        gid = data.get("id", "?")
        ok("create_group", f"gid={gid[:8]}...")
    else:
        fail("create_group", f"HTTP {code}: {body[:120]}")
        return _cleanup(proc, db_path, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # Step 5: Create project
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http("POST", f"{base_url}/groups/{gid}/projects", json_body={
        "name": "HTTP Smoke Project",
        "entry_mode": "problem_first",
        "business_goal": "Verify FDE outcome chain via real HTTP calls.",
    }, headers=h, timeout=timeout)
    if code == 201:
        pid = data.get("id", "?")
        ok("create_project", f"pid={pid[:8]}...")
    else:
        fail("create_project", f"HTTP {code}: {body[:120]}")
        return _cleanup(proc, db_path, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # Step 6: Create outcome record
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http(
        "POST", f"{base_url}/groups/{gid}/projects/{pid}/outcomes",
        json_body={
            "title": "HTTP Smoke Outcome",
            "decision_summary": "HTTP API smoke passed — FDE chain verified.",
            "risks": ["No evidence seeded for HTTP smoke"],
            "next_actions": ["Run full FDE chain with evidence"],
        },
        headers=h, timeout=timeout,
    )
    if code == 201:
        oid = data.get("id", "?")
        ok("create_outcome", f"oid={oid[:8]}...")
    else:
        fail("create_outcome", f"HTTP {code}: {body[:200]}")
        return _cleanup(proc, db_path, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # Step 7: Get outcome-summary
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http(
        "GET", f"{base_url}/groups/{gid}/projects/{pid}/outcome-summary",
        headers=h, timeout=timeout,
    )
    if code == 200:
        ev = data.get("evidence_summary", {}).get("total_active", 0)
        pk = data.get("package_summary", {}).get("count", 0)
        rt = data.get("runtime_summary", {}).get("total_operations", 0)
        has_lo = "yes" if data.get("latest_outcome") else "no"
        ok("outcome_summary", f"evidence={ev} pkg={pk} runtime={rt} outcome={has_lo}")
    else:
        fail("outcome_summary", f"HTTP {code}: {body[:200]}")
        return _cleanup(proc, db_path, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # Step 8: Get outcome-artifact.md
    # ═══════════════════════════════════════════════════════════════════════
    code, body, data = http(
        "GET", f"{base_url}/groups/{gid}/projects/{pid}/outcome-artifact.md",
        headers=h, timeout=timeout,
    )
    # Don't JSON-parse markdown — check raw response
    hdrs_req = urllib.request.Request(
        f"{base_url}/groups/{gid}/projects/{pid}/outcome-artifact.md",
        headers={**h, "Accept": "text/markdown"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(hdrs_req, timeout=timeout) as resp:
            artifact_md = resp.read().decode("utf-8")
            ct = resp.headers.get("Content-Type", "")
            code = resp.status
    except Exception as e:
        artifact_md = ""
        ct = ""
        code = 0

    if code == 200 and "text/markdown" in ct.lower():
        passed, issues = check_artifact(artifact_md)
        ok("outcome_artifact",
           f"size={len(artifact_md)}B ct={ct} check={'PASS' if passed else 'FAIL'}")
        for issue in issues:
            print(f"         {issue}")
    else:
        fail("outcome_artifact", f"HTTP {code} ct={ct}: {body[:120]}")
        return _cleanup(proc, db_path, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════════════
    n_pass = sum(1 for r in RESULTS if r[1])
    n_fail = sum(1 for r in RESULTS if not r[1])
    total_t = time.monotonic() - T0
    all_ok = n_fail == 0
    print(f"\n{'='*60}")
    print(f"HTTP API Smoke: {'PASS' if all_ok else 'FAIL'}")
    print(f"Mode: {'deployment' if args.base_url else 'local'} | "
          f"Steps: {len(RESULTS)}  Passed: {n_pass}  Failed: {n_fail}")
    print(f"Total time: {total_t:.2f}s")
    print(f"{'='*60}")

    return _cleanup(proc, db_path, 0 if all_ok else 1)


def _cleanup(proc, db_path, exit_code: int) -> int:
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    if db_path and os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
