from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from packages.evals.policy.models import LoadedSource, PolicySource, SourceMetric

_PERCENT_RE = re.compile(r"(-?\d+(?:\.\d+)?)%")
_FLOAT_RE = re.compile(r"(-?\d+(?:\.\d+)?)")
_FACTUALITY_CATEGORIES = (
    "unsupported_factual_claim",
    "unsupported_numerical_claim",
    "fabricated_revenue_or_roi",
    "fabricated_statistical_significance",
    "fabricated_experiment_result",
    "citation_missing",
    "citation_does_not_support_claim",
    "contradiction_with_retrieved_context",
    "contradiction_with_structured_experiment_data",
    "overconfident_answer_with_insufficient_evidence",
    "answer_generated_when_abstention_was_expected",
)
_FACTUALITY_SEVERITIES = ("low", "medium", "high", "critical")
_FACTUALITY_CASE_STATUSES = ("pass", "warning", "fail", "skipped")


def load_source(source: PolicySource, report_dir: Path) -> LoadedSource | None:
    path = report_dir / source.path
    if not path.is_file():
        return None
    try:
        if source.format == "rag_markdown":
            metrics = _load_rag_markdown(path)
        elif source.format == "agent_markdown":
            metrics = _load_agent_markdown(path)
        elif source.format == "agent_e2e_markdown":
            metrics = _load_agent_e2e_markdown(path)
        elif source.format == "ragas_json":
            metrics = _load_ragas_json(path)
        elif source.format == "deepeval_json":
            metrics = _load_deepeval_json(path)
        elif source.format == "prompt_regression_json":
            metrics = _load_prompt_regression_json(path)
        elif source.format == "factuality_json":
            metrics = _load_factuality_json(path)
        else:
            raise ValueError(f"unsupported source format: {source.format}")
    except ValueError as exc:
        raise ValueError(f"{source.source_id}: {exc}") from exc
    return LoadedSource(
        source_id=source.source_id,
        path=path,
        format=source.format,
        metrics=metrics,
    )


def _load_rag_markdown(path: Path) -> dict[str, SourceMetric]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    return {
        "rag.questions_evaluated": _value_metric(
            "rag.questions_evaluated",
            _extract_number_after_prefix(lines, "- Questions evaluated:"),
        ),
        "rag.retrieval_success_rate": _value_metric(
            "rag.retrieval_success_rate",
            _extract_percent_after_prefix(lines, "- Retrieval success rate:"),
        ),
        "rag.average_citation_coverage": _value_metric(
            "rag.average_citation_coverage",
            _extract_percent_after_prefix(lines, "- Average citation coverage:"),
        ),
        "rag.average_retrieval_latency_ms": _value_metric(
            "rag.average_retrieval_latency_ms",
            _extract_ms_after_prefix(lines, "- Average retrieval latency:"),
        ),
        "rag.average_llm_latency_ms": _value_metric(
            "rag.average_llm_latency_ms",
            _extract_ms_after_prefix(lines, "- Average LLM latency:"),
        ),
    }


def _load_agent_markdown(path: Path) -> dict[str, SourceMetric]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    summary = _extract_markdown_table(lines, "## Summary")
    metrics = {
        "Samples evaluated": "agent.samples_evaluated",
        "Pass count": "agent.pass_count",
        "Fail count": "agent.fail_count",
        "Workflow success rate": "agent.workflow_success_rate",
        "Average workflow latency": "agent.average_workflow_latency_ms",
        "Average trace completeness": "agent.trace_completeness",
        "Planner intent accuracy": "agent.planner_intent_accuracy",
        "Required agent routing accuracy": "agent.routing_accuracy",
        "Citation coverage": "agent.citation_coverage",
        "Decision recommendation coverage": "agent.recommendation_coverage",
    }
    result: dict[str, SourceMetric] = {}
    for label, metric_id in metrics.items():
        raw_value = summary.get(label)
        if raw_value is None:
            raise ValueError(f"missing `{label}` in agent summary")
        result[metric_id] = _parse_labeled_metric(metric_id, raw_value)

    result["agent.total_tool_calls"] = _value_metric(
        "agent.total_tool_calls",
        _extract_number_after_prefix(lines, "- Total tool calls:"),
    )
    result["agent.total_tool_failures"] = _value_metric(
        "agent.total_tool_failures",
        _extract_number_after_prefix(lines, "- Total tool failures:"),
    )
    result["agent.average_tool_calls"] = _value_metric(
        "agent.average_tool_calls",
        _extract_number_after_prefix(lines, "- Average tool calls per sample:"),
    )
    return result


