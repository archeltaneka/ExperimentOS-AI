"""Pure finite-value descriptive-statistics helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable

from .models import (
    BinarySummary,
    ContinuousSummary,
    CountSummary,
    DescriptiveStatisticsConfig,
    Quantile,
    UnavailableSummary,
)


class NumericSummaryInvariantError(ValueError):
    """Raised when values cannot produce a finite descriptive summary."""


def summarize_continuous(
    values: Iterable[float], config: DescriptiveStatisticsConfig
) -> ContinuousSummary | UnavailableSummary:
    """Summarize finite continuous values with sample standard deviation."""
    observations = _finite_values(values)
    if not observations:
        return _unavailable()

    mean = _mean(observations)
    variance, standard_deviation, standard_error = _sample_statistics(observations, mean)
    ordered = sorted(observations)
    return ContinuousSummary(
        sample_size=len(observations),
        mean=mean,
        variance=variance,
        standard_deviation=standard_deviation,
        standard_error=standard_error,
        minimum=ordered[0],
        maximum=ordered[-1],
        quantiles=tuple(
            Quantile(level=level, value=_linear_quantile(ordered, level))
            for level in config.quantile_levels
        ),
    )


def summarize_binary(
    values: Iterable[float], config: DescriptiveStatisticsConfig
) -> BinarySummary | UnavailableSummary:
    """Summarize exact zero/one outcomes without truthiness coercion."""
    del config
    observations = _finite_values(values)
    if not observations:
        return _unavailable()
    if any(value not in (0.0, 1.0) for value in observations):
        raise NumericSummaryInvariantError("binary values must be exactly 0.0 or 1.0")

    positive_count = sum(value == 1.0 for value in observations)
    proportion = positive_count / len(observations)
    variance, standard_error = _binary_statistics(proportion, len(observations))
    return BinarySummary(
        sample_size=len(observations),
        positive_count=positive_count,
        proportion=proportion,
        success_count=positive_count,
        failure_count=len(observations) - positive_count,
        rate=proportion,
        variance=variance,
        standard_error=standard_error,
    )


def summarize_count(
    values: Iterable[float], config: DescriptiveStatisticsConfig
) -> CountSummary | UnavailableSummary:
    """Summarize non-negative integer count values."""
    del config
    observations = _finite_values(values)
    if not observations:
        return _unavailable()
    if any(value < 0.0 for value in observations):
        raise NumericSummaryInvariantError("count values must not be negative")
    if any(not value.is_integer() for value in observations):
        raise NumericSummaryInvariantError("count values must be integers")

    counts = [int(value) for value in observations]
    mean = _mean(observations)
    variance, _, standard_error = _sample_statistics(observations, mean)
    return CountSummary(
        sample_size=len(counts),
        total=sum(counts),
        mean=mean,
        variance=variance,
        standard_error=standard_error,
        minimum=min(counts),
        maximum=max(counts),
    )


def _finite_values(values: Iterable[float]) -> list[float]:
    observations: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NumericSummaryInvariantError("numeric values must be finite real numbers")
        normalized = float(value)
        if not math.isfinite(normalized):
            raise NumericSummaryInvariantError("numeric values must be finite real numbers")
        observations.append(normalized)
    return observations


def _mean(values: list[float]) -> float:
    try:
        mean = math.fsum(values) / len(values)
    except OverflowError as error:
        raise NumericSummaryInvariantError("summary values must be finite") from error
    _require_finite(mean)
    return mean


def _sample_statistics(
    values: list[float], mean: float
) -> tuple[float | None, float | None, float | None]:
    if len(values) < 2:
        return None, None, None
    try:
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    except OverflowError as error:
        raise NumericSummaryInvariantError("summary values must be finite") from error
    _require_finite(variance)
    standard_deviation = math.sqrt(variance)
    _require_finite(standard_deviation)
    standard_error = standard_deviation / math.sqrt(len(values))
    _require_finite(standard_error)
    return variance, standard_deviation, standard_error


def _binary_statistics(proportion: float, sample_size: int) -> tuple[float | None, float | None]:
    if sample_size < 2:
        return None, None
    variance = proportion * (1.0 - proportion) * sample_size / (sample_size - 1)
    _require_finite(variance)
    standard_error = math.sqrt(proportion * (1.0 - proportion) / sample_size)
    _require_finite(standard_error)
    return variance, standard_error


def _linear_quantile(values: list[float], level: float) -> float:
    position = (len(values) - 1) * level
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    quantile = values[lower] + (values[upper] - values[lower]) * fraction
    _require_finite(quantile)
    return quantile


def _require_finite(value: float) -> None:
    if not math.isfinite(value):
        raise NumericSummaryInvariantError("summary values must be finite")


def _unavailable() -> UnavailableSummary:
    return UnavailableSummary(reason="no observations")
