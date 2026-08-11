"""Finite-safe scalar distribution helpers for randomized analysis."""

from __future__ import annotations

import math
from numbers import Real

import scipy.stats as _stats  # type: ignore[import-untyped]


class RandomizedNumericalError(ValueError):
    """Raised when a randomized numerical helper receives invalid inputs or output."""


def two_sided_t_p_value(statistic: float, degrees_of_freedom: float) -> float:
    """Return a finite two-sided Student's t p-value for a finite statistic."""
    checked_statistic = _finite_real(statistic, name="statistic")
    checked_degrees_of_freedom = _positive_finite_real(
        degrees_of_freedom,
        name="degrees_of_freedom",
    )
    return _finite_probability(
        2.0 * _stats.t.sf(abs(checked_statistic), checked_degrees_of_freedom),
        name="two-sided t p-value",
    )


def t_critical_value(alpha: float, degrees_of_freedom: float) -> float:
    """Return the positive two-sided Student's t critical value for ``alpha``."""
    checked_alpha = _open_probability(alpha, name="alpha")
    checked_degrees_of_freedom = _positive_finite_real(
        degrees_of_freedom,
        name="degrees_of_freedom",
    )
    return _positive_finite_result(
        _stats.t.isf(checked_alpha / 2.0, checked_degrees_of_freedom),
        name="t critical value",
    )


def two_sided_normal_p_value(statistic: float) -> float:
    """Return a finite two-sided standard-normal p-value for a finite statistic."""
    checked_statistic = _finite_real(statistic, name="statistic")
    return _finite_probability(
        2.0 * _stats.norm.sf(abs(checked_statistic)),
        name="two-sided normal p-value",
    )


def normal_critical_value(alpha: float) -> float:
    """Return the positive two-sided standard-normal critical value for ``alpha``."""
    checked_alpha = _open_probability(alpha, name="alpha")
    return _positive_finite_result(
        _stats.norm.isf(checked_alpha / 2.0),
        name="normal critical value",
    )


def _finite_real(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise RandomizedNumericalError(f"{name} must be a finite real number")
    try:
        converted = float(value)
    except OverflowError as error:
        raise RandomizedNumericalError(f"{name} must be a finite real number") from error
    if not math.isfinite(converted):
        raise RandomizedNumericalError(f"{name} must be a finite real number")
    return converted


def _positive_finite_real(value: object, *, name: str) -> float:
    converted = _finite_real(value, name=name)
    if converted <= 0.0:
        raise RandomizedNumericalError(f"{name} must be greater than zero")
    return converted


def _open_probability(value: object, *, name: str) -> float:
    converted = _finite_real(value, name=name)
    if not 0.0 < converted < 1.0:
        raise RandomizedNumericalError(f"{name} must be strictly between zero and one")
    return converted


def _finite_probability(value: object, *, name: str) -> float:
    converted = _finite_real(value, name=name)
    if not 0.0 <= converted <= 1.0:
        raise RandomizedNumericalError(f"{name} must be between zero and one")
    return math.nextafter(0.0, 1.0) if converted == 0.0 else converted


def _positive_finite_result(value: object, *, name: str) -> float:
    converted = _finite_real(value, name=name)
    if converted <= 0.0:
        raise RandomizedNumericalError(f"{name} must be greater than zero")
    return converted


__all__ = [
    "RandomizedNumericalError",
    "normal_critical_value",
    "t_critical_value",
    "two_sided_normal_p_value",
    "two_sided_t_p_value",
]
