from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi.testclient import TestClient

from apps.api.ask_service import AskResponse
from apps.api.main import app, get_ask_service, get_observability_provider
from packages.agents.service import AgentWorkflowService
from packages.agents.state import AgentState
from packages.llm.client import MockLLMClient
from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ObservabilitySettings
from packages.qa.question_answering_service import QuestionAnsweringService
from packages.retrieval.service import RetrievalMetrics, RetrievalResult


class RecordingObservabilityProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(
            ObservabilitySettings(
                enabled=True,
                api_key="ls-test-key",
                project="experimentos-test",
                sampling_rate=1.0,
                trace_inputs=True,
                trace_outputs=False,
            )
        )
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


class FailingObservabilityProvider(RecordingObservabilityProvider):
    def _emit_root(self, record: BufferedSpanRecord) -> None:
        raise RuntimeError("observability transport failed")


class StubRetrievalAgent:
    def run(self, state: AgentState):
        return {
            "retrieved_chunks": [
                {
                    "document_id": "doc-1",
                    "experiment_id": "exp-1",
                    "content": "Retrieved evidence.",
                    "score": 0.91,
                    "metadata": {"section": "Results"},
                }
            ],
            "citations": [
                {
                    "document_id": "doc-1",
                    "experiment_id": "exp-1",
                    "quote": "Retrieved evidence.",
                    "section": "Results",
                    "metadata": {"section": "Results"},
                }
            ],
            "metrics": {
                **state["metrics"],
                "retrieval": {
                    "embedding_time_ms": 4.0,
                    "vector_search_time_ms": 6.0,
                    "retrieved_chunks": 1,
                    "average_similarity": 0.91,
                },
            },
            "trace": [
                {"node": "retrieval", "event": "started", "at": "2026-07-10T00:00:00Z"},
                {"node": "retrieval", "event": "completed", "at": "2026-07-10T00:00:01Z"},
            ],
            "errors": [],
        }


class StubRetrievalService:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.last_metrics = RetrievalMetrics(
            embedding_time_ms=4.0,
            vector_search_time_ms=6.0,
            retrieved_chunks=len(results),
            average_similarity=0.91 if results else 0.0,
        )

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        return self.results


@dataclass
class StubAskService:
    response: AskResponse

    async def answer(self, request) -> AskResponse:
        return self.response


def test_agent_workflow_service_emits_workflow_and_node_spans() -> None:
    provider = RecordingObservabilityProvider()
    service = AgentWorkflowService(
        retrieval_agent=StubRetrievalAgent(),
        observability_provider=provider,
    )

    state = service.run("What happened in the payment recommendation experiment?")

    assert state["run_metadata"]["run_id"]
    assert provider.records
    workflow_record = provider.records[0]
    child_names = [child.name for child in workflow_record.children]
    assert workflow_record.name == "workflow"
    assert workflow_record.metadata["surface"] == "agent_workflow"
    assert workflow_record.metadata["experimentos_trace_id"] == state["run_metadata"]["run_id"]
    assert "planner" in child_names
    assert "retrieval" in child_names


def test_question_answering_service_emits_prompt_and_generation_metadata() -> None:
    provider = RecordingObservabilityProvider()
    result = RetrievalResult(
        experiment_id="exp-1",
        experiment_name="Payment Recommendation Launch",
        document_id="doc-1",
        document_name="Launch Report",
        chunk_text="Payment recommendation improved conversion.",
        similarity=0.91,
        metadata={"section": "Results"},
    )
    service = QuestionAnsweringService(
        retrieval_service=StubRetrievalService([result]),
        llm_client=MockLLMClient(answer="Roll out the treatment.", model="mock-answerer"),
        experiment_exists=lambda _experiment_id: asyncio.sleep(0, result=True),
        observability_provider=provider,
    )

    response = asyncio.run(
        service.answer_question(
            question="Why did it ship?",
            experiment_id="exp-1",
            top_k=3,
        )
    )

    assert response.prompt_id == "rag.answer"
    assert provider.records
    root = provider.records[0]
    child_names = [child.name for child in root.children]
    prompt_span = next(child for child in root.children if child.name == "prompt_rendering")
    assert root.name == "legacy_rag"
    assert "prompt_rendering" in child_names
    assert "llm_generation" in child_names
    assert prompt_span.metadata["prompt_id"] == "rag.answer"
    assert prompt_span.metadata["prompt_version"] == "1"


def test_ask_route_continues_when_observability_export_fails() -> None:
    provider = FailingObservabilityProvider()
    response_payload = AskResponse(
        answer="Rollout is supported.",
        citations=[],
        retrieved_chunks=[],
        retrieval_metrics={"embedding_time_ms": 0.0, "vector_search_time_ms": 0.0},
        llm_metrics={"model": "mock", "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0},
    )
    app.dependency_overrides[get_observability_provider] = lambda: provider
    app.dependency_overrides[get_ask_service] = lambda: StubAskService(response_payload)
    try:
        client = TestClient(app)
        response = client.post(
            "/ask",
            json={
                "question": "What happened?",
                "experiment_id": "00000000-0000-0000-0000-000000000123",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert provider.failure_count == 1


def test_agent_evaluation_run_emits_evaluation_root(monkeypatch) -> None:
    from packages.evals import run_agent

    provider = RecordingObservabilityProvider()
    monkeypatch.setattr(run_agent, "resolve_observability_provider", lambda: provider)
    args = run_agent.parse_args([])

    result = run_agent.build_evaluation_run(args)

    assert result.summary.sample_count > 0
    assert provider.records
    assert provider.records[0].name == "evaluation.agent"
