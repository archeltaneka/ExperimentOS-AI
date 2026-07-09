from __future__ import annotations

import argparse
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.config.env import resolve_setting
from packages.evals.dataset import DEFAULT_DATASET_PATH
from packages.evals.ragas_adapter import (
    DEFAULT_RAGAS_METRICS,
    RagasBindings,
    build_ragas_dataset,
    build_ragas_metric,
    get_ragas_metric_spec,
    import_ragas_bindings,
    prepare_ragas_dataset,
)
from packages.evals.ragas_report import (
    RagasCaseResult,
    RagasEvaluationReport,
    RagasMetricResult,
    ragas_report_to_json,
    render_ragas_report,
)
from packages.evals.run import build_evaluation_run as build_qa_evaluation_run
from packages.evals.run import resolve_runtime_options as resolve_qa_runtime_options
from packages.ingestion.embeddings import (
    BGE_SMALL_EN_MODEL,
    GEMINI_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
)
from packages.ingestion.load_experiment import run_async
from packages.llm.client import GEMINI_LLM_MODEL

DEFAULT_MARKDOWN_REPORT_PATH = Path("reports/phase3/ragas_report.md")
DEFAULT_JSON_REPORT_PATH = Path("reports/phase3/ragas_report.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run optional RAGAS evaluation over the existing QA evaluation harness."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the repository-owned QA evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT_PATH,
        help="Path where the Markdown RAGAS report should be written.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_REPORT_PATH,
        help="Path where the machine-readable RAGAS report should be written.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve.")
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "fake", "openai", "gemini", "huggingface", "ollama"),
        default=None,
        help="Embedding provider used by the QA pipeline under test.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model name used by the QA pipeline under test.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=("mock", "openai", "gemini", "ollama"),
        default=None,
        help="LLM provider used by the QA pipeline under test.",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model name used by the QA pipeline under test.",
    )
    parser.add_argument(
        "--input-cost-per-1k-tokens",
        type=float,
        default=0.0,
        help="Optional QA input-token cost rate for passthrough cost reporting.",
    )
    parser.add_argument(
        "--output-cost-per-1k-tokens",
        type=float,
        default=0.0,
        help="Optional QA output-token cost rate for passthrough cost reporting.",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=sorted(DEFAULT_RAGAS_METRICS),
        default=list(DEFAULT_RAGAS_METRICS),
        help="RAGAS metrics to request. Judge-backed metrics are skipped unless configured.",
    )
    parser.add_argument(
        "--judge-llm-provider",
        choices=("none", "mock", "openai", "gemini"),
        default=None,
        help="Optional judge LLM provider for model-backed RAGAS metrics.",
    )
    parser.add_argument(
        "--judge-llm-model",
        default=None,
        help="Optional judge LLM model for model-backed RAGAS metrics.",
    )
    parser.add_argument(
        "--judge-embedding-provider",
        choices=("none", "fake", "openai", "gemini", "huggingface"),
        default=None,
        help="Optional judge embedding provider for answer relevancy.",
    )
    parser.add_argument(
        "--judge-embedding-model",
        default=None,
        help="Optional judge embedding model for answer relevancy.",
    )
    parser.add_argument(
        "--ragas-timeout",
        type=int,
        default=60,
        help="Per-metric RAGAS timeout in seconds.",
    )
    parser.add_argument(
        "--ragas-max-workers",
        type=int,
        default=4,
        help="Maximum RAGAS metric workers.",
    )
    return parser.parse_args(argv)


def resolve_runtime_options(args: argparse.Namespace) -> argparse.Namespace:
    args = resolve_qa_runtime_options(args)

    args.judge_llm_provider = resolve_setting(
        args.judge_llm_provider,
        env_var="RAGAS_JUDGE_LLM_PROVIDER",
        default="none",
        lowercase=True,
    )
    args.judge_embedding_provider = resolve_setting(
        args.judge_embedding_provider,
        env_var="RAGAS_JUDGE_EMBEDDING_PROVIDER",
        default="none",
        lowercase=True,
    )

    if args.judge_llm_provider == "openai":
        args.judge_llm_model = resolve_setting(
            args.judge_llm_model,
            env_var="RAGAS_JUDGE_LLM_MODEL",
            default="gpt-4.1-mini",
        )
    elif args.judge_llm_provider == "gemini":
        args.judge_llm_model = resolve_setting(
            args.judge_llm_model,
            env_var="RAGAS_JUDGE_LLM_MODEL",
            default=GEMINI_LLM_MODEL,
        )
    else:
        args.judge_llm_model = "none"

    if args.judge_embedding_provider == "openai":
        args.judge_embedding_model = resolve_setting(
            args.judge_embedding_model,
            env_var="RAGAS_JUDGE_EMBEDDING_MODEL",
            default=OPENAI_EMBEDDING_MODEL,
        )
    elif args.judge_embedding_provider == "gemini":
        args.judge_embedding_model = resolve_setting(
            args.judge_embedding_model,
            env_var="RAGAS_JUDGE_EMBEDDING_MODEL",
            default=GEMINI_EMBEDDING_MODEL,
        )
    elif args.judge_embedding_provider == "huggingface":
        args.judge_embedding_model = resolve_setting(
            args.judge_embedding_model,
            env_var="RAGAS_JUDGE_EMBEDDING_MODEL",
            default=BGE_SMALL_EN_MODEL,
        )
    else:
        args.judge_embedding_model = "none"

    return args


