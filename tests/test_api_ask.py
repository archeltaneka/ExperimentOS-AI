from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from apps.api.ask_service import AskResponse
from apps.api.main import app, get_ask_service
from packages.qa.question_answering_service import (
    EmbeddingFailureError,
    LLMGenerationError,
    UnknownExperimentError,
)


@dataclass
class StubAskService:
    response: AskResponse | None = None
    failure: Exception | None = None

    async def answer(self, request) -> AskResponse:
        if self.failure is not None:
            raise self.failure
        if self.response is None:
            raise AssertionError("stub response is required")
        return self.response


def test_ask_endpoint_defaults_to_agent_workflow_response() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_ask_service] = lambda: StubAskService(
        response=AskResponse(
            answer="Rollout is supported by the current evidence.",
            citations=[],
            retrieved_chunks=[],
            retrieval_metrics={
                "embedding_time_ms": 0.0,
                "vector_search_time_ms": 0.0,
                "retrieved_chunks": 0,
                "average_similarity": 0.0,
            },
            llm_metrics={
                "model": "agent-workflow",
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0.0,
            },
            intent="decision_support",
            required_agents=["retrieval", "experiment_analysis", "decision"],
            decision={"recommendation": "rollout"},
            executive_summary={"summary": "Rollout is supported by the current evidence."},
            agent_trace=[{"node": "planner", "event": "planned"}],
            agent_metrics={"decision": {"status": "decided"}},
            approval_status="pending",
        )
    )
    try:
        response = client.post(
            "/ask",
            json={
                "question": "Should we roll out the payment recommendation experiment?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["intent"] == "decision_support"
    assert response.json()["answer"] == "Rollout is supported by the current evidence."


def test_ask_endpoint_uses_legacy_rag_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("ASK_MODE", "legacy_rag")
    client = TestClient(app)
    app.dependency_overrides[get_ask_service] = lambda: StubAskService(
        response=AskResponse(
            answer="Legacy grounded answer.",
            citations=[],
            retrieved_chunks=[],
            retrieval_metrics={
                "embedding_time_ms": 1.0,
                "vector_search_time_ms": 2.0,
                "retrieved_chunks": 0,
                "average_similarity": 0.0,
            },
            llm_metrics={
                "model": "mock",
                "input_tokens": 1,
                "output_tokens": 1,
                "latency_ms": 0.0,
            },
            intent=None,
            required_agents=[],
            decision=None,
            executive_summary=None,
            agent_trace=[],
            agent_metrics={},
            approval_status=None,
        )
    )
    try:
        response = client.post(
            "/ask",
            json={
                "question": "What happened?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 5,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["decision"] is None
    assert response.json()["executive_summary"] is None


def test_ask_endpoint_rejects_empty_question() -> None:
    client = TestClient(app)

    response = client.post("/ask", json={"question": "   ", "experiment_id": "exp-123"})

    assert response.status_code == 422
    assert "question must not be empty" in str(response.json()["detail"])


def test_ask_endpoint_returns_404_for_unknown_experiment() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_ask_service] = lambda: StubAskService(
        failure=UnknownExperimentError("missing experiment")
    )
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
    client = TestClient(app)
    app.dependency_overrides[get_ask_service] = lambda: StubAskService(
        failure=EmbeddingFailureError("embedding failed")
    )
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
    client = TestClient(app)
    app.dependency_overrides[get_ask_service] = lambda: StubAskService(
        failure=LLMGenerationError("llm failed")
    )
    try:
        response = client.post(
            "/ask",
            json={"question": "What happened?", "experiment_id": "exp-123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "llm failed"}
