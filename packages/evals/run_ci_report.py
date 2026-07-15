from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from packages.evals.ci_reporting.aggregator import build_ci_quality_report
from packages.evals.ci_reporting.github import SubprocessGhApiClient, publish_comment
from packages.evals.ci_reporting.models import (
    CategorySummary,
    CiQualityReport,
    ExecutionDetails,
    MetricDelta,
    RenderLimits,
    ReportFinding,
    ReportMetadata,
    SuiteResult,
)
from packages.evals.ci_reporting.renderer import (
    render_job_summary,
    render_pr_comment,
    write_report_outputs,
)

DEFAULT_OUTPUT = Path("reports/phase3/ci/pr_quality_report.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ExperimentOS CI evaluation reports.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Normalize existing evaluation JSON reports.")
    _add_build_arguments(build)

    render = subparsers.add_parser("render", help="Render a normalized CI report.")
    render.add_argument("--input", type=Path, required=True)
    render.add_argument(
        "--format", choices=("job-summary", "pr-comment", "markdown"), default="job-summary"
    )
    render.add_argument("--output", type=Path)
    render.add_argument("--max-findings", type=int, default=5)

    validate = subparsers.add_parser("validate", help="Validate a normalized CI report.")
    validate.add_argument("--input", type=Path, required=True)
    comment = subparsers.add_parser("comment", help="Update the marker-owned PR comment.")
    comment.add_argument("--body-file", type=Path, required=True)
    comment.add_argument("--repository", required=True)
    comment.add_argument("--pull-request-number", type=int, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "build":
            return _build(args)
        if args.command == "render":
            return _render(args)
        if args.command == "validate":
            _load_report(args.input)
            print("CI report is valid.")
            return 0
        if args.command == "comment":
            outcome = publish_comment(
                SubprocessGhApiClient(),
                repository=args.repository,
                pull_request_number=args.pull_request_number,
                body=args.body_file.read_text(encoding="utf-8"),
                is_pull_request=True,
            )
            print(outcome.message)
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CI report error: {exc}")
        return 2
    return 2


def _add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    parser.add_argument("--quality-policy-report", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--format", choices=("all", "json", "markdown", "pr-comment"), default="all"
    )
    parser.add_argument("--max-findings", type=int, default=5)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--workflow-run-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--commit-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--pull-request-number", type=int)
    parser.add_argument("--base-ref", default=os.environ.get("GITHUB_BASE_REF"))
    parser.add_argument("--head-ref", default=os.environ.get("GITHUB_HEAD_REF"))


def _build(args: argparse.Namespace) -> int:
    report_dir = args.report_dir
    if args.quality_policy_report is not None:
        report_dir = args.quality_policy_report.parent.parent
    metadata = ReportMetadata(
        workflow_run_id=args.workflow_run_id,
        repository=args.repository,
        commit_sha=args.commit_sha,
        pull_request_number=args.pull_request_number,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )
    report = build_ci_quality_report(report_dir, metadata=metadata, strict=args.strict)
    output = args.output
    markdown_path = output.with_suffix(".md")
    comment_path = output.with_name("pr_comment.md")
    limits = RenderLimits(max_findings=args.max_findings)
    if args.format == "json":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    elif args.format == "markdown":
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_job_summary(report, limits=limits), encoding="utf-8")
    elif args.format == "pr-comment":
        comment_path.parent.mkdir(parents=True, exist_ok=True)
        comment_path.write_text(render_pr_comment(report, limits=limits), encoding="utf-8")
    else:
        write_report_outputs(
            report,
            json_path=output,
            markdown_path=markdown_path,
            comment_path=comment_path,
            limits=limits,
        )
    print(f"Wrote CI quality report to {output}")
    return 0


def _render(args: argparse.Namespace) -> int:
    report = _load_report(args.input)
    limits = RenderLimits(max_findings=args.max_findings)
    markdown = (
        render_pr_comment(report, limits=limits)
        if args.format == "pr-comment"
        else render_job_summary(report, limits=limits)
    )
    if args.output is None:
        print(markdown, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    return 0


def _load_report(path: Path) -> CiQualityReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CI report must be a JSON object.")
    metadata_payload = _object(payload.get("metadata"))
    execution_payload = _object(payload.get("execution"))
    return CiQualityReport(
        overall_status=_string(payload.get("overall_status")) or "incomplete",
        policy_version=_string(payload.get("policy_version")) or None,
        metadata=ReportMetadata(**_known(ReportMetadata, metadata_payload)),
        categories=tuple(
            CategorySummary(**_known(CategorySummary, _object(item)))
            for item in _list(payload.get("categories"))
        ),
        critical_violations=tuple(
            ReportFinding(**_known(ReportFinding, _object(item)))
            for item in _list(payload.get("critical_violations"))
        ),
        warnings=tuple(
            ReportFinding(**_known(ReportFinding, _object(item)))
            for item in _list(payload.get("warnings"))
        ),
        skipped_metrics=tuple(
            ReportFinding(**_known(ReportFinding, _object(item)))
            for item in _list(payload.get("skipped_metrics"))
        ),
        metric_deltas=tuple(
            MetricDelta(**_known(MetricDelta, _object(item)))
            for item in _list(payload.get("metric_deltas"))
        ),
        suites=tuple(
            SuiteResult(**_suite_values(_object(item))) for item in _list(payload.get("suites"))
        ),
        execution=ExecutionDetails(**_known(ExecutionDetails, execution_payload)),
        failure_type=_string(payload.get("failure_type")) or None,
        artifact_name=_string(payload.get("artifact_name")) or None,
        metadata_extra=_object(payload.get("metadata_extra")),
    )


def _known(dataclass_type: type, payload: dict[str, Any]) -> dict[str, Any]:
    return {name: payload[name] for name in dataclass_type.__dataclass_fields__ if name in payload}


def _suite_values(payload: dict[str, Any]) -> dict[str, Any]:
    values = _known(SuiteResult, payload)
    metrics = values.get("key_metrics")
    if isinstance(metrics, list):
        values["key_metrics"] = tuple(
            tuple(str(value) for value in metric) for metric in metrics if isinstance(metric, list)
        )
    return values


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


if __name__ == "__main__":
    raise SystemExit(main())
