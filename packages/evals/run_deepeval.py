from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from packages.config.env import resolve_setting
from packages.evals.agent_dataset import DEFAULT_AGENT_DATASET_PATH
from packages.evals.dataset import DEFAULT_DATASET_PATH
from packages.evals.deepeval_adapter import (
    DeepEvalBindings,
    DeepEvalPreparedCase,
    build_deepeval_dataset,
    build_llm_test_case,
    import_deepeval_bindings,
    prepare_agent_response_cases,
    prepare_agent_workflow_cases,
    prepare_qa_response_cases,
)
from packages.evals.deepeval_report import (
    DeepEvalEvaluationReport,
    DeepEvalMetricResult,
    deepeval_report_to_json,
    render_deepeval_report,
)
from packages.evals.run import build_evaluation_run as build_qa_evaluation_run
from packages.evals.run import parse_args as parse_qa_args
from packages.evals.run import resolve_runtime_options as resolve_qa_runtime_options
from packages.evals.run_agent import build_evaluation_run as build_agent_evaluation_run
from packages.evals.run_agent import parse_args as parse_agent_args
from packages.evals.run_agent_e2e import build_evaluation_run as build_agent_e2e_evaluation_run
from packages.evals.run_agent_e2e import parse_args as parse_agent_e2e_args
from packages.ingestion.load_experiment import run_async
from packages.observability.factory import resolve_observability_provider

DEFAULT_MARKDOWN_REPORT_PATH = Path("reports/phase3/deepeval_report.md")
DEFAULT_JSON_REPORT_PATH = Path("reports/phase3/deepeval_report.json")


@dataclass(frozen=True)
class DeepEvalMetricSpec:
    name: str
    metric_type: str
    scope: str
    threshold: float
    description: str


SUPPORTED_DEEPEVAL_METRICS = {
    "citation_coverage": DeepEvalMetricSpec(
        name="citation_coverage",
        metric_type="deterministic",
        scope="all",
        threshold=1.0,
        description="Deterministic citation or evidence coverage against repository expectations.",
    ),
    "response_field_completeness": DeepEvalMetricSpec(
        name="response_field_completeness",
        metric_type="deterministic",
        scope="response",
        threshold=1.0,
        description="Deterministic response completeness for answer and evidence fields.",
    ),
    "error_state_correctness": DeepEvalMetricSpec(
        name="error_state_correctness",
        metric_type="deterministic",
        scope="response",
        threshold=1.0,
        description="Deterministic validation for expected non-200 or error-state responses.",
    ),
    "fallback_compatibility": DeepEvalMetricSpec(
        name="fallback_compatibility",
        metric_type="deterministic",
        scope="response",
        threshold=1.0,
        description="Deterministic legacy_rag fallback contract compatibility.",
    ),
    "routing_accuracy": DeepEvalMetricSpec(
        name="routing_accuracy",
        metric_type="deterministic",
        scope="workflow",
        threshold=1.0,
        description="Deterministic agent routing accuracy from expected vs actual required agents.",
    ),
    "decision_status_match": DeepEvalMetricSpec(
        name="decision_status_match",
        metric_type="deterministic",
        scope="workflow",
        threshold=1.0,
        description="Deterministic decision-status match against the golden workflow case.",
    ),
    "approval_status_match": DeepEvalMetricSpec(
        name="approval_status_match",
        metric_type="deterministic",
        scope="workflow",
        threshold=1.0,
        description="Deterministic approval-state match against the golden workflow case.",
    ),
    "summary_status_match": DeepEvalMetricSpec(
        name="summary_status_match",
        metric_type="deterministic",
        scope="workflow",
        threshold=1.0,
        description=(
            "Deterministic executive-summary status match against the golden workflow case."
        ),
    ),
    "trace_completeness": DeepEvalMetricSpec(
        name="trace_completeness",
        metric_type="deterministic",
        scope="workflow",
        threshold=1.0,
        description="Deterministic trace completeness across the expected Phase 2 workflow nodes.",
    ),
    "unsupported_claim_avoidance": DeepEvalMetricSpec(
        name="unsupported_claim_avoidance",
        metric_type="deterministic",
        scope="workflow",
        threshold=1.0,
        description="Deterministic heuristic for unsupported revenue or significance claims.",
    ),
    "answer_relevancy": DeepEvalMetricSpec(
        name="answer_relevancy",
        metric_type="judge",
        scope="response",
        threshold=0.5,
        description="Judge-based answer relevancy for final responses.",
    ),
    "faithfulness": DeepEvalMetricSpec(
        name="faithfulness",
        metric_type="judge",
        scope="response",
        threshold=0.5,
        description="Judge-based faithfulness between answer content and retrieved evidence.",
    ),
    "hallucination": DeepEvalMetricSpec(
        name="hallucination",
        metric_type="judge",
        scope="response",
        threshold=0.5,
        description="Judge-based unsupported-claim detection against retrieved evidence.",
    ),
    "contextual_relevancy": DeepEvalMetricSpec(
        name="contextual_relevancy",
        metric_type="judge",
        scope="response",
        threshold=0.5,
        description="Judge-based contextual relevancy using the retrieved context.",
    ),
}

