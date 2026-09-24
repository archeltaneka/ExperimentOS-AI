"""Offline CLI for the Phase 4 statistical reliability baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

from packages.evals.policy.config import load_quality_policy
from packages.evals.policy.evaluator import PolicyEvaluator
from packages.evals.policy.models import QualityPolicy
from packages.evals.policy.report import quality_policy_report_to_json
from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
from packages.evals.statistical.models import (
    Phase4InfrastructureFailure,
    StatisticalBaselineReport,
    StatisticalCaseResult,
    StatisticalPolicyRuleResult,
    StatisticalPolicySummary,
)
from packages.evals.statistical.reporting import (
    render_phase4_job_summary,
    render_statistical_baseline_markdown,
    statistical_baseline_to_json,
)

DEFAULT_POLICY_PATH = Path("config/evaluation/quality_policy.yaml")
DEFAULT_JSON_OUTPUT = Path("reports/phase4/statistical_baseline.json")
DEFAULT_MARKDOWN_OUTPUT = Path("reports/phase4/statistical_baseline.md")
STATISTICAL_QUALITY_FAILURE_EXIT_CODE = 1
STATISTICAL_INFRASTRUCTURE_EXIT_CODE = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic offline Phase 4 statistical reliability baseline."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_STATISTICAL_DATASET_PATH)
    parser.add_argument(
        "--require-optional",
        choices=("econml", "dowhy"),
        action="append",
        default=[],
        help="Require installed optional capabilities; absence becomes blocking.",
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--scope", choices=("complete", "optional-adapters"), default="complete")
    parser.add_argument("--workflow-dataset", type=Path)
    parser.add_argument("--policy-json-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args(argv)
    args.policy_json_output = (
        args.policy_json_output or args.json_output.parent / "quality_policy.json"
    )
    args.summary_output = args.summary_output or args.json_output.parent / "github_summary.md"
    return args


def run_statistical_baseline(args: argparse.Namespace) -> StatisticalBaselineReport:
    """Evaluate references, apply centralized policy rules, and write both artifacts."""
    from packages.evals.agent_analysis_cases import load_analysis_workflow_cases
    from packages.evals.statistical.advanced.registry import REGISTRY
    from packages.evals.statistical.workflow.cases import REQUIRED_CASE_IDS, validate_case_inventory
    from packages.evals.statistical.workflow.optional import PACKAGES
    from packages.evals.statistical.workflow.policy import workflow_quality_status
    from packages.evals.statistical.workflow.suite import evaluate_workflow_suite
    from packages.evals.statistical.workflow.telemetry import privacy_violations

    args._stage = "configuration"
    outputs = (args.json_output, args.output, args.policy_json_output, args.summary_output)
    if len({p.resolve() for p in outputs}) != len(outputs):
        raise ValueError("artifact destinations must be distinct")
    central_policy = load_quality_policy(args.policy)
    args._stage = "fixtures"
    cases = validate_case_inventory(
        load_analysis_workflow_cases(args.workflow_dataset), required_ids=REQUIRED_CASE_IDS
    )
    dataset = load_statistical_reference_cases(args.dataset)
    if args.scope == "optional-adapters":
        cases = tuple(c for c in cases if c.expected_method in PACKAGES)
        dataset = dataset.model_copy(
            update={
                "cases": tuple(
                    c
                    for c in dataset.cases
                    if c.advanced and REGISTRY[c.advanced.capability_id].dependency
                )
            }
        )
    args._stage = "native"
    report = (
        StatisticalBaselineEvaluator(required_dependencies=tuple(args.require_optional))
        .evaluate(dataset)
        .model_copy(update={"policy_version": central_policy.version})
    )
    args._report = report
    args._stage = "workflow"
    workflow, errors = evaluate_workflow_suite(
        cases, scope=args.scope, required_dependencies=tuple(args.require_optional)
    )
    version = hashlib.sha256(
        json.dumps(
            [c.model_dump(mode="json") for c in cases],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    report = report.model_copy(
        update={
            "scope": args.scope,
            "workflow": workflow,
            "workflow_case_count": len(workflow),
            "workflow_dataset_version": version,
            "workflow_quality_status": workflow_quality_status(
                tuple(check.status for c in workflow for check in c.checks.values())
            ),
            "limitations": tuple(
                x for x in report.limitations if not x.startswith("Business-impact conversion")
            )
            + (
                "Database integration is skipped by this offline command; "
                "the existing database CI job executes it separately.",
                "Business-impact scenarios require explicit sourced inputs; "
                "no rollout automation is performed.",
            ),
        }
    )
    if privacy_violations(report.model_dump(mode="json")):
        args._report = None
        raise ValueError("unsafe evaluation artifact")
    args._report = report
    if errors:
        raise ValueError("workflow infrastructure failure")
    args._stage = "writing"
    _write(args.json_output, statistical_baseline_to_json(report))

    args._stage = "policy"
    source = central_policy.sources.get("statistics")
    if source is None:
        raise ValueError("centralized quality policy is missing the statistics source")
    statistical_policy = QualityPolicy(
        version=central_policy.version,
        sources={
            "statistics": replace(
                source,
                path=Path(args.json_output.name),
            )
        },
        metrics=tuple(
            replace(metric, value=args.scope) if metric.metric_id == "analysis.scope" else metric
            for metric in central_policy.metrics
            if metric.source == "statistics"
        ),
    )
    if not statistical_policy.metrics:
        raise ValueError("centralized quality policy has no statistical rules")
    policy_result = PolicyEvaluator(
        policy=statistical_policy,
        report_dir=args.json_output.parent,
    ).evaluate()
    policy_summary = StatisticalPolicySummary(
        policy_version=policy_result.policy_version,
        overall_status=policy_result.overall_status,
        blocking_rule_ids=tuple(item.metric_id for item in policy_result.violations),
        advisory_rule_ids=tuple(item.metric_id for item in policy_result.warnings),
        skipped_rule_ids=tuple(item.metric_id for item in policy_result.skipped_metrics),
        rules=tuple(
            StatisticalPolicyRuleResult(
                rule_id=item.metric_id,
                category=item.category,
                severity=item.severity,
                status=item.status,
                observed_value=item.observed_value,
                operator=item.operator,
                threshold_value=item.threshold_value,
                required=item.required,
                message=item.message,
                method=_policy_rule_method(item.metric_id, report),
                design=_policy_rule_design(item.metric_id, report),
                estimand=_policy_rule_estimand(item.metric_id, report),
                case_id=_policy_rule_case_id(item.metric_id, report),
                expected_value=item.threshold_value,
                actual_value=item.observed_value,
                diagnostic_evidence=_policy_rule_evidence(item.metric_id, report),
            )
            for item in policy_result.metrics_evaluated
        ),
    )
    overall_status = (
        "fail"
        if report.overall_status == "fail"
        or policy_result.overall_status == "fail"
        or report.workflow_quality_status == "fail"
        else "warning"
        if policy_result.overall_status == "warning"
        or report.workflow_quality_status == "warning"
        or report.cases_advisory > 0
        else "pass"
    )
    report = report.model_copy(
        update={"overall_status": overall_status, "quality_policy": policy_summary}
    )
    args._report = report
    args._stage = "rendering"
    contents = (
        statistical_baseline_to_json(report),
        render_statistical_baseline_markdown(report),
        quality_policy_report_to_json(policy_result),
        render_phase4_job_summary(report),
    )
    if any(privacy_violations(value) for value in contents):
        raise ValueError("unsafe rendered artifact")
    args._stage = "writing"
    for path, content in zip(outputs, contents, strict=True):
        _write(path, content)
    return report


def _write(path: Path, content: str) -> None:
    import os
    from tempfile import mkstemp

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = mkstemp(prefix=".phase4-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _policy_rule_method(metric_id: str, report: StatisticalBaselineReport | None = None) -> str:
    if metric_id.startswith("analysis."):
        methods = (
            {c.method or "unselected" for c in _matching_cases(metric_id, report)}
            if report
            else set()
        )
        return ",".join(sorted(methods)) if methods else "workflow"
    if any(
        name in metric_id
        for name in (
            "interface_leakage",
            "exception_normalization",
            "unsupported_inference",
            "data_leakage",
            "dependency",
        )
    ):
        return "advanced_causal"
    for method in (
        "identification",
        "did",
        "propensity",
        "ipw",
        "coverage",
        "cuped",
        "sequential",
        "bayesian",
        "fixed_horizon",
    ):
        if f".{method}." in metric_id:
            return method
    if "plan_integrity" in metric_id:
        return "sequential"
    if "bayesian" in metric_id:
        return "bayesian"
    return "all_statistical_methods"


def _policy_rule_design(metric_id: str, report: StatisticalBaselineReport) -> str:
    cases = _matching_cases(metric_id, report)
    designs = tuple(sorted({case.design for case in cases}))
    return ",".join(designs) if designs else "aggregate"


def _policy_rule_estimand(metric_id: str, report: StatisticalBaselineReport) -> str:
    cases = _matching_cases(metric_id, report)
    estimands = tuple(sorted({case.estimand for case in cases}))
    return ",".join(estimands) if estimands else "aggregate"


def _policy_rule_case_id(metric_id: str, report: StatisticalBaselineReport) -> str:
    evidence = _matching_case_ids(metric_id, report)
    return ",".join(evidence) if evidence else "aggregate"


def _policy_rule_evidence(
    metric_id: str,
    report: StatisticalBaselineReport,
) -> tuple[str, ...]:
    if metric_id.startswith("analysis."):
        return tuple(
            f"{case.case_id}:{case.method or 'unselected'}:{finding.rule_id}"
            for case in report.workflow
            for finding in case.checks.values()
            if finding.rule_id == metric_id and finding.status == "fail"
        ) or (f"observed:{metric_id}",)
    dimension = metric_id.removeprefix("statistics.failures.")
    evidence: set[str] = set()
    for case in report.case_results:
        failed_rules = tuple(
            check.rule_id
            for check in case.checks
            if check.status.value == "fail" and check.dimension == dimension
        )
        if not failed_rules:
            continue
        codes = tuple(sorted({*failed_rules, *case.diagnostic_codes}))
        evidence.update(f"{case.case_id}:{code}" for code in codes)
    return tuple(sorted(evidence)) or (f"observed:{metric_id}",)


def _matching_case_ids(
    metric_id: str,
    report: StatisticalBaselineReport,
) -> tuple[str, ...]:
    if metric_id.startswith("analysis."):
        return tuple(
            c.case_id
            for c in report.workflow
            if any(
                check.rule_id == metric_id and check.status == "fail" for check in c.checks.values()
            )
        )
    dimension = metric_id.removeprefix("statistics.failures.")
    return tuple(
        case.case_id
        for case in report.case_results
        if any(
            check.status.value == "fail" and check.dimension == dimension for check in case.checks
        )
    )


def _matching_cases(
    metric_id: str,
    report: StatisticalBaselineReport,
) -> tuple[StatisticalCaseResult, ...]:
    matching_ids = set(_matching_case_ids(metric_id, report))
    cases = report.workflow if metric_id.startswith("analysis.") else report.case_results
    return tuple(case for case in cases if case.case_id in matching_ids)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_statistical_baseline(args)
    except Exception:
        failure = Phase4InfrastructureFailure(
            stage=getattr(args, "_stage", "configuration"),
            evaluation=getattr(args, "_report", None),
        )
        message = (
            "Phase 4 infrastructure_fail: " + failure.stage + " (phase4.infrastructure_failure)\n"
        )
        for path, content in (
            (args.json_output, failure.model_dump_json(indent=2) + "\n"),
            (args.policy_json_output, failure.model_dump_json(indent=2) + "\n"),
            (args.output, message),
            (args.summary_output, message),
        ):
            try:
                _write(path, content)
            except OSError:
                pass
        print(message.strip(), file=sys.stderr)
        return STATISTICAL_INFRASTRUCTURE_EXIT_CODE
    print(f"Wrote Phase 4 statistical baseline JSON to {args.json_output}")
    print(f"Wrote Phase 4 statistical baseline Markdown to {args.output}")
    if report.overall_status == "fail":
        return STATISTICAL_QUALITY_FAILURE_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
