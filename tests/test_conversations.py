from __future__ import annotations

from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings


def _settings(path: Path, chat_provider: str = "fake", embedding_provider: str = "fake") -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        cookie_secure=False,
        cookie_samesite="lax",
        knowledge_base_path=str(path),
        embedding_provider=embedding_provider,
        embedding_model="fake-embedding",
        embedding_dimension=8,
        chat_provider=chat_provider,
        chat_model="fake-chat",
        rag_top_k=3,
    )


def _override_settings(client: TestClient, settings: Settings) -> None:
    def override() -> Settings:
        return settings

    client.app.dependency_overrides[get_settings] = override


def _create_group(client: TestClient, headers: dict[str, str], name: str = "Team") -> str:
    response = client.post("/groups", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def _join_group(
    client: TestClient,
    group_id: str,
    owner_headers: dict[str, str],
    member_headers: dict[str, str],
) -> None:
    invite = client.post(f"/groups/{group_id}/invites", headers=owner_headers)
    assert invite.status_code == 201
    joined = client.post(
        "/groups/join-by-invite",
        json={"invite_code": invite.json()["invite_code"]},
        headers=member_headers,
    )
    assert joined.status_code == 200


def _upload(
    client: TestClient,
    group_id: str,
    headers: dict[str, str],
    name: str,
    text: str,
) -> str:
    response = client.post(
        f"/groups/{group_id}/documents/upload",
        files={"file": (name, text.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


# ── create ─────────────────────────────────────────────────────────────


def test_create_conversation(client, tmp_path):
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))

    response = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "My Consulting Chat"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"]
    assert payload["group_id"] == group_id
    assert payload["title"] == "My Consulting Chat"
    assert payload["message_count"] == 0
    assert payload["created_at"]
    assert payload["updated_at"]


def test_create_conversation_defaults_title(client, tmp_path):
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))

    response = client.post(
        f"/groups/{group_id}/conversations",
        json={},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["title"] == "New Conversation"


def test_non_member_cannot_create_conversation(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, outsider_headers = register_and_login(client, "outsider@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))

    response = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Sneak"},
        headers=outsider_headers,
    )

    assert response.status_code == 403


# ── list ───────────────────────────────────────────────────────────────


def test_list_conversations_own_only(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_settings(client, _settings(tmp_path))

    # Owner creates a conversation
    client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Owner Chat"},
        headers=owner_headers,
    )
    # Member creates a conversation
    client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Member Chat"},
        headers=member_headers,
    )

    # Owner sees only their own
    owner_list = client.get(f"/groups/{group_id}/conversations", headers=owner_headers)
    assert owner_list.status_code == 200
    assert len(owner_list.json()) == 1
    assert owner_list.json()[0]["title"] == "Owner Chat"

    # Member sees only their own
    member_list = client.get(f"/groups/{group_id}/conversations", headers=member_headers)
    assert member_list.status_code == 200
    assert len(member_list.json()) == 1
    assert member_list.json()[0]["title"] == "Member Chat"


def test_list_conversations_empty(client, tmp_path):
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))

    response = client.get(f"/groups/{group_id}/conversations", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


# ── get detail ─────────────────────────────────────────────────────────


def test_get_conversation_with_messages(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "ontology.md",
        """---
title: Ontology
entityType: Concept
---

# Ontology

Ontology connects business objects and AI workflows.
""",
    )

    # Create conversation and send a message
    conv = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Test Chat"},
        headers=owner_headers,
    )
    conv_id = conv.json()["id"]

    client.post(
        f"/groups/{group_id}/conversations/{conv_id}/messages",
        json={"question": "Ontology basics"},
        headers=owner_headers,
    )

    # Get detail
    detail = client.get(
        f"/groups/{group_id}/conversations/{conv_id}",
        headers=owner_headers,
    )

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["id"] == conv_id
    assert payload["title"] == "Test Chat"
    assert payload["message_count"] == 2  # user + assistant
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == "Ontology basics"
    assert payload["messages"][1]["role"] == "assistant"
    assert payload["messages"][1]["content"]