DEFAULT_DEEPEVAL_METRICS = tuple(SUPPORTED_DEEPEVAL_METRICS)
JUDGE_METRICS = {
    name for name, spec in SUPPORTED_DEEPEVAL_METRICS.items() if spec.metric_type == "judge"
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run additive DeepEval-backed evaluation without replacing existing harnesses."
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "judge", "all"),
        default="offline",
        help=(
            "Offline runs deterministic checks only. Judge mode enables DeepEval metrics "
            "explicitly."
        ),
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the repository-owned QA evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--agent-dataset",
        type=Path,
        default=DEFAULT_AGENT_DATASET_PATH,
        help="Path to the deterministic agent workflow dataset JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT_PATH,
        help="Path where the Markdown DeepEval report should be written.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_REPORT_PATH,
        help="Path where the JSON DeepEval report should be written.",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=sorted(SUPPORTED_DEEPEVAL_METRICS),
        default=list(DEFAULT_DEEPEVAL_METRICS),
        help="Metrics to request. Judge metrics are skipped in offline mode.",
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
        "--judge-provider",
        choices=("none", "openai", "gemini"),
        default=None,
        help="Optional explicit provider for judge-based DeepEval metrics.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Explicit judge model name for DeepEval metrics in judge/all mode.",
    )
    return parser.parse_args(argv)


def resolve_runtime_options(args: argparse.Namespace) -> argparse.Namespace:
    args = resolve_qa_runtime_options(args)
    args.judge_provider = resolve_setting(
        args.judge_provider,
        env_var="DEEPEVAL_JUDGE_PROVIDER",
        default="none",
        lowercase=True,
    )
    args.judge_model = resolve_setting(
        args.judge_model,
        env_var="DEEPEVAL_JUDGE_MODEL",
        default=None,
    )
    return args


def build_deepeval_report(args: argparse.Namespace) -> DeepEvalEvaluationReport:
    args = resolve_runtime_options(args)
    observability_provider = resolve_observability_provider()
    root_span = observability_provider.start_root_span(
        "evaluation.deepeval",
        trace_id=f"evaluation.deepeval:{args.dataset}",
        inputs={"dataset": str(args.dataset), "metrics": list(args.metrics), "mode": args.mode},
        metadata={
            "surface": "evaluation.deepeval",
            "execution_mode": "evaluation",
            "environment": os.environ.get("APP_ENV", "local"),
        },
        tags=("evaluation", "deepeval"),
    )
    with root_span.activate():
        return _build_deepeval_report(args, observability_provider)