def _load_agent_e2e_markdown(path: Path) -> dict[str, SourceMetric]:
    lines = path.read_text(encoding="utf-8").splitlines()
    pass_fail = _extract_text_after_prefix(lines, "- Pass/fail summary:")
    match = re.search(r"(\d+)\s+passed,\s+(\d+)\s+failed", pass_fail)
    if match is None:
        raise ValueError("agent_e2e pass/fail summary is malformed")
    return {
        "agent_e2e.sample_count": _value_metric(
            "agent_e2e.sample_count",
            _extract_number_after_prefix(lines, "- Total test/eval cases:"),
        ),
        "agent_e2e.pass_count": _value_metric("agent_e2e.pass_count", int(match.group(1))),
        "agent_e2e.fail_count": _value_metric("agent_e2e.fail_count", int(match.group(2))),
        "agent_e2e.default_agent_workflow_coverage": _value_metric(
            "agent_e2e.default_agent_workflow_coverage",
            _extract_percent_after_prefix(lines, "- Default agent workflow coverage:"),
        ),
        "agent_e2e.legacy_fallback_coverage": _value_metric(
            "agent_e2e.legacy_fallback_coverage",
            _extract_percent_after_prefix(lines, "- Legacy fallback coverage:"),
        ),
        "agent_e2e.intent_accuracy": _value_metric(
            "agent_e2e.intent_accuracy",
            _extract_percent_after_prefix(lines, "- Intent accuracy:"),
        ),
        "agent_e2e.routing_accuracy": _value_metric(
            "agent_e2e.routing_accuracy",
            _extract_percent_after_prefix(lines, "- Required agent routing accuracy:"),
        ),
        "agent_e2e.citation_coverage": _value_metric(
            "agent_e2e.citation_coverage",
            _extract_percent_after_prefix(lines, "- Citation coverage:"),
        ),
        "agent_e2e.decision_coverage": _value_metric(
            "agent_e2e.decision_coverage",
            _extract_percent_after_prefix(lines, "- Decision coverage:"),
        ),
        "agent_e2e.executive_summary_coverage": _value_metric(
            "agent_e2e.executive_summary_coverage",
            _extract_percent_after_prefix(lines, "- Executive summary coverage:"),
        ),
        "agent_e2e.approval_status_coverage": _value_metric(
            "agent_e2e.approval_status_coverage",
            _extract_percent_after_prefix(lines, "- Approval status coverage:"),
        ),
        "agent_e2e.average_workflow_latency_ms": _value_metric(
            "agent_e2e.average_workflow_latency_ms",
            _extract_ms_after_prefix(lines, "- Average workflow latency:"),
        ),
    }


def _load_ragas_json(path: Path) -> dict[str, SourceMetric]:
    payload = _load_json(path)
    metric_results = payload.get("metric_results")
    if not isinstance(metric_results, list):
        raise ValueError("ragas metric_results must be a list")
    metrics: dict[str, SourceMetric] = {}
    for item in metric_results:
        if not isinstance(item, dict):
            raise ValueError("ragas metric result entries must be mappings")
        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError("ragas metric result is missing a name")
        metric_id = f"ragas.{name}"
        status = str(item.get("status", "")).strip()
        if status == "skipped":
            metrics[metric_id] = SourceMetric(
                metric_id=metric_id,
                value=None,
                status="skipped",
                reason=str(item.get("reason", "")).strip() or "skipped",
            )
            continue
        metrics[metric_id] = _value_metric(
            metric_id,
            _expect_number(item.get("average_score"), f"ragas metric `{name}`"),
        )
    return metrics


