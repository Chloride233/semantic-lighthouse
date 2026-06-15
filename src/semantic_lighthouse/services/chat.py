from __future__ import annotations

from dataclasses import dataclass
import json

import httpx
from pydantic import BaseModel, Field, ValidationError

from semantic_lighthouse.config import Settings
from semantic_lighthouse.schemas import EvidenceQuality, RagCitation


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


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

LOW_MATURITY_STATUSES = {"draft", "unknown", "outdated"}


def _downgrade(level: str, steps: int = 1) -> str:
    for _ in range(steps):
        level = {"high": "medium", "medium": "low"}.get(level, "low")
    return level


def adjusted_confidence(model_confidence: str, citations: list[RagCitation]) -> tuple[str, str]:
    """Server-side confidence adjustment with human-readable Chinese reason.

    Rules are applied in priority order (first match wins). The returned
    reason explains *why* the confidence was set, so the user can assess
    reliability without trusting the model's self-assessment.

    Returns
    -------
    (confidence, reason) — confidence is one of ``high``/``medium``/``low``;
    reason is a Chinese sentence explaining the decision.
    """
    n = len(citations)
    # score=0.0 is the keyword-search sentinel for "no meaningful score";
    # score=None means no embedding was computed. Filter both out.
    scores = [c.score for c in citations if c.score is not None and c.score > 0.0]
    titles = [c.title for c in citations if c.title]
    doc_ids = {c.document_id for c in citations}

    # ── rule 1: no citations ──────────────────────────────────────────
    if n == 0:
        return (
            "low",
            "未检索到任何可用证据片段，无法生成可靠回答。建议补充知识库文档或改写问题。",
        )

    # ── rule 2: single citation — capped at medium ─────────────────────
    if n == 1:
        title = titles[0] if titles else "未知文档"
        return (
            _cap(model_confidence, "medium"),
            f"仅有一条证据片段（来自「{title}」），覆盖面不足，无法交叉验证。",
        )

    # ── rule 3: all meaningful scores below 0.3 — low ──────────────────
    if scores and all(s < 0.3 for s in scores):
        return (
            "low",
            f"检索到的 {n} 条片段匹配分数均低于 0.3，证据与问题的关联度很弱，无法支撑可信回答。",
        )

    # ── rule 4: all meaningful scores below 0.5 — capped at medium ─────
    if scores and all(s < 0.5 for s in scores):
        return (
            _cap(model_confidence, "medium"),
            f"检索到的 {n} 条片段匹配分数偏低（均 < 0.5），证据强度不足以给出高可信结论。",
        )

    # ── rule 5: >50% from low-maturity sources — downgrade 1 level ─────
    maturity_statuses = [c.status for c in citations if c.status]
    if maturity_statuses:
        low_count = sum(1 for s in maturity_statuses if s in LOW_MATURITY_STATUSES)
        if low_count > len(maturity_statuses) / 2:
            base = _downgrade(model_confidence, 1)
            return (
                base,
                f"大部分引用来源（{low_count}/{len(maturity_statuses)}）状态为草稿/未知/过期，"
                f"来源成熟度不足，可信度已降级。",
            )

    # ── rule 6: ≥2 citations from ≥2 different docs, good scores → high
    if n >= 2 and len(doc_ids) >= 2 and (not scores or any(s >= 0.5 for s in scores)):
        return (
            model_confidence,
            f"共有 {n} 条相关片段来自 {len(doc_ids)} 份不同文档，来源明确，"
            f"内容能直接支持回答。",
        )

    # ── rule 7: fallback — cap at medium, explain why ──────────────────
    reason_parts = [f"共有 {n} 条相关片段"]
    if len(doc_ids) == 1:
        reason_parts.append("但全部来自同一份文档，来源多样性不足")
    if scores and all(s < 0.7 for s in scores):
        reason_parts.append("匹配分数一般")
    reason_parts.append("尚不足以给出高可信结论。")
    return (
        _cap(model_confidence, "medium"),
        "，".join(reason_parts),
    )


def _cap(level: str, ceiling: str) -> str:
    """Return *level* but no higher than *ceiling*."""
    if CONFIDENCE_ORDER.get(level, 0) > CONFIDENCE_ORDER.get(ceiling, 0):
        return ceiling
    return level


def compute_evidence_quality(citations: list[RagCitation]) -> EvidenceQuality:
    """Compute structured evidence quality from citations.

    Uses the same input logic as :func:`adjusted_confidence` to keep
    ``evidence_quality`` and ``confidence_reason`` consistent.
    """
    n = len(citations)
    scores = [c.score for c in citations if c.score is not None and c.score > 0.0]
    doc_ids = {c.document_id for c in citations}
    statuses = [c.status for c in citations if c.status]

    # ── retrieval_coverage ──────────────────────────────────────────
    if n == 0:
        coverage = "none"
    elif n == 1:
        coverage = "weak"
    elif n <= 3:
        coverage = "partial"
    else:
        coverage = "full"

    # ── citation_diversity ──────────────────────────────────────────
    if n == 0:
        diversity = "none"
    elif len(doc_ids) == 1:
        diversity = "low"
    elif len(doc_ids) == 2:
        diversity = "medium"
    else:
        diversity = "high"

    # ── source_maturity ─────────────────────────────────────────────
    if not statuses:
        maturity = "unknown"
    else:
        reviewed = sum(1 for s in statuses if s == "reviewed")
        low_mat = sum(1 for s in statuses if s in LOW_MATURITY_STATUSES)
        if low_mat > len(statuses) / 2:
            maturity = "weak"
        elif reviewed >= len(statuses) / 2:
            maturity = "strong"
        else:
            maturity = "medium"

    # ── score_distribution ──────────────────────────────────────────
    if not scores:
        score_dist = "unknown"
    elif all(s < 0.3 for s in scores):
        score_dist = "weak"
    elif all(s >= 0.5 for s in scores):
        score_dist = "strong"
    else:
        score_dist = "medium"

    # ── summary ─────────────────────────────────────────────────────
    parts: list[str] = []
    if n == 0:
        parts.append("未检索到任何证据片段")
    else:
        parts.append(f"共 {n} 条片段")
        if len(doc_ids) > 1:
            parts.append(f"来自 {len(doc_ids)} 份文档")
        if scores:
            avg = sum(scores) / len(scores)
            parts.append(f"平均匹配分 {avg:.2f}")
        if maturity == "weak":
            parts.append("部分来源为草稿/未知状态")
        elif maturity == "strong":
            parts.append("来源状态良好")

    if coverage == "none":
        summary = "未检索到任何证据片段，无法评估证据质量。建议补充知识库文档或改写问题后重试。"
    elif coverage == "weak":
        summary = "证据质量较弱——" + "，".join(parts) + "。建议补充更多相关文档。"
    elif coverage == "partial" and (maturity == "weak" or score_dist == "weak"):
        summary = "证据质量一般——" + "，".join(parts) + "。部分证据不够充分或来源未验证。"
    elif diversity == "high" and score_dist == "strong" and maturity == "strong":
        summary = "证据质量良好——" + "，".join(parts) + "，能够有效支撑回答。"
    else:
        summary = "证据质量中等——" + "，".join(parts) + "。建议从多角度补充材料以提升可靠性。"

    return EvidenceQuality(
        retrieval_coverage=coverage,
        source_maturity=maturity,
        citation_diversity=diversity,
        score_distribution=score_dist,
        summary=summary,
    )
