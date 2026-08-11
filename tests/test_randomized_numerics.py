"""Numerical and descriptive building blocks for randomized analysis."""

from __future__ import annotations

import math
import sys

import pytest

from packages.experiments.analysis.randomized.descriptive import (
    RandomizedDescriptiveError,
    summarize_binary_arm,
    summarize_continuous_arm,
)
from packages.experiments.analysis.randomized.numerics import (
    RandomizedNumericalError,
    normal_critical_value,
    t_critical_value,
    two_sided_normal_p_value,
    two_sided_t_p_value,
)


def test_two_sided_t_helpers_match_hand_checked_df_ten_boundary() -> None:
    """A t tail or quantile error changes a 5% two-sided decision boundary."""
    statistic = 2.2281388519649385

    assert two_sided_t_p_value(statistic, degrees_of_freedom=10) == pytest.approx(0.05)
    assert t_critical_value(alpha=0.05, degrees_of_freedom=10) == pytest.approx(statistic)


def test_two_sided_normal_helpers_match_hand_checked_five_percent_boundary() -> None:
    """A normal tail or quantile error changes a 5% two-sided decision boundary."""
    statistic = 1.959963984540054

    assert two_sided_normal_p_value(statistic) == pytest.approx(0.05)
    assert normal_critical_value(alpha=0.05) == pytest.approx(statistic)


def test_two_sided_p_values_remain_positive_when_distribution_tail_underflows() -> None:
    assert two_sided_normal_p_value(40.0) > 0.0
    assert two_sided_t_p_value(1e300, degrees_of_freedom=10.0) > 0.0


@pytest.mark.parametrize(
    ("function", "arguments"),
    [
        (two_sided_t_p_value, (math.nan, 10)),
        (two_sided_t_p_value, (1.0, 0)),
        (two_sided_normal_p_value, (math.inf,)),
        (two_sided_normal_p_value, (10**10_000,)),
        (t_critical_value, (0.05, math.nan)),
        (normal_critical_value, (1.0,)),
    ],
)
def test_numerical_helpers_reject_nonfinite_or_invalid_distribution_parameters(
    function: object,
    arguments: tuple[float, ...],
) -> None:
    """Invalid distribution inputs must not leak NaN or infinity into result contracts."""
    if not callable(function):
        raise AssertionError("test case must supply a callable")

    with pytest.raises(RandomizedNumericalError):
        function(*arguments)


def test_summarize_continuous_arm_uses_sample_variance() -> None:
    """Using a population denominator would understate variability for a small arm."""
    summary = summarize_continuous_arm("treatment", (1, 2, 5))

    assert summary.arm_id == "treatment"
    assert summary.n == 3
    assert summary.mean == pytest.approx(8 / 3)
    assert summary.sample_variance == pytest.approx(13 / 3)


@pytest.mark.parametrize(
    "values",
    [
        (),
        (1,),
        (1, math.nan),
        (1, math.inf),
        (sys.float_info.max, sys.float_info.max),
        (1, 10**10_000),
        (1, True),
        (1, "2"),
    ],
)
def test_summarize_continuous_arm_rejects_nonfinite_or_non_numeric_values(
    values: tuple[object, ...],
) -> None:
    """Filtering or coercing outcomes would silently change the analyzed sample."""
    with pytest.raises(RandomizedDescriptiveError):
        summarize_continuous_arm("treatment", values)


def test_summarize_binary_arm_counts_explicit_boolean_and_integer_indicators() -> None:
    """Truthiness would miscount explicit binary outcomes such as a non-empty string."""
    summary = summarize_binary_arm("control", (True, 0, 1, False, True))

    assert summary.arm_id == "control"
    assert summary.n == 5
    assert summary.successes == 3
    assert summary.failures == 2
    assert summary.rate == pytest.approx(0.6)


@pytest.mark.parametrize(
    "values",
    [
        (),
        (True, 2),
        (False, 1.0),
        (1, "0"),
        (0, None),
    ],
)
def test_summarize_binary_arm_rejects_instead_of_filtering_or_coercing(
    values: tuple[object, ...],
) -> None:
    """A bad binary value must reject the entire arm, not be dropped or coerced."""
    with pytest.raises(RandomizedDescriptiveError):
        summarize_binary_arm("control", values)
