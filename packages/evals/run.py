from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config.env import resolve_setting
from packages.db.models import Experiment
from packages.db.session import create_async_session_factory, create_database_engine
from packages.evals.dataset import DEFAULT_DATASET_PATH, EvaluationQuestion, load_evaluation_dataset
from packages.evals.evaluator import OfflineEvaluator
from packages.evals.report import render_evaluation_report
from packages.ingestion.embeddings import (
    BGE_SMALL_EN_MODEL,
    GEMINI_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    build_embedding_provider,
)
from packages.ingestion.load_experiment import run_async
from packages.llm.client import (
    GEMINI_LLM_MODEL,
    OLLAMA_LLM_MODEL,
    GeminiLLMClient,
    MockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
)
from packages.observability.factory import resolve_observability_provider
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
        choices=("auto", "fake", "openai", "gemini", "huggingface", "ollama"),
        default=None,
        help="Embedding provider to use for retrieval.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model name. Used by --embedding-provider=gemini or ollama.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=("mock", "openai", "gemini", "ollama"),
        default=None,
        help="LLM provider to use for answer generation.",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model name. If omitted, the selected provider resolves its default from .env.",
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


def resolve_runtime_options(args: argparse.Namespace) -> argparse.Namespace:
    args.embedding_provider = resolve_setting(
        args.embedding_provider,
        env_var="EMBEDDING_PROVIDER",
        default="auto",
        lowercase=True,
    )
    if args.embedding_provider == "gemini":
        args.embedding_model = resolve_setting(
            args.embedding_model,
            env_var="GEMINI_EMBEDDING_MODEL",
            default=GEMINI_EMBEDDING_MODEL,
        )
    elif args.embedding_provider == "ollama":
        args.embedding_model = resolve_setting(
            args.embedding_model,
            env_var="OLLAMA_EMBEDDING_MODEL",
            default="nomic-embed-text",
        )
    elif args.embedding_provider == "openai":
        args.embedding_model = OPENAI_EMBEDDING_MODEL
    elif args.embedding_provider == "huggingface":
        args.embedding_model = BGE_SMALL_EN_MODEL
    elif args.embedding_provider == "fake":
        args.embedding_model = "fake"
    else:
        args.embedding_model = "auto"

    args.llm_provider = resolve_setting(
        args.llm_provider,
        env_var="LLM_PROVIDER",
        default="mock",
        lowercase=True,
    )
    if args.llm_provider == "gemini":
        args.llm_model = resolve_setting(
            args.llm_model,
            env_var="GEMINI_MODEL",
            default=GEMINI_LLM_MODEL,
        )
    elif args.llm_provider == "ollama":
        args.llm_model = resolve_setting(
            args.llm_model,
            env_var="OLLAMA_MODEL",
            default=OLLAMA_LLM_MODEL,
        )
    elif args.llm_provider == "openai":
        args.llm_model = resolve_setting(
            args.llm_model,
            env_var="OPENAI_MODEL",
            default="gpt-4.1-mini",
        )
    elif args.llm_provider == "mock":
        if isinstance(args.llm_model, str) and args.llm_model.strip():
            args.llm_model = args.llm_model.strip()
        else:
            args.llm_model = "mock"
    else:
        args.llm_model = args.llm_model or GEMINI_LLM_MODEL
    return args


async def run_evaluation(args: argparse.Namespace) -> str:
    result = await build_evaluation_run(args)
    report = render_evaluation_report(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


async def build_evaluation_run(args: argparse.Namespace):
    args = resolve_runtime_options(args)
    observability_provider = resolve_observability_provider()
    root_span = observability_provider.start_root_span(
        "evaluation.rag",
        trace_id=f"evaluation.rag:{args.dataset}",
        inputs={
            "dataset": str(args.dataset),
            "top_k": args.top_k,
            "embedding_provider": args.embedding_provider,
            "llm_provider": args.llm_provider,
        },
        metadata={"surface": "evaluation.rag"},
        tags=("evaluation", "rag"),
    )
    with root_span.activate():
        return await _build_evaluation_run(args, observability_provider)


async def _build_evaluation_run(args: argparse.Namespace, observability_provider):
    questions = load_evaluation_dataset(args.dataset)
    engine = create_database_engine()
    session_factory = create_async_session_factory(engine)
    provider = build_embedding_provider(
        args.embedding_provider,
        model=args.embedding_model if args.embedding_provider in {"gemini", "ollama"} else None,
    )
    try:
        async with session_factory() as session:
            experiment_id_map = await _load_experiment_id_map(session)
            service = QuestionAnsweringService(
                retrieval_service=RetrievalService(
                    session,
                    provider,
                    observability_provider=observability_provider,
                ),
                llm_client=_build_llm_client(args),
                experiment_exists=lambda experiment_id: _experiment_exists(session, experiment_id),
                observability_provider=observability_provider,
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
            root_metadata = {
                "question_count": result.summary.question_count,
                "retrieval_success_rate": result.summary.retrieval_success_rate,
                "surface": "evaluation.rag",
                "execution_mode": "evaluation",
                "environment": os.environ.get("APP_ENV", "local"),
                "workflow_mode": "legacy_rag",
            }
            current_span = observability_provider.current_span()
            if current_span is not None:
                current_span.add_metadata(root_metadata)
                current_span.finish(
                    outputs={
                        "status": "completed",
                        "question_count": result.summary.question_count,
                        "sample_count": len(result.samples),
                    }
                )
            return result
    finally:
        await engine.dispose()


def _build_llm_client(args: argparse.Namespace) -> Any:
    if args.llm_provider == "mock":
        return MockLLMClient(
            answer="Mock evaluation answer generated from retrieved context.",
            model=_llm_model_label(args),
        )
    if args.llm_provider == "ollama":
        return OllamaLLMClient(model=_llm_model_label(args))
    if args.llm_provider == "gemini":
        return GeminiLLMClient(model=_llm_model_label(args))
    model = _llm_model_label(args)
    return OpenAILLMClient(model=model)


def _embedding_model_label(args: argparse.Namespace) -> str:
    if args.embedding_provider == "ollama":
        return args.embedding_model
    if args.embedding_provider == "openai":
        return OPENAI_EMBEDDING_MODEL
    if args.embedding_provider == "gemini":
        return args.embedding_model
    if args.embedding_provider == "huggingface":
        return BGE_SMALL_EN_MODEL
    if args.embedding_provider == "fake":
        return "fake"
    return "auto"


def _llm_model_label(args: argparse.Namespace) -> str:
    if args.llm_provider == "openai" and args.llm_model in {GEMINI_LLM_MODEL, OLLAMA_LLM_MODEL}:
        return "gpt-4.1-mini"
    if args.llm_provider == "mock" and args.llm_model in {GEMINI_LLM_MODEL, OLLAMA_LLM_MODEL}:
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
    args = resolve_runtime_options(parse_args())
    report = run_async(run_evaluation(args))
    print(f"Wrote evaluation report to {args.output}")
    print(report.splitlines()[0])


if __name__ == "__main__":
    main()
