from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from apps.api.ask_service import (
    AgentWorkflowAskService,
    AskRequest,
    AskResponse,
    get_ask_mode,
    map_agent_state_to_ask_response,
)
from apps.api.main import (
    app,
    get_agent_workflow_service,
    get_ask_service,
    get_experiment_exists_dependency,
    get_question_answering_service,
)
from packages.agents.state import create_initial_state
from packages.llm.client import LLMMetrics
from packages.qa.question_answering_service import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    Citation,
    EmbeddingFailureError,
    LLMGenerationError,
    QAResponse,
    UnknownExperimentError,
)
from packages.retrieval.service import RetrievalMetrics, RetrievalResult


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
        self.calls: list[tuple[str, str | None, int]] = []

    def run(self, question: str, experiment_id: str | None = None, top_k: int = 5):
        self.calls.append((question, experiment_id, top_k))
        return self.state


class AsyncioRunWorkflowService:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state

    def run(self, question: str, experiment_id: str | None = None, top_k: int = 5):
        asyncio.run(asyncio.sleep(0))
        return self.state


class RaisingWorkflowService:
    def run(self, question: str, experiment_id: str | None = None, top_k: int = 5):
        raise RuntimeError("workflow exploded")


@dataclass
class StubQuestionAnsweringService:
    response: QAResponse
    calls: list[tuple[str, str, int]] = field(default_factory=list)

    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QAResponse:
        self.calls.append((question, experiment_id, top_k))
        return self.response


class ExplodingQuestionAnsweringService:
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QAResponse:
        raise AssertionError("legacy QA path should not be used")


async def always_true(_: str) -> bool:
    return True


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
        "approval_required": True,
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
        "planner": {"status": "planned", "latency_ms": 1.0},
        "retrieval": {
            "embedding_time_ms": 10.0,
            "vector_search_time_ms": 8.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.91,
        },
        "experiment_analysis": {"status": "completed", "latency_ms": 11.0},
        "business_impact": {"status": "estimated", "latency_ms": 12.0},
        "risk_assessment": {"status": "assessed", "latency_ms": 13.0},
        "decision": {"status": "decided", "latency_ms": 14.0},
        "human_approval": {"status": "pending", "latency_ms": 15.0},
        "executive_summary": {"status": "generated", "latency_ms": 16.0},
    }
    state["trace"] = [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "started", "at": "2026-07-09T00:00:01Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:02Z"},
        {"node": "experiment_analysis", "event": "started", "at": "2026-07-09T00:00:03Z"},
        {
            "node": "experiment_analysis",
            "event": "completed",
            "at": "2026-07-09T00:00:04Z",
        },
        {"node": "business_impact", "event": "started", "at": "2026-07-09T00:00:05Z"},
        {"node": "business_impact", "event": "completed", "at": "2026-07-09T00:00:06Z"},
        {"node": "risk_assessment", "event": "started", "at": "2026-07-09T00:00:07Z"},
        {"node": "risk_assessment", "event": "completed", "at": "2026-07-09T00:00:08Z"},
        {"node": "decision", "event": "started", "at": "2026-07-09T00:00:09Z"},
        {"node": "decision", "event": "completed", "at": "2026-07-09T00:00:10Z"},
        {"node": "human_approval", "event": "started", "at": "2026-07-09T00:00:11Z"},
        {"node": "human_approval", "event": "completed", "at": "2026-07-09T00:00:12Z"},
        {"node": "executive_summary", "event": "started", "at": "2026-07-09T00:00:13Z"},
        {
            "node": "executive_summary",
            "event": "completed",
            "at": "2026-07-09T00:00:14Z",
        },
    ]
    return state


def build_executive_summary_state() -> dict[str, object]:
    state = build_agent_state(
        question="Summarize the payment recommendation experiment for executives."
    )
    state["intent"] = "executive_summary"
    state["experiment_analysis"]["summary"] = "Payment recommendation improved the primary metric."
    state["executive_summary"] = {
        **state["executive_summary"],
        "headline": "Rollout is supported by the current evidence.",
        "summary": "Executives should proceed with a monitored rollout.",
    }
    return state


