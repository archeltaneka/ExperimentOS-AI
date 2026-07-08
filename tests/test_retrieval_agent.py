from __future__ import annotations

import uuid

import pytest

from packages.agents.state import create_initial_state
from packages.retrieval.service import RetrievalMetrics, RetrievalResult


class StubRetrievalClient:
    def __init__(
        self,
        *,
        results: list[RetrievalResult],
        metrics: RetrievalMetrics | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.results = results
        self.failure = failure
        self.last_metrics = metrics
        self.calls: list[tuple[str, list[str], dict[str, object]]] = []

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        metadata_filter: dict[str, object] | None = None,
    ) -> list[RetrievalResult]:
        self.calls.append((query, [], metadata_filter or {}))
        if self.failure is not None:
            raise self.failure
        return self.results

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = 5,
        metadata_filter: dict[str, object] | None = None,
    ) -> list[RetrievalResult]:
        self.calls.append((query, [str(experiment_id)], metadata_filter or {}))
        if self.failure is not None:
            raise self.failure
        return self.results


def build_result(*, section: str = "Results") -> RetrievalResult:
    return RetrievalResult(
        experiment_id=str(uuid.uuid4()),
        experiment_name="Payment Recommendation Launch",
        document_id=str(uuid.uuid4()),
        document_name="Launch Report",
        chunk_text="Guardrails passed and conversion improved.",
        similarity=0.93,
        metadata={"section": section, "source": "report"},
    )


def build_retrieval_agent(client: StubRetrievalClient):
    from packages.agents.retrieval_agent import RetrievalAgent

    return RetrievalAgent(client=client)


def test_retrieval_agent_maps_results_citations_metrics_and_trace() -> None:
    state = create_initial_state("What happened in the payment recommendation experiment?")
    state["required_agents"] = ["retrieval"]
    state["metrics"] = {"planner": {"latency_ms": 12.0}}
    state["experiment_context"] = {
        "experiment_ids": [],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }

    client = StubRetrievalClient(
        results=[build_result()],
        metrics=RetrievalMetrics(
            embedding_time_ms=4.0,
            vector_search_time_ms=8.0,
            retrieved_chunks=1,
            average_similarity=0.93,
        ),
    )

    # Synchronous facade expected by the LangGraph retrieval node.
    update = build_retrieval_agent(client).run(state)

    assert update["retrieved_chunks"][0]["content"] == (
        "Guardrails passed and conversion improved."
    )
    assert update["retrieved_chunks"][0]["document_id"] == client.results[0].document_id
    assert update["retrieved_chunks"][0]["experiment_id"] == client.results[0].experiment_id
    assert update["retrieved_chunks"][0]["score"] == 0.93
    assert update["citations"][0]["quote"] == "Guardrails passed and conversion improved."
    assert update["citations"][0]["document_id"] == client.results[0].document_id
    assert update["citations"][0]["experiment_id"] == client.results[0].experiment_id
    assert update["citations"][0]["section"] == "Results"
    assert update["metrics"]["retrieval"]["embedding_time_ms"] == 4.0
    assert update["metrics"]["retrieval"]["vector_search_time_ms"] == 8.0
    assert update["metrics"]["retrieval"]["retrieved_chunks"] == 1
    assert update["metrics"]["retrieval"]["average_similarity"] == 0.93
    assert update["metrics"]["planner"] == {"latency_ms": 12.0}
    assert [entry["node"] for entry in update["trace"]] == ["retrieval", "retrieval"]
    assert [entry["event"] for entry in update["trace"]] == ["started", "completed"]
    assert update["errors"] == []


def test_retrieval_agent_uses_experiment_scoped_search_when_single_experiment_id_present() -> None:
    experiment_id = str(uuid.uuid4())
    state = create_initial_state("What happened?")
    state["required_agents"] = ["retrieval"]
    state["experiment_context"] = {
        "experiment_ids": [experiment_id],
        "filters": {},
    }

    client = StubRetrievalClient(results=[build_result()])

    build_retrieval_agent(client).run(state)

    assert client.calls == [("What happened?", [experiment_id], {})]


def test_retrieval_agent_uses_normalized_question_from_request() -> None:
    state = create_initial_state("  What happened?  ")
    state["required_agents"] = ["retrieval"]
    state["request"]["normalized_question"] = "What happened?"

    client = StubRetrievalClient(results=[build_result()])

    build_retrieval_agent(client).run(state)

    assert client.calls == [("What happened?", [], {})]


def test_retrieval_agent_captures_structured_errors_without_raising() -> None:
    state = create_initial_state("What happened?")
    state["required_agents"] = ["retrieval"]

    update = build_retrieval_agent(
        StubRetrievalClient(results=[], failure=RuntimeError("vector search failed"))
    ).run(state)

    assert update["retrieved_chunks"] == []
    assert update["citations"] == []
    assert update["errors"][0]["code"] == "retrieval_failed"
    assert update["errors"][0]["node"] == "retrieval"
    assert "vector search failed" in update["errors"][0]["message"]
    assert [entry["node"] for entry in update["trace"]] == ["retrieval", "retrieval"]
    assert [entry["event"] for entry in update["trace"]] == ["started", "failed"]


def test_runtime_retrieval_client_builds_provider_before_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from packages.agents import retrieval_agent

    engine_created = False

    def fake_build_embedding_provider(provider: str) -> object:
        raise RuntimeError(f"provider setup failed for {provider}")

    def fake_create_database_engine() -> object:
        nonlocal engine_created
        engine_created = True
        raise AssertionError("engine should not be created before provider succeeds")

    monkeypatch.setattr(retrieval_agent, "build_embedding_provider", fake_build_embedding_provider)
    monkeypatch.setattr(retrieval_agent, "create_database_engine", fake_create_database_engine)

    client = retrieval_agent.RuntimeRetrievalClient(embedding_provider="fake")

    with pytest.raises(RuntimeError, match="provider setup failed for fake"):
        retrieval_agent.run_async(client.search("What happened?"))

    assert engine_created is False