def build_ragas_report(args: argparse.Namespace) -> RagasEvaluationReport:
    args = resolve_runtime_options(args)
    qa_run = run_async(build_qa_evaluation_run(args))
    prepared = prepare_ragas_dataset(qa_run)

    ragas_available = True
    ragas_version: str | None = None
    ragas_import_note: str | None = None
    bindings: RagasBindings | None = None
    metric_results: list[RagasMetricResult] = []
    per_case_scores = {sample.question.id: {} for sample in qa_run.samples}
    metrics_run: list[str] = []
    limitations: list[str] = []

    try:
        bindings = import_ragas_bindings()
        ragas_version = bindings.version
        if bindings.shimmed_vertexai:
            ragas_import_note = (
                "Applied a local VertexAI import shim because ragas imports that optional "
                "integration eagerly in this environment."
            )
    except Exception as exc:
        ragas_available = False
        limitations.append(
            "RAGAS is optional and was unavailable for this run. Requested metrics were skipped."
        )
        ragas_import_note = f"{type(exc).__name__}: {exc}"

    judge_llm, judge_llm_reason = _build_judge_llm(args, bindings)
    judge_embeddings, judge_embedding_reason = _build_judge_embeddings(args, bindings)

    if args.judge_llm_provider in {"none", "mock"}:
        limitations.append(
            "Judge-backed metrics are opt-in. This run used no judge LLM, so model-backed "
            "RAGAS metrics were skipped by design."
        )
    if prepared.excluded_samples:
        limitations.append(
            f"{len(prepared.excluded_samples)} samples were excluded because the source QA "
            "evaluation recorded an error for them."
        )

    for metric_name in args.metrics:
        spec = get_ragas_metric_spec(metric_name)
        skip_reason = _metric_skip_reason(
            spec.name,
            ragas_available=ragas_available,
            eligible_sample_count=len(prepared.samples),
            judge_llm=judge_llm,
            judge_llm_reason=judge_llm_reason,
            judge_embeddings=judge_embeddings,
            judge_embedding_reason=judge_embedding_reason,
        )
        if skip_reason is not None:
            metric_results.append(
                RagasMetricResult(
                    name=spec.name,
                    status="skipped",
                    average_score=None,
                    reason=skip_reason,
                    description=spec.description,
                )
            )
            continue

        assert bindings is not None
        ragas_dataset = build_ragas_dataset(prepared, bindings)
        metric = build_ragas_metric(spec.name, bindings)
        run_config = bindings.RunConfig(
            timeout=args.ragas_timeout,
            max_workers=args.ragas_max_workers,
        )
        try:
            result = bindings.evaluate(
                dataset=ragas_dataset,
                metrics=[metric],
                llm=judge_llm,
                embeddings=judge_embeddings,
                run_config=run_config,
                show_progress=False,
                raise_exceptions=False,
            )
        except Exception as exc:
            metric_results.append(
                RagasMetricResult(
                    name=spec.name,
                    status="failed",
                    average_score=None,
                    reason=f"{type(exc).__name__}: {exc}",
                    description=spec.description,
                )
            )
            limitations.append(
                f"Metric `{spec.name}` failed at runtime and was reported instead of aborting "
                "the entire RAGAS run."
            )
            continue

        scores = _extract_metric_scores(result, spec.name)
        averages = [score for score in scores if score is not None]
        average_score = sum(averages) / len(averages) if averages else None
        metric_results.append(
            RagasMetricResult(
                name=spec.name,
                status="computed",
                average_score=average_score,
                description=spec.description,
            )
        )
        metrics_run.append(spec.name)
        for prepared_sample, score in zip(prepared.samples, scores, strict=True):
            per_case_scores[prepared_sample.question_id][spec.name] = score

    case_results = tuple(
        RagasCaseResult(
            question_id=sample.question.id,
            experiment_id=sample.question.experiment_id,
            category=sample.question.category,
            difficulty=sample.question.difficulty,
            retrieved_context_count=len(sample.retrieved_contexts),
            retrieved_document_count=len(sample.retrieved_documents),
            source_error=sample.error,
            metric_scores=per_case_scores[sample.question.id],
        )
        for sample in qa_run.samples
    )

    if not ragas_available:
        for metric_name in args.metrics:
            if not any(result.name == metric_name for result in metric_results):
                spec = get_ragas_metric_spec(metric_name)
                metric_results.append(
                    RagasMetricResult(
                        name=spec.name,
                        status="skipped",
                        average_score=None,
                        reason=ragas_import_note,
                        description=spec.description,
                    )
                )

    return RagasEvaluationReport(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        dataset_path=str(args.dataset),
        dataset_size=len(qa_run.samples),
        eligible_sample_count=len(prepared.samples),
        excluded_sample_count=len(prepared.excluded_samples),
        ragas_available=ragas_available,
        ragas_version=ragas_version,
        ragas_import_note=ragas_import_note,
        qa_embedding_provider=qa_run.embedding_provider or "unknown",
        qa_embedding_model=qa_run.embedding_model or "unknown",
        qa_llm_provider=qa_run.llm_provider or "unknown",
        qa_llm_model=qa_run.llm_model or "unknown",
        judge_llm_provider=args.judge_llm_provider,
        judge_llm_model=args.judge_llm_model,
        judge_embedding_provider=args.judge_embedding_provider,
        judge_embedding_model=args.judge_embedding_model,
        metrics_requested=tuple(args.metrics),
        metrics_run=tuple(metrics_run),
        metric_results=tuple(metric_results),
        case_results=case_results,
        limitations=tuple(dict.fromkeys(limitations)),
    )


