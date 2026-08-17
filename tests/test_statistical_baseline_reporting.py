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
    assert payload["dataset_size"] == 48
    assert len(payload["case_results"]) == 48
    assert {item["actual_status"] for item in payload["case_results"]} >= {
        "completed",
        "ineligible",
        "abstained",
        "unsupported",
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
        "## Summary Counts",
        "## Blocking Failures",
        "## Advisory Findings",
        "## Skipped Checks",
        "## Numerical Reference Failures",
        "## Abstention Correctness",
        "## Determinism",
        "## Diagnostic Completeness",
        "## Uncertainty Completeness",
        "## Limitations",
        "## Offline Execution",
    ):
        assert heading in markdown
    assert "13" in markdown
    assert "no network" in markdown.lower()


def test_markdown_is_derived_without_becoming_the_policy_source() -> None:
    report = _report()

    markdown = render_statistical_baseline_markdown(report)

    assert f"- Overall status: {report.overall_status}" in markdown
    assert f"- Cases passed: {report.cases_passed}" in markdown
    assert "Machine-readable JSON is authoritative." in markdown
