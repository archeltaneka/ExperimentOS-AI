from __future__ import annotations

from asyncio import run
from typing import Any

import pytest

from packages.db.models import EMBEDDING_DIMENSION
from packages.ingestion.embeddings import build_embedding_provider
from packages.llm.client import LLMClientError


def test_build_embedding_provider_accepts_ollama(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

    provider = build_embedding_provider("ollama")

    assert provider.model == "nomic-embed-text"
    assert provider.dimension == EMBEDDING_DIMENSION


def test_ollama_embedding_provider_calls_embed_endpoint_and_pads_dimension() -> None:
    from packages.ingestion.embeddings import OllamaEmbeddingProvider

    calls: list[tuple[str, dict[str, Any]]] = []

    def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((url, payload))
        return {"embeddings": [[0.1, 0.2, 0.3]]}

    provider = OllamaEmbeddingProvider(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dimension=5,
        post_json=post_json,
    )

    embeddings = provider.embed_texts(["hello"])

    assert calls == [
        (
            "http://localhost:11434/api/embed",
            {"model": "nomic-embed-text", "input": ["hello"]},
        )
    ]
    assert embeddings == [[0.1, 0.2, 0.3, 0.0, 0.0]]


def test_ollama_embedding_provider_rejects_too_large_embeddings() -> None:
    from packages.ingestion.embeddings import OllamaEmbeddingProvider

    provider = OllamaEmbeddingProvider(
        dimension=2,
        post_json=lambda _url, _payload: {"embeddings": [[0.1, 0.2, 0.3]]},
    )

    with pytest.raises(ValueError, match="exceeds configured storage dimension"):
        provider.embed_texts(["hello"])


def test_ollama_llm_client_calls_generate_endpoint() -> None:
    from packages.llm.client import OllamaLLMClient

    calls: list[tuple[str, dict[str, Any]]] = []

    async def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((url, payload))
        return {
            "response": "Grounded answer.",
            "prompt_eval_count": 12,
            "eval_count": 4,
            "total_duration": 2_000_000,
        }

    client = OllamaLLMClient(
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        post_json=post_json,
    )

    response = run(
        client.generate(
            prompt="Question and context",
            system_instruction="Only answer using context.",
        )
    )

    assert calls == [
        (
            "http://localhost:11434/api/generate",
            {
                "model": "qwen2.5:7b",
                "prompt": "Question and context",
                "system": "Only answer using context.",
                "stream": False,
            },
        )
    ]
    assert response.answer == "Grounded answer."
    assert response.metrics.model == "qwen2.5:7b"
    assert response.metrics.input_tokens == 12
    assert response.metrics.output_tokens == 4
    assert response.metrics.latency_ms == pytest.approx(2.0)


def test_ollama_llm_client_maps_http_failures() -> None:
    from packages.llm.client import OllamaLLMClient

    async def post_json(_url: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("connection refused")

    client = OllamaLLMClient(post_json=post_json)

    with pytest.raises(LLMClientError, match="connection refused"):
        run(client.generate(prompt="Question", system_instruction="System"))
