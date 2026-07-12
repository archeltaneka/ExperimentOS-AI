from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path

from packages.db.session import create_async_session_factory, create_database_engine
from packages.evals.agent_e2e import AgentE2ECase, build_default_agent_e2e_cases
from packages.evals.dataset import DEFAULT_DATASET_PATH, EvaluationQuestion, load_evaluation_dataset
from packages.evals.prompt_regression import (
    PromptRegressionRunner,
    prompt_regression_to_json,
    render_prompt_regression_report,
)
from packages.evals.run import (
    _build_llm_client,
    _load_experiment_id_map,
    _resolve_experiment_id,
    resolve_runtime_options,
)
from packages.ingestion.embeddings import build_embedding_provider
from packages.ingestion.load_experiment import run_async
from packages.observability.factory import resolve_observability_provider
from packages.retrieval.service import RetrievalService

DEFAULT_MARKDOWN_REPORT_PATH = Path("reports/phase3/prompt_regression.md")
DEFAULT_JSON_REPORT_PATH = Path("reports/phase3/prompt_regression.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run prompt regression checks.")
    parser.add_argument("--prompt-id", required=True, help="Prompt ID to compare.")
    parser.add_argument("--baseline-version", required=True, help="Baseline prompt version.")
    parser.add_argument("--candidate-version", required=True, help="Candidate prompt version.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the QA evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT_PATH,
        help="Path where the Markdown prompt regression report should be written.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_REPORT_PATH,
        help="Path where the JSON prompt regression report should be written.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve.")
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "fake", "openai", "gemini", "huggingface", "ollama"),
        default="fake",
        help="Embedding provider used by the QA pipeline under test.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Optional embedding model override.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=("mock", "openai", "gemini", "ollama"),
        default="mock",
        help="LLM provider used by the QA pipeline under test.",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Optional LLM model override.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use deterministic offline mode. This is the default behavior.",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Enable optional judge-backed framework metrics when configured.",
    )
    parser.add_argument(
        "--judge-provider",
        choices=("openai", "gemini"),
        default=None,
        help="Optional judge provider for DeepEval judge mode.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Optional judge model name for DeepEval judge mode.",
    )
    return parser.parse_args(argv)


async def build_prompt_regression_report(args: argparse.Namespace):
    args = resolve_runtime_options(args)
    observability_provider = resolve_observability_provider()
    root_span = observability_provider.start_root_span(
        "evaluation.prompt_regression",
        trace_id=f"evaluation.prompt_regression:{args.prompt_id}",
        inputs={
            "prompt_id": args.prompt_id,
            "baseline_version": args.baseline_version,
            "candidate_version": args.candidate_version,
        },
        metadata={"surface": "evaluation.prompt_regression"},
        tags=("evaluation", "prompt_regression"),
    )
    with root_span.activate():
        return await _build_prompt_regression_report(args, observability_provider)


async def _build_prompt_regression_report(args: argparse.Namespace, observability_provider):
    questions = _resolve_questions(args.dataset)
    engine = create_database_engine()
    session_factory = create_async_session_factory(engine)
    provider = build_embedding_provider(
        args.embedding_provider,
        model=args.embedding_model if args.embedding_provider in {"gemini", "ollama"} else None,
    )
    try:
        async with session_factory() as session:
            experiment_id_map = await _load_experiment_id_map(session)
            resolved_questions = [
                replace(
                    question,
                    experiment_id=_resolve_experiment_id(question, experiment_id_map),
                )
                for question in questions
            ]
            legacy_cases = _build_legacy_ask_cases(resolved_questions)
            runner = PromptRegressionRunner(
                prompt_id=args.prompt_id,
                baseline_version=args.baseline_version,
                candidate_version=args.candidate_version,
                qa_questions=resolved_questions,
                ask_cases=legacy_cases,
                retrieval_service=RetrievalService(
                    session,
                    provider,
                    observability_provider=observability_provider,
                ),
                llm_client_factory=(
                    (lambda _surface: _build_llm_client(args))
                    if args.llm_provider != "mock" and not args.offline
                    else None
                ),
                dataset_label=str(args.dataset),
                judge_mode=args.judge,
                deepeval_judge_provider=args.judge_provider,
                deepeval_judge_model=args.judge_model,
            )
            report = await runner.evaluate()
            current_span = observability_provider.current_span()
            if current_span is not None:
                current_span.add_metadata(
                    {
                        "prompt_id": args.prompt_id,
                        "dataset": str(args.dataset),
                        "legacy_case_count": len(legacy_cases),
                        "execution_mode": "evaluation",
                        "environment": os.environ.get("APP_ENV", "local"),
                    }
                )
                current_span.finish(
                    outputs={
                        "status": "completed",
                        "sample_count": len(report.samples),
                    }
                )
            return report
    finally:
        await engine.dispose()


async def run_prompt_regression(args: argparse.Namespace) -> int:
    report = await build_prompt_regression_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_prompt_regression_report(report), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(prompt_regression_to_json(report), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        return run_async(run_prompt_regression(args))
    except Exception as exc:
        print(str(exc))
        return 1


def _resolve_questions(dataset_path: Path) -> list[EvaluationQuestion]:
    return load_evaluation_dataset(dataset_path)


def _build_legacy_ask_cases(questions: list[EvaluationQuestion]) -> list[AgentE2ECase]:
    if not questions:
        return []
    fallback_case = next(
        case for case in build_default_agent_e2e_cases() if case.ask_mode == "legacy_rag"
    )
    first_payment_question = next(
        (question for question in questions if "payment" in question.experiment_id.lower()),
        questions[0],
    )
    return [
        replace(
            fallback_case,
            experiment_id=first_payment_question.experiment_id,
            top_k=5,
        )
    ]


if __name__ == "__main__":
    raise SystemExit(main())
