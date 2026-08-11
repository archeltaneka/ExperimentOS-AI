"""Finite-safe scalar calculations for one pooled CUPED covariate."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real


class CupedNumericalError(ValueError):
    """Raised when CUPED inputs cannot produce finite scalar evidence."""


class CupedVarianceError(CupedNumericalError):
    """Raised when covariate variance does not exceed the declared minimum."""


@dataclass(frozen=True, slots=True)
class CupedCoefficientValues:
    """Internal pooled coefficient evidence without public contract behavior."""

    theta: float
    covariance: float
    covariate_variance: float
    covariate_mean: float
    outcome_variance: float
    correlation: float | None
    sample_size: int
    degrees_of_freedom: int


@dataclass(frozen=True, slots=True)
class CupedBalanceValues:
    """Internal two-arm covariate balance evidence."""

    treatment_count: int
    control_count: int
    treatment_mean: float
    control_mean: float
    treatment_variance: float
    control_variance: float
    pooled_standard_deviation: float
    standardized_mean_difference: float | None


def estimate_pooled_coefficient(
    outcomes: Sequence[object],
    covariates: Sequence[object],
    *,
    minimum_variance: float,
) -> CupedCoefficientValues:
    """Estimate one pooled CUPED coefficient with sample covariance and variance."""
    threshold = _finite_real(minimum_variance, name="minimum_variance")
    if threshold < 0.0:
        raise CupedNumericalError("minimum_variance must not be negative")
    if len(outcomes) != len(covariates):
        raise CupedNumericalError("outcomes and covariates must have equal lengths")
    if len(outcomes) < 2:
        raise CupedNumericalError("coefficient estimation requires at least two observations")

    pairs = tuple(
        sorted(
            (
                _finite_real(covariate, name="covariate"),
                _finite_real(outcome, name="outcome"),
            )
            for outcome, covariate in zip(outcomes, covariates, strict=True)
        )
    )
    ordered_covariates = tuple(covariate for covariate, _ in pairs)
    ordered_outcomes = tuple(outcome for _, outcome in pairs)
    covariate_mean = _mean(ordered_covariates, name="covariate mean")
    outcome_mean = _mean(ordered_outcomes, name="outcome mean")
    degrees_of_freedom = len(pairs) - 1

    try:
        covariate_squared_deviations = tuple(
            (value - covariate_mean) ** 2 for value in ordered_covariates
        )
        outcome_squared_deviations = tuple(
            (value - outcome_mean) ** 2 for value in ordered_outcomes
        )
        cross_products = tuple(
            (covariate - covariate_mean) * (outcome - outcome_mean)
            for covariate, outcome in pairs
        )
        covariate_variance = math.fsum(covariate_squared_deviations) / degrees_of_freedom
        outcome_variance = math.fsum(outcome_squared_deviations) / degrees_of_freedom
        covariance = math.fsum(cross_products) / degrees_of_freedom
    except (OverflowError, ValueError) as error:
        raise CupedNumericalError("coefficient moments must be finite") from error

    _require_finite(covariate_variance, name="covariate variance")
    _require_finite(outcome_variance, name="outcome variance")
    _require_finite(covariance, name="covariance")
    if covariate_variance <= threshold:
        raise CupedVarianceError("covariate variance does not exceed minimum_variance")

    theta = covariance / covariate_variance
    _require_finite(theta, name="theta")
    correlation = _correlation(
        covariance=covariance,
        covariate_variance=covariate_variance,
        outcome_variance=outcome_variance,
    )
    return CupedCoefficientValues(
        theta=theta,
        covariance=covariance,
        covariate_variance=covariate_variance,
        covariate_mean=covariate_mean,
        outcome_variance=outcome_variance,
        correlation=correlation,
        sample_size=len(pairs),
        degrees_of_freedom=degrees_of_freedom,
    )


def adjust_outcomes(
    outcomes: Sequence[object],
    covariates: Sequence[object],
    coefficient: CupedCoefficientValues,
) -> tuple[float, ...]:
    """Return aligned adjusted outcomes without modifying caller-owned sequences."""
    if len(outcomes) != len(covariates):
        raise CupedNumericalError("outcomes and covariates must have equal lengths")
    adjusted: list[float] = []
    for outcome, covariate in zip(outcomes, covariates, strict=True):
        checked_outcome = _finite_real(outcome, name="outcome")
        checked_covariate = _finite_real(covariate, name="covariate")
        try:
            value = checked_outcome - coefficient.theta * (
                checked_covariate - coefficient.covariate_mean
            )
        except OverflowError as error:
            raise CupedNumericalError("adjusted outcomes must be finite") from error
        _require_finite(value, name="adjusted outcome")
        adjusted.append(value)
    return tuple(adjusted)


def summarize_covariate_balance(
    treatment_covariates: Sequence[object],
    control_covariates: Sequence[object],
) -> CupedBalanceValues:
    """Summarize deterministic two-arm covariate balance on retained rows."""
    treatment = tuple(sorted(_finite_values(treatment_covariates, name="treatment covariate")))
    control = tuple(sorted(_finite_values(control_covariates, name="control covariate")))
    if len(treatment) < 2 or len(control) < 2:
        raise CupedNumericalError("covariate balance requires at least two values per arm")

    treatment_mean = _mean(treatment, name="treatment covariate mean")
    control_mean = _mean(control, name="control covariate mean")
    treatment_variance = _sample_variance(treatment, treatment_mean)
    control_variance = _sample_variance(control, control_mean)
    pooled_degrees_of_freedom = len(treatment) + len(control) - 2
    try:
        pooled_variance = (
            (len(treatment) - 1) * treatment_variance
            + (len(control) - 1) * control_variance
        ) / pooled_degrees_of_freedom
        pooled_standard_deviation = math.sqrt(pooled_variance)
    except (OverflowError, ValueError) as error:
        raise CupedNumericalError("covariate balance must be finite") from error
    _require_finite(pooled_standard_deviation, name="pooled standard deviation")

    standardized_mean_difference = None
    if pooled_standard_deviation > 0.0:
        standardized_mean_difference = (
            treatment_mean - control_mean
        ) / pooled_standard_deviation
        _require_finite(
            standardized_mean_difference,
            name="standardized mean difference",
        )
    return CupedBalanceValues(
        treatment_count=len(treatment),
        control_count=len(control),
        treatment_mean=treatment_mean,
        control_mean=control_mean,
        treatment_variance=treatment_variance,
        control_variance=control_variance,
        pooled_standard_deviation=pooled_standard_deviation,
        standardized_mean_difference=standardized_mean_difference,
    )


def _finite_values(values: Sequence[object], *, name: str) -> tuple[float, ...]:
    return tuple(_finite_real(value, name=name) for value in values)


def _finite_real(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise CupedNumericalError(f"{name} must be a finite real number")
    try:
        converted = float(value)
    except OverflowError as error:
        raise CupedNumericalError(f"{name} must be a finite real number") from error
    if not math.isfinite(converted):
        raise CupedNumericalError(f"{name} must be a finite real number")
    return converted


def _mean(values: Sequence[float], *, name: str) -> float:
    try:
        result = math.fsum(values) / len(values)
    except (OverflowError, ValueError) as error:
        raise CupedNumericalError(f"{name} must be finite") from error
    _require_finite(result, name=name)
    return result


def _sample_variance(values: Sequence[float], mean: float) -> float:
    try:
        result = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    except (OverflowError, ValueError) as error:
        raise CupedNumericalError("sample variance must be finite") from error
    _require_finite(result, name="sample variance")
    return result


def _correlation(
    *,
    covariance: float,
    covariate_variance: float,
    outcome_variance: float,
) -> float | None:
    if outcome_variance == 0.0:
        return None
    try:
        denominator = math.sqrt(covariate_variance * outcome_variance)
        result = covariance / denominator
    except (OverflowError, ValueError, ZeroDivisionError) as error:
        raise CupedNumericalError("correlation must be finite when defined") from error
    _require_finite(result, name="correlation")
    if result > 1.0 and math.isclose(result, 1.0, rel_tol=1e-15, abs_tol=0.0):
        return 1.0
    if result < -1.0 and math.isclose(result, -1.0, rel_tol=1e-15, abs_tol=0.0):
        return -1.0
    if not -1.0 <= result <= 1.0:
        raise CupedNumericalError("correlation must be between negative one and one")
    return result


def _require_finite(value: float, *, name: str) -> None:
    if not math.isfinite(value):
        raise CupedNumericalError(f"{name} must be finite")


__all__ = [
    "CupedBalanceValues",
    "CupedCoefficientValues",
    "CupedNumericalError",
    "CupedVarianceError",
    "adjust_outcomes",
    "estimate_pooled_coefficient",
    "summarize_covariate_balance",
]
