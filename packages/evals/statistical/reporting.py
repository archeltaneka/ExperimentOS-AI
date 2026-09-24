"""Authoritative JSON and derived Markdown for the Phase 4 baseline."""

from __future__ import annotations

from .models import CheckStatus, StatisticalBaselineReport, StatisticalCapability


def statistical_baseline_to_json(report: StatisticalBaselineReport) -> str:
    """Serialize the typed report; this representation is the policy source of truth."""
    return report.model_dump_json(indent=2) + "\n"


def render_phase4_job_summary(report: StatisticalBaselineReport) -> str:
    unavailable = sum(c.dependency_state == "unavailable" for c in report.workflow)
    failed = sum(any(v.status == "fail" for v in c.checks.values()) for c in report.workflow)
    methods = ", ".join(sorted({c.method for c in report.workflow if c.method}))
    blocking = report.quality_policy.blocking_rule_ids if report.quality_policy else ()
    advisory = report.quality_policy.advisory_rule_ids if report.quality_policy else ()
    return "\n".join(
        [
            "## Phase 4 Complete Causal Quality",
            "",
            f"- Scope: `{report.scope}`; status: **{report.overall_status}**.",
            f"- Native references: {report.dataset_size}; failed: {report.cases_failed}; "
            f"advisory: {report.cases_advisory}.",
            f"- Workflow cases: {len(report.workflow)}; failed: {failed}; "
            f"quality: {report.workflow_quality_status}.",
            f"- Methods: {methods or 'not executed'}.",
            f"- Optional unavailable: {unavailable}; "
            "controlled absence is listed separately in JSON.",
            f"- Blocking rules: {', '.join(blocking) or 'none'}.",
            f"- Advisory rules: {', '.join(advisory) or 'none'}.",
            "- Privacy and compatibility: see per-case structured checks; skipped is not passing.",
            "- Database integration: skipped offline; executed separately by the database CI job.",
            "- Artifacts: statistical_baseline.json, statistical_baseline.md, "
            "quality_policy.json, github_summary.md.",
            "",
        ]
    )


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
        (
            "- Covered methods: fixed-horizon, CUPED, sequential, Bayesian A/B, causal "
            "identification, DiD, propensity diagnostics, IPW ATE, and IPW ATT."
        ),
    ]
    if report.workflow:
        lines.extend(
            [
                "",
                "## End-to-End Workflow Quality",
                "",
                render_phase4_job_summary(report),
                "| Case | Method | Execution | Quality | Dependency |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        from .workflow.policy import workflow_quality_status

        for case in report.workflow:
            quality = workflow_quality_status(tuple(c.status for c in case.checks.values()))
            lines.append(
                f"| {case.case_id} | {case.method or 'unselected'} | {case.execution_status} | "
                f"{quality} | {case.dependency_state} |"
            )
        lines.extend(["", "### Workflow Findings", ""])
        for case in report.workflow:
            for finding in case.checks.values():
                if finding.status in {"fail", "warning"}:
                    lines.append(
                        f"- {finding.status}: `{case.case_id}` / "
                        f"`{case.method or 'unselected'}` / `{finding.rule_id}`."
                    )
    _method_section(
        lines,
        report,
        "Overall Observational Reliability Status",
        {
            StatisticalCapability.CAUSAL_IDENTIFICATION,
            StatisticalCapability.DIFFERENCE_IN_DIFFERENCES,
            StatisticalCapability.PROPENSITY_SCORE,
            StatisticalCapability.IPW_ATE,
            StatisticalCapability.IPW_ATT,
            StatisticalCapability.OBSERVATIONAL_COVERAGE,
        },
    )
    _method_section(
        lines,
        report,
        "Identification Status",
        {StatisticalCapability.CAUSAL_IDENTIFICATION},
    )
    _method_section(
        lines,
        report,
        "Difference-in-Differences Results",
        {StatisticalCapability.DIFFERENCE_IN_DIFFERENCES},
    )
    _method_section(
        lines,
        report,
        "Propensity Diagnostics",
        {StatisticalCapability.PROPENSITY_SCORE},
    )
    _method_section(lines, report, "ATE Status", {StatisticalCapability.IPW_ATE})
    _method_section(lines, report, "ATT Status", {StatisticalCapability.IPW_ATT})
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
    _advanced_section(lines, report)
    _finding_section(lines, report, "Advisory Findings", CheckStatus.ADVISORY)
    _finding_section(lines, report, "Skipped Checks", CheckStatus.SKIPPED)
    _dimension_section(lines, report, "Numerical Reference Failures", "reference_accuracy")
    _dimension_section(lines, report, "Abstention Correctness", "abstention")
    _dimension_section(lines, report, "Determinism", "determinism")
    _dimension_section(lines, report, "Telemetry Privacy", "telemetry_privacy")
    _dimension_section(lines, report, "Assumption Completeness", "assumptions")
    _dimension_section(lines, report, "Identification Completeness", "identification")
    _dimension_section(lines, report, "Coverage Simulation Summary", "coverage")
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


def _advanced_section(lines: list[str], report: StatisticalBaselineReport) -> None:
    cases = tuple(c for c in report.case_results if c.advanced is not None)
    if not cases:
        return
    lines.extend(
        [
            "",
            "## Advanced Causal Conformance",
            "",
            "Suite version: 1. Execution status and conformance verdict are separate.",
            "",
            "| Case / capability | Native / semantic status | Verdict | Dependency / version | "
            "Adapter / implementation | Configuration fingerprint | Execution |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for case in cases:
        detail = case.advanced
        assert detail is not None
        lines.append(
            f"| `{case.case_id}` | {case.actual_status} / {detail.semantic_status} | "
            f"{case.evaluation_status.value} | {detail.dependency_state} / "
            f"{detail.dependency_version or 'not installed'} | {detail.adapter_id} "
            f"v{detail.adapter_version} / {detail.implementation_version} | "
            f"`{detail.configuration_fingerprint or 'unavailable'}` | {detail.execution_kind} |"
        )
    for dimension, title in (
        ("determinism", "Advanced Determinism"),
        ("uncertainty", "Advanced Uncertainty"),
        ("telemetry_privacy", "Advanced Privacy"),
        ("provenance", "Advanced Provenance"),
    ):
        checks = [c for case in cases for c in case.checks if c.dimension == dimension]
        lines.extend(
            [
                "",
                f"### {title}",
                "",
                f"Checks: {len(checks)}; "
                f"failed: {sum(c.status is CheckStatus.FAIL for c in checks)}; "
                f"skipped: {sum(c.status is CheckStatus.SKIPPED for c in checks)}.",
            ]
        )


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
