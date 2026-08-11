from __future__ import annotations

from typing import Any

import pytest

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import (
    StatisticalBaselineEvaluator,
    check_abstention,
    check_diagnostics,
    check_expected_value,
    check_uncertainty,
)
from packages.evals.statistical.models import (
    CheckStatus,
    StatisticalExpectedValue,
    StatisticalTolerance,
)


def _floating_expectation(value: float = 2.5) -> StatisticalExpectedValue:
    return StatisticalExpectedValue(
        path="population.summary.mean",
        value=value,
        tolerance=StatisticalTolerance(
            absolute=1e-6,
            rationale="Independent arithmetic reference.",
            provenance="hand-calculated fixture",
        ),
    )


def test_numeric_reference_check_records_delta_and_tolerance_pass() -> None:
    check = check_expected_value(
        {"population": {"summary": {"mean": 2.5000005}}},
        _floating_expectation(),
    )

    assert check.status is CheckStatus.PASS
    assert check.delta == pytest.approx(5e-7)
    assert check.tolerance == 1e-6
    assert check.tolerance_provenance == "hand-calculated fixture"


def test_numeric_reference_check_fails_outside_declared_tolerance() -> None:
    check = check_expected_value(
        {"population": {"summary": {"mean": 2.500002}}},
        _floating_expectation(),
    )

    assert check.status is CheckStatus.FAIL
    assert check.rule_id == "statistics.reference.numeric_tolerance"


def test_categorical_reference_check_uses_exact_equality() -> None:
    expected = StatisticalExpectedValue(path="status", value="completed")

    assert check_expected_value({"status": "completed"}, expected).status is CheckStatus.PASS
    assert check_expected_value({"status": "inconclusive"}, expected).status is CheckStatus.FAIL


def test_abstention_check_rejects_fabricated_inference() -> None:
    checks = check_abstention(
        expected=True,
        expected_reason="sparse_cell",
        actual={
            "status": "abstained",
            "abstention_reason": {"code": "sparse_cell"},
            "point_effect": {"absolute_effect": {"value": 0.2}},
            "test_result": {"p_value": 0.04, "confidence_interval": {"lower": 0.1, "upper": 0.3}},
        },
    )

    failures = {check.rule_id for check in checks if check.status is CheckStatus.FAIL}
    assert "statistics.abstention.no_point_estimate" in failures
    assert "statistics.abstention.no_p_value" in failures
    assert "statistics.abstention.no_interval" in failures


def test_expected_abstention_with_correct_reason_passes() -> None:
    checks = check_abstention(
        expected=True,
        expected_reason="sparse_cell",
        actual={
            "status": "abstained",
            "abstention_reason": {"code": "sparse_cell"},
            "point_effect": None,
            "test_result": None,
        },
    )

    assert checks
    assert all(check.status is CheckStatus.PASS for check in checks)


def test_diagnostic_completeness_detects_missing_code_and_nondeterministic_order() -> None:
    checks = check_diagnostics(
        expected_codes=("a.code", "b.code"),
        expected_advisory_codes=("b.code",),
        actual_diagnostics=(
            {"code": "b.code", "severity": "warning"},
            {"code": "a.code", "severity": "error"},
        ),
        actual_warnings=({"code": "b.code"},),
        repeated_diagnostics=(
            {"code": "a.code", "severity": "error"},
            {"code": "b.code", "severity": "warning"},
        ),
    )

    failures = {check.rule_id for check in checks if check.status is CheckStatus.FAIL}
    assert "statistics.diagnostics.ordering" in failures
    assert "statistics.diagnostics.required_codes" not in failures

    missing = check_diagnostics(
        expected_codes=("a.code", "b.code"),
        expected_advisory_codes=(),
        actual_diagnostics=({"code": "a.code", "severity": "error"},),
        actual_warnings=(),
    )
    assert any(
        check.rule_id == "statistics.diagnostics.required_codes"
        and check.status is CheckStatus.FAIL
        for check in missing
    )


def test_uncertainty_requires_complete_successful_inference() -> None:
    complete: dict[str, Any] = {
        "status": "completed",
        "estimand": {"kind": "difference_in_means"},
        "treatment_summary": {"n": 5},
        "control_summary": {"n": 5},
        "point_effect": {"absolute_effect": {"value": 1.0}},
        "configuration": {"confidence_level": 0.95},
        "test_result": {
            "test_type": "welch_t",
            "standard_error": 2.0,
            "p_value": 0.63,
            "confidence_interval": {"lower": -3.6, "upper": 5.6, "confidence_level": 0.95},
        },
    }

    assert all(check.status is CheckStatus.PASS for check in check_uncertainty(complete))

    missing_interval = {
        **complete,
        "test_result": {**complete["test_result"], "confidence_interval": None},
    }
    assert any(
        check.rule_id == "statistics.uncertainty.interval_present"
        and check.status is CheckStatus.FAIL
        for check in check_uncertainty(missing_interval)
    )

    missing_standard_error = {
        **complete,
        "test_result": {**complete["test_result"], "standard_error": None},
    }
    assert any(
        check.rule_id == "statistics.uncertainty.standard_error_present"
        and check.status is CheckStatus.FAIL
        for check in check_uncertainty(missing_standard_error)
    )

    bad_confidence = {
        **complete,
        "test_result": {
            **complete["test_result"],
            "confidence_interval": {
                "lower": -3.6,
                "upper": 5.6,
                "confidence_level": 0.90,
            },
        },
    }
    assert any(check.status is CheckStatus.FAIL for check in check_uncertainty(bad_confidence))


def test_abstention_does_not_require_uncertainty() -> None:
    assert check_uncertainty({"status": "abstained", "test_result": None}) == ()


def test_repository_cases_pass_all_reliability_dimensions_deterministically() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)

    first = StatisticalBaselineEvaluator().evaluate(dataset)
    repeated = StatisticalBaselineEvaluator().evaluate(dataset)

    assert first.overall_status == "pass"
    assert first.dataset_size == 13
    assert first.cases_passed == 13
    assert first.cases_failed == 0
    assert first.cases_invalid == 4
    assert first.cases_abstained == 3
    assert tuple(result.case_id for result in first.case_results) == tuple(
        sorted(result.case_id for result in first.case_results)
    )
    assert first.model_dump_json() == repeated.model_dump_json()
    assert all(result.determinism_passed for result in first.case_results)


def test_evaluator_reports_a_mutated_reference_as_blocking_failure() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    target = next(
        case for case in dataset.cases if case.case_id == "descriptive-continuous-reference"
    )
    changed_value = target.expected_values[1].model_copy(update={"value": 999.0})
    changed_case = target.model_copy(
        update={
            "expected_values": (
                target.expected_values[0],
                changed_value,
                *target.expected_values[2:],
            )
        }
    )
    changed_dataset = dataset.model_copy(
        update={
            "cases": tuple(
                changed_case if case.case_id == target.case_id else case for case in dataset.cases
            )
        }
    )

    report = StatisticalBaselineEvaluator().evaluate(changed_dataset)

    assert report.overall_status == "fail"
    assert report.cases_failed == 1
    failed_case = next(item for item in report.case_results if item.case_id == target.case_id)
    assert any(check.status is CheckStatus.FAIL for check in failed_case.checks)