def _load_deepeval_json(path: Path) -> dict[str, SourceMetric]:
    payload = _load_json(path)
    metric_results = payload.get("metric_results")
    if not isinstance(metric_results, list):
        raise ValueError("deepeval metric_results must be a list")

    grouped_scores: dict[str, list[float]] = defaultdict(list)
    grouped_skips: dict[str, list[str]] = defaultdict(list)
    for item in metric_results:
        if not isinstance(item, dict):
            raise ValueError("deepeval metric result entries must be mappings")
        metric_name = str(item.get("metric_name", "")).strip()
        if not metric_name:
            raise ValueError("deepeval metric result is missing metric_name")
        if item.get("skipped") is True:
            reason = str(item.get("skip_reason", "")).strip() or "skipped"
            if reason not in grouped_skips[metric_name]:
                grouped_skips[metric_name].append(reason)
            continue
        score = item.get("score")
        if score is None:
            continue
        grouped_scores[metric_name].append(
            _expect_number(score, f"deepeval metric `{metric_name}`")
        )

    metrics: dict[str, SourceMetric] = {}
    for metric_name in sorted(set(grouped_scores) | set(grouped_skips)):
        metric_id = f"deepeval.{metric_name}.average_score"
        if grouped_scores.get(metric_name):
            scores = grouped_scores[metric_name]
            metrics[metric_id] = _value_metric(metric_id, sum(scores) / len(scores))
        else:
            metrics[metric_id] = SourceMetric(
                metric_id=metric_id,
                value=None,
                status="skipped",
                reason="; ".join(grouped_skips[metric_name]),
            )
    return metrics


def _load_prompt_regression_json(path: Path) -> dict[str, SourceMetric]:
    payload = _load_json(path)
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("prompt regression summary must be a mapping")
    cases_run = int(_expect_number(summary.get("cases_run"), "prompt regression cases_run"))
    regressions = int(_expect_number(summary.get("regressions"), "prompt regression regressions"))
    failures = int(_expect_number(summary.get("failures"), "prompt regression failures"))
    pass_rate = 0.0 if cases_run == 0 else (cases_run - regressions - failures) / cases_run
    metrics: dict[str, SourceMetric] = {
        "prompt_regression.summary.pass_rate": _value_metric(
            "prompt_regression.summary.pass_rate",
            pass_rate,
        ),
        "prompt_regression.summary.regressions": _value_metric(
            "prompt_regression.summary.regressions",
            regressions,
        ),
        "prompt_regression.summary.failures": _value_metric(
            "prompt_regression.summary.failures",
            failures,
        ),
        "prompt_regression.summary.passed": _value_metric(
            "prompt_regression.summary.passed",
            1.0 if bool(summary.get("passed")) else 0.0,
        ),
    }
    raw_metrics = payload.get("metrics")
    if not isinstance(raw_metrics, list):
        raise ValueError("prompt regression metrics must be a list")
    for item in raw_metrics:
        if not isinstance(item, dict):
            raise ValueError("prompt regression metric entries must be mappings")
        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError("prompt regression metric is missing a name")
        for suffix in ("baseline", "candidate", "delta"):
            value = item.get(suffix)
            metric_id = f"prompt_regression.metric.{name}.{suffix}"
            if value is None:
                metrics[metric_id] = SourceMetric(
                    metric_id=metric_id,
                    value=None,
                    status="skipped",
                    reason=f"{suffix} value unavailable",
                )
            else:
                metrics[metric_id] = _value_metric(
                    metric_id,
                    _expect_number(value, f"prompt regression metric `{name}.{suffix}`"),
                )
    return metrics


