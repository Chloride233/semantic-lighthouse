from __future__ import annotations

from dataclasses import dataclass
import json

import httpx
from pydantic import BaseModel, Field, ValidationError

from semantic_lighthouse.config import Settings
from semantic_lighthouse.schemas import RagCitation


class ChatError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    confidence: str
    knowledge_gaps: list[str]
    next_steps: list[str]
    model: str


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, str]


@dataclass(frozen=True)
class ChatResponse:
    answer: ChatAnswer | None = None
    tool_call: ToolCall | None = None

    @property
    def is_tool_call(self) -> bool:
        return self.tool_call is not None


class GeneratedAnswer(BaseModel):
    answer: str = Field(min_length=1)
    confidence: str = Field(pattern="^(high|medium|low)$")
    knowledge_gaps: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ChatClient:
    def answer_question(
        self,
        question: str,
        citations: list[RagCitation],
        history: list[dict[str, str]] | None = None,
    ) -> ChatAnswer:
        raise NotImplementedError

    def generate_response(
        self,
        question: str,
        citations: list[RagCitation],
        history: list[dict[str, str]] | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        raise NotImplementedError


class DeepSeekChatClient(ChatClient):
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.chat_base_url.rstrip("/")
        self.model = settings.chat_model
        self.timeout_seconds = settings.chat_timeout_seconds

    def answer_question(
        self,
        question: str,
        citations: list[RagCitation],
        history: list[dict[str, str]] | None = None,
    ) -> ChatAnswer:
        if not self.api_key:
            raise ChatError("DEEPSEEK_API_KEY is required for DeepSeek chat provider")

        payload = {
            "model": self.model,
            "messages": _messages(question, citations, history),
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        _disable_thinking_for_structured_json(payload, self.model)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ChatError(_format_provider_http_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise ChatError(f"Chat provider request failed: {exc}") from exc

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatError("Chat provider returned an unexpected response shape") from exc

        generated = _parse_generated_answer(content)
        return ChatAnswer(
            answer=generated.answer,
            confidence=generated.confidence,
            knowledge_gaps=generated.knowledge_gaps,
            next_steps=generated.next_steps,
            model=self.model,
        )

    def generate_response(
        self,
        question: str,
        citations: list[RagCitation],
        history: list[dict[str, str]] | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        if not self.api_key:
            raise ChatError("DEEPSEEK_API_KEY is required for DeepSeek chat provider")

        effective_tools = tools or []
        payload = {
            "model": self.model,
            "messages": _messages_with_tools(question, citations, history, effective_tools),
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        _disable_thinking_for_structured_json(payload, self.model)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ChatError(_format_provider_http_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise ChatError(f"Chat provider request failed: {exc}") from exc

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatError("Chat provider returned an unexpected response shape") from exc

        return _parse_chat_response(content, self.model)


class FakeChatClient(ChatClient):
    def __init__(self, settings: Settings) -> None:
        self.model = settings.chat_model

    def answer_question(
        self,
        question: str,
        citations: list[RagCitation],
        history: list[dict[str, str]] | None = None,
    ) -> ChatAnswer:
        if not citations:
            return ChatAnswer(
                answer=f"当前知识库没有检索到足够支撑“{question}”的可靠证据，因此不建议直接生成面向客户的结论。",
                confidence="low",
                knowledge_gaps=["没有检索到与问题直接匹配的文档片段。"],
                next_steps=["补充相关知识文档，或把问题改写为更贴近知识库实体、场景和方法论的表述。"],
                model=self.model,
            )
        evidence_titles = _unique_titles(citations)
        evidence_summary = _summarize_citation_text(citations)
        return ChatAnswer(
            answer=(
                f"根据当前知识库中与“{question}”相关的 {len(citations)} 个片段，"
                f"可以先给出一个基于证据的咨询判断：{evidence_summary}"
                f"这些依据主要来自：{evidence_titles}。"
            ),
            confidence="high" if len(citations) >= 2 else "medium",
            knowledge_gaps=[] if len(citations) >= 2 else ["目前只检索到一个支撑片段，证据覆盖面偏窄。"],
            next_steps=["在对外使用前，先复核下方引用片段是否覆盖了客户问题中的关键业务背景。"],
            model=self.model,
        )

    def generate_response(
        self,
        question: str,
        citations: list[RagCitation],
        history: list[dict[str, str]] | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        answer = self.answer_question(question, citations, history)
        return ChatResponse(answer=answer)


def create_chat_client(settings: Settings) -> ChatClient:
    provider = settings.chat_provider.lower()
    if provider == "deepseek":
        return DeepSeekChatClient(settings)
    if provider == "fake":
        return FakeChatClient(settings)
    raise ChatError(f"Unsupported chat provider: {settings.chat_provider}")


def _disable_thinking_for_structured_json(payload: dict, model: str) -> None:
    """Keep DeepSeek V4 responses compatible with strict JSON parsing."""
    if model.startswith("deepseek-v4"):
        payload["thinking"] = {"type": "disabled"}


def _format_provider_http_error(exc: httpx.HTTPStatusError) -> str:
    response = exc.response
    detail = response.text.strip()
    if detail:
        try:
            parsed = response.json()
        except ValueError:
            pass
        else:
            if isinstance(parsed, dict):
                error = parsed.get("error")
                if isinstance(error, dict):
                    message = error.get("message") or error.get("code")
                    if message:
                        detail = str(message)
                elif parsed.get("message"):
                    detail = str(parsed["message"])
    if len(detail) > 500:
        detail = detail[:500] + "..."
    return f"Chat provider request failed: HTTP {response.status_code}: {detail or response.reason_phrase}"


def _format_citations(citations: list[RagCitation]) -> str:
    """Format citation list as a single text block for LLM context."""
    return "\n\n".join(
        (
            f"[{index}] title={citation.title}\n"
            f"source_path={citation.source_path}\n"
            f"heading={citation.heading_path or ''}\n"
            f"metadata={{entityType:{citation.entity_type}, documentType:{citation.document_type}, "
            f"source:{citation.source}, status:{citation.status}}}\n"
            f"snippet={citation.snippet}"
        )
        for index, citation in enumerate(citations, start=1)
    )


def _unique_titles(citations: list[RagCitation]) -> str:
    titles: list[str] = []
    for citation in citations:
        title = citation.title or citation.file_name or citation.source_path
        if title and title not in titles:
            titles.append(title)
    return "、".join(titles[:3]) or "已检索文档"


def _summarize_citation_text(citations: list[RagCitation]) -> str:
    snippets = [citation.snippet.strip() for citation in citations if citation.snippet and citation.snippet.strip()]
    joined = " ".join(snippets)
    if "Ontology" in joined or "本体" in joined or "语义" in joined:
        return (
            "企业需要 Ontology 的核心原因，不是为了再造一个数据仓库，而是为了把分散的数据、业务对象、关系和操作统一到可被人、应用和 AI 理解的语义层中。"
            "这样 AI 在回答或执行任务时看到的是业务语境，而不是孤立字段和零散表结构。"
        )
    if "AI" in joined and ("转型" in joined or "路线图" in joined):
        return (
            "企业 AI 转型应先从数据可访问、语义建模和低复杂度高价值场景切入，逐步建立可检索、可追溯、可评估的知识和业务能力闭环。"
        )
    if snippets:
        compact = " ".join(snippets[:2]).replace("\n", " ").strip()
        # If the compact text is mostly ASCII / English, replace with a Chinese
        # summary so the fake provider never leaks raw English into its output.
        ascii_ratio = sum(1 for ch in compact if ch.isascii()) / max(len(compact), 1)
        if ascii_ratio > 0.5:
            return "检索到多个英文文档片段，内容涉及企业数据平台、知识图谱与AI咨询领域。建议在查看下方引用原文后结合业务背景进行判断。"
        return compact[:220] + ("..." if len(compact) > 220 else "")
    return "当前检索结果提供了一些相关上下文，但证据片段信息量有限，需要进一步补充材料。"


def _messages(
    question: str,
    citations: list[RagCitation],
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    context = _format_citations(citations)
    system_message = {
        "role": "system",
        "content": (
            "你是企业AI转型顾问。仅基于提供的检索上下文回答，不要编造。如果证据不足，明确说明。"
            "所有面向用户的 JSON 值必须使用中文。"
            "严格返回 JSON，包含键：answer, confidence, knowledge_gaps, next_steps。"
            "confidence 必须是 high, medium, low 之一。"
            "禁止在 answer/knowledge_gaps/next_steps 中出现以下英文模板短语："
            "\"Based on retrieved sources\", \"according to the provided context\", "
            "\"the retrieved documents\", \"Review the cited chunks\"。"
        ),
    }
    user_message = {
        "role": "user",
        "content": (
            f"用户问题：\n{question}\n\n"
            f"检索上下文：\n{context or '无检索结果。'}"
        ),
    }
    if history:
        return [system_message] + history + [user_message]
    return [system_message, user_message]


def _messages_with_tools(
    question: str,
    citations: list[RagCitation],
    history: list[dict[str, str]] | None = None,
    tools: list[dict] | None = None,
) -> list[dict[str, str]]:
    """Build prompt messages including tool descriptions.

    The model can respond with either a final answer or a tool_call request.
    """
    context = _format_citations(citations)
    tools_block = ""
    if tools:
        tools_json = json.dumps(tools, indent=2, ensure_ascii=False)
        tools_block = (
            "\n\nAvailable tools (you may request ONE tool call before answering):\n"
            + tools_json
            + "\n\nTo use a tool, respond with JSON:\n"
            '{"tool_call": {"name": "<tool_name>", "arguments": {"<param>": "<value>"}}}\n'
            "To answer directly (no tool needed), respond with the standard JSON format "
            'containing: answer, confidence, knowledge_gaps, next_steps.\n'
            "Never use both tool_call and answer in the same response."
        )

    system_message = {
        "role": "system",
        "content": (
            "你是企业AI转型顾问。仅基于提供的检索上下文回答，不要编造。如果证据不足，明确说明。"
            "所有面向用户的 JSON 值必须使用中文。"
            "如果额外的检索能帮助回答问题，可以请求一次工具调用。"
            "禁止在 answer/knowledge_gaps/next_steps 中出现英文模板短语。"
            + tools_block
        ),
    }
    user_message = {
        "role": "user",
        "content": (
            f"用户问题：\n{question}\n\n"
            f"检索上下文：\n{context or '无检索结果。'}"
        ),
    }
    if history:
        return [system_message] + history + [user_message]
    return [system_message, user_message]


def _parse_chat_response(content: str, model: str) -> ChatResponse:
    """Parse LLM output that may contain either an answer or a tool_call."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ChatError("Chat provider did not return valid JSON") from exc

    tool_call_data = data.get("tool_call")
    if tool_call_data and isinstance(tool_call_data, dict):
        name = tool_call_data.get("name", "")
        arguments = tool_call_data.get("arguments", {})
        if name and isinstance(name, str) and isinstance(arguments, dict):
            return ChatResponse(
                tool_call=ToolCall(name=name, arguments={str(k): str(v) for k, v in arguments.items()}),
            )

    # Treat as direct answer — validate with existing parser
    generated = _parse_generated_answer(content)
    return ChatResponse(
        answer=ChatAnswer(
            answer=generated.answer,
            confidence=generated.confidence,
            knowledge_gaps=generated.knowledge_gaps,
            next_steps=generated.next_steps,
            model=model,
        ),
    )


def _parse_generated_answer(content: str) -> GeneratedAnswer:
    try:
        data = json.loads(content)
        return GeneratedAnswer.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ChatError("Chat provider did not return valid answer JSON") from exc


def sanitize_references(answer: str, citations: list[RagCitation]) -> str:
    """Replace out-of-range ``[N]`` citation markers in *answer*.

    Scans for ``[1]``, ``[99]`` patterns; replaces any where N < 1 or
    N > len(citations) with ``"(source unavailable)"``.  Deterministic —
    no model involvement.
    """
    import re

    max_n = len(citations)

    def _replace(m: re.Match[str]) -> str:
        n = int(m.group(1))
        return m.group(0) if 1 <= n <= max_n else "(source unavailable)"

    return re.sub(r"\[(\d+)\]", _replace, answer)


def adjusted_confidence(model_confidence: str, citations: list[RagCitation]) -> str:
    """Server-side confidence downgrade based on evidence quality.

    - 0 citations → ``"low"``
    - 1 citation  → capped at ``"medium"``
    - All scores < 0.3 → ``"low"``
    - All scores < 0.5 → capped at ``"medium"``
    - Otherwise → model-reported confidence
    """
    order = {"low": 0, "medium": 1, "high": 2}

    if len(citations) == 0:
        return "low"

    scores = [c.score for c in citations if c.score is not None]

    if len(citations) == 1:
        return model_confidence if order[model_confidence] < order["medium"] else "medium"

    if scores and all(s < 0.3 for s in scores):
        return "low"

    if scores and all(s < 0.5 for s in scores):
        return model_confidence if order[model_confidence] < order["medium"] else "medium"

    return model_confidence
