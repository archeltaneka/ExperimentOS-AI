from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DeepEvalMetricResult:
    evaluation_framework: str
    framework_version: str | None
    evaluation_mode: str
    dataset_identifier: str
    case_id: str
    category: str
    scope: str
    surface: str
    metric_name: str
    metric_type: str
    score: float | None
    threshold: float | None
    passed: bool | None
    skipped: bool
    skip_reason: str | None
    error: str | None
    duration_ms: float | None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DeepEvalEvaluationReport:
    generated_at: str
    evaluation_mode: str
    deepeval_available: bool
    deepeval_version: str | None
    deepeval_import_note: str | None
    dataset_identifiers: tuple[str, ...]
    response_case_count: int
    workflow_case_count: int
    metrics_requested: tuple[str, ...]
    metrics_executed: tuple[str, ...]
    metrics_skipped: tuple[str, ...]
    external_judge_used: bool
    judge_provider: str
    judge_model: str | None
    metric_results: tuple[DeepEvalMetricResult, ...]
    limitations: tuple[str, ...]


def render_deepeval_report(report: DeepEvalEvaluationReport) -> str:
    aggregate_scores = _aggregate_scores(report.metric_results)
    category_summary = _category_summary(report.metric_results)
    failing_cases = _failing_cases(report.metric_results)
    skip_reasons = _skip_reasons(report.metric_results)

    lines = [
        "# DeepEval Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Generated at: {report.generated_at}",
        f"- Evaluation mode: {report.evaluation_mode}",
        f"- DeepEval available: {'yes' if report.deepeval_available else 'no'}",
        f"- DeepEval version: {report.deepeval_version or 'unavailable'}",
        f"- Response cases: {report.response_case_count}",
        f"- Workflow cases: {report.workflow_case_count}",
        f"- External judge used: {'yes' if report.external_judge_used else 'no'}",
        f"- Judge provider/model: {report.judge_provider} / {report.judge_model or 'none'}",
        f"- Metrics requested: {', '.join(report.metrics_requested) or 'none'}",
        f"- Metrics executed: {', '.join(report.metrics_executed) or 'none'}",
        f"- Metrics skipped: {', '.join(report.metrics_skipped) or 'none'}",
        "",
        "## Aggregate Scores",
        "",
        "| Metric | Type | Avg Score | Passed | Failed | Skipped |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for metric_name, row in aggregate_scores:
        lines.append(
            f"| {metric_name} | {row['metric_type']} | {row['average_score']} | "
            f"{row['passed']} | {row['failed']} | {row['skipped']} |"
        )

    lines.extend(
        [
            "",
            "## Category Results",
            "",
            "| Category | Pass | Fail | Skip |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for category, counts in category_summary:
        lines.append(
            f"| {category} | {counts['passed']} | {counts['failed']} | {counts['skipped']} |"
        )

    lines.extend(
        [
            "",
            "## Case Metrics",
            "",
            "| Case | Category | Scope | Metric | Score | Status | Detail |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for result in report.metric_results:
        status = "skipped" if result.skipped else ("passed" if result.passed else "failed")
        detail = result.skip_reason or result.error or ""
        score = "" if result.score is None else f"{result.score:.3f}"
        lines.append(
            f"| {result.case_id} | {result.category} | {result.scope} | {result.metric_name} | "
            f"{score} | {status} | {detail} |"
        )

    lines.extend(["", "## Skipped Metrics", ""])
    if not skip_reasons:
        lines.append("No metrics were skipped.")
    else:
        for metric_name, reasons in skip_reasons:
            joined = "; ".join(reasons)
            lines.append(f"- `{metric_name}`: {joined}")

    lines.extend(["", "## Failing Cases", ""])
    if not failing_cases:
        lines.append("No failing cases were recorded.")
    else:
        for case_id, reasons in failing_cases:
            lines.append(f"- `{case_id}`: {'; '.join(reasons)}")

    lines.extend(["", "## Limitations", ""])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")

    return "\n".join(lines) + "\n"


def deepeval_report_to_json(report: DeepEvalEvaluationReport) -> str:
    return json.dumps(asdict(report), indent=2)


def _aggregate_scores(
    results: tuple[DeepEvalMetricResult, ...],
) -> list[tuple[str, dict[str, object]]]:
    grouped: dict[str, list[DeepEvalMetricResult]] = defaultdict(list)
    for result in results:
        grouped[result.metric_name].append(result)

    rows: list[tuple[str, dict[str, object]]] = []
    for metric_name, metric_results in sorted(grouped.items()):
        scores = [result.score for result in metric_results if result.score is not None]
        average = sum(scores) / len(scores) if scores else None
        rows.append(
            (
                metric_name,
                {
                    "metric_type": metric_results[0].metric_type,
                    "average_score": "" if average is None else f"{average:.3f}",
                    "passed": sum(1 for result in metric_results if result.passed is True),
                    "failed": sum(
                        1
                        for result in metric_results
                        if result.skipped is False and result.passed is False
                    ),
                    "skipped": sum(1 for result in metric_results if result.skipped),
                },
            )
        )
    return rows


def _category_summary(
    results: tuple[DeepEvalMetricResult, ...],
) -> list[tuple[str, dict[str, int]]]:
    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {"passed": 0, "failed": 0, "skipped": 0}
    )
    for result in results:
        if result.skipped:
            grouped[result.category]["skipped"] += 1
        elif result.passed:
            grouped[result.category]["passed"] += 1
        else:
            grouped[result.category]["failed"] += 1
    return sorted(grouped.items())


def _failing_cases(
    results: tuple[DeepEvalMetricResult, ...],
) -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for result in results:
        if result.skipped or result.passed is not False:
            continue
        detail = result.error or result.skip_reason or "failed"
        grouped[result.case_id].append(f"{result.metric_name}: {detail}")
    return sorted(grouped.items())


def _skip_reasons(
    results: tuple[DeepEvalMetricResult, ...],
) -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for result in results:
        if not result.skipped or result.skip_reason is None:
            continue
        if result.skip_reason not in grouped[result.metric_name]:
            grouped[result.metric_name].append(result.skip_reason)
    return sorted(grouped.items())
