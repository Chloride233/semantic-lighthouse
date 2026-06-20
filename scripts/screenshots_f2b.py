"""F2C acceptance screenshots — model, validate, pilot at desktop + mobile sizes.
Fixes: close "more tools" menu, wait for stage-specific elements, scroll to top."""
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


def _prepare_page(page):
    """Close 'more tools' menu if open, scroll to top."""
    page.evaluate("() => { const m = document.getElementById('navMoreMenu'); if (m) m.hidden = true; const b = document.getElementById('navMoreBtn'); if (b) b.setAttribute('aria-expanded', 'false'); window.scrollTo(0, 0); }")


def _snap(page, out_dir, name):
    _prepare_page(page)
    page.wait_for_timeout(300)
    path = os.path.join(out_dir, name)
    page.screenshot(path=path, full_page=False)
    size = os.path.getsize(path)
    print(f"  [snap] {name} ({size} bytes)")


def _assert_no_overflow(page, label):
    """Programmatic check: page has no horizontal overflow."""
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    if overflow:
        print(f"  [warn] {label}: page has horizontal overflow")
    return not overflow


def _assert_stage(page, expected_element, label):
    """Check that the expected stage element is visible."""
    visible = page.locator(expected_element).count() > 0
    if not visible:
        print(f"  [warn] {label}: expected element '{expected_element}' not found")
    return visible


def main() -> int:
    if sync_playwright is None:
        print("SKIP: playwright not installed")
        return 0

    port = _free_port()
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    out_dir = os.path.join(os.path.dirname(__file__), "..", ".tmp", "f2c")
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
    all_checks_ok = True

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # ── Desktop (1280x800): full pipeline with stage-verified screenshots ──
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            all_checks_ok &= _run_desktop_pipeline(page, base, out_dir, email)
            page.close()

            # ── Mobile (390x844): fresh pipeline for correct stage captures ──
            page = browser.new_page(viewport={"width": 390, "height": 844})
            all_checks_ok &= _run_mobile_pipeline(page, base, out_dir, email)
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
    all_exist = True
    for name in expected:
        path = os.path.join(out_dir, name)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  [OK] {name} ({size} bytes)")
        else:
            print(f"  [MISSING] {name}")
            all_exist = False

    result = 0 if all_exist and all_checks_ok else 1
    print(f"\nAll checks: {'PASS' if result == 0 else 'FAIL'}")
    return result


