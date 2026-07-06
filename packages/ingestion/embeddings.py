from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from typing import Any, Protocol

from packages.db.models import EMBEDDING_DIMENSION

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
BGE_SMALL_EN_MODEL = "BAAI/bge-small-en-v1.5"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"


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


class HuggingFaceEmbeddingProvider:
    def __init__(
        self,
        *,
        dimension: int = EMBEDDING_DIMENSION,
        model_name: str = BGE_SMALL_EN_MODEL,
        model: Any | None = None,
    ) -> None:
        self.dimension = dimension
        self.model_name = model_name
        if model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "Hugging Face embedding provider requires the "
                    "'sentence-transformers' package to be installed"
                ) from exc
            model = SentenceTransformer(model_name)
        self.model = model

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [
            self._fit_storage_dimension(self._as_float_list(embedding))
            for embedding in embeddings
        ]

    def _as_float_list(self, embedding: Any) -> list[float]:
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        return [float(value) for value in embedding]

    def _fit_storage_dimension(self, embedding: list[float]) -> list[float]:
        if len(embedding) > self.dimension:
            raise ValueError(
                f"Hugging Face embedding dimension {len(embedding)} exceeds configured "
                f"storage dimension {self.dimension}"
            )
        return embedding + ([0.0] * (self.dimension - len(embedding)))


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        dimension: int = EMBEDDING_DIMENSION,
        model: str = OLLAMA_EMBEDDING_MODEL,
        client: Any | None = None,
    ) -> None:
        self.dimension = dimension
        self.model = model
        if client is None:
            try:
                import ollama
            except ImportError as exc:
                raise RuntimeError(
                    "Ollama embedding provider requires the 'ollama' package to be installed"
                ) from exc
            client = ollama
        self.client = client

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.client.embed(model=self.model, input=list(texts))
        embeddings = response["embeddings"] if isinstance(response, dict) else response.embeddings
        return [
            self._fit_storage_dimension(self._as_float_list(embedding))
            for embedding in embeddings
        ]

    def _as_float_list(self, embedding: Any) -> list[float]:
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        return [float(value) for value in embedding]

    def _fit_storage_dimension(self, embedding: list[float]) -> list[float]:
        if len(embedding) > self.dimension:
            raise ValueError(
                f"Ollama embedding dimension {len(embedding)} exceeds configured "
                f"storage dimension {self.dimension}"
            )
        return embedding + ([0.0] * (self.dimension - len(embedding)))


def build_embedding_provider(provider: str, *, model: str | None = None) -> EmbeddingProvider:
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
    if normalized in {"huggingface", "hf", "bge-small-en-v1.5"}:
        return HuggingFaceEmbeddingProvider()
    if normalized in {"ollama", "nomic-embed-text"}:
        return OllamaEmbeddingProvider(model=model or OLLAMA_EMBEDDING_MODEL)
    raise ValueError("embedding provider must be one of: auto, fake, openai, huggingface, ollama")