def _build_deepeval_report(
    args: argparse.Namespace,
    observability_provider,
) -> DeepEvalEvaluationReport:
    judge_metric_names = [name for name in args.metrics if name in JUDGE_METRICS]
    if args.mode != "offline":
        _require_judge_configuration(args, judge_metric_names)

    qa_run = run_async(build_qa_evaluation_run(_build_qa_args(args)))
    agent_run = build_agent_evaluation_run(_build_agent_args(args))
    agent_e2e_run = build_agent_e2e_evaluation_run(_build_agent_e2e_args())

    response_cases = [
        *prepare_qa_response_cases(qa_run, dataset_identifier=str(args.dataset)),
        *prepare_agent_response_cases(agent_e2e_run),
    ]
    workflow_cases = prepare_agent_workflow_cases(
        agent_run,
        dataset_identifier=str(args.agent_dataset),
    )

    deepeval_available = True
    deepeval_version: str | None = None
    deepeval_import_note: str | None = None
    bindings: DeepEvalBindings | None = None
    limitations = [
        (
            "DeepEval remains additive; the existing custom evaluation harnesses and RAGAS "
            "stay intact."
        ),
        (
            "No Confident AI cloud integration, tracing, or observability hooks are enabled "
            "in this adapter."
        ),
        "Workflow deterministic metrics remain ExperimentOS-owned even when DeepEval is installed.",
        "Unsupported-claim avoidance is a deterministic heuristic, not a semantic judge score.",
    ]

    try:
        bindings = import_deepeval_bindings()
        deepeval_version = bindings.version
        build_deepeval_dataset(
            response_cases,
            bindings=bindings,
            name="experimentos-phase3-deepeval-response",
        )
        build_deepeval_dataset(
            workflow_cases,
            bindings=bindings,
            name="experimentos-phase3-deepeval-workflow",
        )
    except Exception as exc:
        deepeval_available = False
        deepeval_import_note = f"{type(exc).__name__}: {exc}"
        limitations.append(
            "DeepEval bindings were unavailable, so judge metrics were skipped and only "
            "repository-owned deterministic checks were executed."
        )

    metric_results = [
        *_evaluate_deterministic_metrics(
            response_cases=response_cases,
            workflow_cases=workflow_cases,
            framework_version=deepeval_version,
            evaluation_mode=args.mode,
            metrics=args.metrics,
        ),
    ]

    if args.mode == "offline":
        metric_results.extend(
            _skip_judge_metrics(
                response_cases=response_cases,
                framework_version=deepeval_version,
                evaluation_mode=args.mode,
                metrics=judge_metric_names,
                reason=(
                    "Judge metrics are disabled in offline mode to avoid implicit live "
                    "provider calls."
                ),
            )
        )
        limitations.append(
            "Offline mode skips judge-based metrics by design and never invokes a live model."
        )
    else:
        if bindings is None:
            raise ValueError(
                "DeepEval is not installed or could not be imported for judge mode."
            )
        metric_results.extend(
            _evaluate_judge_metrics(
                response_cases=response_cases,
                framework_version=deepeval_version,
                evaluation_mode=args.mode,
                metrics=judge_metric_names,
                bindings=bindings,
                judge_provider=args.judge_provider,
                judge_model=args.judge_model,
            )
        )

    metric_results_tuple = tuple(metric_results)
    metrics_executed = tuple(
        dict.fromkeys(
            result.metric_name for result in metric_results_tuple if result.skipped is False
        )
    )
    metrics_skipped = tuple(
        dict.fromkeys(result.metric_name for result in metric_results_tuple if result.skipped)
    )

    report = DeepEvalEvaluationReport(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        evaluation_mode=args.mode,
        deepeval_available=deepeval_available,
        deepeval_version=deepeval_version,
        deepeval_import_note=deepeval_import_note,
        dataset_identifiers=tuple(
            dict.fromkeys(
                [case.dataset_identifier for case in response_cases]
                + [case.dataset_identifier for case in workflow_cases]
            )
        ),
        response_case_count=len(response_cases),
        workflow_case_count=len(workflow_cases),
        metrics_requested=tuple(args.metrics),
        metrics_executed=metrics_executed,
        metrics_skipped=metrics_skipped,
        external_judge_used=args.mode in {"judge", "all"} and bool(judge_metric_names),
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        metric_results=metric_results_tuple,
        limitations=tuple(dict.fromkeys(limitations)),
    )
    current_span = observability_provider.current_span()
    if current_span is not None:
        current_span.add_metadata(
            {
                "response_case_count": report.response_case_count,
                "workflow_case_count": report.workflow_case_count,
                "metrics_executed": list(report.metrics_executed),
                "judge_provider": args.judge_provider,
                "judge_mode": args.mode,
            }
        )
        current_span.finish(
            outputs={
                "status": "completed",
                "metric_count": len(report.metric_results),
            }
        )
    return report


