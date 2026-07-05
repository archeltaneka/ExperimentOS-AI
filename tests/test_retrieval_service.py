from __future__ import annotations

import os
import uuid
from collections.abc import Sequence
from typing import Any

import pytest
from sqlalchemy import delete

from packages.db.models import EMBEDDING_DIMENSION, Document, DocumentChunk, Experiment


class KeywordEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        normalized = text.lower()
        if "payment" in normalized or "recommendation" in normalized or "shipped" in normalized:
            vector[0] = 1.0
        elif "search" in normalized or "ranking" in normalized:
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        return vector


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_semantic_retrieval_returns_expected_experiment() -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import run_async
    from packages.retrieval.service import RetrievalService

    provider = KeywordEmbeddingProvider()

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            payment_id, _search_id = await seed_retrieval_fixtures(session_factory, provider)

            async with session_factory() as session:
                service = RetrievalService(session, provider)
                results = await service.search(
                    "Why was the payment recommendation shipped?",
                    top_k=1,
                )
        finally:
            await cleanup_retrieval_fixtures(session_factory)
            await engine.dispose()

        assert len(results) == 1
        assert results[0].experiment_id == str(payment_id)
        assert results[0].experiment_name == "Payment Recommendation Launch"
        assert "payment recommendation" in results[0].chunk_text
        assert results[0].similarity == pytest.approx(1.0)

    run_async(run_test())


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_experiment_filtering_limits_results() -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import run_async
    from packages.retrieval.service import RetrievalService

    provider = KeywordEmbeddingProvider()

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            _payment_id, search_id = await seed_retrieval_fixtures(session_factory, provider)

            async with session_factory() as session:
                service = RetrievalService(session, provider)
                results = await service.search_by_experiment(
                    search_id,
                    "Why was the payment recommendation shipped?",
                    top_k=5,
                )
        finally:
            await cleanup_retrieval_fixtures(session_factory)
            await engine.dispose()

        assert [result.experiment_id for result in results] == [str(search_id)]
        assert results[0].experiment_name == "Search Ranking Experiment"

    run_async(run_test())


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_top_k_behaves_correctly() -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import run_async
    from packages.retrieval.service import RetrievalService

    provider = KeywordEmbeddingProvider()

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            await seed_retrieval_fixtures(session_factory, provider)

            async with session_factory() as session:
                service = RetrievalService(session, provider)
                results = await service.search("payment recommendation", top_k=2)
                metrics = service.last_metrics
        finally:
            await cleanup_retrieval_fixtures(session_factory)
            await engine.dispose()

        assert len(results) == 2
        assert results[0].similarity >= results[1].similarity
        assert metrics is not None
        assert metrics.embedding_time_ms >= 0.0
        assert metrics.vector_search_time_ms >= 0.0
        assert metrics.retrieved_chunks == 2
        assert metrics.average_similarity == pytest.approx(
            sum(result.similarity for result in results) / len(results)
        )

    run_async(run_test())


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_empty_query_validation() -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import run_async
    from packages.retrieval.service import RetrievalService

    provider = KeywordEmbeddingProvider()

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                service = RetrievalService(session, provider)
                with pytest.raises(ValueError, match="query must not be empty"):
                    await service.search("   ")
        finally:
            await engine.dispose()

    run_async(run_test())


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_unknown_experiment_returns_empty_list() -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import run_async
    from packages.retrieval.service import RetrievalService

    provider = KeywordEmbeddingProvider()

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            await seed_retrieval_fixtures(session_factory, provider)

            async with session_factory() as session:
                service = RetrievalService(session, provider)
                results = await service.search_by_experiment(
                    uuid.uuid4(),
                    "payment recommendation",
                    top_k=5,
                )
        finally:
            await cleanup_retrieval_fixtures(session_factory)
            await engine.dispose()

        assert results == []

    run_async(run_test())


def test_cli_result_format_includes_required_labels() -> None:
    from packages.retrieval.search import format_result
    from packages.retrieval.service import RetrievalResult

    result = RetrievalResult(
        experiment_id=str(uuid.uuid4()),
        experiment_name="Payment Recommendation Launch",
        document_id=str(uuid.uuid4()),
        document_name="Launch Report",
        chunk_text="The payment recommendation was shipped after guardrails passed.",
        similarity=0.875,
        metadata={"section": "Decision"},
    )

    output = format_result(result)

    assert "Similarity Score: 0.8750" in output
    assert "Experiment: Payment Recommendation Launch" in output
    assert "Document: Launch Report" in output
    assert "Retrieved Chunk:" in output
    assert "Metadata:" in output


