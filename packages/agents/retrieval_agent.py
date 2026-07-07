from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from packages.agents.state import (
    AgentState,
    AgentStateUpdate,
    Citation,
    RetrievedChunk,
    create_error_entry,
    create_trace_entry,
)
from packages.config.env import resolve_setting
from packages.db.session import create_async_session_factory, create_database_engine
from packages.ingestion.embeddings import build_embedding_provider
from packages.ingestion.load_experiment import run_async
from packages.retrieval.service import RetrievalMetrics, RetrievalResult, RetrievalService

RETRIEVAL_NODE = "retrieval"
DEFAULT_TOP_K = 5


class RetrievalClient(Protocol):
    last_metrics: RetrievalMetrics | None

    async def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        metadata_filter: Mapping[str, object] | None = None,
    ) -> list[RetrievalResult]:
        pass

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        metadata_filter: Mapping[str, object] | None = None,
    ) -> list[RetrievalResult]:
        pass


@dataclass
class RuntimeRetrievalClient:
    embedding_provider: str | None = None

    def __post_init__(self) -> None:
        self.last_metrics: RetrievalMetrics | None = None

    async def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        metadata_filter: Mapping[str, object] | None = None,
    ) -> list[RetrievalResult]:
        return await self._run_search(
            query=query,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        metadata_filter: Mapping[str, object] | None = None,
    ) -> list[RetrievalResult]:
        return await self._run_search(
            query=query,
            top_k=top_k,
            experiment_id=experiment_id,
            metadata_filter=metadata_filter,
        )

    async def _run_search(
        self,
        *,
        query: str,
        top_k: int,
        experiment_id: str | None = None,
        metadata_filter: Mapping[str, object] | None = None,
    ) -> list[RetrievalResult]:
        provider = build_embedding_provider(self._resolved_embedding_provider())
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                service = RetrievalService(session, provider)
                if experiment_id is None:
                    results = await service.search(
                        query,
                        top_k=top_k,
                        metadata_filter=metadata_filter,
                    )
                else:
                    results = await service.search_by_experiment(
                        experiment_id,
                        query,
                        top_k=top_k,
                        metadata_filter=metadata_filter,
                    )
                self.last_metrics = service.last_metrics
                return results
        finally:
            await engine.dispose()

    def _resolved_embedding_provider(self) -> str:
        return resolve_setting(
            self.embedding_provider,
            env_var="EMBEDDING_PROVIDER",
            default="auto",
            lowercase=True,
        )


@dataclass
class RetrievalAgent:
    client: RetrievalClient | None = None
    top_k: int = DEFAULT_TOP_K

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = RuntimeRetrievalClient()

    def run(self, state: AgentState) -> AgentStateUpdate:
        trace = [create_trace_entry(node=RETRIEVAL_NODE, event="started")]
        try:
            results = run_async(self._search(state))
        except Exception as exc:
            return {
                "retrieved_chunks": [],
                "citations": [],
                "errors": [
                    create_error_entry(
                        code="retrieval_failed",
                        message=f"Retrieval failed: {exc}",
                        node=RETRIEVAL_NODE,
                        details={"error_type": type(exc).__name__},
                    )
                ],
                "trace": [
                    *trace,
                    create_trace_entry(
                        node=RETRIEVAL_NODE,
                        event="failed",
                        details={"error_type": type(exc).__name__},
                    ),
                ],
            }

        metrics = _metrics_to_state(self.client.last_metrics, results)
        return {
            "retrieved_chunks": [_result_to_chunk(result) for result in results],
            "citations": [_result_to_citation(result) for result in results],
            "metrics": {**state["metrics"], "retrieval": metrics},
            "errors": [],
            "trace": [
                *trace,
                create_trace_entry(
                    node=RETRIEVAL_NODE,
                    event="completed",
                    details={"retrieved_chunks": len(results)},
                ),
            ],
        }

    async def _search(self, state: AgentState) -> list[RetrievalResult]:
        metadata_filter = _metadata_filter(state)
        experiment_ids = state["experiment_context"]["experiment_ids"]
        query = state["request"]["normalized_question"]
        if len(experiment_ids) == 1:
            return await self.client.search_by_experiment(
                experiment_ids[0],
                query,
                top_k=self.top_k,
                metadata_filter=metadata_filter,
            )
        return await self.client.search(
            query,
            top_k=self.top_k,
            metadata_filter=metadata_filter,
        )


def _metadata_filter(state: AgentState) -> dict[str, object] | None:
    metadata_filter = state["experiment_context"]["filters"]
    return metadata_filter or None


def _result_to_chunk(result: RetrievalResult) -> RetrievedChunk:
    return {
        "document_id": result.document_id,
        "experiment_id": result.experiment_id,
        "content": result.chunk_text,
        "score": result.similarity_score,
        "metadata": dict(result.metadata),
    }


def _result_to_citation(result: RetrievalResult) -> Citation:
    return {
        "document_id": result.document_id,
        "experiment_id": result.experiment_id,
        "quote": result.chunk_text,
        "section": _metadata_section(result.metadata),
        "metadata": dict(result.metadata),
    }


def _metadata_section(metadata: Mapping[str, Any]) -> str:
    section = metadata.get("section")
    return str(section) if section else ""


def _metrics_to_state(
    metrics: RetrievalMetrics | None,
    results: list[RetrievalResult],
) -> dict[str, float | int]:
    if metrics is not None:
        return asdict(metrics)
    retrieved_chunks = len(results)
    average_similarity = (
        sum(result.similarity_score for result in results) / retrieved_chunks
        if retrieved_chunks
        else 0.0
    )
    return {
        "embedding_time_ms": 0.0,
        "vector_search_time_ms": 0.0,
        "retrieved_chunks": retrieved_chunks,
        "average_similarity": average_similarity,
    }
