from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from typing import Protocol

from packages.db.models import EMBEDDING_DIMENSION

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        pass


class FakeEmbeddingProvider:
    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        values: list[float] = []
        seed = text.encode("utf-8")
        counter = 0
        while len(values) < self.dimension:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            for offset in range(0, len(digest), 4):
                integer = int.from_bytes(digest[offset : offset + 4], "big", signed=False)
                values.append((integer / 2**31) - 1.0)
                if len(values) == self.dimension:
                    break
            counter += 1
        return values


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        dimension: int = EMBEDDING_DIMENSION,
        model: str = OPENAI_EMBEDDING_MODEL,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI embedding provider requires the 'openai' package to be installed"
            ) from exc

        self.dimension = dimension
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.client.embeddings.create(
            input=list(texts),
            model=self.model,
            dimensions=self.dimension,
            encoding_format="float",
        )
        return [list(item.embedding) for item in response.data]


def build_embedding_provider(provider: str) -> EmbeddingProvider:
    normalized = provider.lower()
    if normalized == "fake":
        return FakeEmbeddingProvider()
    if normalized == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for the openai embedding provider")
        return OpenAIEmbeddingProvider()
    if normalized == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            return OpenAIEmbeddingProvider()
        return FakeEmbeddingProvider()
    raise ValueError("embedding provider must be one of: auto, fake, openai")
