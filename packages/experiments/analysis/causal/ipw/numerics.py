"""Pure finite-safe numerical helpers for inverse-probability weighting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

from ..estimands import CausalEstimandKind


class IPWNumericalError(ValueError):
    """Raised when IPW arithmetic cannot produce a finite owned result."""


@dataclass(frozen=True, slots=True)
class WeightClippingResult:
    """Internal immutable evidence from one explicit maximum-weight cap."""

    weights: tuple[float, ...]
    affected_count: int
    treated_affected_count: int
    control_affected_count: int
    affected_proportion: float
    maximum_before: float
    maximum_after: float


def compute_raw_weights(
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
    estimand: CausalEstimandKind,
) -> tuple[float, ...]:
    """Compute unnormalized, unstabilized ATE or ATT weights."""
    if len(scores) != len(treated) or not scores:
        raise IPWNumericalError("scores and treatment indicators must align and be non-empty")
    if estimand not in {CausalEstimandKind.ATE, CausalEstimandKind.ATT}:
        raise IPWNumericalError("only ATE and ATT weights are supported")
    weights: list[float] = []
    for score, is_treated in zip(scores, treated, strict=True):
        checked_score = _probability(score, name="propensity score")
        if estimand is CausalEstimandKind.ATT and is_treated:
            weight = 1.0
        else:
            denominator = checked_score if is_treated else 1.0 - checked_score
            if denominator == 0.0:
                raise IPWNumericalError("weight denominator must be positive")
            weight = (
                1.0 / denominator
                if estimand is CausalEstimandKind.ATE
                else checked_score / denominator
            )
        weights.append(_nonnegative_finite(weight, name="weight"))
    return tuple(weights)


def stabilize_weights(
    raw_weights: tuple[float, ...],
    treated: tuple[bool, ...],
    estimand: CausalEstimandKind,
    *,
    treatment_prevalence: float,
) -> tuple[float, ...]:
    """Apply the explicit ATE or ATT stabilization convention."""
    if len(raw_weights) != len(treated) or not raw_weights:
        raise IPWNumericalError("weights and treatment indicators must align and be non-empty")
    if estimand not in {CausalEstimandKind.ATE, CausalEstimandKind.ATT}:
        raise IPWNumericalError("only ATE and ATT stabilization is supported")
    prevalence = _probability(treatment_prevalence, name="treatment prevalence")
    if prevalence in {0.0, 1.0}:
        raise IPWNumericalError("treatment prevalence must be strictly between zero and one")
    control_factor = (1.0 - prevalence) / prevalence
    stabilized: list[float] = []
    for weight, is_treated in zip(raw_weights, treated, strict=True):
        checked = _nonnegative_finite(weight, name="raw weight")
        if estimand is CausalEstimandKind.ATE:
            factor = prevalence if is_treated else 1.0 - prevalence
        else:
            factor = 1.0 if is_treated else control_factor
        stabilized.append(_nonnegative_finite(checked * factor, name="stabilized weight"))
    return tuple(stabilized)


def clip_weights(
    weights: tuple[float, ...],
    treated: tuple[bool, ...],
    *,
    maximum: float,
) -> WeightClippingResult:
    """Apply one explicit maximum cap without mutating the supplied weights."""
    if len(weights) != len(treated) or not weights:
        raise IPWNumericalError("weights and treatment indicators must align and be non-empty")
    cap = _finite(maximum, name="clipping maximum")
    if cap <= 0.0:
        raise IPWNumericalError("clipping maximum must be positive")
    checked = tuple(_nonnegative_finite(weight, name="weight") for weight in weights)
    clipped = tuple(min(weight, cap) for weight in checked)
    affected = tuple(weight > cap for weight in checked)
    affected_count = sum(affected)
    return WeightClippingResult(
        weights=clipped,
        affected_count=affected_count,
        treated_affected_count=sum(
            changed and is_treated
            for changed, is_treated in zip(affected, treated, strict=True)
        ),
        control_affected_count=sum(
            changed and not is_treated
            for changed, is_treated in zip(affected, treated, strict=True)
        ),
        affected_proportion=affected_count / len(checked),
        maximum_before=max(checked),
        maximum_after=max(clipped),
    )


def weighted_mean(values: tuple[float, ...], weights: tuple[float, ...]) -> float:
    """Compute an explicit Hajek weighted mean without storing normalized weights."""
    if len(values) != len(weights) or not values:
        raise IPWNumericalError("values and weights must align and be non-empty")
    checked_values = tuple(_finite(value, name="outcome") for value in values)
    checked_weights = tuple(_nonnegative_finite(weight, name="weight") for weight in weights)
    maximum = max(checked_weights)
    if maximum == 0.0:
        raise IPWNumericalError("weighted mean requires positive total arm weight")
    scaled = tuple(weight / maximum for weight in checked_weights)
    total = math.fsum(scaled)
    if total <= 0.0 or not math.isfinite(total):
        raise IPWNumericalError("weighted mean requires finite positive total arm weight")
    try:
        result = math.fsum(
            (weight / total) * value
            for value, weight in zip(checked_values, scaled, strict=True)
        )
    except OverflowError as error:
        raise IPWNumericalError("weighted mean must be finite") from error
    return _finite(result, name="weighted mean")


def effective_sample_size(weights: tuple[float, ...]) -> float:
    """Compute Kish ESS using scale-invariant arithmetic to avoid squared-weight overflow."""
    if not weights:
        raise IPWNumericalError("effective sample size requires weights")
    checked = tuple(_nonnegative_finite(weight, name="weight") for weight in weights)
    maximum = max(checked)
    if maximum == 0.0:
        raise IPWNumericalError("effective sample size requires positive total weight")
    scaled = tuple(weight / maximum for weight in checked)
    total = math.fsum(scaled)
    sum_squares = math.fsum(weight * weight for weight in scaled)
    if total <= 0.0 or sum_squares <= 0.0:
        raise IPWNumericalError("effective sample size denominator must be positive")
    result = total * total / sum_squares
    return _nonnegative_finite(result, name="effective sample size")


def _probability(value: object, *, name: str) -> float:
    checked = _finite(value, name=name)
    if not 0.0 <= checked <= 1.0:
        raise IPWNumericalError(f"{name} must be within [0, 1]")
    return checked


def _nonnegative_finite(value: object, *, name: str) -> float:
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


__all__ = [
    "IPWNumericalError",
    "WeightClippingResult",
    "clip_weights",
    "compute_raw_weights",
    "effective_sample_size",
    "stabilize_weights",
    "weighted_mean",
]