def build_lookup_state() -> dict[str, object]:
    experiment_id = "00000000-0000-0000-0000-000000000123"
    state = create_initial_state(
        "What happened in the hotel image quality experiment?",
        experiment_id=experiment_id,
        top_k=2,
    )
    state["intent"] = "experiment_lookup"
    state["required_agents"] = ["retrieval"]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-lookup-1",
            "experiment_id": experiment_id,
            "content": "Hotel image quality treatment improved booking conversion.",
            "score": 0.88,
            "metadata": {"section": "Results", "document_name": "Hotel Report"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-lookup-1",
            "experiment_id": experiment_id,
            "quote": "Hotel image quality treatment improved booking conversion.",
            "section": "Results",
            "metadata": {"section": "Results", "document_name": "Hotel Report"},
        }
    ]
    state["metrics"] = {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {
            "embedding_time_ms": 6.0,
            "vector_search_time_ms": 5.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.88,
        },
    }
    state["trace"] = [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "started", "at": "2026-07-09T00:00:01Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:02Z"},
        {
            "node": "experiment_analysis",
            "event": "skipped",
            "at": "2026-07-09T00:00:03Z",
            "details": {"reason": "not_required"},
        },
        {
            "node": "business_impact",
            "event": "skipped",
            "at": "2026-07-09T00:00:04Z",
            "details": {"reason": "not_required"},
        },
        {
            "node": "risk_assessment",
            "event": "skipped",
            "at": "2026-07-09T00:00:05Z",
            "details": {"reason": "not_required"},
        },
        {
            "node": "decision",
            "event": "skipped",
            "at": "2026-07-09T00:00:06Z",
            "details": {"reason": "not_required"},
        },
        {
            "node": "human_approval",
            "event": "skipped",
            "at": "2026-07-09T00:00:07Z",
            "details": {"reason": "not_required"},
        },
        {
            "node": "executive_summary",
            "event": "skipped",
            "at": "2026-07-09T00:00:08Z",
            "details": {"reason": "not_required"},
        },
    ]
    return state


def build_legacy_qa_response() -> QAResponse:
    return QAResponse(
        answer="Legacy grounded answer.",
        citations=[
            Citation(
                experiment_id="00000000-0000-0000-0000-000000000123",
                document="Legacy Report",
                similarity=0.87,
            )
        ],
        retrieved_chunks=[
            RetrievalResult(
                experiment_id="00000000-0000-0000-0000-000000000123",
                experiment_name="Legacy Experiment",
                document_id="legacy-doc-1",
                document_name="Legacy Report",
                chunk_text="Legacy evidence chunk.",
                similarity=0.87,
                metadata={"section": "Results"},
            )
        ],
        retrieval_metrics=RetrievalMetrics(
            embedding_time_ms=1.0,
            vector_search_time_ms=2.0,
            retrieved_chunks=1,
            average_similarity=0.87,
        ),
        llm_metrics=LLMMetrics(
            model="mock",
            input_tokens=12,
            output_tokens=4,
            latency_ms=0.0,
        ),
        prompt_id="rag.answer",
        prompt_version="1",
    )


