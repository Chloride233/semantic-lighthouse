"""E2E browser tests — R1 frontend redesign flow.

Requires: pytest-playwright (provides `page` and `base_url` fixtures).
If the local machine blocks browser spawn (EPERM), mark tests as skipped.
"""

from pathlib import Path

from playwright.sync_api import Page, expect


def _register(page: Page, email: str = "e2e@test.com") -> None:
    """Register through tabbed auth — switches to Register tab, fills, submits."""
    page.click(".authTab[data-tab='register']")
    page.wait_for_timeout(300)
    page.fill("#registerEmail", email)
    page.fill("#registerName", "E2E User")
    page.fill("#registerPassword", "Passw0rd!")
    page.click("#registerForm button[type=submit]")
    page.wait_for_timeout(1500)


def _login(page: Page) -> None:
    """Sign in through tabbed auth (must be on Sign In tab)."""
    page.fill("#loginPassword", "Passw0rd!")
    page.click("#signinForm button[type=submit]")
    page.wait_for_timeout(1500)


def _onboard(page: Page, name: str = "E2E Workspace") -> str:
    """Create workspace via onboarding. Returns the group_id from URL."""
    expect(page.locator("#onboardName")).to_be_visible(timeout=10000)
    page.fill("#onboardName", name)
    page.click("#onboardCreateBtn")
    page.wait_for_timeout(1500)
    # After creation → Knowledge page
    expect(page.locator("#docFileInput")).to_be_visible(timeout=10000)
    current_hash = page.evaluate("() => location.hash")
    return current_hash.split("/")[2]  # /groups/:gid/documents → gid


# ── Chain 1: Tabbed Auth → Onboarding → Workspace ───────────────────────


def test_tabbed_auth_and_onboarding(page: Page, base_url: str) -> None:
    """R1 flow: tabbed Register → auto-switch → Sign In → 0 groups → Onboarding."""
    page.goto(f"{base_url}/console")

    # Brand renders
    expect(page.locator(".authBrandIcon")).to_be_visible(timeout=5000)
    expect(page.locator(".authTitle")).to_contain_text("Semantic Lighthouse")

    # Register
    _register(page, "e2e-onboard@test.com")
    expect(page.locator(".authSuccess")).to_be_visible()

    # Sign in
    _login(page)

    # 0 groups → onboarding
    expect(page.locator(".onboardTitle")).to_contain_text("Welcome", timeout=10000)

    # Create workspace → Knowledge
    _onboard(page, "E2E Workspace")
    expect(page.locator(".pageTitle")).to_contain_text("Documents")

    # Navbar shows R1 labels
    for label in ("Ask", "Knowledge", "Conversations", "Workspace"):
        expect(page.locator(f".navLinks a:has-text('{label}')")).to_be_visible()

    # Old developer labels are gone
    assert page.locator(".navLinks a:has-text('RAG')").count() == 0
    assert page.locator(".navLinks a:has-text('Jobs')").count() == 0


# ── Chain 2: Ask as home ────────────────────────────────────────────────


def test_ask_is_home_and_empty_kb_shows_guidance(page: Page, base_url: str) -> None:
    """After onboarding, Ask page is home. Empty KB shows upload guidance."""
    page.goto(f"{base_url}/console")

    _register(page, "e2e-askhome@test.com")
    expect(page.locator(".authSuccess")).to_be_visible()
    _login(page)
    _onboard(page, "Ask Home WS")

    # Navigate to Ask
    page.click(".navLinks a:has-text('Ask')")
    page.wait_for_timeout(800)
    expect(page.locator(".askPage")).to_be_visible(timeout=5000)

    # Empty KB → guidance
    expect(page.locator(".emptyState")).to_be_visible()
    expect(page.locator(".emptyTitle")).to_contain_text("No documents")

    # Logout then re-login → Ask (home, not onboarding)
    page.click("#navLogoutBtn")
    page.wait_for_timeout(600)
    page.fill("#loginEmail", "e2e-askhome@test.com")
    _login(page)
    expect(page.locator(".askPage")).to_be_visible(timeout=10000)
    # No onboarding this time
    assert page.locator("#onboardName").count() == 0


# ── Chain 3: Upload → Ask → RAG Answer ─────────────────────────────────


def test_upload_then_ask_with_answer_card(page: Page, base_url: str, tmp_path: Path) -> None:
    """Upload a doc → Ask a question → see confidence bar + answer + citations."""
    page.goto(f"{base_url}/console")

    _register(page, "e2e-rag@test.com")
    expect(page.locator(".authSuccess")).to_be_visible()
    _login(page)
    _onboard(page, "RAG Workspace")

    # On Knowledge page — upload a doc
    md_file = tmp_path / "ontology.md"
    md_file.write_text("""---
title: Enterprise Ontology
entityType: Concept
---

# Ontology

Ontology connects business objects, data, and AI workflows for enterprise context.
""")
    page.set_input_files("#docFileInput", str(md_file))
    page.click("#uploadDocBtn")
    expect(page.locator("#uploadMsg")).to_contain_text("Uploaded!", timeout=8000)

    # Navigate to Ask
    page.click(".navLinks a:has-text('Ask')")
    page.wait_for_timeout(800)
    expect(page.locator("#askQuestion")).to_be_visible(timeout=5000)

    # Ask a question
    page.fill("#askQuestion", "What is ontology?")
    page.click("#askSubmitBtn")

    # Answer card renders
    expect(page.locator(".answerCard")).to_be_visible(timeout=15000)
    expect(page.locator(".confidenceBar")).to_be_visible()
    expect(page.locator(".answerCard-text")).not_to_be_empty()


# ── Chain 4: Old routes preserved ──────────────────────────────────────


def test_old_routes_still_functional(page: Page, base_url: str) -> None:
    """RAG, Jobs, Documents, Groups, Conversations routes still work."""
    page.goto(f"{base_url}/console")

    _register(page, "e2e-oldroutes@test.com")
    expect(page.locator(".authSuccess")).to_be_visible()
    _login(page)
    gid = _onboard(page, "Old Routes WS")

    # Old RAG route (now superseded by #/ask but still functional)
    page.goto(f"{base_url}/console#/groups/{gid}/rag")
    page.wait_for_timeout(1000)
    expect(page.locator("#ragQuestion")).to_be_visible(timeout=5000)

    # Old Jobs route
    page.goto(f"{base_url}/console#/groups/{gid}/jobs")
    page.wait_for_timeout(1500)
    # May show error on empty doc search, but page chrome exists
    assert page.locator(".pageTitle").count() > 0 or page.locator(".error").count() > 0

    # Old Documents route
    page.goto(f"{base_url}/console#/groups/{gid}/documents")
    page.wait_for_timeout(1000)
    expect(page.locator("#docFileInput")).to_be_visible(timeout=5000)

    # Groups page (Workspace)
    page.goto(f"{base_url}/console#/groups")
    page.wait_for_timeout(800)
    expect(page.locator("#groupName")).to_be_visible(timeout=5000)

    # Conversations page
    page.goto(f"{base_url}/console#/groups/{gid}/conversations")
    page.wait_for_timeout(1000)
    expect(page.locator("#convTitle")).to_be_visible(timeout=5000)