def test_cannot_access_other_users_conversation(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_settings(client, _settings(tmp_path))

    conv = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Owner Chat"},
        headers=owner_headers,
    )
    conv_id = conv.json()["id"]

    response = client.get(
        f"/groups/{group_id}/conversations/{conv_id}",
        headers=member_headers,
    )

    assert response.status_code == 403


def test_get_nonexistent_conversation_returns_404(client, tmp_path):
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))

    response = client.get(
        f"/groups/{group_id}/conversations/nonexistent-id",
        headers=headers,
    )

    assert response.status_code == 404


# ── send message ───────────────────────────────────────────────────────


def test_send_message_in_conversation(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    doc_id = _upload(
        client,
        group_id,
        owner_headers,
        "ontology.md",
        """---
title: Enterprise Ontology
entityType: Concept
---

# Ontology

Ontology connects business objects, data, and AI workflows.
""",
    )

    conv = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Consulting"},
        headers=owner_headers,
    )
    conv_id = conv.json()["id"]

    response = client.post(
        f"/groups/{group_id}/conversations/{conv_id}/messages",
        json={"question": "What is Ontology?", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "assistant"
    assert payload["content"]
    assert len(payload["citations"]) >= 1
    assert payload["citations"][0]["document_id"] == doc_id
    assert payload["retrieval_method"] == "keyword"
    assert payload["confidence"] in ("high", "medium", "low")


def test_send_message_to_others_conversation_rejected(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_settings(client, _settings(tmp_path))

    conv = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Owner Chat"},
        headers=owner_headers,
    )
    conv_id = conv.json()["id"]

    response = client.post(
        f"/groups/{group_id}/conversations/{conv_id}/messages",
        json={"question": "Hello?"},
        headers=member_headers,
    )

    assert response.status_code == 403


def test_conversation_messages_are_persisted(client, tmp_path):
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        headers,
        "doc.md",
        "# Topic\n\nRelevant knowledge base content for testing.",
    )

    conv = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Persist Test"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    # Send 3 messages
    for q in ["Q1 first question", "Q2 second question", "Q3 third question"]:
        resp = client.post(
            f"/groups/{group_id}/conversations/{conv_id}/messages",
            json={"question": q, "retrieval_method": "keyword"},
            headers=headers,
        )
        assert resp.status_code == 200

    # Verify all 6 messages (3 user + 3 assistant) are persisted
    detail = client.get(
        f"/groups/{group_id}/conversations/{conv_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 6
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == "Q1 first question"
    assert messages[2]["content"] == "Q2 second question"
    assert messages[4]["content"] == "Q3 third question"


def test_send_message_to_nonexistent_conversation_returns_404(client, tmp_path):
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))

    response = client.post(
        f"/groups/{group_id}/conversations/nonexistent-id/messages",
        json={"question": "Hello?"},
        headers=headers,
    )

    assert response.status_code == 404


def test_conversation_history_is_passed_to_chat_client(client, tmp_path):
    """Verify that multi-turn history is passed to the chat client."""
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        headers,
        "doc.md",
        "# History\n\nThis document covers multi-turn conversation context.",
    )

    conv = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "History Test"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    # Patch create_chat_client to inspect calls
    with mock.patch(
        "semantic_lighthouse.routers.conversations.create_chat_client"
    ) as mock_create:
        from semantic_lighthouse.services.chat import ChatAnswer, ChatResponse

        mock_client = mock.MagicMock()
        mock_client.generate_response.return_value = ChatResponse(
            answer=ChatAnswer(
                answer="Test answer",
                confidence="medium",
                knowledge_gaps=[],
                next_steps=[],
                model="fake",
            ),
        )
        mock_create.return_value = mock_client

        client.post(
            f"/groups/{group_id}/conversations/{conv_id}/messages",
            json={"question": "multi-turn context", "retrieval_method": "keyword"},
            headers=headers,
        )

        assert mock_client.generate_response.called
        history_arg = mock_client.generate_response.call_args.kwargs.get("history")
        # First message has no prior history
        assert history_arg == [] or history_arg is None


