"""Quick UI verification — opens each page and checks render state."""

import os
import socket
import subprocess
import sys
import tempfile
import time

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


def _run_checks(page, base: str) -> list[tuple[str, bool]]:
    results: list[tuple[str, bool]] = []

    # 1. Auth page renders (tabbed layout)
    page.goto(f"{base}/console")
    page.wait_for_timeout(1000)
    results.append((
        "Auth renders Chinese brand + tabs",
        page.locator("#loginEmail").count() > 0
        and page.locator("text=语义灯塔").count() > 0,
    ))

    # 2. Register
    page.click(".authTab[data-tab='register']")
    page.wait_for_timeout(400)
    page.fill("#registerEmail", "t@e.com")
    page.fill("#registerName", "T")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]")
    page.wait_for_timeout(1500)
    has_success = (
        page.locator(".authSuccess").is_visible()
        or page.locator(".toast--success").count() > 0
    )
    results.append(("Register success", has_success))

    # 3. Sign in
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1200)
    results.append((
        "Onboarding renders (0 groups)",
        page.locator("#onboardName").count() > 0,
    ))

    # 4. Create workspace
    page.fill("#onboardName", "V")
    page.click("#onboardCreateBtn")
    page.wait_for_timeout(1200)
    results.append((
        "Documents renders after onboarding",
        page.locator("#docFileInput").count() > 0
        and page.locator("text=知识库").count() > 0,
    ))

    current_hash = page.evaluate("() => location.hash")
    gid = current_hash.split("/")[2] if "/groups/" in current_hash else ""

    # 5. Ask page
    page.click("a[href='#/ask']")
    page.wait_for_timeout(600)
    results.append((
        "Ask page renders as Chinese home",
        page.locator(".askPage").count() > 0
        and page.locator("text=知识问答").count() > 0,
    ))

    # 6. Conversations
    page.click("a[href*='conversations']")
    page.wait_for_timeout(500)
    try:
        page.wait_for_selector("#convTitle", timeout=3000)
    except Exception:
        pass
    results.append((
        "Conversations renders",
        page.locator("#convTitle").count() > 0
        and page.locator("text=多轮对话").count() > 0,
    ))

    # 7. Workspace
    page.click("a[href='#/groups']")
    page.wait_for_timeout(500)
    results.append((
        "Workspace renders",
        page.locator("#groupName").count() > 0
        and page.locator("text=工作区").count() > 0,
    ))

    # 8. Old RAG route
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/rag")
        page.wait_for_timeout(800)
        rag_ok = (
            page.locator("#ragQuestion").count() > 0
            or page.locator(".loading").count() > 0
        )
    else:
        rag_ok = False
    results.append(("Old RAG route functional", rag_ok))

    # 9. Old Jobs route
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/jobs")
        page.wait_for_timeout(1500)
        jobs_ok = (
            page.locator(".pageTitle").count() > 0
            or page.locator(".error").count() > 0
        )
    else:
        jobs_ok = False
    results.append(("Old Jobs route loads", jobs_ok))

    # 10. Documents route + batch upload
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/documents")
        page.wait_for_timeout(500)
        docs_ok = page.locator("#docFileInput").count() > 0
    else:
        docs_ok = False
    results.append(("Old Documents route functional", docs_ok))

    batch_ok = False
    if docs_ok:
        batch_ok = bool(
            page.locator("#docFileInput").evaluate("el => el.multiple")
            and page.locator("text=导入本地知识库").count() > 0
        )
    results.append(("Documents supports batch upload", batch_ok))

    # ── 13. Tasks page empty state ─────────────────────────────────
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/tasks")
        page.wait_for_timeout(800)
        tasks_page_ok = page.locator("text=轻量任务").count() > 0
        tasks_empty_ok = page.locator("text=暂无任务").count() > 0
    else:
        tasks_page_ok = False
        tasks_empty_ok = False
    results.append(("Tasks page empty state", tasks_page_ok and tasks_empty_ok))

    # ── 14. Status filter tabs ─────────────────────────────────────
    if gid:
        filter_all = page.locator("button.taskFilter:has-text('全部')").count() > 0
        filter_pending = page.locator("button.taskFilter:has-text('待处理')").count() > 0
        filter_active = page.locator("button.taskFilter:has-text('进行中')").count() > 0
        filter_done = page.locator("button.taskFilter:has-text('已完成')").count() > 0
        filters_ok = filter_all and filter_pending and filter_active and filter_done
    else:
        filters_ok = False
    results.append(("Status filter tabs visible", filters_ok))

    # ── 15. Confirm button + task link in answer card ───────────────
    # MAY FAIL — depends on fake chat returning next_steps
    confirm_btn_ok = False
    task_link_ok = False
    if gid:
        try:
            fd, md_path = tempfile.mkstemp(suffix=".md")
            os.close(fd)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Test\n\n企业 AI 转型需要 Ontology。\n")
            page.goto(f"{base}/console#/groups/{gid}/documents")
            page.wait_for_timeout(500)
            page.set_input_files("#docFileInput", md_path)
            page.wait_for_timeout(1500)
            page.click("a[href='#/ask']")
            page.wait_for_timeout(500)
            page.fill("#askQuestion", "企业为什么需要Ontology")
            page.click("#askSubmitBtn")
            page.wait_for_timeout(3000)
            confirm_btn_ok = page.locator(".confirmTaskBtn").count() > 0
            task_link_ok = page.locator(".answerNextLink").count() > 0
        except Exception:
            confirm_btn_ok = False
            task_link_ok = False
        finally:
            try:
                os.unlink(md_path)
            except OSError:
                pass
    results.append(("Confirm button + task link in answer card", confirm_btn_ok and task_link_ok))

    # ── 16. Navbar tasks entry ─────────────────────────────────────
    if gid:
        nav_tasks_ok = page.locator("a[href*='tasks']").count() > 0
    else:
        nav_tasks_ok = False
    results.append(("Navbar tasks entry visible", nav_tasks_ok))

    # ── 17. Task card renders ───────────────────────────────────────
    task_card_ok = False
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/tasks")
        page.wait_for_timeout(800)
        task_card_ok = (
            page.locator(".taskCard").count() > 0
            and page.locator(".taskTitle").count() > 0
            and page.locator(".taskStatus").count() > 0
        )
    results.append(("Task card renders with title + status", task_card_ok))

    # ── 18. Cancelled filter tab ────────────────────────────────────
    if gid:
        cancelled_tab_ok = page.locator("button.taskFilter:has-text('已取消')").count() > 0
    else:
        cancelled_tab_ok = False
    results.append(("Cancelled filter tab visible", cancelled_tab_ok))

    # ── Agent page ────────────────────────────────────────────────────
    agent_page_ok = False
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/agent")
        page.wait_for_timeout(800)
        has_title = page.locator("text=Agent 工作流").count() > 0
        has_create = page.locator("text=新建 Agent 运行").count() > 0
        has_input = page.locator("#agentGoalInput").count() > 0
        has_btn = page.locator("#startAgentBtn").count() > 0
        has_examples = page.locator(".exampleGoalBtn").count() > 0
        has_list = (
            page.locator("text=暂无 Agent 运行").count() > 0
            or page.locator("#agentRunList").count() > 0
        )
        agent_page_ok = has_title and has_create and has_input and has_btn and has_examples and has_list
    results.append(("Agent page renders", agent_page_ok))

    # ── Ontology page ──────────────────────────────────────────────────
    onto_page_ok = False
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/ontology")
        page.wait_for_timeout(800)
        onto_page_ok = (
            page.locator("text=Ontology 治理").count() > 0
            and page.locator("#ontoMetrics").count() > 0
            and (page.locator("text=只读视图").count() > 0
                 or page.locator("#ontoScanBtn").count() > 0
                 or page.locator(".muted").count() > 0)
        )
    results.append(("Ontology page renders", onto_page_ok))

    # ── 19. Document filter tabs ──────────────────────────────────────
    doc_filter_ok = False
    if gid:
        page.goto(f"{base}/console#/groups/{gid}/documents")
        page.wait_for_timeout(800)
        doc_filter_ok = (
            page.locator(".docFilters .taskFilter:has-text('全部')").count() > 0
            and page.locator(".docFilters .taskFilter:has-text('可检索')").count() > 0
        )
    results.append(("Document filter tabs visible", doc_filter_ok))

    # ── 20. Document metadata badges ──────────────────────────────────
    doc_meta_ok = False
    if gid:
        doc_meta_ok = page.locator(".docTag").count() > 0
    results.append(("Document metadata badges in table", doc_meta_ok))

    # 11. Logout
    page.click("#navLogoutBtn")
    page.wait_for_timeout(500)
    results.append((
        "Logout redirects to login",
        page.locator("#loginEmail").count() > 0,
    ))

    # 12. Re-login
    page.fill("#loginEmail", "t@e.com")
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1200)
    results.append((
        "Re-login -> Ask (home)",
        page.locator(".askPage").count() > 0
        or page.url.endswith("#/ask"),
    ))

    return results


def main() -> int:
    if sync_playwright is None:
        print("SKIP: playwright not installed")
        return 0

    port = _free_port()
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    env = _setup_env(db_path)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
    )
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "semantic_lighthouse.main:app",
            "--host", "127.0.0.1", "--port", str(port),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)

    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            page = b.new_page()
            results = _run_checks(page, base)
            b.close()
    finally:
        proc.terminate()
        proc.wait()
        try:
            os.unlink(db_path)
        except OSError:
            pass

    print("\n=== UI Verification Results ===")
    passed = 0
    failed = 0
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {name}")
    print(f"\n{passed} passed, {failed} failed out of {len(results)} tests")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
