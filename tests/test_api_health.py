from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from apps.api.main import app, get_embedding_provider_name, get_question_answering_service
from packages.llm.client import LLMMetrics
from packages.qa.question_answering_service import (
    Citation,
    EmbeddingFailureError,
    LLMGenerationError,
    QuestionAnsweringServiceResponse,
    RetrievedChunk,
    UnknownExperimentError,
)


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "experimentos-api"}


def test_embedding_provider_name_uses_environment(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "huggingface")

    assert get_embedding_provider_name() == "huggingface"


@dataclass
class StubQuestionAnsweringService:
    response: QuestionAnsweringServiceResponse | None = None
    failure: Exception | None = None

    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QuestionAnsweringServiceResponse:
        if self.failure is not None:
            raise self.failure
        if self.response is None:
            raise AssertionError("stub response is required")
        return self.response


def test_ask_endpoint_returns_grounded_answer() -> None:
    service = StubQuestionAnsweringService(
        response=QuestionAnsweringServiceResponse(
            answer="The launch passed guardrails.",
            citations=[
                Citation(
                    experiment_id="exp-123",
                    document="Launch Report",
                    similarity=0.91,
                )
            ],
            retrieved_chunks=[
                RetrievedChunk(
                    experiment_id="exp-123",
                    experiment_name="Payment Recommendation Launch",
                    document="Launch Report",
                    text="The launch passed guardrails.",
                    similarity=0.91,
                    metadata={"section": "Decision"},
                )
            ],
            retrieval_metrics={
                "embedding_time_ms": 3.0,
                "vector_search_time_ms": 5.0,
                "retrieved_chunks": 1,
                "average_similarity": 0.91,
            },
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
                "experiment_name": "Payment Recommendation Launch",
                "document": "Launch Report",
                "text": "The launch passed guardrails.",
                "similarity": 0.91,
                "metadata": {"section": "Decision"},
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
