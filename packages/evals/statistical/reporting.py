"""Authoritative JSON and derived Markdown for the Phase 4 baseline."""

from __future__ import annotations

from .models import CheckStatus, StatisticalBaselineReport, StatisticalCapability


def statistical_baseline_to_json(report: StatisticalBaselineReport) -> str:
    """Serialize the typed report; this representation is the policy source of truth."""
    return report.model_dump_json(indent=2) + "\n"


def render_statistical_baseline_markdown(report: StatisticalBaselineReport) -> str:
    """Render a concise developer and CI investigation view from structured results."""
    lines = [
        "# Phase 4 Statistical Reliability Baseline",
        "",
        f"- Overall status: {report.overall_status}",
        f"- Baseline version: `{report.baseline_version}`",
        f"- Policy version: `{report.policy_version}`",
        "- Machine-readable JSON is authoritative.",
        "",
        "## Overall Randomized-Inference Status",
        "",
        f"- Status: {report.overall_status}",
        "- Covered methods: fixed-horizon, CUPED, sequential, and Bayesian A/B.",
    ]
    _method_section(
        lines,
        report,
        "Fixed-Horizon Status",
        {StatisticalCapability.RANDOMIZED_BINARY, StatisticalCapability.RANDOMIZED_CONTINUOUS},
    )
    _method_section(lines, report, "CUPED Status", {StatisticalCapability.CUPED})
    _method_section(lines, report, "Sequential Status", {StatisticalCapability.SEQUENTIAL})
    _method_section(
        lines,
        report,
        "Bayesian Status",
        {StatisticalCapability.BAYESIAN_BINARY, StatisticalCapability.BAYESIAN_CONTINUOUS},
    )
    lines.extend(
        [
            "",
            "## Evaluated Capabilities",
            "",
            "| Capability | Cases | Passed | Failed | Advisory |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for capability in report.capability_results:
        lines.append(
            f"| {capability.capability.value} | {capability.cases} | {capability.passed} | "
            f"{capability.failed} | {capability.advisory} |"
        )
    lines.extend(
        [
            "",
            "## Summary Counts",
            "",
            f"- Dataset size: {report.dataset_size}",
            f"- Cases passed: {report.cases_passed}",
            f"- Cases failed: {report.cases_failed}",
            f"- Cases advisory: {report.cases_advisory}",
            f"- Cases invalid: {report.cases_invalid}",
            f"- Cases abstained: {report.cases_abstained}",
            f"- Cases skipped: {report.cases_skipped}",
        ]
    )
    _finding_section(lines, report, "Blocking Failures", CheckStatus.FAIL)
    _finding_section(lines, report, "Advisory Findings", CheckStatus.ADVISORY)
    _finding_section(lines, report, "Skipped Checks", CheckStatus.SKIPPED)
    _dimension_section(lines, report, "Numerical Reference Failures", "reference_accuracy")
    _dimension_section(lines, report, "Abstention Correctness", "abstention")
    _dimension_section(lines, report, "Determinism", "determinism")
    _dimension_section(lines, report, "Telemetry Privacy", "telemetry_privacy")
    _dimension_section(lines, report, "Assumption Completeness", "assumptions")
    _dimension_section(lines, report, "Sequential Plan Integrity", "plan_integrity")
    _dimension_section(lines, report, "Diagnostic Completeness", "diagnostics")
    _dimension_section(lines, report, "Uncertainty Completeness", "uncertainty")
    lines.extend(["", "## Centralized Quality Policy", ""])
    if report.quality_policy is None:
        lines.append("Policy aggregation was not requested for this in-process report.")
    else:
        lines.append(f"- Overall status: {report.quality_policy.overall_status}")
        lines.append(f"- Blocking failures: {len(report.quality_policy.blocking_rule_ids)}")
        lines.append(f"- Advisory findings: {len(report.quality_policy.advisory_rule_ids)}")
        lines.append(f"- Skipped rules: {len(report.quality_policy.skipped_rule_ids)}")
    lines.extend(["", "## Numerical Tolerances", ""])
    tolerance_rows = [
        (case.case_id, check)
        for case in report.case_results
        for check in case.checks
        if check.tolerance is not None
    ]
    if not tolerance_rows:
        lines.append("No floating-point reference checks were evaluated.")
    else:
        lines.extend(
            [
                "| Case | Field | Absolute tolerance | Provenance |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for case_id, check in tolerance_rows:
            lines.append(
                f"| `{case_id}` | `{check.check_id}` | {check.tolerance} | "
                f"{check.tolerance_provenance} |"
            )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    lines.extend(
        [
            "",
            "## Offline Execution",
            "",
            f"- {report.offline_provider_statement}",
        ]
    )
    return "\n".join(lines) + "\n"


def _finding_section(
    lines: list[str],
    report: StatisticalBaselineReport,
    heading: str,
    status: CheckStatus,
) -> None:
    lines.extend(["", f"## {heading}", ""])
    findings = [
        (case.case_id, check)
        for case in report.case_results
        for check in case.checks
        if check.status is status
    ]
    if not findings:
        lines.append("None.")
        return
    for case_id, check in findings:
        lines.append(f"- `{case_id}` / `{check.rule_id}`: {check.message}")


def _dimension_section(
    lines: list[str],
    report: StatisticalBaselineReport,
    heading: str,
    dimension: str,
) -> None:
    lines.extend(["", f"## {heading}", ""])
    checks = [
        check
        for case in report.case_results
        for check in case.checks
        if check.dimension == dimension
    ]
    failures = sum(check.status is CheckStatus.FAIL for check in checks)
    skipped = sum(check.status is CheckStatus.SKIPPED for check in checks)
    lines.append(f"- Checks: {len(checks)}")
    lines.append(f"- Failures: {failures}")
    lines.append(f"- Skipped: {skipped}")


def _method_section(
    lines: list[str],
    report: StatisticalBaselineReport,
    heading: str,
    capabilities: set[StatisticalCapability],
) -> None:
    cases = tuple(case for case in report.case_results if case.capability in capabilities)
    statuses = {case.evaluation_status for case in cases}
    status = (
        "fail"
        if CheckStatus.FAIL in statuses
        else "advisory"
        if CheckStatus.ADVISORY in statuses
        else "skipped"
        if cases and statuses == {CheckStatus.SKIPPED}
        else "pass"
    )
    lines.extend(
        [
            "",
            f"## {heading}",
            "",
            f"- Status: {status}",
            f"- Cases: {len(cases)}",
            f"- Blocking failures: {sum(c.evaluation_status is CheckStatus.FAIL for c in cases)}",
            "- Advisory findings: "
            f"{sum(c.evaluation_status is CheckStatus.ADVISORY for c in cases)}",
            f"- Skipped cases: {sum(c.evaluation_status is CheckStatus.SKIPPED for c in cases)}",
        ]
    )


__all__ = ["render_statistical_baseline_markdown", "statistical_baseline_to_json"]
