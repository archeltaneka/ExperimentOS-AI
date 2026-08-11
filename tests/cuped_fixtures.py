"""Independent deterministic fixtures for CUPED estimator tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HandCalculatedCoefficientFixture:
    outcomes: tuple[float, ...]
    covariates: tuple[float, ...]
    expected_theta: float
    expected_covariance: float
    expected_covariate_variance: float
    expected_covariate_mean: float
    expected_outcome_variance: float
    expected_correlation: float
    expected_adjusted: tuple[float, ...]


# Means are X=3/2 and Y=9/2. The sample cross-product sum is 12 and the
# covariate squared-deviation sum is 5, so covariance=4, variance=5/3,
# and theta=12/5. These literals are independent of the implementation.
HAND_CALCULATED_COEFFICIENT = HandCalculatedCoefficientFixture(
    outcomes=(1.0, 3.0, 6.0, 8.0),
    covariates=(0.0, 1.0, 2.0, 3.0),
    expected_theta=2.4,
    expected_covariance=4.0,
    expected_covariate_variance=5.0 / 3.0,
    expected_covariate_mean=1.5,
    expected_outcome_variance=29.0 / 3.0,
    expected_correlation=12.0 / (145.0**0.5),
    expected_adjusted=(4.6, 4.2, 4.8, 4.4),
)


__all__ = ["HAND_CALCULATED_COEFFICIENT", "HandCalculatedCoefficientFixture"]


ZERO_REDUCTION_CONTROL_OUTCOMES = (0.0, 1.0, 1.0, 0.0)
ZERO_REDUCTION_TREATMENT_OUTCOMES = (2.0, 3.0, 3.0, 2.0)
ZERO_REDUCTION_COVARIATES = (0.0, 1.0, 2.0, 3.0)

# This fixed case has pooled theta=13/24 and increases the same-sample
# squared standard error from 7/3 to 3.261501736111111.
NEGATIVE_REDUCTION_CONTROL_OUTCOMES = (-2.0, -1.0, -3.0, -2.0)
NEGATIVE_REDUCTION_TREATMENT_OUTCOMES = (6.0, 1.0, 7.0, 2.0)
NEGATIVE_REDUCTION_CONTROL_COVARIATES = (-2.0, 3.0, -1.0, 1.0)
NEGATIVE_REDUCTION_TREATMENT_COVARIATES = (2.0, 3.0, 0.0, 2.0)