def test_ask_endpoint_uses_agent_workflow_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    client = TestClient(app)
    workflow_service = StubWorkflowService(build_agent_state())
    app.dependency_overrides[get_agent_workflow_service] = lambda: workflow_service
    app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
    app.dependency_overrides[get_question_answering_service] = ExplodingQuestionAnsweringService
    try:
        response = client.post(
            "/ask",
            json={
                "question": "Should we roll out the loyalty tier progress nudges experiment?",
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
    assert response.json()["prompt_metadata"] is None
    assert workflow_service.calls == [
        (
            "Should we roll out the loyalty tier progress nudges experiment?",
            "00000000-0000-0000-0000-000000000123",
            3,
        )
    ]


def test_ask_endpoint_uses_legacy_rag_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("ASK_MODE", "legacy_rag")
    client = TestClient(app)
    qa_service = StubQuestionAnsweringService(build_legacy_qa_response())
    app.dependency_overrides[get_question_answering_service] = lambda: qa_service
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
    assert response.json()["prompt_metadata"] == {"prompt_id": "rag.answer", "prompt_version": "1"}
    assert response.json()["decision"] is None
    assert response.json()["executive_summary"] is None
    assert qa_service.calls == [("What happened?", "00000000-0000-0000-0000-000000000123", 5)]


def test_ask_endpoint_returns_executive_summary_when_requested(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    client = TestClient(app)
    app.dependency_overrides[get_agent_workflow_service] = lambda: StubWorkflowService(
        build_executive_summary_state()
    )
    app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
    try:
        response = client.post(
            "/ask",
            json={
                "question": "Summarize the payment recommendation experiment for executives.",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["intent"] == "executive_summary"
    assert response.json()["executive_summary"]["summary_status"] == "generated"
    assert response.json()["answer"] == "Executives should proceed with a monitored rollout."


def test_ask_endpoint_retrieval_only_query_skips_decision_artifacts(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    client = TestClient(app)
    app.dependency_overrides[get_agent_workflow_service] = lambda: StubWorkflowService(
        build_lookup_state()
    )
    app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
    try:
        response = client.post(
            "/ask",
            json={
                "question": "What happened in the hotel image quality experiment?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 2,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["intent"] == "experiment_lookup"
    assert response.json()["required_agents"] == ["retrieval"]
    assert response.json()["decision"]["decision_status"] == "not_required"
    assert response.json()["executive_summary"]["summary_status"] == "not_required"
    assert response.json()["answer"] == "Hotel image quality treatment improved booking conversion."


def test_ask_endpoint_includes_expected_trace_order_for_decision_support(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    client = TestClient(app)
    app.dependency_overrides[get_agent_workflow_service] = lambda: StubWorkflowService(
        build_agent_state()
    )
    app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
    try:
        response = client.post(
            "/ask",
            json={
                "question": "What are the risks of launching the checkout UX experiment?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    trace_nodes = [
        entry["node"]
        for entry in response.json()["agent_trace"]
        if entry["event"] in {"planned", "completed"}
    ]

    assert response.status_code == 200
    assert trace_nodes == [
        "planner",
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]


def test_ask_endpoint_includes_per_agent_metrics(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    client = TestClient(app)
    app.dependency_overrides[get_agent_workflow_service] = lambda: StubWorkflowService(
        build_agent_state()
    )
    app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
    try:
        response = client.post(
            "/ask",
            json={
                "question": "What is the business impact of the search ranking experiment?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    metrics = response.json()["agent_metrics"]

    assert response.status_code == 200
    assert metrics["retrieval"]["retrieved_chunks"] == 1
    assert metrics["experiment_analysis"]["status"] == "completed"
    assert metrics["business_impact"]["status"] == "estimated"
    assert metrics["risk_assessment"]["status"] == "assessed"
    assert metrics["decision"]["status"] == "decided"
    assert metrics["human_approval"]["status"] == "pending"
    assert metrics["executive_summary"]["status"] == "generated"


def test_ask_endpoint_surfaces_pending_approval_without_input(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    client = TestClient(app)
    app.dependency_overrides[get_agent_workflow_service] = lambda: StubWorkflowService(
        build_agent_state()
    )
    app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
    try:
        response = client.post(
            "/ask",
            json={
                "question": "Should we roll out the loyalty tier progress nudges experiment?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["decision"]["approval_required"] is True
    assert response.json()["approval_status"] == "pending"


def test_ask_endpoint_returns_502_for_agent_workflow_failure(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    client = TestClient(app)
    app.dependency_overrides[get_agent_workflow_service] = RaisingWorkflowService
    app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
    try:
        response = client.post(
            "/ask",
            json={
                "question": "Should we roll out the loyalty tier progress nudges experiment?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "workflow exploded"}


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
