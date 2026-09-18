from __future__ import annotations

from typing import Any

import pytest

from packages.evals.statistical import evaluator as statistical_evaluator
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
from packages.evals.statistical.observational_fixtures import (
    run_ipw_fixture,
    run_propensity_fixture,
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


def test_observational_estimand_integrity_blocks_att_substitution() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    case = next(item for item in dataset.cases if item.case_id == "ipw-att-known-effect")
    actual = run_ipw_fixture("ipw_att_known_effect").model_dump(mode="json")
    actual["estimand"]["estimand_type"] = "ate"
    actual["estimand"]["target_population"]["kind"] = "full"
    actual["weights"]["estimand"] = "ate"

    checks = statistical_evaluator.check_observational_estimand_integrity(case, actual)

    failures = {check.rule_id for check in checks if check.status is CheckStatus.FAIL}
    assert "statistics.estimand.declared" in failures
    assert "statistics.estimand.target_population" in failures
    assert "statistics.estimand.weighting_formula" in failures


def test_observational_provenance_blocks_silent_stabilization_and_clipping() -> None:
    stabilized = run_ipw_fixture("ipw_ate_stabilized").model_dump(mode="json")
    stabilized["weights"]["stabilized"] = None
    stabilized["weights"]["stabilization_rule"] = None
    clipped = run_ipw_fixture("ipw_ate_clipped").model_dump(mode="json")
    clipped["weights"]["clipping"]["enabled"] = False

    stabilized_checks = statistical_evaluator.check_observational_transformation_provenance(
        stabilized
    )
    clipped_checks = statistical_evaluator.check_observational_transformation_provenance(clipped)

    assert any(
        check.rule_id == "statistics.provenance.stabilization" and check.status is CheckStatus.FAIL
        for check in stabilized_checks
    )
    assert any(
        check.rule_id == "statistics.provenance.clipping" and check.status is CheckStatus.FAIL
        for check in clipped_checks
    )


def test_propensity_provenance_blocks_silent_trimming_and_weight_capping() -> None:
    silently_trimmed = run_propensity_fixture("propensity_good_overlap").model_dump(mode="json")
    silently_trimmed["configuration"]["trimming"] = {"lower": 0.1, "upper": 0.9}
    silently_trimmed["retained"] = None
    silently_capped = run_propensity_fixture("propensity_good_overlap").model_dump(mode="json")
    silently_capped["configuration"]["weight_cap"] = {"maximum": 5.0}
    silently_capped["capped_weights"] = None

    trimming_checks = statistical_evaluator.check_propensity_transformation_provenance(
        silently_trimmed
    )
    capping_checks = statistical_evaluator.check_propensity_transformation_provenance(
        silently_capped
    )

    assert any(
        check.rule_id == "statistics.provenance.trimming" and check.status is CheckStatus.FAIL
        for check in trimming_checks
    )
    assert any(
        check.rule_id == "statistics.provenance.weight_capping" and check.status is CheckStatus.FAIL
        for check in capping_checks
    )


def test_fixture_caches_include_complete_case_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    first = next(case for case in dataset.cases if case.case_id == "observational-coverage-did-v1")
    assert first.simulation is not None
    second = first.model_copy(
        update={
            "case_id": "observational-coverage-did-alternate",
            "simulation": first.simulation.model_copy(update={"seed": first.simulation.seed + 1}),
        }
    )
    fixture_calls: list[int] = []
    privacy_calls: list[int] = []

    def fake_fixture(case, *, reverse_rows=False):
        fixture_calls.append(case.simulation.seed)
        return object()

    def fake_privacy(case):
        privacy_calls.append(case.simulation.seed)
        return True, ()

    statistical_evaluator._FIXTURE_CACHE.clear()
    statistical_evaluator._TELEMETRY_PRIVACY_CACHE.clear()
    monkeypatch.setattr(statistical_evaluator, "run_statistical_fixture", fake_fixture)
    monkeypatch.setattr(statistical_evaluator, "evaluate_fixture_telemetry_privacy", fake_privacy)

    try:
        statistical_evaluator._cached_fixture(first, reverse_rows=False, execution_slot="first")
        statistical_evaluator._cached_fixture(second, reverse_rows=False, execution_slot="first")
        statistical_evaluator._cached_telemetry_privacy(first)
        statistical_evaluator._cached_telemetry_privacy(second)

        assert fixture_calls == [first.simulation.seed, second.simulation.seed]
        assert privacy_calls == [first.simulation.seed, second.simulation.seed]
    finally:
        statistical_evaluator._FIXTURE_CACHE.clear()
        statistical_evaluator._TELEMETRY_PRIVACY_CACHE.clear()


def test_repository_cases_pass_all_reliability_dimensions_deterministically() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    # Keep exact pre-106 gates; advanced replay/duration has dedicated coverage.
    dataset = dataset.model_copy(
        update={"cases": tuple(c for c in dataset.cases if c.advanced is None)}
    )

    first = StatisticalBaselineEvaluator().evaluate(dataset)
    repeated = StatisticalBaselineEvaluator().evaluate(dataset)

    assert first.overall_status == "pass"
    assert first.dataset_size == 92
    assert first.cases_passed == 69
    assert first.cases_failed == 0
    assert first.cases_advisory == 22
    assert first.cases_invalid == 21
    assert first.cases_abstained == 21
    assert first.cases_skipped == 1
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
