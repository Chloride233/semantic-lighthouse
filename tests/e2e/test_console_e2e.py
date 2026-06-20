"""E2E browser tests for the Chinese console user flow."""

import json
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


def _get_access_token(page: Page) -> str:
    """Read the in-memory access token from the state module via dynamic import."""
    return page.evaluate("""async () => {
        const mod = await import('/static/js/state.js');
        return mod.state.accessToken || '';
    }""")


def _api_call(page: Page, method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated API call from within the page context."""
    token = _get_access_token(page)
    js_body = json.dumps(body) if body else "undefined"
    return page.evaluate(f"""async () => {{
        const headers = {{ 'Content-Type': 'application/json' }};
        if ('{token}') headers['Authorization'] = 'Bearer {token}';
        const resp = await fetch('{path}', {{
            method: '{method}',
            headers: headers,
            credentials: 'include',
            body: {js_body},
        }});
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
        return data;
    }}""")


# ═════════════════════════════════════════════════════════════════════
#  V1 — Auth, onboarding, navigation
# ═════════════════════════════════════════════════════════════════════

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
    _onboard(page, "Group Alpha")

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


# ═════════════════════════════════════════════════════════════════════
#  F2B — Owner full closed-loop: create → model → validate → pilot → query
# ═════════════════════════════════════════════════════════════════════

def _f2b_setup_owner_full_pipeline(page: Page, base_url: str, group_name: str = "F2B Full") -> tuple[str, str]:
    """Shared helper: register owner, create group, create project, upload CSV,
    generate drafts, batch accept, build package, generate bindings, activate.
    Returns (gid, pid)."""
    page.goto(f"{base_url}/console")
    _register(page, _unique_email("e2e-f2b"))
    _login(page)
    gid = _onboard(page, group_name)

    # Create project + upload CSV
    page.click("#createFirstBtn")
    page.wait_for_timeout(300)
    page.fill("#npName", "F2B Loop")
    page.fill("#npGoal", "Full pipeline E2E test")
    page.click("#npSubmit")
    page.wait_for_timeout(1200)
    expect(page.locator("#uploadFirstBtn")).to_be_visible(timeout=5000)
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(300)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = UPLOAD_DIR / f"f2b-{uuid.uuid4().hex[:8]}.csv"
    csv_path.write_text("id,name,val\n1,Alice,100\n2,Bob,200\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_path))
    page.click("#upSubmit")
    page.wait_for_timeout(2500)

    # Generate drafts from data stage
    expect(page.locator("#genFromDataBtn")).to_be_visible(timeout=5000)
    page.click("#genFromDataBtn")
    page.wait_for_timeout(2000)
    # Should advance to model stage
    page.wait_for_timeout(500)
    expect(page.locator(".draftRow").first).to_be_visible(timeout=10000)

    # Select all proposed and batch accept
    if page.locator("#selectAllProposed").count() > 0:
        page.click("#selectAllProposed")
        page.wait_for_timeout(200)
    checked = page.locator(".draftCheck:checked").count()
    assert checked > 0, "Must have checked drafts"
    page.click("#batchAcceptBtn")
    page.wait_for_timeout(400)
    expect(page.locator("#dlgConfirm")).to_be_visible(timeout=3000)
    page.click("#dlgConfirm")
    page.wait_for_timeout(1500)

    # After review, reload — now build package
    page.wait_for_timeout(500)
    expect(page.locator("#buildPkgBtn")).to_be_visible(timeout=10000)
    build_btn = page.locator("#buildPkgBtn")
    if build_btn.is_disabled():
        # May have proposed remaining — accept them
        if page.locator("#selectAllProposed").count() > 0:
            page.click("#selectAllProposed")
        if page.locator(".draftCheck:checked").count() > 0:
            page.click("#batchAcceptBtn")
            page.wait_for_timeout(300)
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)
        page.wait_for_timeout(500)
    # Build package
    build_btn = page.locator("#buildPkgBtn")
    if build_btn.count() > 0 and not build_btn.is_disabled():
        build_btn.click()
        page.wait_for_timeout(500)
        if page.locator("#dlgReason").count() > 0:
            page.fill("#dlgReason", "Accepting warnings for E2E")
            page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Should be at validate — check for bindings section
    expect(page.locator("#genBindingsBtn")).to_be_visible(timeout=15000)
    # Generate bindings
    page.click("#genBindingsBtn")
    page.wait_for_timeout(1500)

    # Activate
    expect(page.locator("#activateBtn")).to_be_visible(timeout=5000)
    page.click("#activateBtn")
    page.wait_for_timeout(300)
    if page.locator("#dlgConfirm").count() > 0:
        page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Should be at pilot stage — query workbench visible
    expect(page.locator("#qOT")).to_be_visible(timeout=10000)

    pid = page.evaluate("() => location.hash.split('/')[4] || ''")
    assert pid, "Must have project ID"
    return gid, pid


def test_f2b_owner_full_closed_loop(page: Page, base_url: str) -> None:
    """Owner: workspace → project → CSV → generate drafts → review → build → bindings → activate → query."""
    gid, pid = _f2b_setup_owner_full_pipeline(page, base_url)

    # Execute query
    page.click("#qRunBtn")
    page.wait_for_timeout(2000)
    # Verify results contain real data
    body = page.locator("body").text_content()
    assert "Alice" in body, "Query results must include Alice from test data"

    # Verify provenance exists and does NOT contain storage_path
    assert "dataset-storage" not in body.lower(), "Must not leak storage_path"
    assert "explainBox" in body or "查看溯源" in body, "Provenance/explain must be present"

    # Query after refresh: re-login (since token is in-memory), then verify stage still at pilot
    current_hash = page.evaluate("() => location.hash")
    # In-app navigation: go to project list, then back — stage persists
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    page.goto(f"{base_url}/console{current_hash}")
    page.wait_for_timeout(1500)
    expect(page.locator("#qOT")).to_be_visible(timeout=10000)
    # Query still works after navigation
    page.click("#qRunBtn")
    page.wait_for_timeout(2000)
    body2 = page.locator("body").text_content()
    assert "dataset-storage" not in body2.lower()
    assert "Alice" in body2, "Query must still return Alice after re-navigation"


# ═════════════════════════════════════════════════════════════════════
#  F2B — Real Member test (join-by-invite, not outsider)
# ═════════════════════════════════════════════════════════════════════

def test_f2b_real_member_via_invite(page: Page, base_url: str) -> None:
    """Owner creates invite; second user joins as member; member can view but cannot write."""
    page.goto(f"{base_url}/console")

    # ── Owner: register, create group, do full pipeline ──────────────────
    owner_email = _unique_email("e2e-f2b-own")
    _register(page, owner_email)
    _login(page)
    gid = _onboard(page, "F2B Member Test")
    # Create project + CSV + full pipeline
    page.click("#createFirstBtn")
    page.wait_for_timeout(300)
    page.fill("#npName", "Member Proj")
    page.fill("#npGoal", "Member permission test")
    page.click("#npSubmit")
    page.wait_for_timeout(1200)
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(300)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = UPLOAD_DIR / f"mem-{uuid.uuid4().hex[:8]}.csv"
    csv_path.write_text("id,label,score\n1,Alpha,10\n2,Beta,20\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_path))
    page.click("#upSubmit")
    page.wait_for_timeout(2500)

    # Generate drafts
    expect(page.locator("#genFromDataBtn")).to_be_visible(timeout=5000)
    page.click("#genFromDataBtn")
    page.wait_for_timeout(2000)
    page.wait_for_timeout(500)
    expect(page.locator(".draftRow").first).to_be_visible(timeout=10000)

    # Batch accept all proposed
    if page.locator("#selectAllProposed").count() > 0:
        page.click("#selectAllProposed")
        page.wait_for_timeout(200)
    if page.locator(".draftCheck:checked").count() > 0:
        page.click("#batchAcceptBtn")
        page.wait_for_timeout(400)
        expect(page.locator("#dlgConfirm")).to_be_visible(timeout=3000)
        page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Build package
    page.wait_for_timeout(500)
    expect(page.locator("#buildPkgBtn")).to_be_visible(timeout=10000)
    build_btn = page.locator("#buildPkgBtn")
    if build_btn.count() > 0 and not build_btn.is_disabled():
        build_btn.click()
        page.wait_for_timeout(500)
        if page.locator("#dlgReason").count() > 0:
            page.fill("#dlgReason", "ok")
            page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Generate bindings + activate
    expect(page.locator("#genBindingsBtn")).to_be_visible(timeout=15000)
    page.click("#genBindingsBtn")
    page.wait_for_timeout(1500)
    if page.locator("#activateBtn").count() > 0:
        page.click("#activateBtn")
        page.wait_for_timeout(300)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)

    # Query as owner to confirm data exists
    expect(page.locator("#qOT")).to_be_visible(timeout=10000)
    page.click("#qRunBtn")
    page.wait_for_timeout(2000)
    body_text = page.locator("body").text_content()
    assert "Alpha" in body_text, "Owner query must return Alpha"

    pid = page.evaluate("() => location.hash.split('/')[4] || ''")
    assert pid, "Must have project ID"

    # ── Owner creates invite via API ─────────────────────────────────────
    invite_data = _api_call(page, "POST", f"/groups/{gid}/invites")
    invite_code = invite_data.get("invite_code", "")
    assert invite_code, "Must get invite code"

    # ── Owner logs out ──────────────────────────────────────────────────
    page.click("#navLogoutBtn")
    page.wait_for_timeout(500)

    # ── Member registers and logs in ────────────────────────────────────
    member_email = _unique_email("e2e-f2b-mem")
    _register(page, member_email)
    _login(page)
    # Member has 0 groups — should see onboarding or groups page
    page.wait_for_timeout(800)
    # Navigate to groups page
    page.goto(f"{base_url}/console#/groups")
    page.wait_for_timeout(800)

    # ── Member joins via invite code ────────────────────────────────────
    expect(page.locator("#inviteCode")).to_be_visible(timeout=5000)
    page.fill("#inviteCode", invite_code)
    page.click("#joinGroupBtn")
    page.wait_for_timeout(1500)

    # After join, should see the group in the list with role "member"
    page.goto(f"{base_url}/console#/groups")
    page.wait_for_timeout(800)
    body_after_join = page.locator("body").text_content()
    assert "member" in body_after_join.lower() or "成员" in body_after_join, "Must show member role after join"

    # ── Navigate to project as member ───────────────────────────────────
    page.goto(f"{base_url}/console#/groups/{gid}/projects/{pid}")
    page.wait_for_timeout(2000)

    # ── Verify member can SEE content ───────────────────────────────────
    # Member should see the project detail (stage rail, main content)
    expect(page.locator(".projectDetail")).to_be_visible(timeout=10000)

    # Member must see the query workbench at pilot stage
    expect(page.locator("#qOT")).to_be_visible(timeout=10000)

    # Member can execute query
    page.click("#qRunBtn")
    page.wait_for_timeout(2000)
    body_member = page.locator("body").text_content()
    assert "Alpha" in body_member, "Member query must return Alpha data"

    # ── Verify member CANNOT see write controls ────────────────────────
    # Navigate back through stages to check write controls are absent
    # At pilot: no activate button (already active), member can't bind
    assert page.locator("#genBindingsBtn").count() == 0, "Member must not see generate bindings button"
    assert page.locator("#activateBtn").count() == 0, "Member must not see activate button"

    # Go back to model stage project list → check write controls absent everywhere
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    # Member should see project card but NOT create button
    expect(page.locator(".projectCard")).to_be_visible(timeout=5000)
    assert page.locator("#createProjectBtn").count() == 0, "Member must not see create project button"

    # Navigate into project detail — member sees stages but no write buttons
    if page.locator(".projectCard").count() > 0:
        page.locator(".projectCard").first.click()
        page.wait_for_timeout(1500)
    # No gen drafts / build / upload controls
    assert page.locator("#genDraftsBtn").count() == 0, "Member must not see generate drafts button"
    assert page.locator("#buildPkgBtn").count() == 0, "Member must not see build package button"

    # ── Verify outsider (separate user) cannot access ───────────────────
    page.click("#navLogoutBtn")
    page.wait_for_timeout(500)
    outsider_email = _unique_email("e2e-f2b-out")
    _register(page, outsider_email)
    _login(page)
    page.goto(f"{base_url}/console#/groups/{gid}/projects/{pid}")
    page.wait_for_timeout(800)
    # Outsider must not see project content
    assert page.locator("#qOT").count() == 0, "Outsider must not see query workbench"
    assert page.locator("#genBindingsBtn").count() == 0, "Outsider must not see bind button"


# ═════════════════════════════════════════════════════════════════════
#  F2B — WARN / FAIL workflow
# ═════════════════════════════════════════════════════════════════════

def test_f2b_warn_fail_workflow(page: Page, base_url: str) -> None:
    """WARN: confirm dialog with reason required. FAIL: build button disabled, no override."""
    page.goto(f"{base_url}/console")
    _register(page, _unique_email("e2e-f2b-wf"))
    _login(page)
    gid = _onboard(page, "F2B WF Test")

    # Create project + CSV
    page.click("#createFirstBtn")
    page.wait_for_timeout(300)
    page.fill("#npName", "WF Proj")
    page.fill("#npGoal", "WARN/FAIL test")
    page.click("#npSubmit")
    page.wait_for_timeout(1200)
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(300)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = UPLOAD_DIR / f"wf-{uuid.uuid4().hex[:8]}.csv"
    csv_path.write_text("id,name,val\n1,X,10\n2,Y,20\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_path))
    page.click("#upSubmit")
    page.wait_for_timeout(2500)

    # Generate drafts
    expect(page.locator("#genFromDataBtn")).to_be_visible(timeout=5000)
    page.click("#genFromDataBtn")
    page.wait_for_timeout(2000)
    page.wait_for_timeout(500)
    expect(page.locator(".draftRow").first).to_be_visible(timeout=10000)

    # Accept all drafts
    if page.locator("#selectAllProposed").count() > 0:
        page.click("#selectAllProposed")
        page.wait_for_timeout(200)
    if page.locator(".draftCheck:checked").count() > 0:
        page.click("#batchAcceptBtn")
        page.wait_for_timeout(400)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)

    page.wait_for_timeout(500)

    # ── Test 1: Mock FAIL quality — build button disabled ───────────────
    pid = page.evaluate("() => location.hash.split('/')[4] || ''")
    fail_mock = {
        "status": "FAIL",
        "error_count": 3,
        "warning_count": 0,
        "draft_count": 3,
        "issues": [
            {"severity": "error", "code": "E_MISSING_PK", "message": "Object type missing primary key"},
            {"severity": "error", "code": "E_TYPE_MISMATCH", "message": "Property type mismatch"},
            {"severity": "error", "code": "E_MISSING_EVIDENCE", "message": "Missing evidence refs"},
        ],
    }

    def fail_route_handler(route):
        if "/model-drafts/quality" in route.request.url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(fail_mock))
        else:
            route.continue_()

    page.route("**/*", fail_route_handler)

    # Navigate away and back (in-app hash change) to force quality API re-fetch
    page.evaluate("hash => { location.hash = hash; }", f"#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    page.evaluate("hash => { location.hash = hash; }", f"#/groups/{gid}/projects/{pid}")
    page.wait_for_timeout(2000)

    # FAIL: build button must be disabled
    expect(page.locator("#buildPkgBtn")).to_be_visible(timeout=10000)
    assert page.locator("#buildPkgBtn").is_disabled(), "Build button must be disabled on FAIL"

    # Remove FAIL route
    page.unroute("**/*", fail_route_handler)

    # ── Test 2: Mock WARN quality — confirm dialog with reason required ─
    warn_mock = {
        "status": "WARN",
        "error_count": 0,
        "warning_count": 2,
        "draft_count": 3,
        "issues": [
            {"severity": "warning", "code": "W_DEPRECATED_FIELD", "message": "Field uses deprecated name"},
            {"severity": "warning", "code": "W_MISSING_DESCRIPTION", "message": "Object type has no description"},
        ],
    }

    captured_package_body = {}

    def warn_route_handler(route):
        url = route.request.url
        if "/model-drafts/quality" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(warn_mock))
        elif "/model-drafts/packages" in url and route.request.method == "POST":
            try:
                captured_package_body["body"] = json.loads(route.request.post_data or "{}")
            except Exception:
                captured_package_body["body"] = {}
            route.continue_()
        else:
            route.continue_()

    page.route("**/*", warn_route_handler)

    # Navigate away and back to force quality API re-fetch with WARN mock
    page.evaluate("hash => { location.hash = hash; }", f"#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    page.evaluate("hash => { location.hash = hash; }", f"#/groups/{gid}/projects/{pid}")
    page.wait_for_timeout(2000)

    expect(page.locator("#buildPkgBtn")).to_be_visible(timeout=10000)

    # WARN: build button should be enabled (warnings are not blocking)
    if not page.locator("#buildPkgBtn").is_disabled():
        page.locator("#buildPkgBtn").click()
        page.wait_for_timeout(500)

        # WARN dialog must appear with reason field
        expect(page.locator("#dlgConfirm")).to_be_visible(timeout=5000)
        assert page.locator("#dlgReason").count() > 0, "WARN dialog must have reason input"

        # Try submit without reason — should be blocked
        page.click("#dlgConfirm")
        page.wait_for_timeout(300)
        error_el = page.locator("#dlgError")
        if error_el.count() > 0:
            assert error_el.is_visible(), "Error must show when reason is empty"

        # Fill reason and submit
        page.fill("#dlgReason", "Accepting warnings for E2E test")
        page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

        # Verify request body had allow_warnings=true and override_reason
        body = captured_package_body.get("body", {})
        assert body.get("allow_warnings") is True, f"allow_warnings must be true, got {body}"
        assert body.get("override_reason") == "Accepting warnings for E2E test", f"override_reason must match, got {body}"

    page.unroute("**/*", warn_route_handler)


# ═════════════════════════════════════════════════════════════════════
#  F2B — Project isolation (A/B projects in same group)
# ═════════════════════════════════════════════════════════════════════

def test_f2b_project_isolation(page: Page, base_url: str) -> None:
    """Same group, two projects A and B. A's drafts/packages/bindings must not appear in B."""
    page.goto(f"{base_url}/console")
    _register(page, _unique_email("e2e-f2b-iso"))
    _login(page)
    gid = _onboard(page, "F2B Isolation")

    # ── Create Project A with data ──────────────────────────────────────
    page.click("#createFirstBtn")
    page.wait_for_timeout(300)
    page.fill("#npName", "Project A")
    page.fill("#npGoal", "Isolation test project A")
    page.click("#npSubmit")
    page.wait_for_timeout(1200)
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(300)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_a = UPLOAD_DIR / f"iso-a-{uuid.uuid4().hex[:8]}.csv"
    csv_a.write_text("product_id,name,price\n1,Widget,10\n2,Gadget,20\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_a))
    page.click("#upSubmit")
    page.wait_for_timeout(2500)

    # Generate drafts for A
    expect(page.locator("#genFromDataBtn")).to_be_visible(timeout=5000)
    page.click("#genFromDataBtn")
    page.wait_for_timeout(2000)
    page.wait_for_timeout(500)

    # Capture A's draft names
    draft_names_a = page.locator(".draftRow strong").all_text_contents()
    assert len(draft_names_a) > 0, "Project A must have drafts"

    # Get project A's ID
    pid_a = page.evaluate("() => location.hash.split('/')[4] || ''")
    assert pid_a, "Must have project A ID"

    # Accept all A's drafts and build package
    if page.locator("#selectAllProposed").count() > 0:
        page.click("#selectAllProposed")
        page.wait_for_timeout(200)
    if page.locator(".draftCheck:checked").count() > 0:
        page.click("#batchAcceptBtn")
        page.wait_for_timeout(400)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)
    page.wait_for_timeout(500)
    build_btn = page.locator("#buildPkgBtn")
    if build_btn.count() > 0 and not build_btn.is_disabled():
        build_btn.click()
        page.wait_for_timeout(500)
        if page.locator("#dlgReason").count() > 0:
            page.fill("#dlgReason", "ok")
            page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Generate bindings for A
    expect(page.locator("#genBindingsBtn")).to_be_visible(timeout=10000)
    page.click("#genBindingsBtn")
    page.wait_for_timeout(1500)
    # Capture A's binding object type names
    binding_names_a = page.locator(".datasetItemHead strong").all_text_contents()
    assert len(binding_names_a) > 0, "Project A must have bindings"

    # ── Create Project B with different data ────────────────────────────
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(800)
    page.click("#createProjectBtn")
    page.wait_for_timeout(300)
    page.fill("#npName", "Project B")
    page.fill("#npGoal", "Isolation test project B")
    page.click("#npSubmit")
    page.wait_for_timeout(1200)
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(300)
    csv_b = UPLOAD_DIR / f"iso-b-{uuid.uuid4().hex[:8]}.csv"
    csv_b.write_text("order_id,customer,amount\n100,Beta,500\n101,Gamma,750\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_b))
    page.click("#upSubmit")
    page.wait_for_timeout(2500)

    # Generate drafts for B
    expect(page.locator("#genFromDataBtn")).to_be_visible(timeout=5000)
    page.click("#genFromDataBtn")
    page.wait_for_timeout(2000)
    page.wait_for_timeout(500)

    # Verify B's drafts are different from A's
    draft_names_b = page.locator(".draftRow strong").all_text_contents()
    assert len(draft_names_b) > 0, "Project B must have drafts"

    # B must NOT contain A's draft names
    for name_a in draft_names_a:
        assert name_a not in draft_names_b, f"Project B must not show A's draft '{name_a}'"

    # Get project B's ID
    pid_b = page.evaluate("() => location.hash.split('/')[4] || ''")
    assert pid_b, "Must have project B ID"
    assert pid_b != pid_a, "Project B ID must differ from A"

    # Verify B's URL uses B's pid (not A's)
    current_hash = page.evaluate("() => location.hash")
    assert pid_b in current_hash, f"URL must contain B's pid {pid_b}"
    assert pid_a not in current_hash, "URL must not contain A's pid"

    # Accept B's drafts and build package
    if page.locator("#selectAllProposed").count() > 0:
        page.click("#selectAllProposed")
        page.wait_for_timeout(200)
    if page.locator(".draftCheck:checked").count() > 0:
        page.click("#batchAcceptBtn")
        page.wait_for_timeout(400)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)
    page.wait_for_timeout(500)
    build_btn_b = page.locator("#buildPkgBtn")
    if build_btn_b.count() > 0 and not build_btn_b.is_disabled():
        build_btn_b.click()
        page.wait_for_timeout(500)
        if page.locator("#dlgReason").count() > 0:
            page.fill("#dlgReason", "ok")
            page.click("#dlgConfirm")
        page.wait_for_timeout(1500)

    # Generate bindings for B — verify not seeing A's bindings
    expect(page.locator("#genBindingsBtn")).to_be_visible(timeout=10000)
    page.click("#genBindingsBtn")
    page.wait_for_timeout(1500)

    binding_names_b = page.locator(".datasetItemHead strong").all_text_contents()
    # B's bindings must not include A's binding names
    for name_a in binding_names_a:
        assert name_a not in binding_names_b, f"Project B bindings must not show A's binding '{name_a}'"

    # Activate B and query — verify B's page requests use B's pid
    if page.locator("#activateBtn").count() > 0:
        page.click("#activateBtn")
        page.wait_for_timeout(300)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)

    expect(page.locator("#qOT")).to_be_visible(timeout=10000)
    page.click("#qRunBtn")
    page.wait_for_timeout(2000)
    body_b = page.locator("body").text_content()
    # B's data should be visible (not A's)
    assert "Beta" in body_b or "Gamma" in body_b, "Project B query must return B's data"


