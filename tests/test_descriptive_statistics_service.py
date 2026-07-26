from __future__ import annotations

from packages.experiments.analysis.descriptive import (
    ComparisonAvailability,
    DescriptiveStatisticsInput,
    DescriptiveStatisticsService,
)
from packages.experiments.analysis.metrics import AnalysisUnit, MetricType
from packages.experiments.analysis.study_designs import NoClustering
from packages.experiments.analysis.validation import (
    AnalysisEligibilityService,
    AnalysisTable,
    ValidationPolicy,
)
from tests.analysis_validation_fixtures import context_for


def _eligible_input(
    rows: tuple[tuple[object, ...], ...],
    *,
    metric_type: MetricType = MetricType.CONTINUOUS,
) -> DescriptiveStatisticsInput:
    context = context_for(
        table=AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome"),
            rows=rows,
        )
    )
    policy = ValidationPolicy(
        minimum_total=1,
        minimum_per_arm=1,
        weak_total=1,
        weak_per_arm=1,
    )
    metric = context.request.outcome.metric.model_copy(update={"metric_type": metric_type})
    outcome = context.request.outcome.model_copy(update={"metric": metric})
    unit = AnalysisUnit(unit_id="order_id", label="Order")
    design = context.request.study_design.model_copy(update={"randomization_unit": unit})
    context = context_for(
        context.request.model_copy(
            update={
                "outcome": outcome,
                "unit_of_analysis": unit,
                "clustering": NoClustering(),
                "study_design": design,
            }
        ),
        table=context.table,
        binding=context.binding.model_copy(update={"randomization_unit_column": "order_id"}),
        policy=policy,
    )
    eligibility = AnalysisEligibilityService(policy=context.policy).validate(
        context.request, context.table, context.binding
    )
    assert eligibility.method_support.data_eligible
    assert not eligibility.method_support.executable
    return DescriptiveStatisticsInput(context=context, eligibility=eligibility)


def test_service_summarizes_overall_and_declared_arms_with_raw_unadjusted_comparison() -> None:
    """Catches a service that omits arm populations or reverses treatment-control subtraction."""
    analysis_input = _eligible_input(
        (
            ("o1", "a1", "control", 1.0),
            ("o2", "a2", "control", 3.0),
            ("o3", "a3", "treatment", 5.0),
            ("o4", "a4", "treatment", 7.0),
        )
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert result.population.row_count == 4
    assert result.population.unique_unit_count == 4
    assert result.population.valid_outcome_count == 4
    assert result.population.missing_outcome_count == 0
    assert result.control.summary.mean == 2.0
    assert result.treatment.summary.mean == 6.0
    assert result.raw_comparison is not None
    assert result.raw_comparison.comparison_type == "raw_unadjusted"
    assert result.raw_comparison.availability is ComparisonAvailability.AVAILABLE
    assert result.raw_comparison.absolute_difference == 4.0
    assert result.raw_comparison.relative_difference == 2.0


def test_service_makes_relative_comparison_unavailable_for_zero_control_baseline() -> None:
    """Catches unsafe division by a zero control summary."""
    analysis_input = _eligible_input(
        (
            ("o1", "a1", "control", 0.0),
            ("o2", "a2", "control", 0.0),
            ("o3", "a3", "treatment", 1.0),
            ("o4", "a4", "treatment", 1.0),
        )
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert result.raw_comparison is not None
    assert result.raw_comparison.availability is ComparisonAvailability.AVAILABLE
    assert result.raw_comparison.absolute_difference == 1.0
    assert result.raw_comparison.relative_difference is None
    assert (
        result.raw_comparison.relative_difference_unavailable_reason
        == "relative difference unavailable: control baseline is zero"
    )


def test_service_counts_missing_outcomes_before_excluding_them_from_metric_summary() -> None:
    """Catches silent missing-value removal or replacement with zero."""
    analysis_input = _eligible_input(
        (
            ("o1", "a1", "control", None),
            ("o2", "a2", "control", 2.0),
            ("o3", "a3", "treatment", None),
            ("o4", "a4", "treatment", 6.0),
        )
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert (result.control.row_count, result.control.missing_outcome_count) == (2, 1)
    assert (result.treatment.row_count, result.treatment.missing_outcome_count) == (2, 1)
    assert result.population.summary.mean == 4.0


def test_service_is_deterministic_when_input_rows_are_reordered() -> None:
    """Catches population summaries that depend on caller row ordering."""
    rows = (
        ("o1", "a1", "control", 1.0),
        ("o2", "a2", "treatment", 7.0),
        ("o3", "a3", "control", 3.0),
        ("o4", "a4", "treatment", 5.0),
    )

    first = DescriptiveStatisticsService().summarize(_eligible_input(rows))
    second = DescriptiveStatisticsService().summarize(_eligible_input(tuple(reversed(rows))))

    assert first == second
