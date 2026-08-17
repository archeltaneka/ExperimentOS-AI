"""Finite-safety and deterministic reference tests for Bayesian numerics."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.randomized.bayesian import BayesianComputationConfig
from packages.experiments.analysis.randomized.bayesian.numerics import (
    BayesianNumericalError,
    beta_difference_cdf,
    beta_equal_tailed_interval,
    beta_moments,
    invert_bounded_cdf,
)


def test_beta_moments_and_interval_match_independent_references() -> None:
    mean, variance = beta_moments(3.0, 1.0)
    lower, upper = beta_equal_tailed_interval(3.0, 1.0, 0.8)

    assert mean == 0.75
    assert variance == 0.0375
    # Beta(3, 1) has CDF x^3, so its 10th and 90th percentiles are cube roots.
    assert lower == pytest.approx(0.1 ** (1.0 / 3.0), abs=1e-12)
    assert upper == pytest.approx(0.9 ** (1.0 / 3.0), abs=1e-12)


def test_beta_difference_cdf_matches_polynomial_superiority_reference() -> None:
    config = BayesianComputationConfig()

    probability = beta_difference_cdf(
        0.0,
        treatment_alpha=3.0,
        treatment_beta=1.0,
        control_alpha=2.0,
        control_beta=2.0,
        config=config,
    )

    # Integral 3*x^2 * (1 - (3*x^2 - 2*x^3)) dx from 0 to 1 is 0.2.
    assert probability.value == pytest.approx(0.2, abs=1e-11)
    assert probability.absolute_error <= config.quadrature_absolute_tolerance


def test_bounded_cdf_inversion_is_repeatable() -> None:
    config = BayesianComputationConfig()

    def cdf(value: float):
        return beta_difference_cdf(
            value,
            treatment_alpha=3.0,
            treatment_beta=1.0,
            control_alpha=2.0,
            control_beta=2.0,
            config=config,
        )

    first = invert_bounded_cdf(cdf, target=0.5, lower=-1.0, upper=1.0, config=config)
    second = invert_bounded_cdf(cdf, target=0.5, lower=-1.0, upper=1.0, config=config)

    assert first == second
    assert -1.0 < first < 1.0


@pytest.mark.parametrize(
    ("alpha", "beta"),
    ((0.0, 1.0), (1.0, 0.0), (math.inf, 1.0), (1.0, math.nan)),
)
def test_beta_helpers_reject_invalid_or_nonfinite_parameters(alpha: float, beta: float) -> None:
    with pytest.raises(BayesianNumericalError):
        beta_moments(alpha, beta)


def test_cdf_inversion_rejects_unbracketed_target() -> None:
    config = BayesianComputationConfig()

    with pytest.raises(BayesianNumericalError, match="bracket"):
        invert_bounded_cdf(
            lambda _: type("Result", (), {"value": 0.25, "absolute_error": 0.0})(),
            target=0.5,
            lower=-1.0,
            upper=1.0,
            config=config,
        )
