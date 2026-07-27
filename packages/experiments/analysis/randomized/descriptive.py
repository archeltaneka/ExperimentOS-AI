"""Reusable immutable arm summaries for randomized analysis."""

from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Real

from .models import BinaryArmSummary, ContinuousArmSummary


class RandomizedDescriptiveError(ValueError):
    """Raised when an arm cannot produce a complete deterministic summary."""


def summarize_continuous_arm(
    arm_id: str,
    values: Sequence[object],
) -> ContinuousArmSummary:
    """Build a continuous arm summary with the sample variance denominator ``n - 1``."""
    if len(values) < 2:
        raise RandomizedDescriptiveError("continuous arms require at least two observations")

    numeric_values = tuple(_finite_continuous_value(value) for value in values)
    try:
        mean = math.fsum(numeric_values) / len(numeric_values)
        squared_deviations = ((value - mean) ** 2 for value in numeric_values)
        sample_variance = math.fsum(squared_deviations) / (len(numeric_values) - 1)
    except (OverflowError, ValueError) as error:
        raise RandomizedDescriptiveError("continuous arm summary must be finite") from error
    if not math.isfinite(mean) or not math.isfinite(sample_variance):
        raise RandomizedDescriptiveError("continuous arm summary must be finite")
    return ContinuousArmSummary(
        arm_id=arm_id,
        n=len(numeric_values),
        mean=mean,
        sample_variance=sample_variance,
    )


def summarize_binary_arm(arm_id: str, values: Sequence[object]) -> BinaryArmSummary:
    """Build a binary arm summary from explicit ``bool`` or exact integer ``0``/``1`` values."""
    if len(values) == 0:
        raise RandomizedDescriptiveError("binary arms require at least one observation")

    successes = 0
    for value in values:
        if type(value) is bool:
            if value is True:
                successes += 1
        elif type(value) is int and value in (0, 1):
            successes += value
        else:
            raise RandomizedDescriptiveError(
                "binary arm values must be bool or exact integer zero or one"
            )

    n = len(values)
    return BinaryArmSummary(
        arm_id=arm_id,
        n=n,
        successes=successes,
        failures=n - successes,
        rate=successes / n,
    )


def _finite_continuous_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise RandomizedDescriptiveError("continuous arm values must be finite real numbers")
    try:
        converted = float(value)
    except OverflowError as error:
        raise RandomizedDescriptiveError(
            "continuous arm values must be finite real numbers"
        ) from error
    if not math.isfinite(converted):
        raise RandomizedDescriptiveError("continuous arm values must be finite real numbers")
    return converted


__all__ = [
    "RandomizedDescriptiveError",
    "summarize_binary_arm",
    "summarize_continuous_arm",
]
