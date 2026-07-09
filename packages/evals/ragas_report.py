from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RagasMetricResult:
    name: str
    status: str
    average_score: float | None
    reason: str | None = None
    description: str = ""


@dataclass(frozen=True)
class RagasCaseResult:
    question_id: str
    experiment_id: str
    category: str
    difficulty: str
    retrieved_context_count: int
    retrieved_document_count: int
    source_error: str | None
    metric_scores: dict[str, float | None]


@dataclass(frozen=True)
class RagasEvaluationReport:
    generated_at: str
    dataset_path: str
    dataset_size: int
    eligible_sample_count: int
    excluded_sample_count: int
    ragas_available: bool
    ragas_version: str | None
    ragas_import_note: str | None
    qa_embedding_provider: str
    qa_embedding_model: str
    qa_llm_provider: str
    qa_llm_model: str
    judge_llm_provider: str
    judge_llm_model: str
    judge_embedding_provider: str
    judge_embedding_model: str
    metrics_requested: tuple[str, ...]
    metrics_run: tuple[str, ...]
    metric_results: tuple[RagasMetricResult, ...]
    case_results: tuple[RagasCaseResult, ...]
    limitations: tuple[str, ...]


def render_ragas_report(report: RagasEvaluationReport) -> str:
    lines = [
        "# RAGAS Evaluation Report",
        "",
        "## Dataset",
        "",
        f"- Source dataset: `{report.dataset_path}`",
        f"- Dataset size: {report.dataset_size}",
        f"- Eligible samples: {report.eligible_sample_count}",
        f"- Excluded samples: {report.excluded_sample_count}",
        "",
        "## Providers",
        "",
        f"- QA embedding provider: {report.qa_embedding_provider}",
        f"- QA embedding model: {report.qa_embedding_model}",
        f"- QA LLM provider: {report.qa_llm_provider}",
        f"- QA LLM model: {report.qa_llm_model}",
        f"- Judge LLM provider: {report.judge_llm_provider}",
        f"- Judge LLM model: {report.judge_llm_model}",
        f"- Judge embedding provider: {report.judge_embedding_provider}",
        f"- Judge embedding model: {report.judge_embedding_model}",
        "",
        "## RAGAS Runtime",
        "",
        f"- RAGAS available: {_yes_no(report.ragas_available)}",
        f"- RAGAS version: {report.ragas_version or 'unavailable'}",
        f"- Metrics requested: {', '.join(report.metrics_requested) or 'none'}",
        f"- Metrics run: {', '.join(report.metrics_run) or 'none'}",
    ]
    if report.ragas_import_note:
        lines.append(f"- Import note: {report.ragas_import_note}")

    lines.extend(
        [
            "",
            "## Metric Summary",
            "",
            "| Metric | Status | Average Score | Reason |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for metric in report.metric_results:
        score = _format_score(metric.average_score)
        lines.append(
            f"| {metric.name} | {metric.status} | {score} | {metric.reason or ''} |"
        )

    lines.extend(
        [
            "",
            "## Per-Case Results",
            "",
            "| ID | Experiment | Category | Difficulty | Contexts | Documents | "
            "Source Error | Scores |",
            "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for case in report.case_results:
        scores = ", ".join(
            f"{name}={_format_score(value)}"
            for name, value in sorted(case.metric_scores.items())
        )
        lines.append(
            f"| {case.question_id} | {case.experiment_id} | {case.category} | "
            f"{case.difficulty} | {case.retrieved_context_count} | "
            f"{case.retrieved_document_count} | {case.source_error or ''} | {scores} |"
        )

    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    if not report.limitations:
        lines.append("No additional limitations were recorded for this run.")
    else:
        for limitation in report.limitations:
            lines.append(f"- {limitation}")

    return "\n".join(lines) + "\n"


def ragas_report_to_json(report: RagasEvaluationReport) -> str:
    return json.dumps(_report_to_mapping(report), indent=2) + "\n"


def _report_to_mapping(report: RagasEvaluationReport) -> dict[str, object]:
    payload = asdict(report)
    payload["metric_results"] = [asdict(metric) for metric in report.metric_results]
    payload["case_results"] = [asdict(case) for case in report.case_results]
    return payload


def _format_score(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "n/a"
    return f"{value:.4f}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
