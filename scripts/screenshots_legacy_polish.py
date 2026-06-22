"""Legacy console visual acceptance screenshots.

Captures Documents, Tasks, Ontology, Agent, Conversations, and Groups at
desktop and 390px mobile widths. This is a visual QA helper, not a product
feature.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment]


PAGES = [
    ("documents", "#/groups/{gid}/documents", ".legacyPage"),
    ("tasks", "#/groups/{gid}/tasks", ".legacyPage"),
    ("ontology", "#/groups/{gid}/ontology", ".ontoPage.legacyPage"),
    ("agent", "#/groups/{gid}/agent", ".agentPage.legacyPage"),
    ("conversations", "#/groups/{gid}/conversations", ".legacyPage"),
    ("groups", "#/groups", ".legacyPage"),
]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _setup_env(db_path: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        DATABASE_URL=f"sqlite+pysqlite:///{db_path}",
        JWT_SECRET_KEY="vrfy-32-bytes-key-xxxxxxxxxxxxx",
        CHAT_PROVIDER="fake",
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_MODEL="fake",
        EMBEDDING_DIMENSION="8",
        CHAT_MODEL="fake",
    )
    return env


def _prepare(page) -> None:
    page.evaluate(
        """() => {
          document.querySelectorAll('.toast').forEach(t => t.remove());
          const m = document.getElementById('navMoreMenu');
          if (m) m.hidden = true;
          const b = document.getElementById('navMoreBtn');
          if (b) b.setAttribute('aria-expanded', 'false');
          window.scrollTo(0, 0);
        }"""
    )
    page.wait_for_timeout(250)


def _has_overflow(page) -> bool:
    return bool(
        page.evaluate(
            "() => document.documentElement.scrollWidth > window.innerWidth + 1"
        )
    )


def _bootstrap_user(page, base: str) -> str:
    email = f"legacy-{uuid.uuid4().hex[:8]}@test.com"
    page.goto(f"{base}/console")
    page.wait_for_timeout(800)

    page.click(".authTab[data-tab='register']")
    page.fill("#registerEmail", email)
    page.fill("#registerName", "Legacy Shot")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]")
    page.wait_for_timeout(1200)

    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1000)

    page.fill("#onboardName", "Legacy Visual QA")
    page.click("#onboardCreateBtn")
    page.wait_for_timeout(1000)

    hash_value = page.evaluate("() => location.hash")
    return hash_value.split("/")[2]


def _capture_set(page, base: str, out_dir: Path, gid: str, size_name: str) -> bool:
    all_ok = True
    for name, route, selector in PAGES:
        page.goto(f"{base}/console{route.format(gid=gid)}")
        page.wait_for_timeout(900)
        try:
            page.wait_for_selector(selector, timeout=3000)
        except Exception:
            print(f"  [warn] {size_name}/{name}: selector missing: {selector}")
            all_ok = False
        _prepare(page)
        overflow = _has_overflow(page)
        if overflow:
            print(f"  [warn] {size_name}/{name}: horizontal overflow")
            all_ok = False
        path = out_dir / f"{name}-{size_name}.png"
        page.screenshot(path=str(path), full_page=False)
        print(f"  [snap] {path.name} ({path.stat().st_size} bytes)")
    return all_ok


def main() -> int:
    if sync_playwright is None:
        print("SKIP: playwright not installed")
        return 0

    root = Path(__file__).resolve().parents[1]
    out_dir = root / ".tmp" / "legacy-polish"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_shot in out_dir.glob("*.png"):
        old_shot.unlink()

    port = _free_port()
    db_path = str(root / ".tmp" / f"legacy-polish-{uuid.uuid4().hex}.db")

    env = _setup_env(db_path)
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        check=False,
    )
    if migration.returncode != 0:
        print(migration.stdout.decode(errors="replace"))
        print(migration.stderr.decode(errors="replace"))
        return migration.returncode
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "semantic_lighthouse.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    base = f"http://127.0.0.1:{port}"

    all_ok = True
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            desktop = browser.new_page(viewport={"width": 1280, "height": 800})
            gid = _bootstrap_user(desktop, base)
            all_ok &= _capture_set(desktop, base, out_dir, gid, "desktop")
            desktop.close()

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            gid_mobile = _bootstrap_user(mobile, base)
            all_ok &= _capture_set(mobile, base, out_dir, gid_mobile, "mobile")
            mobile.close()

            browser.close()
    finally:
        proc.terminate()
        proc.wait()
        try:
            Path(db_path).unlink()
        except OSError:
            pass

    expected = len(PAGES) * 2
    actual = len(list(out_dir.glob("*.png")))
    print(f"\nLegacy polish screenshots: {actual}/{expected} in {out_dir}")
    print(f"All checks: {'PASS' if all_ok and actual >= expected else 'FAIL'}")
    return 0 if all_ok and actual >= expected else 1


if __name__ == "__main__":
    sys.exit(main())
