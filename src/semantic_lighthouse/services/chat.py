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


class GeneratedAnswer(BaseModel):
    answer: str = Field(min_length=1)
    confidence: str = Field(pattern="^(high|medium|low)$")
    knowledge_gaps: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ChatClient:
    def answer_question(self, question: str, citations: list[RagCitation]) -> ChatAnswer:
        raise NotImplementedError


class DeepSeekChatClient(ChatClient):
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.chat_base_url.rstrip("/")
        self.model = settings.chat_model
        self.timeout_seconds = settings.chat_timeout_seconds

    def answer_question(self, question: str, citations: list[RagCitation]) -> ChatAnswer:
        if not self.api_key:
            raise ChatError("DEEPSEEK_API_KEY is required for DeepSeek chat provider")

        payload = {
            "model": self.model,
            "messages": _messages(question, citations),
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
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


class FakeChatClient(ChatClient):
    def __init__(self, settings: Settings) -> None:
        self.model = settings.chat_model

    def answer_question(self, question: str, citations: list[RagCitation]) -> ChatAnswer:
        if not citations:
            return ChatAnswer(
                answer=f"No reliable local evidence was found for: {question}",
                confidence="low",
                knowledge_gaps=["No retrieved chunks matched the question."],
                next_steps=["Import or index more relevant knowledge before using this answer."],
                model=self.model,
            )
        return ChatAnswer(
            answer=f"Based on {len(citations)} retrieved source(s), answer the client question: {question}",
            confidence="high" if len(citations) >= 2 else "medium",
            knowledge_gaps=[] if len(citations) >= 2 else ["Only one supporting source was retrieved."],
            next_steps=["Review the cited chunks before using the answer in a client-facing setting."],
            model=self.model,
        )


def create_chat_client(settings: Settings) -> ChatClient:
    provider = settings.chat_provider.lower()
    if provider == "deepseek":
        return DeepSeekChatClient(settings)
    if provider == "fake":
        return FakeChatClient(settings)
    raise ChatError(f"Unsupported chat provider: {settings.chat_provider}")


def _messages(question: str, citations: list[RagCitation]) -> list[dict[str, str]]:
    context = "\n\n".join(
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
    return [
        {
            "role": "system",
            "content": (
                "You are an enterprise AI transformation consultant. "
                "Answer only from the provided context. If evidence is weak, say so. "
                "Return strict JSON with keys: answer, confidence, knowledge_gaps, next_steps. "
                "confidence must be one of high, medium, low."
            ),
        },
        {
            "role": "user",
            "content": f"Question:\n{question}\n\nRetrieved context:\n{context or 'No context retrieved.'}",
        },
    ]


def _parse_generated_answer(content: str) -> GeneratedAnswer:
    try:
        data = json.loads(content)
        return GeneratedAnswer.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ChatError("Chat provider did not return valid answer JSON") from exc
