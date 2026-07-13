from __future__ import annotations

import json
from dataclasses import asdict

from packages.evals.policy.models import PolicyEvaluationResult


def render_quality_policy_report(result: PolicyEvaluationResult) -> str:
    lines = [
        "# Phase 3 Quality Policy Report",
        "",
        f"- Policy version: {result.policy_version}",
        f"- Report directory: `{result.report_dir}`",
        f"- Overall status: {result.overall_status}",
        f"- Recommendation: {result.recommendation}",
        "",
        "## Categories",
        "",
        "| Category | Status | Pass | Warning | Fail | Skipped |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for category in result.category_results.values():
        lines.append(
            f"| {category.name} | {category.status} | {category.passed_count} | "
            f"{category.warning_count} | {category.failed_count} | {category.skipped_count} |"
        )

    lines.extend(["", "## Metrics Evaluated", ""])
    for metric in result.metrics_evaluated:
        lines.append(
            f"- `{metric.metric_id}`: status={metric.status}, observed={metric.observed_value}, "
            f"threshold={metric.operator} {metric.threshold_value}, source=`{metric.source_path}`"
        )

    lines.extend(["", "## Violations", ""])
    if not result.violations:
        lines.append("No blocking policy violations were recorded.")
    else:
        for violation in result.violations:
            lines.append(f"- `{violation.metric_id}` ({violation.severity}): {violation.message}")

    lines.extend(["", "## Warnings", ""])
    if not result.warnings:
        lines.append("No warning-only deviations were recorded.")
    else:
        for warning in result.warnings:
            lines.append(f"- `{warning.metric_id}`: {warning.message}")

    lines.extend(["", "## Skipped Metrics", ""])
    if not result.skipped_metrics:
        lines.append("No metrics were skipped.")
    else:
        for metric in result.skipped_metrics:
            lines.append(f"- `{metric.metric_id}`: {metric.message}")

    lines.extend(["", "## Rationale", ""])
    for reason in result.rationale:
        lines.append(f"- {reason}")

    return "\n".join(lines) + "\n"


def quality_policy_report_to_json(result: PolicyEvaluationResult) -> str:
    return json.dumps(asdict(result), indent=2) + "\n"
