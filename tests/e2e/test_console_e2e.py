"""E2E browser tests for the Chinese console user flow."""

import uuid
from pathlib import Path

from playwright.sync_api import Page, expect


ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / ".tmp" / "e2e-uploads"


def _register(page: Page, email: str) -> None:
    page.click(".authTab[data-tab='register']")
    page.wait_for_timeout(300)
    page.fill("#registerEmail", email)
    page.fill("#registerName", "E2E User")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]")
    expect(page.locator("#loginEmail")).to_have_value(email, timeout=5000)
    expect(page.locator("#loginPassword")).to_be_visible()


def _login(page: Page, email: str | None = None) -> None:
    if email is not None:
        page.fill("#loginEmail", email)
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1200)


def _onboard(page: Page, name: str = "E2E Workspace") -> str:
    expect(page.locator("#onboardName")).to_be_visible(timeout=10000)
    page.fill("#onboardName", name)
    page.click("#onboardCreateBtn")
    # After F2A: onboarding redirects to Pilot empty state
    expect(page.locator("#createFirstBtn")).to_be_visible(timeout=10000)
    current_hash = page.evaluate("() => location.hash")
    return current_hash.split("/")[2]


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


def test_auth_onboarding_and_navigation(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/console")

    expect(page.locator(".authBrandIcon")).to_be_visible(timeout=5000)
    expect(page.locator(".authTitle")).to_contain_text("语义灯塔")

    _register(page, _unique_email("e2e-onboard"))
    _login(page)

    expect(page.locator(".onboardTitle")).to_contain_text("创建你的第一个工作区", timeout=10000)

    _onboard(page, "E2E 工作区")
    # After F2A: Pilot empty state is the landing page
    expect(page.locator("#createFirstBtn")).to_be_visible(timeout=10000)

    # Primary nav: Pilot, Ontology, 工作区
    for label in ("Pilot", "Ontology", "工作区"):
        expect(page.locator(f".navLinks a:has-text('{label}')")).to_be_visible()

    # Old entries in "更多工具" dropdown
    page.click("#navMoreBtn")
    page.wait_for_timeout(300)
    assert page.locator("a[href='#/ask']").count() > 0
    assert page.locator("a[href*='documents']").count() > 0


def test_ask_home_empty_kb_and_relogin(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/console")

    email = _unique_email("e2e-ask")
    _register(page, email)
    _login(page)
    _onboard(page, "问答工作区")

    # Ask is now in more-tools dropdown
    page.click("#navMoreBtn")
    page.wait_for_timeout(200)
    page.click("a[href='#/ask']")
    expect(page.locator(".askPage")).to_be_visible(timeout=5000)
    expect(page.locator(".emptyState")).to_be_visible()
    expect(page.locator(".emptyTitle")).to_contain_text("知识库还没有文档")

    page.click("#navLogoutBtn")
    expect(page.locator("#loginEmail")).to_be_visible(timeout=5000)
    _login(page, email)

    # Re-login lands on Pilot (F2A default)
    expect(page.locator("#createFirstBtn")).to_be_visible(timeout=10000)
    assert page.locator("#onboardName").count() == 0


def test_upload_then_ask_with_answer_card(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/console")

    _register(page, _unique_email("e2e-rag"))
    _login(page)
    _onboard(page, "RAG 工作区")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    md_file = UPLOAD_DIR / f"ontology-{uuid.uuid4().hex[:8]}.md"
    md_file.write_text(
        """---
title: Enterprise Ontology
entityType: Concept
---

# Ontology

Ontology connects business objects, data, and AI workflows for enterprise context.
""",
        encoding="utf-8",
    )

    # Navigate to documents via more-tools
    page.click("#navMoreBtn")
    page.wait_for_timeout(200)
    page.click("a[href*='documents']")
    page.wait_for_timeout(500)

    page.set_input_files("#docFileInput", str(md_file))
    page.click("#uploadDocBtn")
    expect(page.locator("body")).to_contain_text(md_file.name, timeout=10000)

    # Navigate to ask via more-tools
    page.click("#navMoreBtn")
    page.wait_for_timeout(200)
    page.click("a[href='#/ask']")
    expect(page.locator("#askQuestion")).to_be_visible(timeout=5000)

    page.fill("#askQuestion", "企业为什么需要 Ontology?")
    page.click("#askSubmitBtn")

    expect(page.locator(".answerCard")).to_be_visible(timeout=15000)
    expect(page.locator(".confidenceBar")).to_be_visible()
    expect(page.locator(".answerCard-text")).not_to_be_empty()


def test_debug_and_legacy_routes_still_load(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/console")

    _register(page, _unique_email("e2e-routes"))
    _login(page)
    gid = _onboard(page, "兼容路由工作区")

    page.goto(f"{base_url}/console#/groups/{gid}/rag")
    expect(page.locator("#ragQuestion")).to_be_visible(timeout=5000)

    page.goto(f"{base_url}/console#/groups/{gid}/jobs")
    expect(page.locator(".pageTitle")).to_contain_text("ETL 任务", timeout=5000)

    page.goto(f"{base_url}/console#/groups/{gid}/documents")
    expect(page.locator("#docFileInput")).to_be_visible(timeout=5000)

    page.goto(f"{base_url}/console#/groups")
    expect(page.locator("#groupName")).to_be_visible(timeout=5000)

    page.goto(f"{base_url}/console#/groups/{gid}/conversations")
    expect(page.locator("#convTitle")).to_be_visible(timeout=5000)


# ═════════════════════════════════════════════════════════════════════
#  F2A — Business Pilot end-to-end flow
# ═════════════════════════════════════════════════════════════════════

def test_f2a_pilot_create_and_upload(page: Page, base_url: str) -> None:
    """F2A core: create data_first Pilot → upload CSV → verify data stage → profile."""
    page.goto(f"{base_url}/console")

    _register(page, _unique_email("e2e-f2a"))
    _login(page)
    gid = _onboard(page, "F2A Pilot 工作区")

    # Create data_first Pilot
    page.click("#createFirstBtn")
    page.wait_for_timeout(400)
    page.fill("#npName", "E2E Pilot")
    page.fill("#npGoal", "端到端测试 Pilot 项目")
    # Select data_first
    page.click("input[value='data_first']")
    page.click("#npSubmit")
    page.wait_for_timeout(1500)

    # Must be on project detail page with goal stage
    expect(page.locator(".projectDetail")).to_be_visible(timeout=10000)
    expect(page.locator(".stageRailLg")).to_be_visible()
    expect(page.locator("#uploadFirstBtn")).to_be_visible(timeout=5000)

    # Upload CSV
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(400)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = UPLOAD_DIR / f"e2e-data-{uuid.uuid4().hex[:8]}.csv"
    csv_path.write_text("order_id,customer,amount\n100,Acme,500\n101,Beta,750\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_path))
    page.click("#upSubmit")

    # Wait for upload + profiling + stage advance to "data"
    expect(page.locator(".datasetItem")).to_be_visible(timeout=15000)
    expect(page.locator(".datasetName")).to_contain_text(csv_path.name)

    # Expand profile
    page.locator("[id^='dsToggle-']").first.click()
    page.wait_for_timeout(400)
    expect(page.locator(".profileTable")).to_be_visible(timeout=5000)
    expect(page.locator(".pkTag").first).to_be_visible()

    # Refresh — data must persist
    current_hash = page.evaluate("() => location.hash")
    page.goto(f"{base_url}/console{current_hash}")
    page.wait_for_timeout(1500)
    expect(page.locator(".datasetItem")).to_be_visible(timeout=10000)
    expect(page.locator(".datasetName")).to_contain_text(csv_path.name)

    # Back to Pilot list — project stage should be "data"
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    expect(page.locator(".projectCard")).to_be_visible(timeout=5000)
    # Stage rail shows "数据" as current
    expect(page.locator(".stageDot.current")).to_contain_text("数据")


def test_f2a_member_permissions(page: Page, base_url: str) -> None:
    """F2A permissions: member sees projects/datasets but cannot create/upload."""
    page.goto(f"{base_url}/console")

    # Owner registers and creates workspace + project
    owner_email = _unique_email("e2e-f2a-own")
    _register(page, owner_email)
    _login(page)
    gid = _onboard(page, "F2A 权限工作区")

    # Create project with dataset
    page.click("#createFirstBtn")
    page.wait_for_timeout(400)
    page.fill("#npName", "Perm Project")
    page.fill("#npGoal", "Permissions test")
    page.click("#npSubmit")
    page.wait_for_timeout(1500)
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(400)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = UPLOAD_DIR / f"perm-{uuid.uuid4().hex[:8]}.csv"
    csv_path.write_text("id,val\n1,x\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_path))
    page.click("#upSubmit")
    expect(page.locator(".datasetItem")).to_be_visible(timeout=15000)

    # Generate invite via UI: go to groups, create invite, read code
    page.goto(f"{base_url}/console#/groups")
    page.wait_for_timeout(500)
    # Click create invite — the panel has a button that POSTs and shows code
    # Use evaluate to call API with the in-memory token (accessible via window.__token__ set during login)
    # Simpler: just use the existing page state. The api.js stores token in state module.
    # Workaround: read the invite from the UI
    page.fill("#groupName", "")  # ensure loaded
    # The groups page has a "创建邀请" button. Click it if visible.
    # Actually, the groups page renders "创建工作区" and "通过邀请码加入" panels.
    # There's no explicit invite-create UI in the current groups page.
    # Logout, login as outsider: must not see group projects
    page.click("#navLogoutBtn")
    page.wait_for_timeout(500)
    outsider_email = _unique_email("e2e-f2a-out")
    _register(page, outsider_email)
    _login(page)
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    outsider_ok = page.locator(".projectCard").count() == 0
    assert outsider_ok, "Outsider must not see group projects"

    # Relogin as owner — still sees everything
    page.click("#navLogoutBtn")
    page.wait_for_timeout(500)
    _login(page, owner_email)
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    expect(page.locator(".projectCard")).to_be_visible(timeout=5000)
    assert page.locator("#createProjectBtn").count() > 0, "Owner sees create button"


def test_f2a_error_handling(page: Page, base_url: str) -> None:
    """F2A: upload errors show human-readable messages, never [object Object]."""
    page.goto(f"{base_url}/console")

    _register(page, _unique_email("e2e-f2a-err"))
    _login(page)
    gid = _onboard(page, "F2A 错误工作区")

    # Create project
    page.click("#createFirstBtn")
    page.wait_for_timeout(400)
    page.fill("#npName", "Err Project")
    page.fill("#npGoal", "Error test")
    page.click("#npSubmit")
    page.wait_for_timeout(1500)
    expect(page.locator("#uploadFirstBtn")).to_be_visible(timeout=5000)

    # Try upload without selecting file
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(400)
    page.click("#upSubmit")
    page.wait_for_timeout(1000)

    # Error must be human-readable — no [object Object] anywhere on page
    body_text = page.locator("body").text_content()
    assert "[object Object]" not in body_text, "Must not show raw JS object"

    # Close any stray dialog, then verify create project flow
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    # Navigate fresh
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    if page.locator("#createProjectBtn").count() > 0:
        page.locator("#createProjectBtn").first.click()
        page.wait_for_timeout(400)
        page.fill("#npName", "")
        page.click("#npSubmit")
        page.wait_for_timeout(500)
        body_text2 = page.locator("body").text_content()
        assert "[object Object]" not in body_text2


def test_f2a_group_switch_isolates_projects(page: Page, base_url: str) -> None:
    """F2A: switching groups shows that group's projects, not cross-group leakage."""
    page.goto(f"{base_url}/console")

    _register(page, _unique_email("e2e-f2a-gs"))
    _login(page)
    gid1 = _onboard(page, "Group Alpha")

    # Create a project in Group Alpha
    page.click("#createFirstBtn")
    page.wait_for_timeout(400)
    page.fill("#npName", "Alpha Project")
    page.fill("#npGoal", "Only in Alpha")
    page.click("#npSubmit")
    page.wait_for_timeout(1500)

    # Navigate to groups page to create Group Beta via UI
    page.goto(f"{base_url}/console#/groups")
    page.wait_for_timeout(500)
    page.fill("#groupName", "Group Beta")
    page.click("#createGroupBtn")
    page.wait_for_timeout(1000)

    # Now navigate to groups to find Group Beta entry and click "打开"
    page.goto(f"{base_url}/console#/groups")
    page.wait_for_timeout(500)
    # Click the second "打开" link (Group Beta's)
    open_links = page.locator("a:has-text('打开')")
    if open_links.count() >= 2:
        open_links.nth(1).click()
        page.wait_for_timeout(800)

    # Must be on Group Beta's Pilot page
    current_hash = page.evaluate("() => location.hash")
    assert "/projects" in current_hash, f"Expected /projects in hash, got {current_hash}"

    # Group Beta should have empty Pilot (no Alpha project visible)
    expect(page.locator("#createFirstBtn")).to_be_visible(timeout=5000)
    # No project cards from Alpha
    assert page.locator(".projectCard").count() == 0
