"""Analytic robust uncertainty for weighted Hajek arm means."""

from __future__ import annotations

import math
from numbers import Real

from ...randomized.numerics import normal_critical_value, two_sided_normal_p_value
from ...uncertainty import ConfidenceInterval
from .models import IPWTestResult, IPWVarianceMethod
from .numerics import IPWNumericalError


def compute_fixed_score_robust_inference(
    *,
    treatment_outcomes: tuple[float, ...],
    treatment_weights: tuple[float, ...],
    control_outcomes: tuple[float, ...],
    control_weights: tuple[float, ...],
    treatment_mean: float,
    control_mean: float,
    effect: float,
    confidence_level: float,
) -> IPWTestResult:
    """Return arm-wise HC1-style robust inference treating fitted scores as fixed."""
    checked_effect = _finite(effect, name="effect")
    treatment_variance = _arm_variance(
        treatment_outcomes,
        treatment_weights,
        mean=treatment_mean,
    )
    control_variance = _arm_variance(
        control_outcomes,
        control_weights,
        mean=control_mean,
    )
    variance = _finite(treatment_variance + control_variance, name="effect variance")
    if variance < 0.0:
        raise IPWNumericalError("effect variance must be nonnegative")
    standard_error = _finite(math.sqrt(variance), name="standard error")
    if standard_error == 0.0:
        if checked_effect != 0.0:
            raise IPWNumericalError("nonzero effect has zero robust uncertainty")
        statistic = 0.0
        p_value = 1.0
        lower = upper = checked_effect
    else:
        statistic = _finite(checked_effect / standard_error, name="test statistic")
        p_value = two_sided_normal_p_value(statistic)
        alpha = 1.0 - _open_probability(confidence_level, name="confidence level")
        critical = normal_critical_value(alpha)
        lower = _finite(
            checked_effect - critical * standard_error,
            name="confidence lower bound",
        )
        upper = _finite(
            checked_effect + critical * standard_error,
            name="confidence upper bound",
        )
    return IPWTestResult(
        variance_method=IPWVarianceMethod.FIXED_PROPENSITY_HAJEK_HC1,
        standard_error=standard_error,
        statistic=statistic,
        p_value=p_value,
        confidence_interval=ConfidenceInterval(
            lower=lower,
            upper=upper,
            confidence_level=confidence_level,
        ),
    )


def _arm_variance(
    outcomes: tuple[float, ...],
    weights: tuple[float, ...],
    *,
    mean: float,
) -> float:
    if len(outcomes) != len(weights) or len(outcomes) < 2:
        raise IPWNumericalError("robust uncertainty requires two aligned units per arm")
    checked_mean = _finite(mean, name="weighted mean")
    checked_outcomes = tuple(_finite(value, name="outcome") for value in outcomes)
    checked_weights = tuple(_nonnegative(weight, name="weight") for weight in weights)
    maximum_weight = max(checked_weights)
    if maximum_weight == 0.0:
        raise IPWNumericalError("robust uncertainty requires positive arm weight")
    scaled = tuple(weight / maximum_weight for weight in checked_weights)
    total = math.fsum(scaled)
    contributions: list[float] = []
    try:
        for outcome, weight in zip(checked_outcomes, scaled, strict=True):
            residual = _finite(outcome - checked_mean, name="outcome residual")
            contributions.append(_finite((weight / total) * residual, name="influence value"))
    except OverflowError as error:
        raise IPWNumericalError("robust variance contributions must be finite") from error
    maximum_contribution = max(abs(value) for value in contributions)
    if maximum_contribution == 0.0:
        return 0.0
    normalized_sum_squares = math.fsum(
        (value / maximum_contribution) ** 2 for value in contributions
    )
    correction = len(outcomes) / (len(outcomes) - 1)
    try:
        variance = correction * maximum_contribution**2 * normalized_sum_squares
    except OverflowError as error:
        raise IPWNumericalError("robust arm variance must be finite") from error
    return _finite(variance, name="robust arm variance")


def _open_probability(value: object, *, name: str) -> float:
    checked = _finite(value, name=name)
    if not 0.0 < checked < 1.0:
        raise IPWNumericalError(f"{name} must be strictly between zero and one")
    return checked


def _nonnegative(value: object, *, name: str) -> float:
    checked = _finite(value, name=name)
    if checked < 0.0:
        raise IPWNumericalError(f"{name} must be nonnegative")
    return checked


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise IPWNumericalError(f"{name} must be a finite real number")
    try:
        checked = float(value)
    except OverflowError as error:
        raise IPWNumericalError(f"{name} must be a finite real number") from error
    if not math.isfinite(checked):
        raise IPWNumericalError(f"{name} must be a finite real number")
    return checked


__all__ = ["compute_fixed_score_robust_inference"]
