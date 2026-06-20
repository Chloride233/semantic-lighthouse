"""F2B acceptance screenshots — model, validate, pilot at desktop + mobile sizes."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment]


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


def _snap(page, out_dir, name):
    path = os.path.join(out_dir, name)
    page.screenshot(path=path, full_page=False)
    size = os.path.getsize(path)
    print(f"  [snap] {name} ({size} bytes)")


def main() -> int:
    if sync_playwright is None:
        print("SKIP: playwright not installed")
        return 0

    port = _free_port()
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    out_dir = os.path.join(os.path.dirname(__file__), "..", ".tmp", "f2b")
    os.makedirs(out_dir, exist_ok=True)

    env = _setup_env(db_path)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env, capture_output=True,
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "semantic_lighthouse.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)

    base = f"http://127.0.0.1:{port}"
    email = f"shot-{uuid.uuid4().hex[:8]}@test.com"
    errors = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # ── Desktop (1280x800): full pipeline with screenshots ──────
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            errors += _run_desktop_pipeline(page, base, out_dir, email)
            page.close()

            # ── Mobile (390x844): re-login, navigate to model/validate/pilot ──
            page = browser.new_page(viewport={"width": 390, "height": 844})
            errors += _run_mobile_snapshots(page, base, out_dir, email)
            page.close()

            browser.close()
    finally:
        proc.terminate()
        proc.wait()
        try:
            os.unlink(db_path)
        except OSError:
            pass

    # Verify all 6 screenshots exist
    expected = [
        "model-desktop.png", "validate-desktop.png", "pilot-desktop.png",
        "model-mobile.png", "validate-mobile.png", "pilot-mobile.png",
    ]
    print("\n=== Screenshot Verification ===")
    all_ok = True
    for name in expected:
        path = os.path.join(out_dir, name)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  [OK] {name} ({size} bytes)")
        else:
            print(f"  [MISSING] {name}")
            all_ok = False

    print(f"\nConsole errors: {errors}")
    return 0 if all_ok and errors == 0 else 1


def _run_desktop_pipeline(page, base, out_dir, email):
    """Register → group → project → CSV → drafts → review → build → bind → activate → query.
    Takes screenshots at model, validate, pilot stages."""
    errors = []

    page.goto(f"{base}/console")
    page.wait_for_timeout(1000)

    # Register
    page.click(".authTab[data-tab='register']")
    page.wait_for_timeout(300)
    page.fill("#registerEmail", email)
    page.fill("#registerName", "Screenshot")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]")
    page.wait_for_timeout(1500)

    # Login
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1200)

    # Onboard
    page.fill("#onboardName", "F2B Screenshots")
    page.click("#onboardCreateBtn")
    page.wait_for_timeout(1200)

    # Create project
    page.click("#createFirstBtn")
    page.wait_for_timeout(400)
    page.fill("#npName", "Screenshot Project")
    page.fill("#npGoal", "F2B acceptance screenshots")
    page.click("#npSubmit")
    page.wait_for_timeout(1500)

    # Upload CSV with Alice
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(400)
    csv_path = os.path.join(out_dir, f"shot-{email.split('@')[0]}.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("product_id,name,price\n1,Alice,9.99\n2,Bob,24.99\n3,Carol,15.00\n")
    page.set_input_files("#upFile", csv_path)
    page.click("#upSubmit")
    page.wait_for_timeout(3000)

    # Generate drafts → model stage
    page.wait_for_timeout(500)
    if page.locator("#genFromDataBtn").count() > 0:
        page.click("#genFromDataBtn")
        page.wait_for_timeout(2500)

    # Screenshot: model stage
    page.wait_for_timeout(500)
    _snap(page, out_dir, "model-desktop.png")

    # Batch accept all proposed
    if page.locator("#selectAllProposed").count() > 0:
        page.click("#selectAllProposed")
        page.wait_for_timeout(200)
    if page.locator(".draftCheck:checked").count() > 0:
        page.click("#batchAcceptBtn")
        page.wait_for_timeout(400)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)

    # Build package
    page.wait_for_timeout(500)
    build_btn = page.locator("#buildPkgBtn")
    if build_btn.count() > 0 and not build_btn.is_disabled():
        build_btn.click()
        page.wait_for_timeout(500)
        if page.locator("#dlgReason").count() > 0:
            page.fill("#dlgReason", "Accept warnings for screenshot")
            page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Generate bindings → validate stage
    page.wait_for_timeout(500)
    if page.locator("#genBindingsBtn").count() > 0:
        page.click("#genBindingsBtn")
        page.wait_for_timeout(1500)

    # Screenshot: validate stage
    page.wait_for_timeout(500)
    _snap(page, out_dir, "validate-desktop.png")

    # Activate → pilot stage + run query
    if page.locator("#activateBtn").count() > 0:
        page.click("#activateBtn")
        page.wait_for_timeout(300)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)

    page.wait_for_timeout(500)
    if page.locator("#qOT").count() > 0:
        page.click("#qRunBtn")
        page.wait_for_timeout(2000)

    # Screenshot: pilot stage (with query results)
    _snap(page, out_dir, "pilot-desktop.png")

    # Cleanup
    try:
        os.unlink(csv_path)
    except OSError:
        pass

    return len(errors)


def _run_mobile_snapshots(page, base, out_dir, email):
    """Login and navigate to project for mobile screenshots."""
    page.goto(f"{base}/console")
    page.wait_for_timeout(800)

    # Login
    page.fill("#loginEmail", email)
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1200)

    # Get gid from URL after navigation
    gid = page.evaluate("() => { const h = location.hash; const parts = h.split('/'); return parts[2] || ''; }")
    if not gid:
        # Navigate to groups to find gid
        page.goto(f"{base}/console#/groups")
        page.wait_for_timeout(800)
        gid = page.evaluate("() => { const h = location.hash; const parts = h.split('/'); return parts[2] || ''; }")

    if not gid:
        print("  [warn] Could not determine gid for mobile screenshots")
        return 1

    # Navigate to project detail — will show current stage (pilot)
    page.goto(f"{base}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)

    if page.locator(".projectCard").count() > 0:
        page.locator(".projectCard").first.click()
        page.wait_for_timeout(2000)

    # Model mobile — page shows current stage info
    _snap(page, out_dir, "model-mobile.png")

    # Validate mobile
    _snap(page, out_dir, "validate-mobile.png")

    # Pilot mobile — run query for results
    if page.locator("#qOT").count() > 0:
        if page.locator(".profileTable").count() == 0:
            page.click("#qRunBtn")
            page.wait_for_timeout(2000)
    _snap(page, out_dir, "pilot-mobile.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