def test_retrieval_result_exposes_shared_contract_fields() -> None:
    from dataclasses import fields

    from packages.retrieval.service import RetrievalResult

    field_names = {field.name for field in fields(RetrievalResult)}

    assert {
        "experiment_id",
        "experiment_name",
        "document_name",
        "chunk_text",
        "similarity",
        "metadata",
    } <= field_names


def test_cli_metrics_format_includes_required_labels() -> None:
    from packages.retrieval.search import format_metrics
    from packages.retrieval.service import RetrievalMetrics

    metrics = RetrievalMetrics(
        embedding_time_ms=28.4,
        vector_search_time_ms=9.2,
        retrieved_chunks=5,
        average_similarity=0.84,
    )

    output = format_metrics(metrics)

    assert "Embedding Time: 28 ms" in output
    assert "Vector Search: 9 ms" in output
    assert "Retrieved Chunks: 5" in output
    assert "Average Similarity: 0.84" in output


def test_retrieval_cli_accepts_huggingface_provider() -> None:
    from packages.retrieval.search import parse_args

    args = parse_args(
        [
            "--query",
            "payment recommendation",
            "--embedding-provider",
            "huggingface",
        ]
    )

    assert args.embedding_provider == "huggingface"


async def seed_retrieval_fixtures(
    session_factory: Any,
    provider: KeywordEmbeddingProvider,
) -> tuple[uuid.UUID, uuid.UUID]:
    await cleanup_retrieval_fixtures(session_factory)

    async with session_factory() as session:
        async with session.begin():
            payment = Experiment(
                name="Payment Recommendation Launch",
                description="Payment experiment",
                config={"fixture": "retrieval-service"},
                status="completed",
            )
            search = Experiment(
                name="Search Ranking Experiment",
                description="Search experiment",
                config={"fixture": "retrieval-service"},
                status="completed",
            )
            session.add_all([payment, search])
            await session.flush()

            payment_document = Document(
                experiment_id=payment.id,
                source_uri="retrieval-fixture/payment.md",
                source_type="markdown",
                title="Payment Report",
                content="Payment report",
                document_metadata={"fixture": "retrieval-service"},
            )
            search_document = Document(
                experiment_id=search.id,
                source_uri="retrieval-fixture/search.md",
                source_type="markdown",
                title="Search Report",
                content="Search report",
                document_metadata={"fixture": "retrieval-service"},
            )
            session.add_all([payment_document, search_document])
            await session.flush()

            chunk_texts = [
                "The payment recommendation was shipped after conversion guardrails passed.",
                "The search ranking experiment improved result ordering.",
                "A neutral operations note about monitoring dashboards.",
            ]
            embeddings = provider.embed_texts(chunk_texts)
            session.add_all(
                [
                    DocumentChunk(
                        document_id=payment_document.id,
                        chunk_index=0,
                        chunk_text=chunk_texts[0],
                        token_count=8,
                        embedding=embeddings[0],
                        chunk_metadata={"section": "Decision", "fixture": "retrieval-service"},
                    ),
                    DocumentChunk(
                        document_id=search_document.id,
                        chunk_index=0,
                        chunk_text=chunk_texts[1],
                        token_count=8,
                        embedding=embeddings[1],
                        chunk_metadata={"section": "Results", "fixture": "retrieval-service"},
                    ),
                    DocumentChunk(
                        document_id=payment_document.id,
                        chunk_index=1,
                        chunk_text=chunk_texts[2],
                        token_count=8,
                        embedding=embeddings[2],
                        chunk_metadata={"section": "Monitoring", "fixture": "retrieval-service"},
                    ),
                ]
            )

        return payment.id, search.id


async def cleanup_retrieval_fixtures(session_factory: Any) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(Experiment).where(
                Experiment.name.in_(
                    [
                        "Payment Recommendation Launch",
                        "Search Ranking Experiment",
                    ]
                )
            )
        )
        await session.commit()
