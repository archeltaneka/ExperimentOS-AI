from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from packages.db.session import create_async_session_factory, create_database_engine
from packages.ingestion.embeddings import build_embedding_provider
from packages.ingestion.load_experiment import run_async
from packages.retrieval.service import RetrievalResult, RetrievalService


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
    experiment = result.experiment_name or str(result.experiment_id)
    document = result.document_title or str(result.document_id)
    metadata = json.dumps(result.metadata, sort_keys=True)
    return "\n".join(
        [
            f"Similarity Score: {result.similarity_score:.4f}",
            f"Experiment: {experiment} ({result.experiment_id})",
            f"Document: {document} ({result.document_id})",
            "Retrieved Chunk:",
            result.chunk_text,
            "Metadata:",
            metadata,
        ]
    )


async def _run_cli(
    *,
    query: str,
    top_k: int,
    experiment_id: uuid.UUID | None,
    embedding_provider: str,
    metadata_filter: dict[str, Any],
) -> list[RetrievalResult]:
    engine = create_database_engine()
    session_factory = create_async_session_factory(engine)
    provider = build_embedding_provider(embedding_provider)
    try:
        async with session_factory() as session:
            service = RetrievalService(session, provider)
            if experiment_id is None:
                return await service.search(
                    query,
                    top_k=top_k,
                    metadata_filter=metadata_filter or None,
                )
            return await service.search_by_experiment(
                experiment_id,
                query,
                top_k=top_k,
                metadata_filter=metadata_filter or None,
            )
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
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
        choices=("auto", "fake", "openai"),
        default="auto",
        help=(
            "Embedding provider to use. 'auto' uses OpenAI when OPENAI_API_KEY is set, "
            "otherwise deterministic fake embeddings."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        metadata_filter = parse_metadata_filter(args.metadata)
        results = run_async(
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


if __name__ == "__main__":
    main()