def write_ragas_reports(args: argparse.Namespace) -> RagasEvaluationReport:
    report = build_ragas_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_ragas_report(report), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(ragas_report_to_json(report), encoding="utf-8")
    return report


def _build_judge_llm(
    args: argparse.Namespace,
    bindings: RagasBindings | None,
) -> tuple[Any | None, str | None]:
    if bindings is None:
        return None, "RAGAS bindings are unavailable."
    if args.judge_llm_provider in {"none", "mock"}:
        return (
            None,
            f"judge llm provider `{args.judge_llm_provider}` does not enable RAGAS "
            "judge metrics",
        )
    if args.judge_llm_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None, "OPENAI_API_KEY is required for judge_llm_provider=openai"
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        return (
            bindings.llm_factory(
                model=args.judge_llm_model,
                provider="openai",
                client=client,
            ),
            None,
        )
    if args.judge_llm_provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None, "GOOGLE_API_KEY is required for judge_llm_provider=gemini"
        from google import genai

        client = genai.Client(api_key=api_key)
        return (
            bindings.llm_factory(
                model=args.judge_llm_model,
                provider="google",
                client=client,
            ),
            None,
        )
    return None, f"unsupported judge llm provider `{args.judge_llm_provider}`"


def _build_judge_embeddings(
    args: argparse.Namespace,
    bindings: RagasBindings | None,
) -> tuple[Any | None, str | None]:
    if bindings is None:
        return None, "RAGAS bindings are unavailable."
    if args.judge_embedding_provider in {"none", "fake"}:
        return (
            None,
            "judge embedding provider does not enable model-backed answer relevancy",
        )
    if args.judge_embedding_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None, "OPENAI_API_KEY is required for judge_embedding_provider=openai"
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        return (
            bindings.embedding_factory(
                "openai",
                model=args.judge_embedding_model,
                client=client,
            ),
            None,
        )
    if args.judge_embedding_provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None, "GOOGLE_API_KEY is required for judge_embedding_provider=gemini"
        from google import genai

        client = genai.Client(api_key=api_key)
        return (
            bindings.embedding_factory(
                "google",
                model=args.judge_embedding_model,
                client=client,
            ),
            None,
        )
    if args.judge_embedding_provider == "huggingface":
        return (
            bindings.embedding_factory(
                "huggingface",
                model=args.judge_embedding_model,
            ),
            None,
        )
    return None, f"unsupported judge embedding provider `{args.judge_embedding_provider}`"


def _metric_skip_reason(
    metric_name: str,
    *,
    ragas_available: bool,
    eligible_sample_count: int,
    judge_llm: Any | None,
    judge_llm_reason: str | None,
    judge_embeddings: Any | None,
    judge_embedding_reason: str | None,
) -> str | None:
    if not ragas_available:
        return "RAGAS is not installed or could not be imported."
    if eligible_sample_count == 0:
        return "No QA samples were eligible for RAGAS evaluation."

    spec = get_ragas_metric_spec(metric_name)
    if spec.requires_judge_llm and judge_llm is None:
        return judge_llm_reason or "A judge LLM is required for this metric."
    if spec.requires_judge_embeddings and judge_embeddings is None:
        return judge_embedding_reason or "Judge embeddings are required for this metric."
    return None


def _extract_metric_scores(result: Any, metric_name: str) -> list[float | None]:
    values: list[float | None] = []
    for row in getattr(result, "scores", []):
        if metric_name not in row:
            values.append(None)
            continue
        value = row[metric_name]
        if value is None:
            values.append(None)
            continue
        numeric = float(value)
        values.append(None if math.isnan(numeric) else numeric)
    return values


def main() -> None:
    args = resolve_runtime_options(parse_args())
    report = write_ragas_reports(args)
    print(f"Wrote RAGAS report to {args.output}")
    print(report.metrics_run[0] if report.metrics_run else "no ragas metrics computed")


if __name__ == "__main__":
    main()
