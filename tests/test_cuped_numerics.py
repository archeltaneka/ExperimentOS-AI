"""Hand-calculated tests for the finite-safe CUPED numerical boundary."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.randomized.cuped.numerics import (
    CupedNumericalError,
    adjust_outcomes,
    estimate_pooled_coefficient,
    summarize_covariate_balance,
)
from tests.cuped_fixtures import HAND_CALCULATED_COEFFICIENT


def test_pooled_coefficient_matches_hand_calculation() -> None:
    fixture = HAND_CALCULATED_COEFFICIENT

    coefficient = estimate_pooled_coefficient(
        fixture.outcomes,
        fixture.covariates,
        minimum_variance=0.0,
    )

    assert coefficient.theta == pytest.approx(fixture.expected_theta, abs=1e-12)
    assert coefficient.covariance == pytest.approx(fixture.expected_covariance, abs=1e-12)
    assert coefficient.covariate_variance == pytest.approx(
        fixture.expected_covariate_variance,
        abs=1e-12,
    )
    assert coefficient.covariate_mean == pytest.approx(
        fixture.expected_covariate_mean,
        abs=1e-12,
    )
    assert coefficient.outcome_variance == pytest.approx(
        fixture.expected_outcome_variance,
        abs=1e-12,
    )
    assert coefficient.correlation == pytest.approx(fixture.expected_correlation, abs=1e-12)
    assert coefficient.sample_size == 4
    assert coefficient.degrees_of_freedom == 3


def test_adjusted_outcome_matches_hand_calculation_without_mutating_inputs() -> None:
    fixture = HAND_CALCULATED_COEFFICIENT
    original_outcomes = fixture.outcomes
    original_covariates = fixture.covariates
    coefficient = estimate_pooled_coefficient(
        original_outcomes,
        original_covariates,
        minimum_variance=0.0,
    )

    adjusted = adjust_outcomes(original_outcomes, original_covariates, coefficient)

    assert adjusted == pytest.approx(fixture.expected_adjusted, abs=1e-12)
    assert fixture.outcomes is original_outcomes
    assert fixture.covariates is original_covariates


def test_coefficient_is_invariant_to_pair_order() -> None:
    fixture = HAND_CALCULATED_COEFFICIENT
    order = (2, 0, 3, 1)

    reordered = estimate_pooled_coefficient(
        tuple(fixture.outcomes[index] for index in order),
        tuple(fixture.covariates[index] for index in order),
        minimum_variance=0.0,
    )
    original = estimate_pooled_coefficient(
        fixture.outcomes,
        fixture.covariates,
        minimum_variance=0.0,
    )

    assert reordered == original


def test_zero_outcome_variance_leaves_correlation_unavailable() -> None:
    coefficient = estimate_pooled_coefficient(
        (4.0, 4.0, 4.0),
        (1.0, 2.0, 3.0),
        minimum_variance=0.0,
    )

    assert coefficient.theta == 0.0
    assert coefficient.covariance == 0.0
    assert coefficient.outcome_variance == 0.0
    assert coefficient.correlation is None


@pytest.mark.parametrize(
    ("covariates", "minimum_variance"),
    [
        ((2.0, 2.0, 2.0), 0.0),
        ((0.0, 1e-8, 2e-8), 1e-15),
    ],
)
def test_constant_or_configured_near_zero_covariate_variance_is_rejected(
    covariates: tuple[float, ...],
    minimum_variance: float,
) -> None:
    with pytest.raises(CupedNumericalError, match="variance"):
        estimate_pooled_coefficient(
            (1.0, 2.0, 3.0),
            covariates,
            minimum_variance=minimum_variance,
        )


@pytest.mark.parametrize(
    ("outcomes", "covariates"),
    [
        ((1.0,), (1.0,)),
        ((1.0, 2.0), (1.0,)),
        ((True, 2.0), (1.0, 2.0)),
        ((1.0, 2.0), (False, 2.0)),
        ((1.0, math.nan), (1.0, 2.0)),
        ((1.0, 2.0), (1.0, math.inf)),
        ((1.0, "2"), (1.0, 2.0)),
    ],
)
def test_invalid_coefficient_inputs_are_rejected(
    outcomes: tuple[object, ...],
    covariates: tuple[object, ...],
) -> None:
    with pytest.raises(CupedNumericalError):
        estimate_pooled_coefficient(outcomes, covariates, minimum_variance=0.0)


def test_nonfinite_intermediate_from_extreme_finite_values_is_rejected() -> None:
    with pytest.raises(CupedNumericalError):
        estimate_pooled_coefficient(
            (1e308, -1e308, 1e308),
            (-1e308, 0.0, 1e308),
            minimum_variance=0.0,
        )


def test_covariate_balance_matches_hand_calculation() -> None:
    balance = summarize_covariate_balance(
        treatment_covariates=(2.0, 3.0),
        control_covariates=(0.0, 1.0),
    )

    assert balance.treatment_count == 2
    assert balance.control_count == 2
    assert balance.treatment_mean == pytest.approx(2.5)
    assert balance.control_mean == pytest.approx(0.5)
    assert balance.treatment_variance == pytest.approx(0.5)
    assert balance.control_variance == pytest.approx(0.5)
    assert balance.pooled_standard_deviation == pytest.approx(math.sqrt(0.5))
    assert balance.standardized_mean_difference == pytest.approx(2.0 / math.sqrt(0.5))


def test_balance_is_order_invariant_and_unavailable_when_pooled_variance_is_zero() -> None:
    first = summarize_covariate_balance(
        treatment_covariates=(3.0, 2.0),
        control_covariates=(1.0, 0.0),
    )
    second = summarize_covariate_balance(
        treatment_covariates=(2.0, 3.0),
        control_covariates=(0.0, 1.0),
    )
    unavailable = summarize_covariate_balance(
        treatment_covariates=(2.0, 2.0),
        control_covariates=(1.0, 1.0),
    )

    assert first == second
    assert unavailable.pooled_standard_deviation == 0.0
    assert unavailable.standardized_mean_difference is None
