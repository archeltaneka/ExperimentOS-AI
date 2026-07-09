from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from apps.api.ask_service import (
    AgentWorkflowAskService,
    AskRequest,
    AskResponse,
    get_ask_mode,
    map_agent_state_to_ask_response,
)
from apps.api.main import app, get_ask_service
from packages.agents.state import create_initial_state
from packages.qa.question_answering_service import (
    INSUFFICIENT_EVIDENCE_ANSWER,
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


class StubWorkflowService:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state

    def run(self, question: str, experiment_id: str | None = None, top_k: int = 5):
        return self.state


class AsyncioRunWorkflowService:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state

    def run(self, question: str, experiment_id: str | None = None, top_k: int = 5):
        asyncio.run(asyncio.sleep(0))
        return self.state


def build_agent_state(
    *,
    question: str = "Should we roll out the payment recommendation experiment?",
    experiment_id: str = "00000000-0000-0000-0000-000000000123",
    top_k: int = 3,
) -> dict[str, object]:
    state = create_initial_state(question, experiment_id=experiment_id, top_k=top_k)
    state["intent"] = "decision_support"
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-1",
            "experiment_id": experiment_id,
            "content": "Primary metric improved by 8.9% in treatment.",
            "score": 0.91,
            "metadata": {"section": "Results", "document_name": "Launch Report"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": experiment_id,
            "quote": "Primary metric improved by 8.9% in treatment.",
            "section": "Results",
            "metadata": {"section": "Results", "document_name": "Launch Report"},
        }
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "summary": "Treatment beat control on the primary metric.",
        "status": "completed",
        "experiment_id": experiment_id,
        "experiment_name": "Adaptive Payment Method Recommendation",
    }
    state["business_impact"] = {
        **state["business_impact"],
        "summary": "Projected incremental payment success is material.",
        "impact_status": "estimated",
    }
    state["decision"] = {
        **state["decision"],
        "decision_status": "decided",
        "recommendation": "rollout",
        "confidence": "medium",
        "rationale": "Positive lift outweighed manageable rollout risk.",
    }
    state["executive_summary"] = {
        **state["executive_summary"],
        "summary_status": "generated",
        "summary": "Rollout is supported by the current evidence.",
    }
    state["human_approval"] = {
        **state["human_approval"],
        "status": "pending",
        "required": True,
    }
    state["metrics"] = {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {
            "embedding_time_ms": 10.0,
            "vector_search_time_ms": 8.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.91,
        },
        "decision": {"status": "decided"},
    }
    state["trace"] = [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:01Z"},
    ]
    return state


