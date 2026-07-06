from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Experiment
from packages.db.session import create_async_session_factory, create_database_engine
from packages.evals.dataset import DEFAULT_DATASET_PATH, EvaluationQuestion, load_evaluation_dataset
from packages.evals.evaluator import OfflineEvaluator
from packages.evals.report import render_evaluation_report
from packages.ingestion.embeddings import (
    BGE_SMALL_EN_MODEL,
    OLLAMA_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    build_embedding_provider,
)
from packages.ingestion.load_experiment import run_async
from packages.llm.client import OLLAMA_LLM_MODEL, MockLLMClient, OllamaLLMClient, OpenAILLMClient
from packages.qa.question_answering_service import QuestionAnsweringService
from packages.retrieval.service import RetrievalService

DEFAULT_REPORT_PATH = Path("reports/evaluation.md")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline QA evaluation harness.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path where the Markdown evaluation report should be written.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve.")
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "fake", "openai", "huggingface", "ollama"),
        default="auto",
        help="Embedding provider to use for retrieval.",
    )
    parser.add_argument(
        "--embedding-model",
        default=OLLAMA_EMBEDDING_MODEL,
        help="Embedding model name. Used by --embedding-provider=ollama.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=("mock", "openai", "ollama"),
        default="mock",
        help="LLM provider to use for answer generation.",
    )
    parser.add_argument(
        "--llm-model",
        default=OLLAMA_LLM_MODEL,
        help="LLM model name. Defaults to qwen2.5:7b for --llm-provider=ollama.",
    )
    parser.add_argument(
        "--input-cost-per-1k-tokens",
        type=float,
        default=0.0,
        help="Optional input-token cost rate for estimated cost reporting.",
    )
    parser.add_argument(
        "--output-cost-per-1k-tokens",
        type=float,
        default=0.0,
        help="Optional output-token cost rate for estimated cost reporting.",
    )
    return parser.parse_args(argv)


async def run_evaluation(args: argparse.Namespace) -> str:
    questions = load_evaluation_dataset(args.dataset)
    engine = create_database_engine()
    session_factory = create_async_session_factory(engine)
    provider = build_embedding_provider(
        args.embedding_provider,
        model=args.embedding_model if args.embedding_provider == "ollama" else None,
    )
    try:
        async with session_factory() as session:
            experiment_id_map = await _load_experiment_id_map(session)
            service = QuestionAnsweringService(
                retrieval_service=RetrievalService(session, provider),
                llm_client=_build_llm_client(args),
                experiment_exists=lambda experiment_id: _experiment_exists(session, experiment_id),
            )
            evaluator = OfflineEvaluator(
                qa_service=service,
                questions=questions,
                top_k=args.top_k,
                experiment_id_resolver=lambda question: _resolve_experiment_id(
                    question,
                    experiment_id_map,
                ),
                input_cost_per_1k_tokens=args.input_cost_per_1k_tokens,
                output_cost_per_1k_tokens=args.output_cost_per_1k_tokens,
                embedding_provider=args.embedding_provider,
                embedding_model=_embedding_model_label(args),
                llm_provider=args.llm_provider,
                llm_model=_llm_model_label(args),
            )
            result = await evaluator.evaluate()
    finally:
        await engine.dispose()

    report = render_evaluation_report(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


def _build_llm_client(args: argparse.Namespace) -> Any:
    if args.llm_provider == "mock":
        return MockLLMClient(
            answer="Mock evaluation answer generated from retrieved context.",
            model=_llm_model_label(args),
        )
    if args.llm_provider == "ollama":
        return OllamaLLMClient(model=_llm_model_label(args))
    model = args.llm_model if args.llm_model != "mock" else "gpt-4.1-mini"
    return OpenAILLMClient(model=model)


def _embedding_model_label(args: argparse.Namespace) -> str:
    if args.embedding_provider == "ollama":
        return args.embedding_model
    if args.embedding_provider == "openai":
        return OPENAI_EMBEDDING_MODEL
    if args.embedding_provider == "huggingface":
        return BGE_SMALL_EN_MODEL
    if args.embedding_provider == "fake":
        return "fake"
    return "auto"


def _llm_model_label(args: argparse.Namespace) -> str:
    if args.llm_provider == "openai" and args.llm_model == OLLAMA_LLM_MODEL:
        return "gpt-4.1-mini"
    if args.llm_provider == "mock" and args.llm_model == OLLAMA_LLM_MODEL:
        return "mock"
    return args.llm_model


async def _load_experiment_id_map(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(Experiment.id, Experiment.config))).all()
    mapping: dict[str, str] = {}
    for experiment_id, config in rows:
        synthetic_id = config.get("experiment_id") if isinstance(config, dict) else None
        if isinstance(synthetic_id, str):
            mapping[synthetic_id] = str(experiment_id)
    return mapping


def _resolve_experiment_id(
    question: EvaluationQuestion,
    experiment_id_map: dict[str, str],
) -> str:
    return experiment_id_map.get(question.experiment_id, question.experiment_id)


async def _experiment_exists(session: AsyncSession, experiment_id: str) -> bool:
    try:
        parsed_id = uuid.UUID(str(experiment_id))
    except ValueError:
        return False
    return await session.scalar(select(Experiment.id).where(Experiment.id == parsed_id)) is not None


def main() -> None:
    args = parse_args()
    report = run_async(run_evaluation(args))
    print(f"Wrote evaluation report to {args.output}")
    print(report.splitlines()[0])


if __name__ == "__main__":
    main()
