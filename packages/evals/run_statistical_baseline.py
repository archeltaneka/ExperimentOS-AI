"""Offline CLI for the Phase 4 statistical reliability baseline."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from packages.evals.policy.config import load_quality_policy
from packages.evals.policy.evaluator import PolicyEvaluator
from packages.evals.policy.models import QualityPolicy
from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
from packages.evals.statistical.models import (
    StatisticalBaselineReport,
    StatisticalPolicyRuleResult,
    StatisticalPolicySummary,
)
from packages.evals.statistical.reporting import (
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
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args(argv)


def run_statistical_baseline(args: argparse.Namespace) -> StatisticalBaselineReport:
    """Evaluate references, apply centralized policy rules, and write both artifacts."""
    central_policy = load_quality_policy(args.policy)
    dataset = load_statistical_reference_cases(args.dataset)
    report = (
        StatisticalBaselineEvaluator()
        .evaluate(dataset)
        .model_copy(update={"policy_version": central_policy.version})
    )
    _write(args.json_output, statistical_baseline_to_json(report))

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
        metrics=tuple(metric for metric in central_policy.metrics if metric.source == "statistics"),
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
                method=_policy_rule_method(item.metric_id),
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
        if report.overall_status == "fail" or policy_result.overall_status == "fail"
        else "pass"
    )
    report = report.model_copy(
        update={"overall_status": overall_status, "quality_policy": policy_summary}
    )
    _write(args.json_output, statistical_baseline_to_json(report))
    _write(args.output, render_statistical_baseline_markdown(report))
    return report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _policy_rule_method(metric_id: str) -> str:
    for method in ("cuped", "sequential", "bayesian", "fixed_horizon"):
        if f".{method}." in metric_id:
            return method
    if "plan_integrity" in metric_id:
        return "sequential"
    if "bayesian" in metric_id:
        return "bayesian"
    return "all_randomized_inference"


def _policy_rule_case_id(metric_id: str, report: StatisticalBaselineReport) -> str:
    evidence = _matching_case_ids(metric_id, report)
    return ",".join(evidence) if evidence else "aggregate"


def _policy_rule_evidence(
    metric_id: str,
    report: StatisticalBaselineReport,
) -> tuple[str, ...]:
    dimension = metric_id.removeprefix("statistics.failures.")
    evidence = tuple(
        f"{case.case_id}:{check.rule_id}"
        for case in report.case_results
        for check in case.checks
        if check.status.value == "fail" and check.dimension == dimension
    )
    return evidence or (f"observed:{metric_id}",)


def _matching_case_ids(
    metric_id: str,
    report: StatisticalBaselineReport,
) -> tuple[str, ...]:
    dimension = metric_id.removeprefix("statistics.failures.")
    return tuple(
        case.case_id
        for case in report.case_results
        if any(
            check.status.value == "fail" and check.dimension == dimension for check in case.checks
        )
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_statistical_baseline(args)
    except Exception as error:
        print(f"Statistical baseline infrastructure error: {error}")
        return STATISTICAL_INFRASTRUCTURE_EXIT_CODE
    print(f"Wrote Phase 4 statistical baseline JSON to {args.json_output}")
    print(f"Wrote Phase 4 statistical baseline Markdown to {args.output}")
    if report.overall_status == "fail":
        return STATISTICAL_QUALITY_FAILURE_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
