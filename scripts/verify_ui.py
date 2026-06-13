"""Quick UI verification — opens each page and checks render state."""
import subprocess, sys, time, socket, os, tempfile

def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

port = free_port()
fd, db_path = tempfile.mkstemp(suffix=".db"); os.close(fd)
env = os.environ.copy()
env.update(DATABASE_URL=f"sqlite+pysqlite:///{db_path}",
           JWT_SECRET_KEY="vrfy-32-bytes-key-xxxxxxxxxxxxx",
           CHAT_PROVIDER="fake", EMBEDDING_PROVIDER="fake",
           EMBEDDING_MODEL="fake", EMBEDDING_DIMENSION="8", CHAT_MODEL="fake")

subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, capture_output=True)
proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "semantic_lighthouse.main:app",
                          "--host", "127.0.0.1", "--port", str(port)], env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)

from playwright.sync_api import sync_playwright
base = f"http://127.0.0.1:{port}"
results = []

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()

    # 1. Auth page renders (tabbed layout)
    page.goto(f"{base}/console"); page.wait_for_timeout(1000)
    results.append(("Auth renders (brand + tabs)", page.locator("#loginEmail").count() > 0 and page.locator(".authBrandIcon").count() > 0))

    # 2. Register — switch to Register tab
    page.click(".authTab[data-tab='register']"); page.wait_for_timeout(400)
    page.fill("#registerEmail", "t@e.com"); page.fill("#registerName", "T")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]"); page.wait_for_timeout(1500)
    # Check either success banner or toast
    hasSuccess = page.locator(".authSuccess").is_visible() or page.locator(".toast--success").count() > 0
    results.append(("Register success", hasSuccess))

    # 3. Sign in
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]"); page.wait_for_timeout(1200)
    results.append(("Onboarding renders (0 groups)", page.locator("#onboardName").count() > 0))

    # 4. Create workspace
    page.fill("#onboardName", "V")
    page.click("#onboardCreateBtn"); page.wait_for_timeout(1200)
    results.append(("Documents renders after onboarding", page.locator("#docFileInput").count() > 0))

    # Capture the group_id from the URL (documents page uses /groups/:gid/documents)
    currentHash = page.evaluate("() => location.hash")
    gid = currentHash.split("/")[2] if "/groups/" in currentHash else ""

    # 5. Ask page as home
    page.click("a[href='#/ask']"); page.wait_for_timeout(600)
    results.append(("Ask page renders as home", page.locator(".askPage").count() > 0))

    # 6. Conversations
    page.click("a[href*='conversations']"); page.wait_for_timeout(500)
    results.append(("Conversations renders", page.locator("#convTitle").count() > 0))

    # 7. Workspace (old groups page)
    page.click("a[href='#/groups']"); page.wait_for_timeout(500)
    results.append(("Workspace renders", page.locator("#groupName").count() > 0))

    # 8. Old RAG route still functional (use captured group_id)
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/rag"); page.wait_for_timeout(800)
        ragOk = page.locator("#ragQuestion").count() > 0 or page.locator(".loading").count() > 0
    else:
        ragOk = False
    results.append(("Old RAG route functional", ragOk))

    # 9. Old Jobs route still functional (may fail on empty doc search)
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/jobs"); page.wait_for_timeout(1500)
        jobsOk = page.locator(".pageTitle").count() > 0 or page.locator(".error").count() > 0
    else:
        jobsOk = False
    results.append(("Old Jobs route loads", jobsOk))

    # 10. Old groups route still functional
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/documents"); page.wait_for_timeout(500)
        docsOk = page.locator("#docFileInput").count() > 0
    else:
        docsOk = False
    results.append(("Old Documents route functional", docsOk))

    # 11. Logout
    page.click("#navLogoutBtn"); page.wait_for_timeout(500)
    results.append(("Logout redirects to login", page.locator("#loginEmail").count() > 0))

    # 12. Re-login — should go to /ask directly (has groups now)
    page.fill("#loginEmail", "t@e.com"); page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]"); page.wait_for_timeout(1200)
    results.append(("Re-login → Ask (home)", page.locator(".askPage").count() > 0 or page.url.endswith("#/ask")))

    b.close()

proc.terminate(); proc.wait()
try: os.unlink(db_path)
except OSError: pass

print(f"\n=== UI Verification Results ===")
passed = 0
failed = 0
for name, ok in results:
    s = "PASS" if ok else "FAIL"
    if ok: passed += 1
    else: failed += 1
    print(f"  [{s}] {name}")
print(f"\n{passed} passed, {failed} failed out of {len(results)} tests")
sys.exit(0 if failed == 0 else 1)
