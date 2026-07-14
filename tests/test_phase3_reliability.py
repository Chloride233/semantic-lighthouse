from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.models import RagRun
from semantic_lighthouse.services.chat import ChatAnswer, ChatError, DeepSeekChatClient
from semantic_lighthouse.services.reliability import (
    AdmissionRejected,
    RagAdmissionController,
    post_with_retry,
)


def _response(status_code: int) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://provider.example/v1/chat"),
        json={"error": {"message": "provider failure"}},
    )


def _run_async(coroutine):
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


def test_provider_retries_transient_503(monkeypatch):
    responses = iter([_response(503), _response(200)])
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return next(responses)

    monkeypatch.setattr(httpx, "post", fake_post)

    response = post_with_retry(
        "https://provider.example/v1/chat",
        json={},
        headers={},
        timeout=1,
        max_attempts=2,
        backoff_seconds=0,
    )

    assert response.status_code == 200
    assert calls == 2


def test_provider_does_not_retry_non_transient_400(monkeypatch):
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(400)

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(httpx.HTTPStatusError):
        post_with_retry(
            "https://provider.example/v1/chat",
            json={},
            headers={},
            timeout=1,
            max_attempts=3,
            backoff_seconds=0,
        )

    assert calls == 1


def test_provider_retries_timeout_then_raises(monkeypatch):
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow provider")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(httpx.ReadTimeout):
        post_with_retry(
            "https://provider.example/v1/chat",
            json={},
            headers={},
            timeout=1,
            max_attempts=2,
            backoff_seconds=0,
        )

    assert calls == 2


def test_chat_timeout_is_classified_after_retries(monkeypatch):
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow provider")

    monkeypatch.setattr(httpx, "post", fake_post)
    settings = Settings(
        deepseek_api_key="sk-test",
        provider_max_attempts=2,
        provider_retry_backoff_seconds=0,
    )

    with pytest.raises(ChatError) as exc_info:
        DeepSeekChatClient(settings).answer_question("Ontology?", [])

    assert exc_info.value.kind == "timeout"
    assert calls == 2


def test_chat_quota_exhaustion_is_classified(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _response(429))
    settings = Settings(
        deepseek_api_key="sk-test",
        provider_max_attempts=1,
        provider_retry_backoff_seconds=0,
    )

    with pytest.raises(ChatError) as exc_info:
        DeepSeekChatClient(settings).answer_question("Ontology?", [])

    assert exc_info.value.kind == "quota"


def test_rate_limit_rejects_second_request_in_window():
    async def scenario():
        controller = RagAdmissionController(
            max_concurrency=1,
            max_queue=1,
            queue_timeout_seconds=0.1,
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        )
        lease = await controller.acquire("group:user")
        lease.release()
        with pytest.raises(AdmissionRejected) as exc_info:
            await controller.acquire("group:user")
        assert exc_info.value.status_code == 429

    _run_async(scenario())


def test_full_queue_rejects_with_backpressure():
    async def scenario():
        controller = RagAdmissionController(
            max_concurrency=1,
            max_queue=1,
            queue_timeout_seconds=1,
            rate_limit_requests=10,
            rate_limit_window_seconds=60,
        )
        active = await controller.acquire("active")
        queued_task = asyncio.create_task(controller.acquire("queued"))
        await asyncio.sleep(0)

        with pytest.raises(AdmissionRejected) as exc_info:
            await controller.acquire("overflow")
        assert exc_info.value.status_code == 503
        assert "queue is full" in str(exc_info.value).lower()

        active.release()
        queued = await queued_task
        queued.release()

    _run_async(scenario())


def test_queue_wait_timeout_returns_503():
    async def scenario():
        controller = RagAdmissionController(
            max_concurrency=1,
            max_queue=1,
            queue_timeout_seconds=0.01,
            rate_limit_requests=10,
            rate_limit_window_seconds=60,
        )
        active = await controller.acquire("active")
        with pytest.raises(AdmissionRejected) as exc_info:
            await controller.acquire("queued")
        assert exc_info.value.status_code == 503
        assert "queue wait timed out" in str(exc_info.value).lower()
        active.release()

    _run_async(scenario())


