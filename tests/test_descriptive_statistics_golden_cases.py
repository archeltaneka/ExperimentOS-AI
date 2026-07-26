"""Hand-calculable deterministic golden cases for descriptive statistics."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.descriptive import (
    BinarySummary,
    CountSummary,
    DescriptiveStatisticsInput,
    DescriptiveStatisticsInvariantError,
    DescriptiveStatisticsService,
)
from packages.experiments.analysis.metrics import AnalysisUnit, MetricType
from packages.experiments.analysis.populations import (
    CriterionOperator,
    SegmentDefinition,
    SelectionCriterion,
)
from packages.experiments.analysis.serialization import (
    descriptive_statistics_result_from_json,
    to_canonical_json,
)
from packages.experiments.analysis.study_designs import Clustered
from packages.experiments.analysis.validation import AnalysisTable, ValidationPolicy
from tests.analysis_contract_fixtures import quasi_experimental_request
from tests.test_descriptive_statistics_diagnostics import _input_for
from tests.test_descriptive_statistics_service import _eligible_input


@pytest.mark.parametrize(
    ("name", "metric_type", "rows", "control_mean", "treatment_mean", "expected_type"),
    (
        (
            "balanced_continuous",
            MetricType.CONTINUOUS,
            (
                ("o1", "a1", "control", 1.0),
                ("o2", "a2", "control", 3.0),
                ("o3", "a3", "treatment", 5.0),
                ("o4", "a4", "treatment", 7.0),
            ),
            2.0,
            6.0,
            None,
        ),
        (
            "unbalanced_continuous",
            MetricType.CONTINUOUS,
            (
                ("o1", "a1", "control", 2.0),
                ("o2", "a2", "treatment", 4.0),
                ("o3", "a3", "treatment", 6.0),
                ("o4", "a4", "treatment", 8.0),
            ),
            2.0,
            6.0,
            None,
        ),
        (
            "binary",
            MetricType.BINARY,
            (
                ("o1", "a1", "control", 0),
                ("o2", "a2", "control", 1),
                ("o3", "a3", "treatment", 1),
                ("o4", "a4", "treatment", 1),
            ),
            0.5,
            1.0,
            BinarySummary,
        ),
        (
            "count",
            MetricType.COUNT,
            (
                ("o1", "a1", "control", 0),
                ("o2", "a2", "control", 2),
                ("o3", "a3", "treatment", 3),
                ("o4", "a4", "treatment", 5),
            ),
            1.0,
            4.0,
            CountSummary,
        ),
    ),
)
def test_hand_calculable_metric_goldens(
    name: str,
    metric_type: MetricType,
    rows: tuple[tuple[object, ...], ...],
    control_mean: float,
    treatment_mean: float,
    expected_type: type[BinarySummary | CountSummary] | None,
) -> None:
    """Catches an arm ordering or metric-dispatch regression in a fixed numeric fixture."""
    if name == "unbalanced_continuous":
        analysis_input = _force_data_eligible(
            _input_for(
                AnalysisTable(
                    columns=("order_id", "account_id", "arm", "outcome"),
                    rows=rows,
                ),
                allow_data_ineligible=True,
            )
        )
    else:
        analysis_input = _eligible_input(rows, metric_type=metric_type)
    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert result.control is not None
    assert result.treatment is not None
    if expected_type is not None:
        assert isinstance(result.population.summary, expected_type), name
    if isinstance(result.control.summary, BinarySummary):
        assert result.control.summary.rate == pytest.approx(control_mean)
        assert result.treatment.summary.rate == pytest.approx(treatment_mean)
    else:
        assert result.control.summary.mean == pytest.approx(control_mean)
        assert result.treatment.summary.mean == pytest.approx(treatment_mean)
    assert result.raw_comparison is not None
    assert result.raw_comparison.absolute_difference == pytest.approx(treatment_mean - control_mean)


def test_missing_all_missing_one_value_and_zero_variance_goldens() -> None:
    """Catches fabricated zero summaries for exclusions and undefined sample variance."""
    missing = DescriptiveStatisticsService().summarize(
        _eligible_input(
            (
                ("o1", "a1", "control", None),
                ("o2", "a2", "control", 2.0),
                ("o3", "a3", "treatment", None),
                ("o4", "a4", "treatment", 6.0),
            )
        )
    )
    assert (
        missing.population.valid_outcome_count,
        missing.population.missing_outcome_count,
    ) == (2, 2)
    assert missing.population.summary.mean == pytest.approx(4.0)

    all_missing_input = _force_data_eligible(
        _input_for(
            AnalysisTable(
                columns=("order_id", "account_id", "arm", "outcome"),
                rows=(("o1", "a1", "control", None), ("o2", "a2", "treatment", None)),
            ),
            allow_data_ineligible=True,
        )
    )
    all_missing = DescriptiveStatisticsService().summarize(all_missing_input)
    assert all_missing.population.summary.summary_type == "unavailable"
    assert tuple(item.code for item in all_missing.diagnostics) == ("outcome.all_missing",)

    one_value_input = _force_data_eligible(
        _input_for(
            AnalysisTable(
                columns=("order_id", "account_id", "arm", "outcome"),
                rows=(("o1", "a1", "control", None), ("o2", "a2", "treatment", 2.0)),
            ),
            allow_data_ineligible=True,
        )
    )
    one_value = DescriptiveStatisticsService().summarize(one_value_input)
    assert one_value.treatment is not None
    assert one_value.treatment.summary.variance is None
    assert tuple(item.code for item in one_value.diagnostics) == ("outcome.sparse_valid_sample",)

    zero_variance_input = _force_data_eligible(
        _input_for(
            AnalysisTable(
                columns=("order_id", "account_id", "arm", "outcome"),
                rows=(("o1", "a1", "control", 2.0), ("o2", "a2", "treatment", 2.0)),
            ),
            allow_data_ineligible=True,
        )
    )
    zero_variance = DescriptiveStatisticsService().summarize(zero_variance_input)
    assert zero_variance.population.summary.variance == 0.0
    assert tuple(item.code for item in zero_variance.diagnostics) == ("outcome.zero_variance",)


def test_zero_baseline_and_nonfinite_input_goldens() -> None:
    """Catches unsafe relative division and any non-finite value reaching numerical helpers."""
    baseline = DescriptiveStatisticsService().summarize(
        _eligible_input(
            (
                ("o1", "a1", "control", 0.0),
                ("o2", "a2", "control", 0.0),
                ("o3", "a3", "treatment", 1.0),
                ("o4", "a4", "treatment", 1.0),
            )
        )
    )
    assert baseline.raw_comparison is not None
    assert baseline.raw_comparison.absolute_difference == 1.0
    assert baseline.raw_comparison.relative_difference is None
    assert baseline.raw_comparison.relative_difference_unavailable_reason is not None

    unsafe_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome"),
            rows=(("o1", "a1", "control", 0.0), ("o2", "a2", "treatment", math.inf)),
        ),
        allow_data_ineligible=True,
    )
    with pytest.raises(DescriptiveStatisticsInvariantError):
        DescriptiveStatisticsService().summarize(unsafe_input)


def test_segment_period_order_and_canonical_json_are_deterministic() -> None:
    """Catches ordering regressions or unstable serialization in structured output."""
    segment = SegmentDefinition(
        segment_id="australian_users",
        label="Australian users",
        criteria=(
            SelectionCriterion(attribute="country", operator=CriterionOperator.EQUAL, value="AU"),
        ),
    )
    segment_result = DescriptiveStatisticsService().summarize(
        _input_for(
            AnalysisTable(
                columns=("order_id", "account_id", "arm", "outcome", "country"),
                rows=(
                    ("o1", "a1", "control", 1.0, "AU"),
                    ("o2", "a2", "treatment", 3.0, "AU"),
                    ("o3", "a3", "control", 8.0, "NZ"),
                    ("o4", "a4", "treatment", 10.0, "NZ"),
                ),
            ),
            request_update={"segment": segment},
        )
    )
    assert tuple(item.segment_id for item in segment_result.segments) == ("australian_users",)
    assert segment_result.segments[0].raw_comparison is not None
    assert segment_result.segments[0].raw_comparison.absolute_difference == 2.0

    period_result = _quasi_period_result()
    assert tuple(item.period_id for item in period_result.periods) == ("pre", "post")
    assert period_result.periods[0].control is not None
    assert period_result.periods[0].control.summary.rate == 0.0
    assert period_result.periods[1].treatment is not None
    assert period_result.periods[1].treatment.summary.rate == 1.0

    first_json = to_canonical_json(segment_result)
    second_json = to_canonical_json(segment_result)
    assert first_json == second_json
    assert descriptive_statistics_result_from_json(first_json) == segment_result


def _force_data_eligible(analysis_input: DescriptiveStatisticsInput) -> DescriptiveStatisticsInput:
    """Reuse validation evidence when a golden describes a reported numerical limitation."""
    return DescriptiveStatisticsInput(
        context=analysis_input.context,
        eligibility=analysis_input.eligibility.model_copy(
            update={
                "method_support": analysis_input.eligibility.method_support.model_copy(
                    update={"data_eligible": True}
                )
            }
        ),
    )


def _quasi_period_result():
    request = quasi_experimental_request().model_copy(
        update={"clustering": Clustered(unit=AnalysisUnit(unit_id="account", label="Account"))}
    )
    analysis_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome", "observed_at"),
            rows=(
                ("o1", "a1", "control", 0.0, "2026-06-15T00:00:00Z"),
                ("o1", "a1", "control", 1.0, "2026-07-05T00:00:00Z"),
                ("o2", "a2", "treatment", 0.0, "2026-06-15T00:00:00Z"),
                ("o2", "a2", "treatment", 1.0, "2026-07-05T00:00:00Z"),
            ),
        ),
        request_update={
            "study_design": request.study_design,
            "clustering": request.clustering,
            "outcome": request.outcome,
            "estimand": request.estimand,
        },
        binding_update={"timestamp_column": "observed_at", "clustering_unit_column": "account_id"},
        policy=ValidationPolicy(
            minimum_total=1,
            minimum_per_arm=1,
            weak_total=1,
            weak_per_arm=1,
            minimum_per_segment_arm=1,
            minimum_clusters=2,
            weak_clusters=2,
        ),
    )
    return DescriptiveStatisticsService().summarize(analysis_input)
