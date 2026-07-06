from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import (
    app,
    get_embedding_provider_name,
    get_llm_client,
    get_question_answering_service,
)
from packages.llm.client import LLMMetrics
from packages.qa.question_answering_service import (
    Citation,
    EmbeddingFailureError,
    LLMGenerationError,
    QAResponse,
    UnknownExperimentError,
)
from packages.retrieval.service import RetrievalMetrics, RetrievalResult


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "experimentos-api"}


def test_embedding_provider_name_uses_dotenv(monkeypatch, tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("EMBEDDING_PROVIDER=huggingface\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert get_embedding_provider_name() == "huggingface"


def test_llm_client_auto_prefers_gemini_when_api_key_is_set(monkeypatch, tmp_path: Path) -> None:
    import apps.api.main as main_module

    class StubGeminiClient:
        def __init__(self, *, model: str) -> None:
            self.model = model

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "GEMINI_API_KEY=test-key",
                "OPENAI_API_KEY=openai-key",
                "GEMINI_MODEL=gemini-test-model",
                "LLM_PROVIDER=auto",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_module, "GeminiLLMClient", StubGeminiClient)

    client = get_llm_client()

    assert isinstance(client, StubGeminiClient)
    assert client.model == "gemini-test-model"


def test_llm_client_loads_dotenv_for_gemini_auto_provider(monkeypatch, tmp_path: Path) -> None:
    import apps.api.main as main_module

    class StubGeminiClient:
        def __init__(self, *, model: str) -> None:
            self.model = model

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=auto",
                "GEMINI_API_KEY=gemini-from-dotenv",
                "GEMINI_MODEL=gemini-dotenv-model",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(main_module, "GeminiLLMClient", StubGeminiClient)

    client = get_llm_client()

    assert isinstance(client, StubGeminiClient)
    assert client.model == "gemini-dotenv-model"


@dataclass
class StubQuestionAnsweringService:
    response: QAResponse | None = None
    failure: Exception | None = None

    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QAResponse:
        if self.failure is not None:
            raise self.failure
        if self.response is None:
            raise AssertionError("stub response is required")
        return self.response


def test_ask_endpoint_returns_grounded_answer() -> None:
    retrieval_result = RetrievalResult(
        experiment_id="exp-123",
        metadata={"section": "Decision"},
        experiment_name="Payment Recommendation Launch",
        document_id="doc-123",
        document_name="Launch Report",
        chunk_text="The launch passed guardrails.",
        similarity=0.91,
    )
    service = StubQuestionAnsweringService(
        response=QAResponse(
            answer="The launch passed guardrails.",
            citations=[
                Citation(
                    experiment_id="exp-123",
                    document="Launch Report",
                    similarity=0.91,
                )
            ],
            retrieved_chunks=[retrieval_result],
            retrieval_metrics=RetrievalMetrics(
                embedding_time_ms=3.0,
                vector_search_time_ms=5.0,
                retrieved_chunks=1,
                average_similarity=0.91,
            ),
            llm_metrics=LLMMetrics(
                model="mock-answerer",
                input_tokens=42,
                output_tokens=5,
                latency_ms=1.5,
            ),
        )
    )
    client = TestClient(app)
    app.dependency_overrides[get_question_answering_service] = lambda: service
    try:
        response = client.post(
            "/ask",
            json={"question": "Why was it launched?", "experiment_id": "exp-123", "top_k": 5},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The launch passed guardrails.",
        "citations": [
            {
                "experiment_id": "exp-123",
                "document": "Launch Report",
                "similarity": 0.91,
            }
        ],
        "retrieved_chunks": [
            {
                "experiment_id": "exp-123",
                "metadata": {"section": "Decision"},
                "experiment_name": "Payment Recommendation Launch",
                "document_id": "doc-123",
                "document_name": "Launch Report",
                "chunk_text": "The launch passed guardrails.",
                "similarity": 0.91,
            }
        ],
        "retrieval_metrics": {
            "embedding_time_ms": 3.0,
            "vector_search_time_ms": 5.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.91,
        },
        "llm_metrics": {
            "model": "mock-answerer",
            "input_tokens": 42,
            "output_tokens": 5,
            "latency_ms": 1.5,
        },
    }


def test_ask_endpoint_rejects_empty_question() -> None:
    client = TestClient(app)

    response = client.post("/ask", json={"question": "   ", "experiment_id": "exp-123"})

    assert response.status_code == 422
    assert "question must not be empty" in str(response.json()["detail"])


def test_ask_endpoint_returns_404_for_unknown_experiment() -> None:
    service = StubQuestionAnsweringService(failure=UnknownExperimentError("missing experiment"))
    client = TestClient(app)
    app.dependency_overrides[get_question_answering_service] = lambda: service
    try:
        response = client.post(
            "/ask",
            json={"question": "What happened?", "experiment_id": "missing-exp"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "missing experiment"}


def test_ask_endpoint_returns_502_for_embedding_failure() -> None:
    service = StubQuestionAnsweringService(failure=EmbeddingFailureError("embedding failed"))
    client = TestClient(app)
    app.dependency_overrides[get_question_answering_service] = lambda: service
    try:
        response = client.post(
            "/ask",
            json={"question": "What happened?", "experiment_id": "exp-123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "embedding failed"}


def test_ask_endpoint_returns_502_for_llm_failure() -> None:
    service = StubQuestionAnsweringService(failure=LLMGenerationError("llm failed"))
    client = TestClient(app)
    app.dependency_overrides[get_question_answering_service] = lambda: service
    try:
        response = client.post(
            "/ask",
            json={"question": "What happened?", "experiment_id": "exp-123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "llm failed"}
