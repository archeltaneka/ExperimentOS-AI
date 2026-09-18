from __future__ import annotations

import json

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
from packages.evals.statistical.models import StatisticalBaselineReport
from packages.evals.statistical.reporting import (
    render_statistical_baseline_markdown,
    statistical_baseline_to_json,
)


def _report() -> StatisticalBaselineReport:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    return StatisticalBaselineEvaluator().evaluate(dataset)


def test_json_is_authoritative_structured_and_deterministic() -> None:
    report = _report()

    first = statistical_baseline_to_json(report)
    repeated = statistical_baseline_to_json(report)
    payload = json.loads(first)

    assert first == repeated
    assert first.endswith("\n")
    assert payload["schema_version"] == "1"
    assert payload["overall_status"] == "pass"
    assert len([c for c in payload["case_results"] if c["advanced"] is None]) == 92
    assert payload["dataset_size"] == len(payload["case_results"])
    assert {item["actual_status"] for item in payload["case_results"]} >= {
        "completed",
        "ineligible",
        "abstained",
        "unsupported",
        "identified",
        "invalid",
        "partially_identified",
    }


def test_json_exposes_tolerance_provenance_on_numerical_checks() -> None:
    payload = json.loads(statistical_baseline_to_json(_report()))
    numerical_checks = [
        check
        for case in payload["case_results"]
        for check in case["checks"]
        if check["tolerance"] is not None
    ]

    assert numerical_checks
    assert all(check["tolerance_rationale"] for check in numerical_checks)
    assert all(check["tolerance_provenance"] for check in numerical_checks)


def test_markdown_contains_required_investigation_sections() -> None:
    markdown = render_statistical_baseline_markdown(_report())

    for heading in (
        "# Phase 4 Statistical Reliability Baseline",
        "## Evaluated Capabilities",
        "## Overall Observational Reliability Status",
        "## Identification Status",
        "## Difference-in-Differences Results",
        "## Propensity Diagnostics",
        "## ATE Status",
        "## ATT Status",
        "## Summary Counts",
        "## Blocking Failures",
        "## Advisory Findings",
        "## Skipped Checks",
        "## Numerical Reference Failures",
        "## Abstention Correctness",
        "## Determinism",
        "## Diagnostic Completeness",
        "## Uncertainty Completeness",
        "## Coverage Simulation Summary",
        "## Limitations",
        "## Offline Execution",
    ):
        assert heading in markdown
    assert "13" in markdown
    assert "no network" in markdown.lower()


def test_artifact_schema_has_observational_dimensions_without_raw_analysis_records() -> None:
    payload = json.loads(statistical_baseline_to_json(_report()))
    observational = [
        case
        for case in payload["case_results"]
        if case["capability"]
        in {
            "causal_identification",
            "difference_in_differences",
            "propensity_score",
            "ipw_ate",
            "ipw_att",
            "observational_coverage",
        }
    ]

    assert observational
    assert all(
        {"case_id", "design", "estimand", "method", "reference_result", "tolerances", "duration_ms"}
        <= set(case)
        for case in observational
    )
    coverage = next(
        case for case in observational if case["capability"] == "observational_coverage"
    )
    assert coverage["simulation_metadata"]["dgp_version"] == "1.0.0"
    serialized = json.dumps(payload)
    for forbidden in ('"scores":', '"weights":', '"unit_id":', '"outcome":'):
        assert forbidden not in serialized


def test_markdown_is_derived_without_becoming_the_policy_source() -> None:
    report = _report()

    markdown = render_statistical_baseline_markdown(report)

    assert f"- Overall status: {report.overall_status}" in markdown
    assert f"- Cases passed: {report.cases_passed}" in markdown
    assert "Machine-readable JSON is authoritative." in markdown
