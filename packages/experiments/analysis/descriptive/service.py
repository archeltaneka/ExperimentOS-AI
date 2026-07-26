"""Orchestrate deterministic, non-causal descriptive population summaries."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from datetime import datetime
from time import perf_counter

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ..metrics import MetricType
from ..study_designs import CovariateTiming, QuasiExperimentalDesign, TimePeriod
from ..validation.context import ValidationContext
from ..validation.criteria import evaluate_criteria
from ..validation.table import AnalysisTable
from .diagnostics import distribution_diagnostics, small_arm_warning
from .input import DescriptiveStatisticsInput, DescriptiveStatisticsInvariantError
from .models import (
    BinarySummary,
    ComparisonAvailability,
    ContinuousSummary,
    CountSummary,
    CovariateSummary,
    DescriptiveStatisticsConfig,
    DescriptiveStatisticsResult,
    DescriptiveSummary,
    PeriodSummary,
    PopulationSummary,
    RawComparison,
    SegmentSummary,
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

    def __init__(
        self,
        *,
        config: DescriptiveStatisticsConfig | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self._config = config or DescriptiveStatisticsConfig()
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def summarize(self, analysis_input: DescriptiveStatisticsInput) -> DescriptiveStatisticsResult:
        """Return overall and arm-level summaries without estimating a treatment effect."""
        context = analysis_input.context
        started_at = perf_counter()
        span = _start_descriptive_span(
            self.observability_provider,
            row_count=len(context.table.rows),
            metric_type=context.request.outcome.metric.metric_type.value,
        )
        try:
            analysis_input.assert_data_eligible()
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
            covariates = _covariate_summaries(context, config=self._config)
            segments = _segment_summaries(context, config=self._config)
            periods = _period_summaries(context, config=self._config)
            result = DescriptiveStatisticsResult(
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
                covariates=covariates,
                segments=segments,
                periods=periods,
                diagnostics=distribution_diagnostics(
                    overall,
                    configured_missingness_limit=context.policy.maximum_outcome_missingness,
                ),
            )
        except Exception as error:
            _finish_descriptive_failure(
                self.observability_provider,
                span,
                error=error,
                duration_ms=(perf_counter() - started_at) * 1000.0,
            )
            raise

        _finish_descriptive_success(
            self.observability_provider,
            span,
            result=result,
            duration_ms=(perf_counter() - started_at) * 1000.0,
        )
        return result


def _start_descriptive_span(
    provider: BaseObservabilityProvider,
    *,
    row_count: int,
    metric_type: str,
) -> BufferedSpan | None:
    """Begin a root span with aggregate, non-sensitive calculation context only."""
    before_failures = _provider_failure_count(provider)
    try:
        return provider.start_root_span(
            "descriptive_statistics",
            inputs={"row_count": row_count},
            metadata={
                "metric_type": metric_type,
                "descriptive_statistics_started": True,
            },
        )
    except Exception:
        _increment_provider_failure(provider, before_failures)
        return None


def _finish_descriptive_success(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: DescriptiveStatisticsResult,
    duration_ms: float,
) -> None:
    """Record low-cardinality completion metadata without affecting the result."""
    if span is None:
        return
    _run_observability_operation(
        provider,
        lambda: span.add_metadata(
            {
                "status": "completed",
                "group_count": _group_count(result),
                "segment_count": len(result.segments),
                "warning_count": _warning_count(result),
                "unavailable_comparison_count": _unavailable_comparison_count(result),
                "duration_ms": duration_ms,
                "numeric_safety_failure": False,
                "descriptive_statistics_completed": True,
            }
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.finish(
            outputs={"status": "completed", "descriptive_statistics_completed": True}
        ),
    )


def _finish_descriptive_failure(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    error: Exception,
    duration_ms: float,
) -> None:
    """Safely report a logical failure without serializing source data or error text."""
    if span is None:
        return
    numeric_safety_failure = isinstance(error, DescriptiveStatisticsInvariantError)
    _run_observability_operation(
        provider,
        lambda: span.add_metadata(
            {
                "status": "failed",
                "duration_ms": duration_ms,
                "numeric_safety_failure": numeric_safety_failure,
                "descriptive_statistics_completed": False,
            }
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.record_error(
            "Descriptive statistics failed.",
            details={"type": error.__class__.__name__},
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.finish(
            outputs={"status": "failed", "descriptive_statistics_completed": False}
        ),
    )


def _group_count(result: DescriptiveStatisticsResult) -> int:
    return sum(
        population is not None
        for population in (result.population, result.treatment, result.control)
    )


def _warning_count(result: DescriptiveStatisticsResult) -> int:
    return len(result.diagnostics) + sum(len(segment.warnings) for segment in result.segments)


def _unavailable_comparison_count(result: DescriptiveStatisticsResult) -> int:
    comparisons = [result.raw_comparison]
    comparisons.extend(segment.raw_comparison for segment in result.segments)
    comparisons.extend(period.raw_comparison for period in result.periods)
    return sum(
        comparison is not None and comparison.availability is ComparisonAvailability.UNAVAILABLE
        for comparison in comparisons
    )


def _run_observability_operation(
    provider: BaseObservabilityProvider,
    operation: Callable[[], None],
) -> None:
    before_failures = _provider_failure_count(provider)
    try:
        operation()
    except Exception:
        _increment_provider_failure(provider, before_failures)


def _provider_failure_count(provider: BaseObservabilityProvider) -> int | None:
    try:
        return provider.failure_count
    except Exception:
        return None


def _increment_provider_failure(
    provider: BaseObservabilityProvider,
    before_failures: int | None,
) -> None:
    try:
        current_failures = provider.failure_count
    except Exception:
        current_failures = None
    try:
        if (
            before_failures is None
            or current_failures is None
            or current_failures == before_failures
        ):
            provider.increment_failure()
    except Exception:
        return


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
    if summary.repeated_observation_count and context.binding.timestamp_column is None:
        raise DescriptiveStatisticsInvariantError(
            "validated input has unresolved repeated observation units"
        )
    if summary.assignment_conflict_count:
        raise DescriptiveStatisticsInvariantError("validated input has assignment conflicts")


def _extract_populations(
    context: ValidationContext,
    *,
    criteria: tuple[object, ...] = (),
    require_declared_arms: bool = True,
) -> _PopulationRows:
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
            context.request.population.criteria + tuple(criteria),
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
    if require_declared_arms and (not treatment or not control):
        raise DescriptiveStatisticsInvariantError("data-eligible input is missing a declared arm")
    return _PopulationRows(
        overall=tuple(overall), treatment=tuple(treatment), control=tuple(control)
    )


def _extract_populations_for_column(
    context: ValidationContext,
    *,
    value_column: str,
    criteria: tuple[object, ...] = (),
) -> _PopulationRows:
    """Select a declared scalar role using population and optional segment criteria."""
    columns = {name: index for index, name in enumerate(context.table.columns)}
    try:
        treatment_index = columns[context.binding.treatment_column]
        unit_index = columns[context.binding.observation_unit_column]
        value_index = columns[value_column]
    except KeyError as error:
        raise DescriptiveStatisticsInvariantError(
            "validated input is missing a bound column"
        ) from error

    overall: list[tuple[object, object]] = []
    treatment: list[tuple[object, object]] = []
    control: list[tuple[object, object]] = []
    declared_criteria = context.request.population.criteria + tuple(criteria)
    for row in context.table.rows:
        values = {column: row[index] for column, index in columns.items()}
        if not evaluate_criteria(values, declared_criteria):
            continue
        item = (row[unit_index], row[value_index])
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


def _population_triplet(
    context: ValidationContext,
    populations: _PopulationRows,
    *,
    metric_type: MetricType,
    config: DescriptiveStatisticsConfig,
    prefix: str,
    label: str,
) -> tuple[PopulationSummary, PopulationSummary, PopulationSummary]:
    """Create deterministic overall, treatment, and control summaries for one role."""
    overall = _population_summary(
        population_id=f"{prefix}:population",
        label=label,
        rows=populations.overall,
        metric_type=metric_type,
        config=config,
    )
    treatment = _population_summary(
        population_id=f"{prefix}:{context.request.treatment.treatment_id}",
        label=context.request.treatment.label,
        rows=populations.treatment,
        metric_type=metric_type,
        config=config,
    )
    control = _population_summary(
        population_id=f"{prefix}:{context.request.control.control_id}",
        label=context.request.control.label,
        rows=populations.control,
        metric_type=metric_type,
        config=config,
    )
    return overall, treatment, control


def _covariate_summaries(
    context: ValidationContext,
    *,
    config: DescriptiveStatisticsConfig,
) -> tuple[CovariateSummary, ...]:
    """Summarize only declared pre-treatment scalar covariates in request order."""
    bindings = {binding.metric_id: binding.column for binding in context.binding.covariates}
    summaries: list[CovariateSummary] = []
    for covariate in context.request.covariates:
        if covariate.timing is not CovariateTiming.PRE_TREATMENT:
            continue
        column = bindings.get(covariate.metric.metric_id)
        if column is None:
            raise DescriptiveStatisticsInvariantError(
                "validated input is missing a covariate binding"
            )
        populations = _extract_populations_for_column(context, value_column=column)
        overall, treatment, control = _population_triplet(
            context,
            populations,
            metric_type=covariate.metric.metric_type,
            config=config,
            prefix=f"covariate:{covariate.metric.metric_id}",
            label=covariate.metric.label,
        )
        summaries.append(
            CovariateSummary(
                covariate_id=covariate.metric.metric_id,
                label=covariate.metric.label,
                population=overall,
                treatment=treatment,
                control=control,
            )
        )
    return tuple(summaries)


def _segment_summaries(
    context: ValidationContext,
    *,
    config: DescriptiveStatisticsConfig,
) -> tuple[SegmentSummary, ...]:
    """Summarize the one selected, validated segment without ranking or discovery."""
    segment = context.request.segment
    if segment is None:
        return ()
    populations = _extract_populations(
        context,
        criteria=segment.criteria,
        require_declared_arms=False,
    )
    overall, treatment, control = _population_triplet(
        context,
        populations,
        metric_type=context.request.outcome.metric.metric_type,
        config=config,
        prefix=f"segment:{segment.segment_id}",
        label=segment.label,
    )
    return (
        SegmentSummary(
            segment_id=segment.segment_id,
            label=segment.label,
            population=overall,
            treatment=treatment,
            control=control,
            raw_comparison=_raw_comparison(
                treatment=treatment.summary,
                control=control.summary,
                outcome_direction=context.request.outcome.direction,
            ),
            warnings=small_arm_warning(
                treatment,
                control,
                advisory_minimum=context.policy.weak_per_arm,
            ),
        ),
    )


def _period_summaries(
    context: ValidationContext,
    *,
    config: DescriptiveStatisticsConfig,
) -> tuple[PeriodSummary, ...]:
    """Summarize explicitly declared quasi-experimental periods without DiD."""
    design = context.request.study_design
    if not isinstance(design, QuasiExperimentalDesign):
        return ()
    return tuple(
        _period_summary(
            context,
            period_id=period_id,
            label=label,
            period=period,
            config=config,
        )
        for period_id, label, period in (
            ("pre", "Pre-treatment period", design.pre_treatment_period),
            ("post", "Post-treatment period", design.post_treatment_period),
        )
    )


def _period_summary(
    context: ValidationContext,
    *,
    period_id: str,
    label: str,
    period: TimePeriod,
    config: DescriptiveStatisticsConfig,
) -> PeriodSummary:
    timestamp_column = context.binding.timestamp_column
    if timestamp_column is None:
        raise DescriptiveStatisticsInvariantError(
            "validated quasi input is missing a timestamp binding"
        )
    columns = {name: index for index, name in enumerate(context.table.columns)}
    try:
        timestamp_index = columns[timestamp_column]
    except KeyError as error:
        raise DescriptiveStatisticsInvariantError(
            "validated quasi input is missing a timestamp column"
        ) from error
    selected_rows = tuple(
        row for row in context.table.rows if _timestamp_in_period(row[timestamp_index], period)
    )
    period_context = ValidationContext(
        request=context.request,
        table=AnalysisTable(columns=context.table.columns, rows=selected_rows),
        binding=context.binding,
        policy=context.policy,
    )
    populations = _extract_populations(period_context, require_declared_arms=False)
    overall, treatment, control = _population_triplet(
        context,
        populations,
        metric_type=context.request.outcome.metric.metric_type,
        config=config,
        prefix=f"period:{period_id}",
        label=label,
    )
    return PeriodSummary(
        period_id=period_id,
        label=label,
        population=overall,
        treatment=treatment,
        control=control,
        raw_comparison=_raw_comparison(
            treatment=treatment.summary,
            control=control.summary,
            outcome_direction=context.request.outcome.direction,
        ),
    )


def _timestamp_in_period(value: object, period: TimePeriod) -> bool:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        raise DescriptiveStatisticsInvariantError("validated input contains an invalid timestamp")
    return period.start <= timestamp < period.end


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (OverflowError, ValueError):
            return None
    else:
        return None
    return timestamp if timestamp.utcoffset() is not None else None


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
