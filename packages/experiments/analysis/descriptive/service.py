"""Orchestrate deterministic, non-causal descriptive population summaries."""

from __future__ import annotations

import math
from collections.abc import Iterable

from ..metrics import MetricType
from ..validation.context import ValidationContext
from ..validation.criteria import evaluate_criteria
from .input import DescriptiveStatisticsInput, DescriptiveStatisticsInvariantError
from .models import (
    BinarySummary,
    ComparisonAvailability,
    ContinuousSummary,
    CountSummary,
    DescriptiveStatisticsConfig,
    DescriptiveStatisticsResult,
    DescriptiveSummary,
    PopulationSummary,
    RawComparison,
    UnavailableSummary,
)
from .numeric import (
    NumericSummaryInvariantError,
    summarize_binary,
    summarize_continuous,
    summarize_count,
)


class DescriptiveStatisticsService:
    """Build typed raw summaries from eligibility-approved immutable analysis inputs."""

    def __init__(self, *, config: DescriptiveStatisticsConfig | None = None) -> None:
        self._config = config or DescriptiveStatisticsConfig()

    def summarize(self, analysis_input: DescriptiveStatisticsInput) -> DescriptiveStatisticsResult:
        """Return overall and arm-level summaries without estimating a treatment effect."""
        analysis_input.assert_data_eligible()
        context = analysis_input.context
        _assert_internal_invariants(context, analysis_input)
        populations = _extract_populations(context)
        metric_type = context.request.outcome.metric.metric_type
        overall = _population_summary(
            population_id=context.request.population.population_id,
            label=context.request.population.label,
            rows=populations.overall,
            metric_type=metric_type,
            config=self._config,
        )
        control = _population_summary(
            population_id=context.request.control.control_id,
            label=context.request.control.label,
            rows=populations.control,
            metric_type=metric_type,
            config=self._config,
        )
        treatment = _population_summary(
            population_id=context.request.treatment.treatment_id,
            label=context.request.treatment.label,
            rows=populations.treatment,
            metric_type=metric_type,
            config=self._config,
        )
        return DescriptiveStatisticsResult(
            outcome_id=context.request.outcome.metric.metric_id,
            outcome_label=context.request.outcome.metric.label,
            outcome_direction=context.request.outcome.direction,
            config=self._config,
            population=overall,
            treatment=treatment,
            control=control,
            raw_comparison=_raw_comparison(
                treatment=treatment.summary,
                control=control.summary,
                outcome_direction=context.request.outcome.direction,
            ),
        )


class _PopulationRows:
    """One exact assignment partition after eligibility selected the population."""

    def __init__(
        self,
        *,
        overall: tuple[tuple[object, object], ...],
        treatment: tuple[tuple[object, object], ...],
        control: tuple[tuple[object, object], ...],
    ) -> None:
        self.overall = overall
        self.treatment = treatment
        self.control = control


def _assert_internal_invariants(
    context: ValidationContext,
    analysis_input: DescriptiveStatisticsInput,
) -> None:
    summary = analysis_input.eligibility.unit_integrity_summary
    if summary.repeated_observation_count:
        raise DescriptiveStatisticsInvariantError(
            "validated input has unresolved repeated observation units"
        )
    if summary.assignment_conflict_count:
        raise DescriptiveStatisticsInvariantError("validated input has assignment conflicts")


def _extract_populations(context: ValidationContext) -> _PopulationRows:
    """Partition immutable rows by exact declared scalar assignments without coercion."""
    columns = {name: index for index, name in enumerate(context.table.columns)}
    try:
        treatment_index = columns[context.binding.treatment_column]
        unit_index = columns[context.binding.observation_unit_column]
        outcome_indexes = tuple(columns[column] for column in context.binding.outcome.columns)
    except KeyError as error:
        raise DescriptiveStatisticsInvariantError(
            "validated input is missing a bound column"
        ) from error

    overall: list[tuple[object, object]] = []
    treatment: list[tuple[object, object]] = []
    control: list[tuple[object, object]] = []
    for row in context.table.rows:
        if not evaluate_criteria(
            {column: row[index] for column, index in columns.items()},
            context.request.population.criteria,
        ):
            continue
        outcome = (
            row[outcome_indexes[0]]
            if len(outcome_indexes) == 1
            else tuple(row[index] for index in outcome_indexes)
        )
        item = (row[unit_index], outcome)
        assignment = row[treatment_index]
        if _typed_equal(assignment, context.request.treatment.assignment_value):
            treatment.append(item)
            overall.append(item)
        elif _typed_equal(assignment, context.request.control.assignment_value):
            control.append(item)
            overall.append(item)
        else:
            raise DescriptiveStatisticsInvariantError(
                "data-eligible input contains an assignment outside declared arms"
            )
    if not treatment or not control:
        raise DescriptiveStatisticsInvariantError("data-eligible input is missing a declared arm")
    return _PopulationRows(
        overall=tuple(overall), treatment=tuple(treatment), control=tuple(control)
    )