def _load_factuality_json(path: Path) -> dict[str, SourceMetric]:
    payload = _load_json(path)
    metrics: dict[str, SourceMetric] = {}
    policy_result = payload.get("policy_result", {})
    if not isinstance(policy_result, dict):
        raise ValueError("factuality policy_result must be a mapping")
    status = str(policy_result.get("status", "")).strip()
    if status:
        metrics["factuality.policy_status"] = SourceMetric(
            metric_id="factuality.policy_status",
            value=status,
            status="pass",
        )
    findings_by_category = _expect_mapping(
        payload.get("findings_by_category"), "findings_by_category"
    )
    for category in _FACTUALITY_CATEGORIES:
        metric_id = f"factuality.findings.{category}"
        metrics[metric_id] = _value_metric(
            metric_id,
            _expect_number(findings_by_category.get(category, 0), metric_id),
        )

    findings_by_severity = _expect_mapping(
        payload.get("findings_by_severity"), "findings_by_severity"
    )
    for severity in _FACTUALITY_SEVERITIES:
        metric_id = f"factuality.severity.{severity}"
        metrics[metric_id] = _value_metric(
            metric_id,
            _expect_number(findings_by_severity.get(severity, 0), metric_id),
        )

    case_status_counts = _expect_mapping(payload.get("case_status_counts"), "case_status_counts")
    for status_name in _FACTUALITY_CASE_STATUSES:
        metric_id = f"factuality.case_status.{status_name}"
        metrics[metric_id] = _value_metric(
            metric_id,
            _expect_number(case_status_counts.get(status_name, 0), metric_id),
        )
    return metrics


def _extract_markdown_table(lines: list[str], heading: str) -> dict[str, str]:
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise ValueError(f"missing heading `{heading}`") from exc
    rows: dict[str, str] = {}
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("## ") and stripped != heading:
            break
        if not stripped.startswith("|"):
            continue
        parts = [part.strip() for part in stripped.split("|")[1:-1]]
        if len(parts) != 2 or parts[0] in {"Metric", "---"} or parts[0].startswith("---"):
            continue
        rows[parts[0]] = parts[1]
    return rows


def _extract_text_after_prefix(lines: list[str], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            return line.split(prefix, maxsplit=1)[1].strip()
    raise ValueError(f"missing `{prefix}`")


def _extract_number_after_prefix(lines: list[str], prefix: str) -> int | float:
    text = _extract_text_after_prefix(lines, prefix)
    return _extract_float(text)


def _extract_percent_after_prefix(lines: list[str], prefix: str) -> float:
    text = _extract_text_after_prefix(lines, prefix)
    match = _PERCENT_RE.search(text)
    if match is None:
        raise ValueError(f"missing percent value for `{prefix}`")
    return float(match.group(1)) / 100.0


def _extract_ms_after_prefix(lines: list[str], prefix: str) -> float:
    text = _extract_text_after_prefix(lines, prefix)
    return float(_extract_float(text))


def _extract_float(text: str) -> float | int:
    match = _FLOAT_RE.search(text)
    if match is None:
        raise ValueError(f"missing numeric value in `{text}`")
    value = float(match.group(1))
    return int(value) if value.is_integer() else value


def _parse_labeled_metric(metric_id: str, raw_value: str) -> SourceMetric:
    if raw_value.endswith("%"):
        return _value_metric(
            metric_id,
            _extract_percent_after_prefix([f"- x: {raw_value}"], "- x:"),
        )
    if "ms" in raw_value:
        return _value_metric(metric_id, float(_extract_float(raw_value)))
    return _value_metric(metric_id, _extract_float(raw_value))


def _value_metric(metric_id: str, value: float | int | str | bool) -> SourceMetric:
    return SourceMetric(metric_id=metric_id, value=value, status="pass")


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.name}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _expect_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"factuality `{label}` must be a mapping")
    return value


def _expect_number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)
