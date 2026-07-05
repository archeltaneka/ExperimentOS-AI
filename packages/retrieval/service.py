from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Document, DocumentChunk, Experiment
from packages.ingestion.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class RetrievalResult:
    chunk_text: str
    similarity_score: float
    document_id: uuid.UUID
    experiment_id: uuid.UUID
    metadata: dict[str, Any]
    experiment_name: str | None = None
    document_title: str | None = None


class RetrievalService:
    def __init__(self, session: AsyncSession, embedding_provider: EmbeddingProvider) -> None:
        self.session = session
        self.embedding_provider = embedding_provider

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
            return []

        query_embedding = self._embed_query(normalized_query)
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

        rows = (await self.session.execute(stmt)).all()
        return [
            RetrievalResult(
                chunk_text=chunk.chunk_text,
                similarity_score=1.0 - float(distance_value),
                document_id=document.id,
                experiment_id=experiment.id,
                metadata=dict(chunk.chunk_metadata),
                experiment_name=experiment.name,
                document_title=document.title,
            )
            for chunk, document, experiment, distance_value in rows
        ]

    def _embed_query(self, query: str) -> list[float]:
        embeddings = self.embedding_provider.embed_texts([query])
        if len(embeddings) != 1:
            raise RuntimeError("embedding provider must return one embedding for one query")
        return embeddings[0]
