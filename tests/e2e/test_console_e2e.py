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
    expect(page.locator("#docFileInput")).to_be_visible(timeout=10000)
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
    expect(page.locator(".panelHeader h2").filter(has_text="导入知识")).to_be_visible()
    expect(page.locator(".panelHeader h2").filter(has_text="文档列表")).to_be_visible()

    for label in ("问答", "知识库", "对话", "工作区"):
        expect(page.locator(f".navLinks a:has-text('{label}')")).to_be_visible()

    assert page.locator(".navLinks a:has-text('RAG')").count() == 0
    assert page.locator(".navLinks a:has-text('Jobs')").count() == 0


def test_ask_home_empty_kb_and_relogin(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/console")

    email = _unique_email("e2e-ask")
    _register(page, email)
    _login(page)
    _onboard(page, "问答工作区")

    page.click(".navLinks a:has-text('问答')")
    expect(page.locator(".askPage")).to_be_visible(timeout=5000)
    expect(page.locator(".emptyState")).to_be_visible()
    expect(page.locator(".emptyTitle")).to_contain_text("知识库还没有文档")

    page.click("#navLogoutBtn")
    expect(page.locator("#loginEmail")).to_be_visible(timeout=5000)
    _login(page, email)

    expect(page.locator(".askPage")).to_be_visible(timeout=10000)
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

    page.set_input_files("#docFileInput", str(md_file))
    page.click("#uploadDocBtn")
    expect(page.locator("body")).to_contain_text(md_file.name, timeout=10000)

    page.click(".navLinks a:has-text('问答')")
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