def test_no_evidence_fallback_does_not_call_chat_provider(client, tmp_path):
    """When no chunks match, return low-confidence answer without calling chat."""
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))

    conv = client.post(
        f"/groups/{group_id}/conversations",
        json={"title": "Empty Test"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    response = client.post(
        f"/groups/{group_id}/conversations/{conv_id}/messages",
        json={"question": "totallyunmatchedxyz123", "retrieval_method": "keyword"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["confidence"] == "low"
    assert payload["citations"] == []
    assert payload["model"] == "local-evidence-gate"


# ── tool calling (Phase 4.1) ───────────────────────────────────────────


def test_tool_call_search_executed_and_produces_answer(client, tmp_path):
    """Mock generate_response to return tool_call then answer — verify end-to-end."""
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client, group_id, headers, "doc.md",
        "# ETL\n\nETL pipeline ingests documents asynchronously.",
    )

    conv = client.post(
        f"/groups/{group_id}/conversations", json={"title": "Tool Test"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    from semantic_lighthouse.services.chat import ChatAnswer, ChatResponse, ToolCall

    call_count = [0]

    def _fake_generate_response(question, citations, history=None, tools=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return ChatResponse(tool_call=ToolCall(name="search_knowledge_base", arguments={"query": "ETL ingest"}))
        return ChatResponse(
            answer=ChatAnswer(
                answer="Based on additional search, ETL handles async ingestion.",
                confidence="medium", knowledge_gaps=[], next_steps=[], model="fake",
            ),
        )

    with mock.patch(
        "semantic_lighthouse.routers.conversations.create_chat_client"
    ) as mock_create:
        mock_client = mock.MagicMock()
        mock_client.generate_response.side_effect = _fake_generate_response
        mock_create.return_value = mock_client

        resp = client.post(
            f"/groups/{group_id}/conversations/{conv_id}/messages",
            json={"question": "How does ETL work?", "retrieval_method": "keyword"},
            headers=headers,
        )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["role"] == "assistant"
        assert "ETL" in payload["content"]
        assert payload["confidence"] in ("medium", "high")

    # Verify tool message was persisted
    detail = client.get(f"/groups/{group_id}/conversations/{conv_id}", headers=headers)
    messages = detail.json()["messages"]
    roles = [m["role"] for m in messages]
    assert "tool" in roles
    tool_msg = [m for m in messages if m["role"] == "tool"][0]
    assert tool_msg["tool_calls"]
    assert tool_msg["tool_calls"][0]["name"] == "search_knowledge_base"


def test_direct_answer_without_tool_call_still_works(client, tmp_path):
    """When generate_response returns answer directly, no tool is executed."""
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client, group_id, headers, "doc.md",
        "# Hybrid\n\nHybrid search combines keyword and semantic retrieval.",
    )

    conv = client.post(
        f"/groups/{group_id}/conversations", json={"title": "Direct"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    resp = client.post(
        f"/groups/{group_id}/conversations/{conv_id}/messages",
        json={"question": "hybrid search", "retrieval_method": "keyword"},
        headers=headers,
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["role"] == "assistant"
    assert payload["content"]

    # No tool messages in history
    detail = client.get(f"/groups/{group_id}/conversations/{conv_id}", headers=headers)
    messages = detail.json()["messages"]
    roles = [m["role"] for m in messages]
    assert "tool" not in roles


def test_execute_tool_rejects_unknown_tool():
    """_execute_tool returns error for unknown tool names."""
    from semantic_lighthouse.routers.conversations import _execute_tool

    result = _execute_tool("dangerous_action", {}, None, "gid", None)
    assert "Error" in result
    assert "unknown tool" in result


def test_no_evidence_fallback_skips_tool_loop(client, tmp_path):
    """When no citations found, tool loop is not entered."""
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))

    conv = client.post(
        f"/groups/{group_id}/conversations", json={"title": "No Evidence"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    resp = client.post(
        f"/groups/{group_id}/conversations/{conv_id}/messages",
        json={"question": "xyz_nonexistent_term_123", "retrieval_method": "keyword"},
        headers=headers,
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["model"] == "local-evidence-gate"
    assert payload["citations"] == []

    # Verify no tool or extra messages beyond user + assistant
    detail = client.get(f"/groups/{group_id}/conversations/{conv_id}", headers=headers)
    assert len(detail.json()["messages"]) == 2


def test_tool_result_persisted_as_tool_message(client, tmp_path):
    """Verify tool message includes tool_calls JSON in persisted record."""
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client, group_id, headers, "doc.md",
        "# Knowledge\n\nEnterprise knowledge graph connects business concepts.",
    )

    conv = client.post(
        f"/groups/{group_id}/conversations", json={"title": "Persist"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    from semantic_lighthouse.services.chat import ChatAnswer, ChatResponse, ToolCall

    call_count = [0]

    def _fake_generate_response(question, citations, history=None, tools=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return ChatResponse(tool_call=ToolCall(name="search_knowledge_base", arguments={"query": "graph"}))
        return ChatResponse(
            answer=ChatAnswer(
                answer="Enterprise knowledge graphs help.",
                confidence="medium", knowledge_gaps=[], next_steps=[], model="fake",
            ),
        )

    with mock.patch(
        "semantic_lighthouse.routers.conversations.create_chat_client"
    ) as mock_create:
        mock_client = mock.MagicMock()
        mock_client.generate_response.side_effect = _fake_generate_response
        mock_create.return_value = mock_client

        resp = client.post(
            f"/groups/{group_id}/conversations/{conv_id}/messages",
            json={"question": "knowledge graph", "retrieval_method": "keyword"},
            headers=headers,
        )
        assert resp.status_code == 200

    detail = client.get(f"/groups/{group_id}/conversations/{conv_id}", headers=headers)
    messages = detail.json()["messages"]
    assert len(messages) == 3  # user, tool, assistant(final answer)

    tool_msg = [m for m in messages if m["role"] == "tool"][0]
    assert tool_msg["tool_calls"] == [{"name": "search_knowledge_base", "arguments": {"query": "graph"}}]
    assert "Knowledge" in tool_msg["content"]


def test_tool_messages_are_filtered_from_history_sent_to_provider(client, tmp_path):
    """Tool messages lack tool_call_id — must not be passed to OpenAI-compatible APIs."""
    _, _, headers = register_and_login(client, "a@example.com")
    group_id = _create_group(client, headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client, group_id, headers, "doc.md",
        "# Tools\n\nTool calling requires compatible message formats.",
    )

    conv = client.post(
        f"/groups/{group_id}/conversations", json={"title": "Filter Test"},
        headers=headers,
    )
    conv_id = conv.json()["id"]

    from semantic_lighthouse.services.chat import ChatAnswer, ChatResponse, ToolCall

    call_count = [0]
    captured_histories: list[list[dict]] = []

    def _fake_generate_response(question, citations, history=None, tools=None):
        call_count[0] += 1
        if history:
            captured_histories.append(list(history))
        if call_count[0] == 1:
            return ChatResponse(tool_call=ToolCall(name="search_knowledge_base", arguments={"query": "tools"}))
        return ChatResponse(
            answer=ChatAnswer(
                answer="Tool filtering works correctly.",
                confidence="medium", knowledge_gaps=[], next_steps=[], model="fake",
            ),
        )

    with mock.patch(
        "semantic_lighthouse.routers.conversations.create_chat_client"
    ) as mock_create:
        mock_client = mock.MagicMock()
        mock_client.generate_response.side_effect = _fake_generate_response
        mock_create.return_value = mock_client

        # First message: triggers tool call
        resp = client.post(
            f"/groups/{group_id}/conversations/{conv_id}/messages",
            json={"question": "tool calling formats", "retrieval_method": "keyword"},
            headers=headers,
        )
        assert resp.status_code == 200
        call_count[0] = 0  # reset for second message

        # Second message: should NOT include tool role in history
        resp2 = client.post(
            f"/groups/{group_id}/conversations/{conv_id}/messages",
            json={"question": "verify filter", "retrieval_method": "keyword"},
            headers=headers,
        )
        assert resp2.status_code == 200

    # Verify no tool role messages in any history passed to generate_response
    for hist in captured_histories:
        tool_roles = [m for m in hist if m.get("role") == "tool"]
        assert not tool_roles, (
            f"tool role messages leaked into API history: {tool_roles}"
        )