def test_cancelled_waiter_does_not_leak_queue_capacity():
    async def scenario():
        controller = RagAdmissionController(
            max_concurrency=1,
            max_queue=1,
            queue_timeout_seconds=1,
            rate_limit_requests=10,
            rate_limit_window_seconds=60,
        )
        active = await controller.acquire("active")
        cancelled_task = asyncio.create_task(controller.acquire("cancelled"))
        await asyncio.sleep(0)
        cancelled_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_task

        replacement_task = asyncio.create_task(controller.acquire("replacement"))
        await asyncio.sleep(0)
        active.release()
        replacement = await replacement_task
        replacement.release()

    _run_async(scenario())


def test_rag_api_rate_limit_returns_429(client: TestClient, tmp_path):
    _, _, headers = register_and_login(client, "phase3-rate-limit@example.com")
    group_response = client.post("/groups", json={"name": "Rate Limit"}, headers=headers)
    assert group_response.status_code == 201
    group_id = group_response.json()["id"]
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        knowledge_base_path=str(tmp_path),
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=8,
        chat_provider="fake",
        chat_model="fake-chat",
        rag_rate_limit_requests=1,
        rag_rate_limit_window_seconds=60,
    )
    client.app.dependency_overrides[get_settings] = lambda: settings

    first = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=headers,
    )
    second = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "1"


def _rag_settings(tmp_path, **overrides) -> Settings:
    values = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "jwt_secret_key": "test-secret-key-at-least-32-bytes",
        "knowledge_base_path": str(tmp_path),
        "embedding_provider": "fake",
        "embedding_model": "fake-embedding",
        "embedding_dimension": 8,
        "chat_provider": "fake",
        "chat_model": "fake-chat",
        "rag_rate_limit_requests": 100,
    }
    values.update(overrides)
    return Settings(**values)


def _rag_group_with_document(client: TestClient, tmp_path, email: str):
    _, _, headers = register_and_login(client, email)
    group = client.post("/groups", json={"name": "Reliability"}, headers=headers)
    assert group.status_code == 201
    group_id = group.json()["id"]
    client.app.dependency_overrides[get_settings] = lambda: _rag_settings(tmp_path)
    upload = client.post(
        f"/groups/{group_id}/documents/upload",
        files={
            "file": (
                "ontology.md",
                b"# Ontology\n\nOntology connects business objects and AI workflows.",
                "text/markdown",
            )
        },
        headers=headers,
    )
    assert upload.status_code == 201
    return group_id, headers


class CountingChatClient:
    def __init__(self, error: ChatError | None = None) -> None:
        self.calls = 0
        self.error = error

    def answer_question(self, question, citations, history=None):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ChatAnswer(
            answer="Ontology connects business objects and AI workflows.",
            confidence="high",
            knowledge_gaps=[],
            next_steps=[],
            model="counting-chat",
        )


def test_completed_idempotency_key_replays_without_provider_call(client, tmp_path):
    group_id, headers = _rag_group_with_document(
        client, tmp_path, "phase3-idempotent@example.com"
    )
    chat_client = CountingChatClient()

    with mock.patch(
        "semantic_lighthouse.routers.rag.create_chat_client",
        return_value=chat_client,
    ):
        first = client.post(
            f"/groups/{group_id}/rag/answer",
            json={"question": "Ontology", "retrieval_method": "keyword"},
            headers={**headers, "Idempotency-Key": "same-answer"},
        )
        second = client.post(
            f"/groups/{group_id}/rag/answer",
            json={"question": "Ontology", "retrieval_method": "keyword"},
            headers={**headers, "Idempotency-Key": "same-answer"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert chat_client.calls == 1


def test_idempotency_key_rejects_different_request(client, tmp_path):
    group_id, headers = _rag_group_with_document(
        client, tmp_path, "phase3-idempotency-conflict@example.com"
    )
    first = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers={**headers, "Idempotency-Key": "conflicting-answer"},
    )
    second = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Different question", "retrieval_method": "keyword"},
        headers={**headers, "Idempotency-Key": "conflicting-answer"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "different request" in second.json()["detail"].lower()


def test_pending_idempotency_key_returns_409(client, db_session, tmp_path):
    group_id, headers = _rag_group_with_document(
        client, tmp_path, "phase3-idempotency-pending@example.com"
    )
    first = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers={**headers, "Idempotency-Key": "pending-answer"},
    )
    assert first.status_code == 200
    run = db_session.get(RagRun, first.json()["run_id"])
    run.status = "pending"
    db_session.commit()

    second = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers={**headers, "Idempotency-Key": "pending-answer"},
    )

    assert second.status_code == 409
    assert "in progress" in second.json()["detail"].lower()