def test_ask_endpoint_defaults_to_agent_workflow_response() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_ask_service] = lambda: StubAskService(
        response=AskResponse(
            answer="Rollout is supported by the current evidence.",
            citations=[
                {
                    "experiment_id": "00000000-0000-0000-0000-000000000123",
                    "quote": "Primary metric improved by 8.9% in treatment.",
                }
            ],
            retrieved_chunks=[
                {
                    "experiment_id": "00000000-0000-0000-0000-000000000123",
                    "metadata": {"section": "Results"},
                    "experiment_name": "Adaptive Payment Method Recommendation",
                    "document_id": "doc-1",
                    "document_name": "Launch Report",
                    "chunk_text": "Primary metric improved by 8.9% in treatment.",
                    "similarity": 0.91,
                }
            ],
            retrieval_metrics={
                "embedding_time_ms": 10.0,
                "vector_search_time_ms": 8.0,
                "retrieved_chunks": 1,
                "average_similarity": 0.91,
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
    assert response.json()["citations"]
    assert response.json()["agent_trace"]
    assert response.json()["agent_metrics"]["decision"]["status"] == "decided"


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
    assert response.json()["answer"] == "Legacy grounded answer."
    assert "citations" in response.json()
    assert "retrieved_chunks" in response.json()
    assert "retrieval_metrics" in response.json()
    assert "llm_metrics" in response.json()
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


def test_map_agent_state_prefers_executive_summary_for_answer() -> None:
    state = build_agent_state()
    state["decision"]["rationale"] = "Fallback rationale."
    state["executive_summary"]["summary"] = "Rollout is supported by the current evidence."

    response = map_agent_state_to_ask_response(state)

    assert response.answer == "Rollout is supported by the current evidence."


def test_map_agent_state_uses_retrieved_chunk_for_experiment_lookup_queries() -> None:
    state = create_initial_state(
        "What happened in the payment recommendation experiment?",
        experiment_id="00000000-0000-0000-0000-000000000123",
        top_k=2,
    )
    state["intent"] = "experiment_lookup"
    state["required_agents"] = ["retrieval"]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "00000000-0000-0000-0000-000000000123",
            "content": "Checkout completion improved after the treatment launched.",
            "score": 0.87,
            "metadata": {"section": "Results", "document_name": "Launch Report"},
        }
    ]
    state["metrics"] = {
        "retrieval": {
            "embedding_time_ms": 5.0,
            "vector_search_time_ms": 4.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.87,
        }
    }

    response = map_agent_state_to_ask_response(state)

    assert response.answer == "Checkout completion improved after the treatment launched."


def test_map_agent_state_returns_insufficient_evidence_when_workflow_has_no_answer() -> None:
    state = create_initial_state(
        "What happened in the payment recommendation experiment?",
        experiment_id="00000000-0000-0000-0000-000000000123",
        top_k=2,
    )
    state["intent"] = "experiment_lookup"
    state["required_agents"] = ["retrieval"]

    response = map_agent_state_to_ask_response(state)

    assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER


def test_map_agent_state_includes_citations_metrics_and_trace() -> None:
    state = build_agent_state()

    response = map_agent_state_to_ask_response(state)

    assert response.citations[0]["experiment_id"] == "00000000-0000-0000-0000-000000000123"
    assert response.retrieval_metrics["retrieved_chunks"] == 1
    assert response.agent_metrics["retrieval"]["average_similarity"] == 0.91
    assert response.agent_trace[0]["node"] == "planner"
    assert response.approval_status == "pending"


def test_map_agent_state_returns_partial_result_when_agent_errors_exist() -> None:
    state = build_agent_state()
    state["executive_summary"]["summary"] = ""
    state["errors"] = [
        {
            "code": "risk_assessment_failed",
            "message": "risk step failed",
            "node": "risk_assessment",
            "at": "2026-07-09T00:00:00Z",
        }
    ]

    response = map_agent_state_to_ask_response(state)

    assert response.answer == "Positive lift outweighed manageable rollout risk."
    assert response.agent_trace
    assert response.agent_metrics


def test_agent_workflow_ask_service_returns_404_for_unknown_experiment() -> None:
    async def experiment_exists(_: str) -> bool:
        return False

    service = AgentWorkflowAskService(
        StubWorkflowService(build_agent_state()),
        experiment_exists=experiment_exists,
    )

    with pytest.raises(UnknownExperimentError, match="was not found"):
        asyncio.run(
            service.answer(
                AskRequest(
                    question="What happened?",
                    experiment_id="00000000-0000-0000-0000-000000000999",
                    top_k=3,
                )
            )
        )


def test_agent_workflow_ask_service_supports_workflow_using_asyncio_run() -> None:
    async def experiment_exists(_: str) -> bool:
        return True

    service = AgentWorkflowAskService(
        AsyncioRunWorkflowService(build_agent_state()),
        experiment_exists=experiment_exists,
    )

    response = asyncio.run(
        service.answer(
            AskRequest(
                question="What happened?",
                experiment_id="00000000-0000-0000-0000-000000000123",
                top_k=3,
            )
        )
    )

    assert response.answer == "Rollout is supported by the current evidence."


def test_get_ask_mode_defaults_to_agent_workflow(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)

    assert get_ask_mode() == "agent_workflow"


def test_get_ask_mode_allows_legacy_rag(monkeypatch) -> None:
    monkeypatch.setenv("ASK_MODE", "legacy_rag")

    assert get_ask_mode() == "legacy_rag"
