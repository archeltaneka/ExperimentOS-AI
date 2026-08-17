"""Finite-safe private SciPy helpers for Bayesian randomized analysis."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from numbers import Real

from scipy import integrate as _integrate  # type: ignore[import-untyped]
from scipy import optimize as _optimize
from scipy import stats as _stats

from .models import BayesianComputationConfig


class BayesianNumericalError(ValueError):
    """Raised when Bayesian numerical inputs or outputs are invalid."""


@dataclass(frozen=True, slots=True)
class NumericalProbability:
    """A finite probability and deterministic quadrature error estimate."""

    value: float
    absolute_error: float


def beta_moments(alpha: float, beta: float) -> tuple[float, float]:
    """Return analytic mean and variance for a proper Beta distribution."""
    checked_alpha = _positive_finite(alpha, name="alpha")
    checked_beta = _positive_finite(beta, name="beta")
    total = checked_alpha + checked_beta
    mean = checked_alpha / total
    variance = (checked_alpha * checked_beta) / (total * total * (total + 1.0))
    return (
        _probability(mean, name="Beta mean"),
        _nonnegative_finite(variance, name="Beta variance"),
    )


def beta_equal_tailed_interval(
    alpha: float,
    beta: float,
    credible_level: float,
) -> tuple[float, float]:
    """Return an equal-tailed credible interval for a proper Beta distribution."""
    checked_alpha = _positive_finite(alpha, name="alpha")
    checked_beta = _positive_finite(beta, name="beta")
    checked_level = _open_probability(credible_level, name="credible_level")
    tail = (1.0 - checked_level) / 2.0
    lower = _probability(
        _stats.beta.ppf(tail, checked_alpha, checked_beta),
        name="Beta lower quantile",
    )
    upper = _probability(
        _stats.beta.ppf(1.0 - tail, checked_alpha, checked_beta),
        name="Beta upper quantile",
    )
    if lower > upper:
        raise BayesianNumericalError("Beta credible interval bounds are not ordered")
    return (lower, upper)


def beta_difference_cdf(
    difference: float,
    *,
    treatment_alpha: float,
    treatment_beta: float,
    control_alpha: float,
    control_beta: float,
    config: BayesianComputationConfig,
) -> NumericalProbability:
    """Evaluate P(theta_treatment - theta_control <= difference)."""
    checked_difference = _finite(difference, name="difference")
    treatment_alpha = _positive_finite(treatment_alpha, name="treatment_alpha")
    treatment_beta = _positive_finite(treatment_beta, name="treatment_beta")
    control_alpha = _positive_finite(control_alpha, name="control_alpha")
    control_beta = _positive_finite(control_beta, name="control_beta")
    if checked_difference <= -1.0:
        return NumericalProbability(value=0.0, absolute_error=0.0)
    if checked_difference >= 1.0:
        return NumericalProbability(value=1.0, absolute_error=0.0)

    baseline = 0.0
    integration_lower = 0.0
    integration_upper = 1.0
    if checked_difference > 0.0:
        baseline = _stats.beta.cdf(
            checked_difference,
            treatment_alpha,
            treatment_beta,
        )
        integration_lower = checked_difference
    elif checked_difference < 0.0:
        integration_upper = 1.0 + checked_difference

    def integrand(value: float) -> float:
        threshold = value - checked_difference
        density = _stats.beta.pdf(value, treatment_alpha, treatment_beta)
        survival = _stats.beta.sf(threshold, control_alpha, control_beta)
        return float(density * survival)

    integral, error = _quadrature(
        integrand,
        integration_lower,
        integration_upper,
        config=config,
    )
    return NumericalProbability(
        value=_probability_with_roundoff(
            baseline + integral,
            config=config,
            name="Beta difference CDF",
        ),
        absolute_error=_nonnegative_finite(error, name="Beta difference CDF error"),
    )


def student_t_equal_tailed_interval(
    degrees_of_freedom: float,
    location: float,
    scale: float,
    credible_level: float,
) -> tuple[float, float]:
    """Return an equal-tailed interval for a location-scale Student-t distribution."""
    checked_df = _positive_finite(degrees_of_freedom, name="degrees_of_freedom")
    checked_location = _finite(location, name="location")
    checked_scale = _positive_finite(scale, name="scale")
    checked_level = _open_probability(credible_level, name="credible_level")
    tail = (1.0 - checked_level) / 2.0
    lower = _finite(
        _stats.t.ppf(tail, checked_df, loc=checked_location, scale=checked_scale),
        name="Student-t lower quantile",
    )
    upper = _finite(
        _stats.t.ppf(1.0 - tail, checked_df, loc=checked_location, scale=checked_scale),
        name="Student-t upper quantile",
    )
    if lower > upper:
        raise BayesianNumericalError("Student-t credible interval bounds are not ordered")
    return (lower, upper)


def student_t_difference_cdf(
    difference: float,
    *,
    treatment_degrees_of_freedom: float,
    treatment_location: float,
    treatment_scale: float,
    control_degrees_of_freedom: float,
    control_location: float,
    control_scale: float,
    config: BayesianComputationConfig,
) -> NumericalProbability:
    """Evaluate the CDF of a difference of independent Student-t variables."""
    difference = _finite(difference, name="difference")
    treatment_df = _positive_finite(
        treatment_degrees_of_freedom,
        name="treatment_degrees_of_freedom",
    )
    treatment_location = _finite(treatment_location, name="treatment_location")
    treatment_scale = _positive_finite(treatment_scale, name="treatment_scale")
    control_df = _positive_finite(
        control_degrees_of_freedom,
        name="control_degrees_of_freedom",
    )
    control_location = _finite(control_location, name="control_location")
    control_scale = _positive_finite(control_scale, name="control_scale")

    def integrand(value: float) -> float:
        density = _stats.t.pdf(
            value,
            treatment_df,
            loc=treatment_location,
            scale=treatment_scale,
        )
        survival = _stats.t.sf(
            value - difference,
            control_df,
            loc=control_location,
            scale=control_scale,
        )
        return float(density * survival)

    integral, error = _quadrature(
        integrand,
        -math.inf,
        math.inf,
        config=config,
    )
    return NumericalProbability(
        value=_probability_with_roundoff(
            integral,
            config=config,
            name="Student-t difference CDF",
        ),
        absolute_error=_nonnegative_finite(error, name="Student-t difference CDF error"),
    )


def invert_bounded_cdf(
    cdf: Callable[[float], NumericalProbability],
    *,
    target: float,
    lower: float,
    upper: float,
    config: BayesianComputationConfig,
) -> float:
    """Invert a deterministic CDF inside a finite bracket."""
    checked_target = _open_probability(target, name="target")
    checked_lower = _finite(lower, name="lower")
    checked_upper = _finite(upper, name="upper")
    if checked_lower >= checked_upper:
        raise BayesianNumericalError("CDF inversion requires an ordered bracket")

    lower_value = _probability(cdf(checked_lower).value, name="lower CDF")
    upper_value = _probability(cdf(checked_upper).value, name="upper CDF")
    if lower_value > checked_target or upper_value < checked_target:
        raise BayesianNumericalError("CDF target is not contained in the supplied bracket")
    if lower_value == checked_target:
        return checked_lower
    if upper_value == checked_target:
        return checked_upper

    def objective(value: float) -> float:
        return _probability(cdf(value).value, name="CDF value") - checked_target

    root = _optimize.brentq(
        objective,
        checked_lower,
        checked_upper,
        xtol=config.root_absolute_tolerance,
        rtol=max(4.0 * float.fromhex("0x1.0000000000000p-52"), 1e-15),
    )
    return _finite(root, name="CDF root")


def invert_unbounded_cdf(
    cdf: Callable[[float], NumericalProbability],
    *,
    target: float,
    center: float,
    initial_half_width: float,
    config: BayesianComputationConfig,
) -> float:
    """Invert an unbounded CDF using a deterministic expanding finite bracket."""
    checked_target = _open_probability(target, name="target")
    checked_center = _finite(center, name="center")
    width = _positive_finite(initial_half_width, name="initial_half_width")
    for _ in range(64):
        lower = checked_center - width
        upper = checked_center + width
        if not math.isfinite(lower) or not math.isfinite(upper):
            break
        lower_value = _probability(cdf(lower).value, name="lower CDF")
        upper_value = _probability(cdf(upper).value, name="upper CDF")
        if lower_value <= checked_target <= upper_value:
            return invert_bounded_cdf(
                cdf,
                target=checked_target,
                lower=lower,
                upper=upper,
                config=config,
            )
        width *= 2.0
    raise BayesianNumericalError("CDF target could not be bracketed on finite support")


def _quadrature(
    integrand: Callable[[float], float],
    lower: float,
    upper: float,
    *,
    config: BayesianComputationConfig,
) -> tuple[float, float]:
    if lower == upper:
        return (0.0, 0.0)
    try:
        value, error = _integrate.quad(
            integrand,
            lower,
            upper,
            epsabs=config.quadrature_absolute_tolerance,
            epsrel=config.quadrature_relative_tolerance,
            limit=config.integration_subdivision_limit,
        )
    except (OverflowError, ValueError) as exc:
        raise BayesianNumericalError("adaptive quadrature failed") from exc
    return (
        _finite(value, name="quadrature value"),
        _nonnegative_finite(error, name="quadrature absolute error"),
    )


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise BayesianNumericalError(f"{name} must be a finite real number")
    try:
        converted = float(value)
    except OverflowError as exc:
        raise BayesianNumericalError(f"{name} must be a finite real number") from exc
    if not math.isfinite(converted):
        raise BayesianNumericalError(f"{name} must be a finite real number")
    return converted


def _positive_finite(value: object, *, name: str) -> float:
    converted = _finite(value, name=name)
    if converted <= 0.0:
        raise BayesianNumericalError(f"{name} must be greater than zero")
    return converted


def _nonnegative_finite(value: object, *, name: str) -> float:
    converted = _finite(value, name=name)
    if converted < 0.0:
        raise BayesianNumericalError(f"{name} must be nonnegative")
    return converted


def _open_probability(value: object, *, name: str) -> float:
    converted = _finite(value, name=name)
    if not 0.0 < converted < 1.0:
        raise BayesianNumericalError(f"{name} must be strictly between zero and one")
    return converted


def _probability(value: object, *, name: str) -> float:
    converted = _finite(value, name=name)
    if not 0.0 <= converted <= 1.0:
        raise BayesianNumericalError(f"{name} must be between zero and one")
    return converted


def _probability_with_roundoff(
    value: object,
    *,
    config: BayesianComputationConfig,
    name: str,
) -> float:
    converted = _finite(value, name=name)
    tolerance = max(
        config.quadrature_absolute_tolerance,
        config.quadrature_relative_tolerance,
    )
    if converted < -tolerance or converted > 1.0 + tolerance:
        raise BayesianNumericalError(f"{name} must be between zero and one")
    return min(1.0, max(0.0, converted))


__all__ = [
    "BayesianNumericalError",
    "NumericalProbability",
    "beta_difference_cdf",
    "beta_equal_tailed_interval",
    "beta_moments",
    "invert_bounded_cdf",
    "invert_unbounded_cdf",
    "student_t_difference_cdf",
    "student_t_equal_tailed_interval",
]