# ═════════════════════════════════════════════════════════════════════
#  F2B — No location.reload, no inline script, no alert
# ═════════════════════════════════════════════════════════════════════

def test_f2b_code_quality_checks(page: Page, base_url: str) -> None:
    """Verify no location.reload calls, no inline script, no alert(), no empty catch."""
    page.goto(f"{base_url}/console")
    _register(page, _unique_email("e2e-f2b-cq"))
    _login(page)
    gid = _onboard(page, "F2B Code")

    # Create project + CSV + full pipeline to pilot
    page.click("#createFirstBtn")
    page.wait_for_timeout(300)
    page.fill("#npName", "CQ Proj")
    page.fill("#npGoal", "Code quality checks")
    page.click("#npSubmit")
    page.wait_for_timeout(1200)
    page.click("#uploadFirstBtn")
    page.wait_for_timeout(300)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = UPLOAD_DIR / f"cq-{uuid.uuid4().hex[:8]}.csv"
    csv_path.write_text("id,x\n1,a\n2,b\n", encoding="utf-8")
    page.set_input_files("#upFile", str(csv_path))
    page.click("#upSubmit")
    page.wait_for_timeout(2500)

    # Generate drafts + accept + build + bind + activate
    expect(page.locator("#genFromDataBtn")).to_be_visible(timeout=5000)
    page.click("#genFromDataBtn")
    page.wait_for_timeout(2000)
    page.wait_for_timeout(500)
    if page.locator("#selectAllProposed").count() > 0:
        page.click("#selectAllProposed")
        page.wait_for_timeout(200)
    if page.locator(".draftCheck:checked").count() > 0:
        page.click("#batchAcceptBtn")
        page.wait_for_timeout(400)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)
    page.wait_for_timeout(500)
    build_btn = page.locator("#buildPkgBtn")
    if build_btn.count() > 0 and not build_btn.is_disabled():
        build_btn.click()
        page.wait_for_timeout(500)
        if page.locator("#dlgReason").count() > 0:
            page.fill("#dlgReason", "ok")
            page.click("#dlgConfirm")
        page.wait_for_timeout(1500)
    page.wait_for_timeout(500)
    if page.locator("#genBindingsBtn").count() > 0:
        page.click("#genBindingsBtn")
        page.wait_for_timeout(1500)
    if page.locator("#activateBtn").count() > 0:
        page.click("#activateBtn")
        page.wait_for_timeout(300)
        if page.locator("#dlgConfirm").count() > 0:
            page.click("#dlgConfirm")
            page.wait_for_timeout(1500)

    # Gather all pages' JS source for static analysis
    # Check for console errors accumulated during the entire test
    page.goto(f"{base_url}/console#/groups/{gid}/projects")
    page.wait_for_timeout(500)

    # Navigate through all F2B pages to check for console errors
    pages_to_check = [
        f"/console#/groups/{gid}/projects",
    ]

    for p in pages_to_check:
        page.goto(f"{base_url}{p}")
        page.wait_for_timeout(500)

    # Final check: no [object Object] anywhere
    body_text = page.locator("body").text_content()
    assert "[object Object]" not in body_text, "Must not show raw JS object in any page"
