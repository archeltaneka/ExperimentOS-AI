from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.descriptive.models import (
    BinarySummary,
    ContinuousSummary,
    CountSummary,
    DescriptiveStatisticsConfig,
    DescriptiveStatisticsResult,
    PopulationSummary,
    RawComparison,
)
from packages.experiments.analysis.serialization import (
    DESCRIPTIVE_STATISTICS_RESULT_ADAPTER,
    descriptive_statistics_result_from_json,
    to_canonical_json,
)


def test_config_defaults_to_sorted_quartiles_and_rejects_duplicate_levels() -> None:
    assert DescriptiveStatisticsConfig().quantile_levels == (0.25, 0.5, 0.75)

    with pytest.raises(ValidationError, match="unique ascending"):
        DescriptiveStatisticsConfig(quantile_levels=(0.25, 0.25))


def test_continuous_summary_rejects_non_finite_numeric_values() -> None:
    with pytest.raises(ValidationError):
        ContinuousSummary(sample_size=12, mean=math.nan)


@pytest.mark.parametrize(
    ("summary_type", "kwargs"),
    [
        (
            ContinuousSummary,
            {
                "sample_size": 4,
                "variance": 1.25,
                "standard_error": 0.56,
            },
        ),
        (
            CountSummary,
            {
                "sample_size": 4,
                "variance": 1.25,
                "standard_error": 0.56,
            },
        ),
        (
            BinarySummary,
            {
                "sample_size": 4,
                "success_count": 2,
                "failure_count": 2,
                "rate": 0.5,
                "variance": 0.25,
                "standard_error": 0.25,
            },
        ),
    ],
)
def test_summary_dispersion_fields_are_finite_and_nullable(
    summary_type: type[ContinuousSummary | CountSummary | BinarySummary],
    kwargs: dict[str, object],
) -> None:
    summary = summary_type(**kwargs)

    assert summary.variance is not None
    assert summary.standard_error is not None

    with pytest.raises(ValidationError):
        summary_type(**{**kwargs, "variance": math.nan})


def test_unavailable_raw_comparison_rejects_numeric_results() -> None:
    with pytest.raises(ValidationError, match="must not include numeric differences"):
        RawComparison(
            outcome_direction="increase",
            availability="unavailable",
            unavailable_reason="insufficient data",
            absolute_difference=0.0,
        )


def test_descriptive_result_round_trips_through_canonical_json() -> None:
    original = DescriptiveStatisticsResult(
        outcome_id="conversion_rate",
        outcome_label="Conversion rate",
        outcome_direction="increase",
        population=PopulationSummary(
            population_id="all_users",
            label="All users",
            summary=ContinuousSummary(sample_size=120, mean=0.14),
        ),
    )

    payload = to_canonical_json(original)

    assert descriptive_statistics_result_from_json(payload) == original
    assert DESCRIPTIVE_STATISTICS_RESULT_ADAPTER.validate_json(payload) == original