def _run_desktop_pipeline(page, base, out_dir, email):
    """Register → group → project → CSV → screenshots at model/validate/pilot."""
    ok = True
    page.goto(f"{base}/console")
    page.wait_for_timeout(1000)

    # Register
    page.click(".authTab[data-tab='register']")
    page.wait_for_timeout(300)
    page.fill("#registerEmail", email)
    page.fill("#registerName", "Desktop Shot")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]")
    page.wait_for_timeout(1500)

    # Login
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1200)

    # Onboard
    page.fill("#onboardName", "F2C Desktop")
    page.click("#onboardCreateBtn")
    page.wait_for_timeout(1200)

    # Create project
    page.click("#createFirstBtn")
    page.wait_for_timeout(400)
    page.fill("#npName", "Desktop Project")
    page.fill("#npGoal", "F2C desktop screenshot project")
    page.click("#npSubmit")
    page.wait_for_timeout(1500)

    # Upload CSV
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(400)
    csv_path = os.path.join(out_dir, f"ds-{email.split('@')[0]}.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("product_id,name,price,category\n1,Alice,9.99,tools\n2,Bob,24.99,electronics\n3,Carol,15.00,tools\n")
    page.set_input_files("#upFile", csv_path)
    page.click("#upSubmit")
    page.wait_for_timeout(3000)

    # Generate drafts → model stage
    page.wait_for_timeout(500)
    if page.locator("#genFromDataBtn").count() > 0:
        page.click("#genFromDataBtn")
        page.wait_for_timeout(2500)

    # ── Model screenshot: wait for .draftList to be visible ────────
    page.wait_for_timeout(500)
    try:
        page.wait_for_selector(".draftRow", timeout=5000)
    except Exception:
        pass
    ok &= _assert_stage(page, ".draftRow", "model-desktop")
    ok &= _assert_no_overflow(page, "model-desktop")
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

    # ── Validate screenshot: wait for contract/bindings content ────
    page.wait_for_timeout(500)
    try:
        page.wait_for_selector(".stagePanel", timeout=5000)
    except Exception:
        pass
    ok &= _assert_stage(page, ".stagePanel", "validate-desktop")
    ok &= _assert_no_overflow(page, "validate-desktop")
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

    # ── Pilot screenshot: wait for query form + results ────────────
    try:
        page.wait_for_selector(".queryForm", timeout=5000)
    except Exception:
        pass
    ok &= _assert_stage(page, ".queryForm", "pilot-desktop")
    ok &= _assert_no_overflow(page, "pilot-desktop")
    _snap(page, out_dir, "pilot-desktop.png")

    try:
        os.unlink(csv_path)
    except OSError:
        pass
    return ok


def _run_mobile_pipeline(page, base, out_dir, email):
    """Run full pipeline at 390px viewport. Takes stage-verified mobile screenshots."""
    ok = True
    mobile_email = f"mobile-{email}"
    page.goto(f"{base}/console")
    page.wait_for_timeout(1000)

    # Register
    page.click(".authTab[data-tab='register']")
    page.wait_for_timeout(300)
    page.fill("#registerEmail", mobile_email)
    page.fill("#registerName", "Mobile Shot")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]")
    page.wait_for_timeout(1500)

    # Login
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1200)

    # Onboard (mobile onboarding)
    page.fill("#onboardName", "F2C Mobile")
    page.click("#onboardCreateBtn")
    page.wait_for_timeout(1200)

    # Create project
    page.click("#createFirstBtn")
    page.wait_for_timeout(400)
    page.fill("#npName", "Mobile Project")
    page.fill("#npGoal", "F2C mobile screenshot")
    page.click("#npSubmit")
    page.wait_for_timeout(1500)

    # Upload CSV
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(400)
    csv_path = os.path.join(out_dir, f"dm-{uuid.uuid4().hex[:8]}.csv")
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

    # ── Model mobile screenshot ────────────────────────────────────
    page.wait_for_timeout(500)
    try:
        page.wait_for_selector(".draftRow", timeout=5000)
    except Exception:
        pass
    ok &= _assert_stage(page, ".draftRow", "model-mobile")
    ok &= _assert_no_overflow(page, "model-mobile")
    _snap(page, out_dir, "model-mobile.png")

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
            page.fill("#dlgReason", "Accept warnings")
            page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Generate bindings → validate
    page.wait_for_timeout(500)
    if page.locator("#genBindingsBtn").count() > 0:
        page.click("#genBindingsBtn")
        page.wait_for_timeout(1500)

    # ── Validate mobile screenshot ─────────────────────────────────
    page.wait_for_timeout(500)
    try:
        page.wait_for_selector(".stagePanel", timeout=5000)
    except Exception:
        pass
    ok &= _assert_stage(page, ".stagePanel", "validate-mobile")
    ok &= _assert_no_overflow(page, "validate-mobile")
    _snap(page, out_dir, "validate-mobile.png")

    # Activate → pilot
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

    # ── Pilot mobile screenshot ────────────────────────────────────
    try:
        page.wait_for_selector(".queryForm", timeout=5000)
    except Exception:
        pass
    ok &= _assert_stage(page, ".queryForm", "pilot-mobile")
    ok &= _assert_no_overflow(page, "pilot-mobile")
    _snap(page, out_dir, "pilot-mobile.png")

    try:
        os.unlink(csv_path)
    except OSError:
        pass
    return ok


if __name__ == "__main__":
    sys.exit(main())
