from __future__ import annotations

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import (
    StatisticalBaselineEvaluator,
    check_assumptions,
    check_method_uncertainty,
)
from packages.evals.statistical.models import CheckStatus, StatisticalCapability


def test_missing_required_assumption_is_blocking() -> None:
    checks = check_assumptions(
        required_codes=("random_assignment", "covariate_pre_treatment"),
        actual_assumptions=({"code": "random_assignment", "status": "unassessed"},),
    )

    assert any(
        check.rule_id == "statistics.assumptions.required_codes"
        and check.status is CheckStatus.FAIL
        for check in checks
    )


def test_bayesian_uncertainty_uses_credible_not_frequentist_semantics() -> None:
    actual = {
        "status": "completed",
        "treatment_prior": {"prior_family": "beta", "provenance": [{"source_id": "p"}]},
        "control_prior": {"prior_family": "beta", "provenance": [{"source_id": "p"}]},
        "treatment_posterior": {"posterior_alpha": 3.0, "posterior_beta": 2.0},
        "control_posterior": {"posterior_alpha": 2.0, "posterior_beta": 3.0},
        "effect": {
            "posterior_mean": 0.2,
            "posterior_standard_deviation": 0.1,
            "credible_interval": {"lower": 0.0, "upper": 0.4, "credible_level": 0.95},
            "probability_of_superiority": {"probability": 0.9},
            "computation_method": "deterministic_quadrature",
        },
    }

    checks = check_method_uncertainty(StatisticalCapability.BAYESIAN_BINARY, actual)

    assert checks
    assert all(check.status is CheckStatus.PASS for check in checks)
    assert all("p_value" not in check.rule_id for check in checks)
    assert all("confidence_interval" not in check.rule_id for check in checks)


def test_repository_randomized_inference_cases_have_no_blocking_failures() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)

    report = StatisticalBaselineEvaluator().evaluate(dataset)
    randomized = [
        result
        for result in report.case_results
        if result.capability
        in {
            StatisticalCapability.CUPED,
            StatisticalCapability.SEQUENTIAL,
            StatisticalCapability.BAYESIAN_BINARY,
            StatisticalCapability.BAYESIAN_CONTINUOUS,
        }
    ]

    assert randomized
    assert all(result.evaluation_status is not CheckStatus.FAIL for result in randomized)
    assert any(result.evaluation_status is CheckStatus.ADVISORY for result in randomized)
    assert any(result.evaluation_status is CheckStatus.SKIPPED for result in randomized)
