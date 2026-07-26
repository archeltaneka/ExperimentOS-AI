from __future__ import annotations

import math
import sys

import pytest

from packages.experiments.analysis.descriptive.models import (
    BinarySummary,
    ContinuousSummary,
    DescriptiveStatisticsConfig,
    UnavailableSummary,
)
from packages.experiments.analysis.descriptive.numeric import (
    NumericSummaryInvariantError,
    summarize_binary,
    summarize_continuous,
    summarize_count,
)


def test_continuous_summary_uses_sample_statistics_and_linear_quartiles() -> None:
    summary = summarize_continuous([1.0, 2.0, 3.0, 4.0], DescriptiveStatisticsConfig())

    assert summary == ContinuousSummary(
        sample_size=4,
        mean=2.5,
        variance=5 / 3,
        standard_deviation=math.sqrt(5 / 3),
        standard_error=math.sqrt(5 / 3) / 2,
        minimum=1.0,
        maximum=4.0,
        quantiles=(
            {"level": 0.25, "value": 1.75},
            {"level": 0.5, "value": 2.5},
            {"level": 0.75, "value": 3.25},
        ),
    )


def test_continuous_summary_retains_single_observation_statistics_without_deviation() -> None:
    summary = summarize_continuous([3.5], DescriptiveStatisticsConfig())

    assert summary == ContinuousSummary(
        sample_size=1,
        mean=3.5,
        variance=None,
        standard_error=None,
        minimum=3.5,
        maximum=3.5,
        quantiles=(
            {"level": 0.25, "value": 3.5},
            {"level": 0.5, "value": 3.5},
            {"level": 0.75, "value": 3.5},
        ),
    )


def test_empty_inputs_return_an_explicit_unavailable_summary() -> None:
    config = DescriptiveStatisticsConfig()

    for summarize in (summarize_continuous, summarize_binary, summarize_count):
        summary = summarize([], config)
        assert isinstance(summary, UnavailableSummary)
        assert summary.reason == "no observations"


def test_continuous_summary_preserves_zero_variance() -> None:
    summary = summarize_continuous([5.0, 5.0], DescriptiveStatisticsConfig())

    assert summary.standard_deviation == 0.0
    assert summary.variance == 0.0
    assert summary.standard_error == 0.0


def test_continuous_summary_accepts_extreme_finite_values_without_non_finite_outputs() -> None:
    summary = summarize_continuous(
        [sys.float_info.max, sys.float_info.max], DescriptiveStatisticsConfig()
    )

    assert summary.mean == sys.float_info.max
    assert summary.standard_deviation == 0.0
    assert summary.variance == 0.0
    assert summary.standard_error == 0.0
    assert all(
        math.isfinite(value)
        for value in (
            summary.mean,
            summary.variance,
            summary.standard_deviation,
            summary.standard_error,
        )
    )


def test_binary_summary_counts_all_valid_outcomes_and_computes_proportion() -> None:
    summary = summarize_binary([0.0, 1.0, 1.0, 0.0], DescriptiveStatisticsConfig())

    assert summary == BinarySummary(
        sample_size=4,
        positive_count=2,
        proportion=0.5,
        success_count=2,
        failure_count=2,
        rate=0.5,
        variance=1 / 3,
        standard_error=0.25,
    )


def test_binary_summary_rejects_values_other_than_exact_zero_or_one() -> None:
    with pytest.raises(NumericSummaryInvariantError, match="binary"):
        summarize_binary([0.0, 2.0], DescriptiveStatisticsConfig())


def test_binary_summary_marks_variance_and_standard_error_unavailable_for_one_observation() -> None:
    summary = summarize_binary([1.0], DescriptiveStatisticsConfig())

    assert summary.variance is None
    assert summary.standard_error is None


def test_count_summary_handles_zero_counts() -> None:
    summary = summarize_count([0.0, 0.0, 2.0], DescriptiveStatisticsConfig())

    assert summary.sample_size == 3
    assert summary.total == 2
    assert summary.mean == 2 / 3
    assert summary.variance == pytest.approx(4 / 3)
    assert summary.standard_error == pytest.approx(2 / 3)
    assert summary.minimum == 0
    assert summary.maximum == 2


def test_count_summary_marks_variance_and_standard_error_unavailable_for_one_observation() -> None:
    summary = summarize_count([2.0], DescriptiveStatisticsConfig())

    assert summary.variance is None
    assert summary.standard_error is None


def test_count_summary_rejects_negative_counts() -> None:
    with pytest.raises(NumericSummaryInvariantError, match="negative"):
        summarize_count([0.0, -1.0], DescriptiveStatisticsConfig())
