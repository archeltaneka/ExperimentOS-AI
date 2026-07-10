from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Document, DocumentChunk, Experiment
from packages.ingestion.embeddings import EmbeddingProvider
from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider


@dataclass(frozen=True)
class RetrievalResult:
    experiment_id: str
    metadata: dict[str, Any]
    experiment_name: str
    document_id: str
    document_name: str
    chunk_text: str
    similarity: float

    @property
    def similarity_score(self) -> float:
        return self.similarity

    @property
    def document_title(self) -> str:
        return self.document_name


@dataclass(frozen=True)
class RetrievalMetrics:
    embedding_time_ms: float
    vector_search_time_ms: float
    retrieved_chunks: int
    average_similarity: float


class RetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        *,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.session = session
        self.embedding_provider = embedding_provider
        self.last_metrics: RetrievalMetrics | None = None
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        return await self._search(
            query,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

    async def search_by_experiment(
        self,
        experiment_id: uuid.UUID | str,
        query: str,
        *,
        top_k: int = 5,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        return await self._search(
            query,
            top_k=top_k,
            experiment_id=uuid.UUID(str(experiment_id)),
            metadata_filter=metadata_filter,
        )

    async def _search(
        self,
        query: str,
        *,
        top_k: int,
        experiment_id: uuid.UUID | None = None,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k < 1:
            self.last_metrics = RetrievalMetrics(
                embedding_time_ms=0.0,
                vector_search_time_ms=0.0,
                retrieved_chunks=0,
                average_similarity=0.0,
            )
            return []

        span = self.observability_provider.start_span(
            "retrieval",
            run_type="retriever",
            inputs={
                "query": normalized_query,
                "top_k": top_k,
                "experiment_id": str(experiment_id) if experiment_id is not None else "",
                "metadata_filter": dict(metadata_filter or {}),
            },
            metadata={
                "embedding_provider": self.embedding_provider.__class__.__name__,
                "embedding_model": str(getattr(self.embedding_provider, "model", "unknown")),
            },
        )
        with span.activate():
            try:
                return await self._execute_search(
                    normalized_query,
                    top_k=top_k,
                    experiment_id=experiment_id,
                    metadata_filter=metadata_filter,
                    span=span,
                )
            except Exception as exc:
                span.record_error(exc, details={"surface": "retrieval"})
                span.finish(outputs={"status": "failed"})
                raise

    async def _execute_search(
        self,
        normalized_query: str,
        *,
        top_k: int,
        experiment_id: uuid.UUID | None = None,
        metadata_filter: Mapping[str, Any] | None = None,
        span,
    ) -> list[RetrievalResult]:

        embedding_started_at = perf_counter()
        query_embedding = self._embed_query(normalized_query)
        embedding_time_ms = (perf_counter() - embedding_started_at) * 1000.0

        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(DocumentChunk, Document, Experiment, distance)
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(Experiment, Document.experiment_id == Experiment.id)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )

        if experiment_id is not None:
            stmt = stmt.where(Document.experiment_id == experiment_id)
        if metadata_filter:
            stmt = stmt.where(DocumentChunk.chunk_metadata.contains(dict(metadata_filter)))

        search_started_at = perf_counter()
        rows = (await self.session.execute(stmt)).all()
        vector_search_time_ms = (perf_counter() - search_started_at) * 1000.0
        results = [
            RetrievalResult(
                experiment_id=str(experiment.id),
                metadata=dict(chunk.chunk_metadata),
                experiment_name=experiment.name,
                document_id=str(document.id),
                document_name=document.title or document.source_uri,
                chunk_text=chunk.chunk_text,
                similarity=1.0 - float(distance_value),
            )
            for chunk, document, experiment, distance_value in rows
        ]
        average_similarity = (
            sum(result.similarity_score for result in results) / len(results) if results else 0.0
        )
        self.last_metrics = RetrievalMetrics(
            embedding_time_ms=embedding_time_ms,
            vector_search_time_ms=vector_search_time_ms,
            retrieved_chunks=len(results),
            average_similarity=average_similarity,
        )
        span.add_metadata(
            {
                "retrieved_count": len(results),
                "empty_retrieval": not results,
                "average_similarity": average_similarity,
                "embedding_time_ms": embedding_time_ms,
                "vector_search_time_ms": vector_search_time_ms,
            }
        )
        span.finish(
            outputs={
                "retrieved_chunks": len(results),
                "average_similarity": average_similarity,
                "status": "completed",
            }
        )
        return results

    def _embed_query(self, query: str) -> list[float]:
        embeddings = self.embedding_provider.embed_texts([query])
        if len(embeddings) != 1:
            raise RuntimeError("embedding provider must return one embedding for one query")
        return embeddings[0]