def _population_summary(
    *,
    population_id: str,
    label: str,
    rows: tuple[tuple[object, object], ...],
    metric_type: MetricType,
    config: DescriptiveStatisticsConfig,
) -> PopulationSummary:
    values: list[float] = []
    missing_count = 0
    valid_outcome_count = 0
    for _, value in rows:
        if _outcome_is_missing(value):
            missing_count += 1
            continue
        valid_outcome_count += 1
        if metric_type is not MetricType.RATIO:
            values.append(_finite_numeric_value(value))
    try:
        summary = _summarize_metric(metric_type, sorted(values), config)
    except NumericSummaryInvariantError as error:
        raise DescriptiveStatisticsInvariantError(str(error)) from error
    return PopulationSummary(
        population_id=population_id,
        label=label,
        row_count=len(rows),
        unique_unit_count=_distinct_unit_count(row[0] for row in rows),
        valid_outcome_count=valid_outcome_count,
        missing_outcome_count=missing_count,
        summary=summary,
    )


def _summarize_metric(
    metric_type: MetricType,
    values: Iterable[float],
    config: DescriptiveStatisticsConfig,
) -> DescriptiveSummary:
    if metric_type is MetricType.CONTINUOUS or metric_type is MetricType.RATE:
        return summarize_continuous(values, config)
    if metric_type in {MetricType.BINARY, MetricType.PROPORTION}:
        return summarize_binary(values, config)
    if metric_type is MetricType.COUNT:
        return summarize_count(values, config)
    if metric_type is MetricType.RATIO:
        return UnavailableSummary(reason="ratio aggregation semantics are not declared")
    raise DescriptiveStatisticsInvariantError("validated input has an unsupported metric type")


def _raw_comparison(
    *,
    treatment: DescriptiveSummary,
    control: DescriptiveSummary,
    outcome_direction: object,
) -> RawComparison:
    treatment_value = _comparison_value(treatment)
    control_value = _comparison_value(control)
    if treatment_value is None or control_value is None:
        return RawComparison(
            outcome_direction=outcome_direction,
            availability=ComparisonAvailability.UNAVAILABLE,
            unavailable_reason="raw comparison unavailable: one arm has no valid outcome summary",
        )
    absolute_difference = treatment_value - control_value
    if not math.isfinite(absolute_difference):
        raise DescriptiveStatisticsInvariantError("raw comparison is not finite")
    if control_value == 0.0:
        return RawComparison(
            outcome_direction=outcome_direction,
            availability=ComparisonAvailability.AVAILABLE,
            absolute_difference=absolute_difference,
            relative_difference_unavailable_reason=(
                "relative difference unavailable: control baseline is zero"
            ),
        )
    relative_difference = absolute_difference / control_value
    if not math.isfinite(relative_difference):
        raise DescriptiveStatisticsInvariantError("raw relative comparison is not finite")
    return RawComparison(
        outcome_direction=outcome_direction,
        availability=ComparisonAvailability.AVAILABLE,
        absolute_difference=absolute_difference,
        relative_difference=relative_difference,
    )


def _comparison_value(summary: DescriptiveSummary) -> float | None:
    if isinstance(summary, (ContinuousSummary, CountSummary)):
        return summary.mean
    if isinstance(summary, BinarySummary):
        return summary.rate
    return None


def _finite_numeric_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DescriptiveStatisticsInvariantError("outcome values must be finite real numbers")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise DescriptiveStatisticsInvariantError("outcome values must be finite real numbers")
    return normalized


def _outcome_is_missing(value: object) -> bool:
    if isinstance(value, tuple):
        return any(item is None for item in value)
    return value is None


def _typed_equal(actual: object, expected: object) -> bool:
    return type(actual) is type(expected) and actual == expected


def _distinct_unit_count(values: Iterable[object]) -> int:
    distinct: list[object] = []
    for value in values:
        if not any(_typed_equal(value, existing) for existing in distinct):
            distinct.append(value)
    return len(distinct)