def write_deepeval_reports(args: argparse.Namespace) -> DeepEvalEvaluationReport:
    report = build_deepeval_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_deepeval_report(report), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(deepeval_report_to_json(report), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        report = write_deepeval_reports(args)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Wrote DeepEval report to {args.output}")
    print(report.metrics_executed[0] if report.metrics_executed else "no deepeval metrics executed")
    return 0


def _build_qa_args(args: argparse.Namespace) -> argparse.Namespace:
    argv = [
        "--dataset",
        str(args.dataset),
        "--output",
        str(DEFAULT_MARKDOWN_REPORT_PATH),
        "--top-k",
        str(args.top_k),
    ]
    if args.embedding_provider is not None:
        argv.extend(["--embedding-provider", args.embedding_provider])
    if args.embedding_model:
        argv.extend(["--embedding-model", args.embedding_model])
    if args.llm_provider is not None:
        argv.extend(["--llm-provider", args.llm_provider])
    if args.llm_model:
        argv.extend(["--llm-model", args.llm_model])
    return parse_qa_args(argv)


def _build_agent_args(args: argparse.Namespace) -> argparse.Namespace:
    return parse_agent_args(
        [
            "--dataset",
            str(args.agent_dataset),
            "--output",
            str(DEFAULT_MARKDOWN_REPORT_PATH),
        ]
    )


def _build_agent_e2e_args() -> argparse.Namespace:
    return parse_agent_e2e_args(["--output", str(DEFAULT_MARKDOWN_REPORT_PATH)])


def _evaluate_deterministic_metrics(
    *,
    response_cases: list[DeepEvalPreparedCase],
    workflow_cases: list[DeepEvalPreparedCase],
    framework_version: str | None,
    evaluation_mode: str,
    metrics: list[str],
) -> list[DeepEvalMetricResult]:
    results: list[DeepEvalMetricResult] = []
    requested = set(metrics)

    if "citation_coverage" in requested:
        for case in response_cases + workflow_cases:
            metric = _deterministic_metric(
                case=case,
                framework_version=framework_version,
                evaluation_mode=evaluation_mode,
                metric_name="citation_coverage",
                threshold=SUPPORTED_DEEPEVAL_METRICS["citation_coverage"].threshold,
                score=_citation_score(case),
                metadata={},
            )
            if metric is not None:
                results.append(metric)

    if "response_field_completeness" in requested:
        for case in response_cases:
            score = _response_field_completeness(case)
            if score is None:
                continue
            results.append(
                _build_metric_result(
                    case=case,
                    framework_version=framework_version,
                    evaluation_mode=evaluation_mode,
                    metric_name="response_field_completeness",
                    metric_type="deterministic",
                    score=score,
                    threshold=1.0,
                    metadata={},
                )
            )

    if "error_state_correctness" in requested:
        for case in response_cases:
            score = _error_state_correctness(case)
            if score is None:
                continue
            results.append(
                _build_metric_result(
                    case=case,
                    framework_version=framework_version,
                    evaluation_mode=evaluation_mode,
                    metric_name="error_state_correctness",
                    metric_type="deterministic",
                    score=score,
                    threshold=1.0,
                    metadata={},
                )
            )

    if "fallback_compatibility" in requested:
        for case in response_cases:
            if case.metadata.get("used_legacy_fallback") is not True:
                continue
            score = 1.0 if _legacy_fallback_is_compatible(case) else 0.0
            results.append(
                _build_metric_result(
                    case=case,
                    framework_version=framework_version,
                    evaluation_mode=evaluation_mode,
                    metric_name="fallback_compatibility",
                    metric_type="deterministic",
                    score=score,
                    threshold=1.0,
                    metadata={},
                )
            )

    for metric_name in (
        "routing_accuracy",
        "decision_status_match",
        "approval_status_match",
        "summary_status_match",
        "trace_completeness",
        "unsupported_claim_avoidance",
    ):
        if metric_name not in requested:
            continue
        for case in workflow_cases:
            maybe_result = _workflow_metric_result(
                case=case,
                framework_version=framework_version,
                evaluation_mode=evaluation_mode,
                metric_name=metric_name,
            )
            if maybe_result is not None:
                results.append(maybe_result)

    return results


def _skip_judge_metrics(
    *,
    response_cases: list[DeepEvalPreparedCase],
    framework_version: str | None,
    evaluation_mode: str,
    metrics: list[str],
    reason: str,
) -> list[DeepEvalMetricResult]:
    results: list[DeepEvalMetricResult] = []
    for metric_name in metrics:
        spec = SUPPORTED_DEEPEVAL_METRICS[metric_name]
        for case in response_cases:
            results.append(
                _build_metric_result(
                    case=case,
                    framework_version=framework_version,
                    evaluation_mode=evaluation_mode,
                    metric_name=metric_name,
                    metric_type=spec.metric_type,
                    score=None,
                    threshold=spec.threshold,
                    skipped=True,
                    skip_reason=reason,
                    metadata={},
                )
            )
    return results


def _evaluate_judge_metrics(
    *,
    response_cases: list[DeepEvalPreparedCase],
    framework_version: str | None,
    evaluation_mode: str,
    metrics: list[str],
    bindings: DeepEvalBindings,
    judge_provider: str,
    judge_model: str | None,
) -> list[DeepEvalMetricResult]:
    results: list[DeepEvalMetricResult] = []
    for metric_name in metrics:
        spec = SUPPORTED_DEEPEVAL_METRICS[metric_name]
        eligible_cases: list[DeepEvalPreparedCase] = []
        for case in response_cases:
            skip_reason = _judge_skip_reason(metric_name, case)
            if skip_reason is not None:
                results.append(
                    _build_metric_result(
                        case=case,
                        framework_version=framework_version,
                        evaluation_mode=evaluation_mode,
                        metric_name=metric_name,
                        metric_type=spec.metric_type,
                        score=None,
                        threshold=spec.threshold,
                        skipped=True,
                        skip_reason=skip_reason,
                        metadata={},
                    )
                )
                continue
            eligible_cases.append(case)

        if not eligible_cases:
            continue

        metric = _build_judge_metric(
            metric_name=metric_name,
            spec=spec,
            bindings=bindings,
            judge_provider=judge_provider,
            judge_model=judge_model,
        )
        started_at = perf_counter()
        try:
            evaluation_result = bindings.evaluate(
                test_cases=[
                    build_llm_test_case(case, bindings=bindings) for case in eligible_cases
                ],
                metrics=[metric],
                async_config=bindings.AsyncConfig(run_async=False),
                display_config=bindings.DisplayConfig(
                    show_indicator=False,
                    print_results=False,
                    inspect_after_run=False,
                ),
                cache_config=bindings.CacheConfig(write_cache=False, use_cache=False),
                error_config=bindings.ErrorConfig(
                    ignore_errors=False,
                    skip_on_missing_params=False,
                ),
            )
        except Exception as exc:
            duration_ms = max((perf_counter() - started_at) * 1000.0, 0.0)
            for case in eligible_cases:
                results.append(
                    _build_metric_result(
                        case=case,
                        framework_version=framework_version,
                        evaluation_mode=evaluation_mode,
                        metric_name=metric_name,
                        metric_type=spec.metric_type,
                        score=None,
                        threshold=spec.threshold,
                        error=f"{type(exc).__name__}: {exc}",
                        duration_ms=duration_ms,
                        metadata={},
                    )
                )
            continue

        duration_ms = max((perf_counter() - started_at) * 1000.0, 0.0)
        for case, test_result in zip(
            eligible_cases,
            getattr(evaluation_result, "test_results", []),
            strict=True,
        ):
            metric_data = _metric_data_for_name(test_result, metric_name)
            if metric_data is None:
                results.append(
                    _build_metric_result(
                        case=case,
                        framework_version=framework_version,
                        evaluation_mode=evaluation_mode,
                        metric_name=metric_name,
                        metric_type=spec.metric_type,
                        score=None,
                        threshold=spec.threshold,
                        error="DeepEval returned no metric payload for the requested metric.",
                        duration_ms=duration_ms,
                        metadata={},
                    )
                )
                continue

            results.append(
                _build_metric_result(
                    case=case,
                    framework_version=framework_version,
                    evaluation_mode=evaluation_mode,
                    metric_name=metric_name,
                    metric_type=spec.metric_type,
                    score=_float_or_none(getattr(metric_data, "score", None)),
                    threshold=_float_or_none(getattr(metric_data, "threshold", spec.threshold)),
                    passed=bool(getattr(metric_data, "success", False)),
                    error=_string_or_none(getattr(metric_data, "error", None)),
                    duration_ms=duration_ms,
                    metadata={
                        "evaluation_model": _string_or_none(
                            getattr(metric_data, "evaluation_model", None)
                        )
                    },
                )
            )
    return results


def _build_judge_metric(
    *,
    metric_name: str,
    spec: DeepEvalMetricSpec,
    bindings: DeepEvalBindings,
    judge_provider: str,
    judge_model: str | None,
):
    if judge_provider == "gemini":
        os.environ["USE_GEMINI_MODEL"] = "1"
    factory = bindings.metric_factories[metric_name]
    return factory(
        threshold=spec.threshold,
        model=judge_model,
        async_mode=False,
    )


def _require_judge_configuration(args: argparse.Namespace, judge_metrics: list[str]) -> None:
    if not judge_metrics:
        return
    if args.judge_provider == "none" or not args.judge_model:
        raise ValueError(
            "Judge mode requires explicit judge configuration: set --judge-provider and "
            "--judge-model."
        )
    if args.judge_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required for judge-provider=openai.")
    if args.judge_provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY is required for judge-provider=gemini.")


def _judge_skip_reason(metric_name: str, case: DeepEvalPreparedCase) -> str | None:
    if not case.actual_output:
        return "answer text is missing for this case"
    if metric_name in {"faithfulness", "hallucination", "contextual_relevancy"} and not (
        case.retrieval_context or case.context
    ):
        return "retrieval context is required for this metric"
    return None


def _workflow_metric_result(
    *,
    case: DeepEvalPreparedCase,
    framework_version: str | None,
    evaluation_mode: str,
    metric_name: str,
) -> DeepEvalMetricResult | None:
    metadata = case.metadata
    if metric_name == "routing_accuracy":
        return _build_metric_result(
            case=case,
            framework_version=framework_version,
            evaluation_mode=evaluation_mode,
            metric_name=metric_name,
            metric_type="deterministic",
            score=_float_or_none(metadata.get("routing_accuracy")) or 0.0,
            threshold=1.0,
            metadata={},
        )
    if metric_name == "decision_status_match":
        expected = metadata.get("expected_decision_status")
        if expected is None:
            return None
        score = 1.0 if metadata.get("decision_status") == expected else 0.0
        return _build_metric_result(
            case=case,
            framework_version=framework_version,
            evaluation_mode=evaluation_mode,
            metric_name=metric_name,
            metric_type="deterministic",
            score=score,
            threshold=1.0,
            metadata={},
        )
    if metric_name == "approval_status_match":
        expected = metadata.get("expected_approval_status")
        if expected is None:
            return None
        score = 1.0 if metadata.get("approval_status") == expected else 0.0
        return _build_metric_result(
            case=case,
            framework_version=framework_version,
            evaluation_mode=evaluation_mode,
            metric_name=metric_name,
            metric_type="deterministic",
            score=score,
            threshold=1.0,
            metadata={},
        )
    if metric_name == "summary_status_match":
        expected = metadata.get("expected_summary_status")
        if expected is None:
            return None
        score = 1.0 if metadata.get("summary_status") == expected else 0.0
        return _build_metric_result(
            case=case,
            framework_version=framework_version,
            evaluation_mode=evaluation_mode,
            metric_name=metric_name,
            metric_type="deterministic",
            score=score,
            threshold=1.0,
            metadata={},
        )
    if metric_name == "trace_completeness":
        return _build_metric_result(
            case=case,
            framework_version=framework_version,
            evaluation_mode=evaluation_mode,
            metric_name=metric_name,
            metric_type="deterministic",
            score=_float_or_none(metadata.get("trace_completeness")) or 0.0,
            threshold=1.0,
            metadata={},
        )
    if metric_name == "unsupported_claim_avoidance":
        expected_failure_mode = _string_or_none(metadata.get("expected_failure_mode"))
        notes = _string_or_none(metadata.get("notes")) or ""
        if (
            expected_failure_mode != "insufficient_business_evidence"
            and "avoid inventing" not in notes.lower()
        ):
            return None
        score = 0.0 if _contains_unsupported_claim(case.actual_output or "") else 1.0
        return _build_metric_result(
            case=case,
            framework_version=framework_version,
            evaluation_mode=evaluation_mode,
            metric_name=metric_name,
            metric_type="deterministic",
            score=score,
            threshold=1.0,
            metadata={},
        )
    return None


def _deterministic_metric(
    *,
    case: DeepEvalPreparedCase,
    framework_version: str | None,
    evaluation_mode: str,
    metric_name: str,
    threshold: float,
    score: float | None,
    metadata: dict[str, object],
) -> DeepEvalMetricResult | None:
    if score is None:
        return None
    return _build_metric_result(
        case=case,
        framework_version=framework_version,
        evaluation_mode=evaluation_mode,
        metric_name=metric_name,
        metric_type="deterministic",
        score=score,
        threshold=threshold,
        metadata=metadata,
    )


def _build_metric_result(
    *,
    case: DeepEvalPreparedCase,
    framework_version: str | None,
    evaluation_mode: str,
    metric_name: str,
    metric_type: str,
    score: float | None,
    threshold: float | None,
    passed: bool | None = None,
    skipped: bool = False,
    skip_reason: str | None = None,
    error: str | None = None,
    duration_ms: float | None = None,
    metadata: dict[str, object],
) -> DeepEvalMetricResult:
    if (
        passed is None
        and skipped is False
        and error is None
        and score is not None
        and threshold is not None
    ):
        passed = score >= threshold
    if skipped:
        passed = None
    elif error is not None and passed is None:
        passed = False
    return DeepEvalMetricResult(
        evaluation_framework="deepeval",
        framework_version=framework_version,
        evaluation_mode=evaluation_mode,
        dataset_identifier=case.dataset_identifier,
        case_id=case.case_id,
        category=case.category,
        scope=case.scope,
        surface=case.surface,
        metric_name=metric_name,
        metric_type=metric_type,
        score=score,
        threshold=threshold,
        passed=passed,
        skipped=skipped,
        skip_reason=skip_reason,
        error=error,
        duration_ms=duration_ms,
        metadata={**case.metadata, **metadata},
    )


def _citation_score(case: DeepEvalPreparedCase) -> float | None:
    metadata = case.metadata
    if case.scope == "workflow":
        coverage = _float_or_none(metadata.get("citation_coverage"))
        return coverage if coverage is not None else 0.0

    if "citation_coverage" in metadata:
        return _float_or_none(metadata.get("citation_coverage")) or 0.0

    expected_min_citations = int(metadata.get("expected_min_citations", 0) or 0)
    actual_citation_count = int(metadata.get("actual_citation_count", 0) or 0)
    if expected_min_citations == 0:
        return 1.0
    return min(actual_citation_count / expected_min_citations, 1.0)


def _response_field_completeness(case: DeepEvalPreparedCase) -> float | None:
    expected_status_code = int(case.metadata.get("expected_status_code", 200) or 200)
    if expected_status_code != 200:
        return None
    checks = [bool(case.actual_output and case.actual_output.strip())]
    expected_min_citations = int(case.metadata.get("expected_min_citations", 0) or 0)
    expected_citation_required = bool(case.metadata.get("expected_citation_required", False))
    if expected_min_citations > 0 or expected_citation_required:
        actual_citation_count = case.metadata.get("actual_citation_count")
        if actual_citation_count is not None:
            checks.append(int(actual_citation_count or 0) > 0)
        else:
            checks.append(bool(case.retrieval_context))
    if case.metadata.get("used_agent_workflow") is True:
        checks.append(bool(case.metadata.get("actual_intent")))
    if case.metadata.get("used_legacy_fallback") is True:
        checks.append(_legacy_fallback_is_compatible(case))
    return sum(1.0 for check in checks if check) / len(checks)


def _error_state_correctness(case: DeepEvalPreparedCase) -> float | None:
    expected_status_code = int(case.metadata.get("expected_status_code", 200) or 200)
    if expected_status_code == 200 and case.source_error is None:
        return None
    actual_status_code = int(case.metadata.get("status_code", expected_status_code) or 0)
    expected_error_detail = _string_or_none(case.metadata.get("expected_error_detail"))
    actual_error_detail = _string_or_none(case.metadata.get("actual_error_detail"))
    if actual_status_code != expected_status_code:
        return 0.0
    if expected_error_detail is not None and actual_error_detail != expected_error_detail:
        return 0.0
    if expected_status_code != 200 and not actual_error_detail:
        return 0.0
    return 1.0


def _legacy_fallback_is_compatible(case: DeepEvalPreparedCase) -> bool:
    metadata = case.metadata
    return (
        metadata.get("used_legacy_fallback") is True
        and metadata.get("actual_intent") in (None, "")
        and metadata.get("decision_status") in (None, "")
        and metadata.get("summary_status") in (None, "")
    )


def _contains_unsupported_claim(text: str) -> bool:
    normalized = text.lower()
    forbidden_fragments = (
        "annualized",
        "revenue lift",
        "usd ",
        "statistically significant",
        "roi",
    )
    return any(fragment in normalized for fragment in forbidden_fragments)


def _metric_data_for_name(test_result: object, metric_name: str):
    for metric_data in getattr(test_result, "metrics_data", []) or []:
        if getattr(metric_data, "name", None) == metric_name:
            return metric_data
    return None


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
