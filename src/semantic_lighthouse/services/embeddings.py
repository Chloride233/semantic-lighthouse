from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import httpx

from semantic_lighthouse.config import Settings


class EmbeddingError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str


class EmbeddingClient:
    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        raise NotImplementedError


class AliyunEmbeddingClient(EmbeddingClient):
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.dashscope_api_key
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dimension
        self.timeout_seconds = settings.embedding_timeout_seconds

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not self.api_key:
            raise EmbeddingError("DASHSCOPE_API_KEY is required for Aliyun embedding provider")
        if not texts:
            return EmbeddingResult(vectors=[], model=self.model)

        payload = {"model": self.model, "input": texts}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = httpx.post(self.endpoint, json=payload, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Embedding provider request failed: {exc}") from exc

        body = response.json()
        try:
            vectors = [item["embedding"] for item in sorted(body["data"], key=lambda item: item["index"])]
        except (KeyError, TypeError) as exc:
            raise EmbeddingError("Embedding provider returned an unexpected response shape") from exc
        _validate_vectors(vectors, self.dimension)
        return EmbeddingResult(vectors=vectors, model=body.get("model") or self.model)


class FakeEmbeddingClient(EmbeddingClient):
    def __init__(self, settings: Settings) -> None:
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dimension

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        vectors = [_hash_embedding(text, self.dimension) for text in texts]
        return EmbeddingResult(vectors=vectors, model=self.model)


def create_embedding_client(settings: Settings) -> EmbeddingClient:
    provider = settings.embedding_provider.lower()
    if provider == "aliyun":
        return AliyunEmbeddingClient(settings)
    if provider == "fake":
        return FakeEmbeddingClient(settings)
    raise EmbeddingError(f"Unsupported embedding provider: {settings.embedding_provider}")


def _validate_vectors(vectors: list[list[float]], dimension: int) -> None:
    for vector in vectors:
        if len(vector) != dimension:
            raise EmbeddingError(f"Embedding dimension mismatch: expected {dimension}, got {len(vector)}")


def _hash_embedding(text: str, dimension: int) -> list[float]:
    digest = sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        block = sha256(digest + counter.to_bytes(4, "big")).digest()
        for byte in block:
            values.append((byte / 255.0) * 2.0 - 1.0)
            if len(values) >= dimension:
                break
        counter += 1
    return values


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