def test_failed_idempotency_key_replays_provider_error(client, tmp_path):
    group_id, headers = _rag_group_with_document(
        client, tmp_path, "phase3-idempotency-error@example.com"
    )
    chat_client = CountingChatClient(
        ChatError("Chat provider quota exhausted", kind="quota", retry_after_seconds=7)
    )

    with mock.patch(
        "semantic_lighthouse.routers.rag.create_chat_client",
        return_value=chat_client,
    ):
        first = client.post(
            f"/groups/{group_id}/rag/answer",
            json={"question": "Ontology", "retrieval_method": "keyword"},
            headers={**headers, "Idempotency-Key": "failed-answer"},
        )
        second = client.post(
            f"/groups/{group_id}/rag/answer",
            json={"question": "Ontology", "retrieval_method": "keyword"},
            headers={**headers, "Idempotency-Key": "failed-answer"},
        )

    assert first.status_code == 503
    assert second.status_code == 503
    assert second.json() == first.json()
    assert second.headers["Retry-After"] == "7"
    assert chat_client.calls == 1


def test_idempotency_key_length_is_bounded(client, tmp_path):
    group_id, headers = _rag_group_with_document(
        client, tmp_path, "phase3-idempotency-length@example.com"
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers={**headers, "Idempotency-Key": "x" * 129},
    )

    assert response.status_code == 400


def test_database_failure_returns_bounded_503_with_request_id(client, tmp_path):
    group_id, headers = _rag_group_with_document(
        client, tmp_path, "phase3-database-error@example.com"
    )
    request_id = "phase3-db-trace"
    failure = OperationalError(
        "SELECT secret FROM private_table",
        {},
        Exception("password=do-not-expose"),
    )

    with mock.patch(
        "semantic_lighthouse.routers.rag._answer_question_in_scope",
        side_effect=failure,
    ):
        response = client.post(
            f"/groups/{group_id}/rag/answer",
            json={"question": "Ontology", "retrieval_method": "keyword"},
            headers={**headers, "X-Request-ID": request_id},
        )

    assert response.status_code == 503
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["Retry-After"] == "1"
    body = response.json()
    assert body == {
        "detail": "Database temporarily unavailable",
        "request_id": request_id,
    }
    assert "secret" not in response.text
    assert "password" not in response.text


@pytest.mark.parametrize(
    ("kind", "expected_status", "retry_after"),
    [
        ("unavailable", 503, "1"),
        ("quota", 503, "9"),
        ("timeout", 504, None),
    ],
)
def test_provider_faults_degrade_with_audited_api_errors(
    client,
    db_session,
    tmp_path,
    kind,
    expected_status,
    retry_after,
):
    group_id, headers = _rag_group_with_document(
        client, tmp_path, f"phase3-provider-{kind}@example.com"
    )
    request_id = f"phase3-{kind}-trace"
    chat_client = CountingChatClient(
        ChatError(
            f"Chat provider {kind}",
            kind=kind,
            retry_after_seconds=9 if kind == "quota" else None,
        )
    )

    with mock.patch(
        "semantic_lighthouse.routers.rag.create_chat_client",
        return_value=chat_client,
    ):
        response = client.post(
            f"/groups/{group_id}/rag/answer",
            json={"question": "Ontology", "retrieval_method": "keyword"},
            headers={**headers, "X-Request-ID": request_id},
        )

    assert response.status_code == expected_status
    assert response.headers["X-Request-ID"] == request_id
    if retry_after is None:
        assert "Retry-After" not in response.headers
    else:
        assert response.headers["Retry-After"] == retry_after
    run = db_session.query(RagRun).filter(RagRun.group_id == group_id).one()
    assert run.status == "error"
    assert run.error_kind == kind
    assert run.error_message == f"Chat provider {kind}"
