from __future__ import annotations

import json

import httpx
import pytest

from semantic_lighthouse.config import Settings
from semantic_lighthouse.services.chat import ChatError, DeepSeekChatClient


def _settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        chat_model="deepseek-v4-flash",
        chat_base_url="https://api.deepseek.com",
    )


def test_deepseek_v4_payload_disables_thinking_for_json_response(monkeypatch):
    captured: dict[str, dict] = {}

    def fake_post(url, json, headers, timeout):
        captured["payload"] = json
        request = httpx.Request("POST", url)
        content = {
            "answer": "企业需要 Ontology 来建立可检索、可追溯的业务语义层。",
            "confidence": "medium",
            "knowledge_gaps": [],
            "next_steps": ["复核引用来源。"],
        }
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": json_module.dumps(content)}}]},
        )

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)

    answer = DeepSeekChatClient(_settings()).answer_question("企业为什么需要 Ontology？", [])

    assert answer.confidence == "medium"
    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["thinking"] == {"type": "disabled"}


def test_deepseek_http_error_includes_provider_message(monkeypatch):
    def fake_post(url, json, headers, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(
            400,
            request=request,
            json={"error": {"message": "thinking mode is incompatible with this request"}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ChatError) as exc_info:
        DeepSeekChatClient(_settings()).answer_question("企业为什么需要 Ontology？", [])

    message = str(exc_info.value)
    assert "HTTP 400" in message
    assert "thinking mode is incompatible" in message


def test_deepseek_agent_decide_call_tool_parses_json(monkeypatch):
    captured: dict = {}

    def fake_post(url, json, headers, timeout):
        captured["payload"] = json
        request = httpx.Request("POST", url)
        return httpx.Response(
            200, request=request,
            json={"choices": [{"message": {"content": __import__("json").dumps({
                "thought": "Searching.", "action": "call_tool",
                "tool_name": "search_knowledge_base", "tool_arguments": {"query": "Ontology"},
            })}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    decision = DeepSeekChatClient(_settings()).agent_decide(
        [{"role": "user", "content": "Find Ontology"}], [],
    )
    assert decision.action == "call_tool"
    assert decision.tool_name == "search_knowledge_base"
    assert decision.tool_arguments == {"query": "Ontology"}
    assert decision.raw_response is not None and len(decision.raw_response) > 0
    assert captured["payload"]["response_format"] == {"type": "json_object"}


def test_deepseek_agent_decide_finalize_parses_json(monkeypatch):
    def fake_post(url, json, headers, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(
            200, request=request,
            json={"choices": [{"message": {"content": __import__("json").dumps({
                "thought": "Done.", "action": "finalize",
                "final_answer": "Ontology connects business and AI.",
            })}}]},
        )
    monkeypatch.setattr(httpx, "post", fake_post)
    decision = DeepSeekChatClient(_settings()).agent_decide([], [])
    assert decision.action == "finalize"
    assert decision.final_answer == "Ontology connects business and AI."


def test_deepseek_agent_decide_invalid_json_raises_chat_error(monkeypatch):
    def fake_post(url, json, headers, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(
            200, request=request,
            json={"choices": [{"message": {"content": "not json"}}]},
        )
    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(ChatError):
        DeepSeekChatClient(_settings()).agent_decide([], [])
