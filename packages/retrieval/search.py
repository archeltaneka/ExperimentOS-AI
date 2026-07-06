from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from packages.db.session import create_async_session_factory, create_database_engine
from packages.ingestion.embeddings import build_embedding_provider
from packages.ingestion.load_experiment import run_async
from packages.retrieval.service import RetrievalMetrics, RetrievalResult, RetrievalService


def parse_metadata_filter(values: list[str]) -> dict[str, Any]:
    metadata_filter: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("metadata filters must use key=value format")
        key, raw_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("metadata filter keys must not be empty")
        metadata_filter[key] = raw_value.strip()
    return metadata_filter


def format_result(result: RetrievalResult) -> str:
    metadata = json.dumps(result.metadata, sort_keys=True)
    return "\n".join(
        [
            f"Similarity Score: {result.similarity:.4f}",
            f"Experiment: {result.experiment_name} ({result.experiment_id})",
            f"Document: {result.document_name} ({result.document_id})",
            "Retrieved Chunk:",
            result.chunk_text,
            "Metadata:",
            metadata,
        ]
    )


def format_metrics(metrics: RetrievalMetrics) -> str:
    return "\n".join(
        [
            f"Embedding Time: {metrics.embedding_time_ms:.0f} ms",
            f"Vector Search: {metrics.vector_search_time_ms:.0f} ms",
            f"Retrieved Chunks: {metrics.retrieved_chunks}",
            f"Average Similarity: {metrics.average_similarity:.2f}",
        ]
    )


async def _run_cli(
    *,
    query: str,
    top_k: int,
    experiment_id: uuid.UUID | None,
    embedding_provider: str,
    metadata_filter: dict[str, Any],
) -> tuple[list[RetrievalResult], RetrievalMetrics]:
    engine = create_database_engine()
    session_factory = create_async_session_factory(engine)
    provider = build_embedding_provider(embedding_provider)
    try:
        async with session_factory() as session:
            service = RetrievalService(session, provider)
            if experiment_id is None:
                results = await service.search(
                    query,
                    top_k=top_k,
                    metadata_filter=metadata_filter or None,
                )
            else:
                results = await service.search_by_experiment(
                    experiment_id,
                    query,
                    top_k=top_k,
                    metadata_filter=metadata_filter or None,
                )
            if service.last_metrics is None:
                raise RuntimeError("retrieval metrics were not recorded")
            return results, service.last_metrics
    finally:
        await engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search experiment document chunks with pgvector.")
    parser.add_argument(
        "--query",
        required=True,
        help="Search query to embed and retrieve against.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Maximum number of chunks to return.")
    parser.add_argument(
        "--experiment-id",
        type=uuid.UUID,
        help="Optional experiment UUID filter.",
    )
    parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        help="Optional chunk metadata filter in key=value format. Can be repeated.",
    )
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "fake", "openai", "gemini", "huggingface", "ollama"),
        default="auto",
        help=(
            "Embedding provider to use. 'auto' uses Gemini when GEMINI_API_KEY is set, "
            "OpenAI when OPENAI_API_KEY is set, otherwise deterministic fake embeddings. "
            "'gemini' uses gemini-embedding-001 by default. 'huggingface' uses "
            "BAAI/bge-small-en-v1.5. 'ollama' uses nomic-embed-text."
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        metadata_filter = parse_metadata_filter(args.metadata)
        results, metrics = run_async(
            _run_cli(
                query=args.query,
                top_k=args.top_k,
                experiment_id=args.experiment_id,
                embedding_provider=args.embedding_provider,
                metadata_filter=metadata_filter,
            )
        )
    except ValueError as exc:
        raise SystemExit(f"Input error: {exc}") from exc

    for index, result in enumerate(results):
        if index:
            print()
        print(format_result(result))

    if results:
        print()
    print(format_metrics(metrics))


if __name__ == "__main__":
    main()
