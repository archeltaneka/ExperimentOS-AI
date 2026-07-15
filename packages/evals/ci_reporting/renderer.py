from __future__ import annotations

import json
from pathlib import Path

from packages.evals.ci_reporting.models import CiQualityReport, RenderLimits

COMMENT_MARKER = "<!-- experimentos-ai-quality-report -->"
DEFAULT_LIMITS = RenderLimits()


def render_job_summary(report: CiQualityReport, *, limits: RenderLimits = DEFAULT_LIMITS) -> str:
    return _render(report, limits=limits, comment=False)


def render_pr_comment(report: CiQualityReport, *, limits: RenderLimits = DEFAULT_LIMITS) -> str:
    return _render(report, limits=limits, comment=True)


def write_report_outputs(
    report: CiQualityReport,
    *,
    json_path: Path,
    markdown_path: Path,
    comment_path: Path | None = None,
    limits: RenderLimits = DEFAULT_LIMITS,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_job_summary(report, limits=limits), encoding="utf-8")
    if comment_path is not None:
        comment_path.parent.mkdir(parents=True, exist_ok=True)
        comment_path.write_text(render_pr_comment(report, limits=limits), encoding="utf-8")


def _render(report: CiQualityReport, *, limits: RenderLimits, comment: bool) -> str:
    lines = [COMMENT_MARKER] if comment else []
    lines.extend(
        [
            "# ExperimentOS AI Quality Report",
            "",
            f"Overall: **{report.overall_status.upper()}**",
            f"- Policy version: {_text(report.policy_version or 'unavailable')}",
            f"- Commit: {_text(report.metadata.commit_sha or 'unavailable')}",
            f"- Execution mode: {_text(report.metadata.execution_mode)}",
            "",
            "## Quality categories",
            "",
            "| Category | Status | Key result |",
            "| --- | --- | --- |",
        ]
    )
    if report.categories:
        for category in report.categories:
            name = _text(category.name)
            status = _text(category.status)
            key_result = _text(category.key_result)
            lines.append(f"| {name} | {status} | {key_result} |")
    else:
        lines.append("| unavailable | incomplete | No policy category data |")

    _findings(lines, "Critical findings", report.critical_violations, limits.max_findings)
    _findings(lines, "Warnings", report.warnings, limits.max_warnings)
    _findings(lines, "Skipped metrics", report.skipped_metrics, limits.max_warnings)

    lines.extend(["", "## Metric changes", ""])
    deltas = [delta for delta in report.metric_deltas if delta.status != "unavailable"]
    if not deltas:
        lines.append("No compatible baseline comparisons were available.")
    else:
        lines.extend(
            [
                "| Metric | Current | Baseline | Delta | Threshold | Status |",
                "| --- | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for delta in deltas[: limits.max_findings]:
            lines.append(
                f"| {_text(delta.metric_id)} | {_text(delta.current_value)} | "
                f"{_text(delta.baseline_value)} | {_text(delta.absolute_delta)} | "
                f"{_text(delta.threshold)} | {_text(delta.status)} |"
            )

    lines.extend(["", "## Evaluation suites", ""])
    for suite in report.suites[: limits.max_suite_failures]:
        counts = ""
        if suite.cases_run is not None:
            counts = f" ({suite.passed or 0} passed, {suite.failed or 0} failed)"
        lines.append(f"- **{_text(suite.suite_name)}**: {_text(suite.status)}{counts}")
    if len(report.suites) > limits.max_suite_failures:
        omitted = len(report.suites) - limits.max_suite_failures
        lines.append(f"- {omitted} additional suite{'s' if omitted != 1 else ''} omitted.")

    lines.extend(
        [
            "",
            "## Execution details",
            "",
            "- Database-backed path executed: "
            + _yes_no(report.execution.database_backed_path_executed),
            (
                "- Fake providers used: "
                + _yes_no(
                    report.execution.embedding_provider == "fake"
                    and report.execution.llm_provider == "mock"
                )
            ),
            f"- External judge used: {_yes_no(report.execution.external_judge_used)}",
            f"- Live external services called: {_yes_no(report.execution.live_provider_used)}",
            f"- Artifact name: {_text(report.artifact_name or 'unavailable')}",
            "- Workflow run identifier: "
            + _text(report.execution.workflow_run_id or "unavailable"),
            "",
            "## Artifacts",
            "",
            "Open this workflow run's artifacts for full structured and Markdown reports.",
        ]
    )
    return _truncate("\n".join(lines) + "\n", limits.max_characters)


def _findings(lines: list[str], heading: str, findings: tuple, limit: int) -> None:
    lines.extend(["", f"## {heading}", ""])
    if not findings:
        lines.append("None.")
        return
    for finding in findings[:limit]:
        lines.append(f"- {_text(finding.metric_id)}: {_text(finding.message)}")
    omitted = len(findings) - limit
    if omitted > 0:
        noun = heading.lower().removesuffix("s")
        lines.append(f"- {omitted} additional {noun} omitted; see artifacts.")


def _truncate(markdown: str, maximum: int) -> str:
    if len(markdown) <= maximum:
        return markdown
    notice = "\n\n_Report truncated; see artifacts for full details._\n"
    return markdown[: maximum - len(notice)].rstrip() + notice


def _text(value: object) -> str:
    return (
        str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    )


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "unavailable"
    return "yes" if value else "no"
