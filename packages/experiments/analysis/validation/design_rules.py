"""Unit, covariate, time, and segment eligibility rules for immutable tables."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from ..populations import CriterionOperator, SelectionCriterion
from ..provenance import DiagnosticOutcome, DiagnosticSeverity
from ..study_designs import (
    ObservationalStudyDesign,
    QuasiExperimentalDesign,
    RandomizedExperimentDesign,
    TimePeriod,
)
from .context import ValidationContext
from .criteria import evaluate_criteria
from .data_rules import DataRuleResult
from .models import (
    DiagnosticDisposition,
    EligibilityDiagnostic,
    SegmentEligibilitySummary,
    TimeDesignSummary,
    UnitIntegritySummary,
    ValidationCategory,
)


@dataclass(frozen=True, slots=True)
class DesignRuleResult:
    """Design-level diagnostics and summaries derived without rewriting table data."""

    diagnostics: tuple[EligibilityDiagnostic, ...]
    unit_integrity_summary: UnitIntegritySummary
    time_summary: TimeDesignSummary | None
    segment_summary: SegmentEligibilitySummary | None


@dataclass(frozen=True, slots=True)
class _TimeEvidence:
    """Parsed timestamp evidence retained separately from the immutable source table."""

    by_row_index: dict[int, datetime]
    pre_period: TimePeriod | None
    post_period: TimePeriod | None


def validate_design(
    context: ValidationContext,
    data_result: DataRuleResult,
) -> DesignRuleResult:
    """Validate design-level relationships in deterministic rule-family order."""
    unit_diagnostics, unit_summary = _validate_units(context, data_result)
    time_diagnostics, time_summary, time_evidence = _validate_time(context, data_result)
    covariate_diagnostics = _validate_covariates(context, data_result, time_evidence)
    segment_diagnostics, segment_summary = _validate_segment(context, data_result)
    return DesignRuleResult(
        diagnostics=(
            unit_diagnostics
            + covariate_diagnostics
            + time_diagnostics
            + segment_diagnostics
        ),
        unit_integrity_summary=unit_summary,
        time_summary=time_summary,
        segment_summary=segment_summary,
    )


def _validate_segment(
    context: ValidationContext,
    data_result: DataRuleResult,
) -> tuple[tuple[EligibilityDiagnostic, ...], SegmentEligibilitySummary | None]:
    segment = context.request.segment
    if segment is None:
        return (), None
    empty_summary = SegmentEligibilitySummary(
        segment_id=segment.segment_id,
        selected_count=0,
        treatment_count=0,
        control_count=0,
        treatment_valid_outcome_count=0,
        control_valid_outcome_count=0,
    )
    if len(context.table.columns) != len(set(context.table.columns)):
        return (), empty_summary
    indexes = data_result.population_row_indexes
    if not indexes:
        return (), empty_summary

    attributes = tuple(dict.fromkeys(criterion.attribute for criterion in segment.criteria))
    missing_columns = tuple(
        attribute for attribute in attributes if attribute not in context.table.columns
    )
    if missing_columns:
        return (
            tuple(
                _blocking(
                    code="segment.column_missing",
                    category=ValidationCategory.SEGMENT,
                    message="A declared segment attribute is missing from the table.",
                    context={"attribute": attribute, "segment_id": segment.segment_id},
                )
                for attribute in missing_columns
            ),
            empty_summary,
        )

    column_indexes = {column: index for index, column in enumerate(context.table.columns)}
    diagnostics: list[EligibilityDiagnostic] = []
    missing_assignment_count = sum(
        any(
            context.table.rows[row_index][column_indexes[attribute]] is None
            for attribute in attributes
        )
        for row_index in indexes
    )
    if missing_assignment_count:
        diagnostics.append(
            _blocking(
                code="segment.missing_assignment",
                category=ValidationCategory.SEGMENT,
                message="Segment attributes must be present for selected population rows.",
                context={
                    "missing_count": missing_assignment_count,
                    "segment_id": segment.segment_id,
                },
            )
        )

    for attribute in attributes:
        cardinality = len(
            _exact_values(
                context.table.rows[row_index][column_indexes[attribute]]
                for row_index in indexes
                if context.table.rows[row_index][column_indexes[attribute]] is not None
            )
        )
        if cardinality > context.policy.maximum_segment_cardinality:
            diagnostics.append(
                _warning(
                    code="segment.high_cardinality",
                    category=ValidationCategory.SEGMENT,
                    message="A segment attribute exceeds the configured cardinality advisory.",
                    context={
                        "attribute": attribute,
                        "observed": cardinality,
                        "segment_id": segment.segment_id,
                        "threshold": context.policy.maximum_segment_cardinality,
                    },
                )
            )

    selected_indexes: list[int] = []
    incompatible_count = 0
    for row_index in indexes:
        row_values = {
            column: context.table.rows[row_index][index]
            for column, index in column_indexes.items()
        }
        if any(row_values[attribute] is None for attribute in attributes):
            continue
        if any(
            not _criterion_types_compatible(row_values[criterion.attribute], criterion)
            for criterion in segment.criteria
        ):
            incompatible_count += 1
            continue
        try:
            selected = evaluate_criteria(row_values, segment.criteria)
        except (TypeError, ValueError):
            incompatible_count += 1
            continue
        if selected:
            selected_indexes.append(row_index)
    if incompatible_count:
        diagnostics.append(
            _blocking(
                code="segment.criteria_incompatible",
                category=ValidationCategory.SEGMENT,
                message="Segment criteria cannot be compared with observed attribute values.",
                context={
                    "incompatible_count": incompatible_count,
                    "segment_id": segment.segment_id,
                },
            )
        )

    treatment_index = column_indexes.get(context.binding.treatment_column)
    treatment_rows: list[int] = []
    control_rows: list[int] = []
    if treatment_index is not None:
        for row_index in selected_indexes:
            value = context.table.rows[row_index][treatment_index]
            if _typed_equal(value, context.request.treatment.assignment_value):
                treatment_rows.append(row_index)
            elif _typed_equal(value, context.request.control.assignment_value):
                control_rows.append(row_index)
    valid_indexes = set(data_result.valid_row_indexes)
    treatment_valid_count = sum(index in valid_indexes for index in treatment_rows)
    control_valid_count = sum(index in valid_indexes for index in control_rows)
    summary = SegmentEligibilitySummary(
        segment_id=segment.segment_id,
        selected_count=len(selected_indexes),
        treatment_count=len(treatment_rows),
        control_count=len(control_rows),
        treatment_valid_outcome_count=treatment_valid_count,
        control_valid_outcome_count=control_valid_count,
    )
    if not selected_indexes:
        if not missing_assignment_count and not incompatible_count:
            diagnostics.append(
                _needs_more_data(
                    code="segment.value_absent",
                    category=ValidationCategory.SEGMENT,
                    message="The requested segment selects no population rows.",
                    context={"segment_id": segment.segment_id},
                )
            )
        return tuple(diagnostics), summary

    if not treatment_rows or not control_rows:
        diagnostics.append(
            _needs_more_data(
                code="segment.arm_missing",
                category=ValidationCategory.SEGMENT,
                message="The requested segment must contain both declared treatment arms.",
                context={
                    "control_missing": not control_rows,
                    "segment_id": segment.segment_id,
                    "treatment_missing": not treatment_rows,
                },
            )
        )
    elif min(treatment_valid_count, control_valid_count) < context.policy.minimum_per_segment_arm:
        diagnostics.append(
            _needs_more_data(
                code="segment.insufficient_sample",
                category=ValidationCategory.SEGMENT,
                message="A segment arm is below the operational valid-outcome minimum.",
                context={
                    "observed": min(treatment_valid_count, control_valid_count),
                    "segment_id": segment.segment_id,
                    "threshold": context.policy.minimum_per_segment_arm,
                },
            )
        )
    return tuple(diagnostics), summary


def _criterion_types_compatible(
    value: object,
    criterion: SelectionCriterion,
) -> bool:
    ordered_operators = {
        CriterionOperator.GREATER_THAN,
        CriterionOperator.GREATER_THAN_OR_EQUAL,
        CriterionOperator.LESS_THAN,
        CriterionOperator.LESS_THAN_OR_EQUAL,
    }
    if criterion.operator not in ordered_operators:
        return True
    expected = criterion.value
    return not isinstance(expected, tuple) and type(value) is type(expected)


def _validate_time(
    context: ValidationContext,
    data_result: DataRuleResult,
) -> tuple[
    tuple[EligibilityDiagnostic, ...],
    TimeDesignSummary | None,
    _TimeEvidence | None,
]:
    timestamp_column = context.binding.timestamp_column
    indexes = data_result.population_row_indexes
    if (
        timestamp_column is None
        or timestamp_column not in context.table.columns
        or not indexes
        or len(context.table.columns) != len(set(context.table.columns))
    ):
        return (), None, None

    timestamp_index = context.table.columns.index(timestamp_column)
    parsed: dict[int, datetime] = {}
    missing_count = 0
    invalid_count = 0
    for row_index in indexes:
        value = context.table.rows[row_index][timestamp_index]
        if value is None:
            missing_count += 1
            continue
        timestamp = _parse_timestamp(value)
        if timestamp is None:
            invalid_count += 1
            continue
        parsed[row_index] = timestamp

    diagnostics: list[EligibilityDiagnostic] = []
    if missing_count:
        diagnostics.append(
            _blocking(
                code="time.timestamp_missing",
                category=ValidationCategory.TIME,
                message="Bound observation timestamps must be present for selected rows.",
                context={"missing_count": missing_count},
            )
        )
    if invalid_count:
        diagnostics.append(
            _blocking(
                code="time.invalid_timestamp",
                category=ValidationCategory.TIME,
                message="Timestamps must be ISO 8601 values with an explicit timezone.",
                context={"invalid_count": invalid_count},
            )
        )

    pre_period, post_period = _declared_periods(context)
    pre_rows = {
        row_index
        for row_index, timestamp in parsed.items()
        if pre_period is not None and _in_period(timestamp, pre_period)
    }
    post_rows = {
        row_index
        for row_index, timestamp in parsed.items()
        if post_period is not None and _in_period(timestamp, post_period)
    }
    missing_pre, missing_post = _missing_period_units(
        context,
        indexes,
        pre_rows,
        post_rows,
        require_pre=pre_period is not None,
        require_post=post_period is not None,
    )
    if missing_pre or missing_post:
        diagnostics.append(
            _needs_more_data(
                code="time.period_coverage_missing",
                category=ValidationCategory.TIME,
                message="Units lack observations in one or more declared analysis periods.",
                context={
                    "missing_post_unit_count": missing_post,
                    "missing_pre_unit_count": missing_pre,
                },
            )
        )

    diagnostics.extend(_treatment_time_diagnostics(context, indexes))
    return (
        tuple(diagnostics),
        TimeDesignSummary(
            total_count=len(indexes),
            valid_count=len(parsed),
            missing_count=missing_count,
            invalid_count=invalid_count,
            pre_period_count=len(pre_rows),
            post_period_count=len(post_rows),
        ),
        _TimeEvidence(
            by_row_index=parsed,
            pre_period=pre_period,
            post_period=post_period,
        ),
    )


def _validate_covariates(
    context: ValidationContext,
    data_result: DataRuleResult,
    time_evidence: _TimeEvidence | None,
) -> tuple[EligibilityDiagnostic, ...]:
    indexes = data_result.population_row_indexes
    if not indexes or len(context.table.columns) != len(set(context.table.columns)):
        return ()
    binding_by_metric = {
        binding.metric_id: binding.column for binding in context.binding.covariates
    }
    diagnostics: list[EligibilityDiagnostic] = []
    for covariate in context.request.covariates:
        metric_id = covariate.metric.metric_id
        column = binding_by_metric.get(metric_id)
        if column is None:
            diagnostics.append(
                _blocking(
                    code="covariate.binding_missing",
                    category=ValidationCategory.COVARIATE,
                    message="A declared covariate has no physical column binding.",
                    context={"metric_id": metric_id},
                )
            )
            continue
        if column not in context.table.columns:
            continue
        covariate_index = context.table.columns.index(column)
        missing_count = sum(
            context.table.rows[row_index][covariate_index] is None for row_index in indexes
        )
        if missing_count:
            diagnostics.append(
                _blocking(
                    code="covariate.missing",
                    category=ValidationCategory.COVARIATE,
                    message="A declared covariate has missing values in selected rows.",
                    context={"metric_id": metric_id, "missing_count": missing_count},
                )
            )
        unavailable_count = _covariate_period_unavailable_count(
            context,
            indexes,
            covariate_index,
            covariate.measurement_period,
            time_evidence,
        )
        if unavailable_count:
            diagnostics.append(
                _blocking(
                    code="covariate.period_unavailable",
                    category=ValidationCategory.COVARIATE,
                    message="Covariate values are unavailable in the declared measurement period.",
                    context={
                        "metric_id": metric_id,
                        "unavailable_unit_count": unavailable_count,
                    },
                )
            )
    return tuple(diagnostics)


def _covariate_period_unavailable_count(
    context: ValidationContext,
    indexes: tuple[int, ...],
    covariate_index: int,
    period: TimePeriod,
    time_evidence: _TimeEvidence | None,
) -> int:
    observation_column = context.binding.observation_unit_column
    if observation_column not in context.table.columns:
        return 0
    observation_index = context.table.columns.index(observation_column)
    groups = _exact_groups(
        tuple(
            (row_index, context.table.rows[row_index][observation_index])
            for row_index in indexes
        )
    )
    if time_evidence is None:
        return len(groups)
    return sum(
        not any(
            context.table.rows[row_index][covariate_index] is not None
            and row_index in time_evidence.by_row_index
            and _in_period(time_evidence.by_row_index[row_index], period)
            for row_index in row_indexes
        )
        for _, row_indexes in groups
    )


def _declared_periods(
    context: ValidationContext,
) -> tuple[TimePeriod | None, TimePeriod | None]:
    design = context.request.study_design
    if isinstance(design, QuasiExperimentalDesign):
        return design.pre_treatment_period, design.post_treatment_period
    if isinstance(design, RandomizedExperimentDesign):
        return None, design.experiment_period
    if isinstance(design, ObservationalStudyDesign):
        return None, design.observation_period
    return None, None


def _missing_period_units(
    context: ValidationContext,
    indexes: tuple[int, ...],
    pre_rows: set[int],
    post_rows: set[int],
    *,
    require_pre: bool,
    require_post: bool,
) -> tuple[int, int]:
    observation_column = context.binding.observation_unit_column
    if observation_column not in context.table.columns:
        return 0, 0
    observation_index = context.table.columns.index(observation_column)
    groups = _exact_groups(
        tuple(
            (row_index, context.table.rows[row_index][observation_index])
            for row_index in indexes
        )
    )
    missing_pre = sum(
        require_pre and not any(row_index in pre_rows for row_index in row_indexes)
        for _, row_indexes in groups
    )
    missing_post = sum(
        require_post and not any(row_index in post_rows for row_index in row_indexes)
        for _, row_indexes in groups
    )
    return missing_pre, missing_post


def _treatment_time_diagnostics(
    context: ValidationContext,
    indexes: tuple[int, ...],
) -> tuple[EligibilityDiagnostic, ...]:
    treatment_time_column = context.binding.treatment_timestamp_column
    observation_column = context.binding.observation_unit_column
    if (
        treatment_time_column is None
        or treatment_time_column not in context.table.columns
        or observation_column not in context.table.columns
    ):
        return ()
    treatment_time_index = context.table.columns.index(treatment_time_column)
    observation_index = context.table.columns.index(observation_column)
    invalid_count = 0
    parsed: dict[int, datetime] = {}
    for row_index in indexes:
        value = context.table.rows[row_index][treatment_time_index]
        if value is None:
            continue
        timestamp = _parse_timestamp(value)
        if timestamp is None:
            invalid_count += 1
        else:
            parsed[row_index] = timestamp
    diagnostics: list[EligibilityDiagnostic] = []
    if invalid_count:
        diagnostics.append(
            _blocking(
                code="time.invalid_treatment_timestamp",
                category=ValidationCategory.TIME,
                message="Treatment timestamps must be timezone-aware ISO 8601 values.",
                context={"invalid_count": invalid_count},
            )
        )
    observation_groups = _exact_groups(
        tuple(
            (row_index, context.table.rows[row_index][observation_index])
            for row_index in indexes
        )
    )
    inconsistent_count = sum(
        len(_exact_values(parsed[index] for index in row_indexes if index in parsed)) > 1
        for _, row_indexes in observation_groups
    )
    if inconsistent_count:
        diagnostics.append(
            _blocking(
                code="treatment.timing_inconsistent",
                category=ValidationCategory.TREATMENT,
                message="An observation unit has inconsistent supplied treatment timestamps.",
                context={"inconsistent_unit_count": inconsistent_count},
            )
        )
    return tuple(diagnostics)


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            return None
    else:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed


def _in_period(timestamp: datetime, period: TimePeriod) -> bool:
    return period.start <= timestamp < period.end


def _validate_units(
    context: ValidationContext,
    data_result: DataRuleResult,
) -> tuple[tuple[EligibilityDiagnostic, ...], UnitIntegritySummary]:
    binding = context.binding
    indexes = data_result.population_row_indexes
    empty = UnitIntegritySummary(
        observation_unit_count=0,
        missing_identifier_count=0,
        duplicate_identifier_count=0,
        repeated_observation_count=0,
        assignment_conflict_count=0,
        cluster_count=None,
    )
    if not indexes or len(context.table.columns) != len(set(context.table.columns)):
        return (), empty
    if binding.observation_unit_column not in context.table.columns:
        return (), empty

    column_indexes = {column: index for index, column in enumerate(context.table.columns)}
    observation_index = column_indexes[binding.observation_unit_column]
    treatment_index = column_indexes.get(binding.treatment_column)
    observations = tuple(
        (row_index, context.table.rows[row_index][observation_index])
        for row_index in indexes
    )
    missing_identifier_count = sum(value is None for _, value in observations)
    observation_groups = _exact_groups(observations)
    duplicate_groups = tuple(group for group in observation_groups if len(group[1]) > 1)
    duplicate_identifier_count = len(duplicate_groups)
    repeated_observation_count = sum(len(row_indexes) - 1 for _, row_indexes in duplicate_groups)

    diagnostics: list[EligibilityDiagnostic] = []
    if missing_identifier_count:
        diagnostics.append(
            _blocking(
                code="unit.identifier_missing",
                category=ValidationCategory.UNIT,
                message="Observation-unit identifiers must be present for selected rows.",
                context={"missing_count": missing_identifier_count},
            )
        )
    if duplicate_identifier_count and binding.timestamp_column is None:
        diagnostics.append(
            _blocking(
                code="unit.duplicate_observation",
                category=ValidationCategory.UNIT,
                message="Single-row observation units must not have duplicate identifiers.",
                context={"duplicate_identifier_count": duplicate_identifier_count},
            )
        )
    if (
        repeated_observation_count
        and binding.timestamp_column is not None
        and context.request.clustering.kind == "none"
    ):
        diagnostics.append(
            _blocking(
                code="unit.repeated_without_clustering",
                category=ValidationCategory.UNIT,
                message="Repeated observations require an explicit clustering declaration.",
                context={"repeated_observation_count": repeated_observation_count},
            )
        )

    switching_count = 0
    if treatment_index is not None:
        switching_count = sum(
            len(_recognized_assignments(context, row_indexes, treatment_index)) > 1
            for _, row_indexes in duplicate_groups
        )
        if switching_count:
            diagnostics.append(
                _blocking(
                    code="treatment.switching",
                    category=ValidationCategory.TREATMENT,
                    message="An observation unit has conflicting declared arm assignments.",
                    context={"switching_unit_count": switching_count},
                )
            )

    randomization_conflict_count, mapping_conflict_count = _randomization_checks(
        context,
        indexes,
        observation_groups,
        column_indexes,
        treatment_index,
        diagnostics,
    )
    cluster_count = _cluster_checks(context, indexes, column_indexes, diagnostics)
    return (
        tuple(diagnostics),
        UnitIntegritySummary(
            observation_unit_count=len(observation_groups),
            missing_identifier_count=missing_identifier_count,
            duplicate_identifier_count=duplicate_identifier_count,
            repeated_observation_count=repeated_observation_count,
            assignment_conflict_count=(
                switching_count + randomization_conflict_count + mapping_conflict_count
            ),
            cluster_count=cluster_count,
        ),
    )


def _randomization_checks(
    context: ValidationContext,
    indexes: tuple[int, ...],
    observation_groups: tuple[tuple[object, tuple[int, ...]], ...],
    column_indexes: dict[str, int],
    treatment_index: int | None,
    diagnostics: list[EligibilityDiagnostic],
) -> tuple[int, int]:
    randomization_column = context.binding.randomization_unit_column
    if randomization_column is None or randomization_column not in column_indexes:
        return 0, 0
    randomization_index = column_indexes[randomization_column]
    values = tuple(
        (row_index, context.table.rows[row_index][randomization_index]) for row_index in indexes
    )
    missing_count = sum(value is None for _, value in values)
    if missing_count:
        diagnostics.append(
            _blocking(
                code="unit.randomization_identifier_missing",
                category=ValidationCategory.UNIT,
                message="Randomization-unit identifiers must be present for selected rows.",
                context={"missing_count": missing_count},
            )
        )

    randomization_groups = _exact_groups(values)
    conflict_count = 0
    if treatment_index is not None:
        conflict_count = sum(
            len(_recognized_assignments(context, row_indexes, treatment_index)) > 1
            for _, row_indexes in randomization_groups
        )
    if conflict_count:
        diagnostics.append(
            _blocking(
                code="treatment.unit_multiple_assignments",
                category=ValidationCategory.TREATMENT,
                message="A randomization unit appears in more than one declared arm.",
                context={"conflicting_unit_count": conflict_count},
            )
        )

    mapping_conflict_count = sum(
        len(
            _exact_values(
                context.table.rows[row_index][randomization_index]
                for row_index in row_indexes
                if context.table.rows[row_index][randomization_index] is not None
            )
        )
        > 1
        for _, row_indexes in observation_groups
    )
    if mapping_conflict_count:
        diagnostics.append(
            _blocking(
                code="unit.randomization_observation_mismatch",
                category=ValidationCategory.UNIT,
                message="An observation unit maps to multiple randomization units.",
                context={"conflicting_observation_count": mapping_conflict_count},
            )
        )
    return conflict_count, mapping_conflict_count


def _cluster_checks(
    context: ValidationContext,
    indexes: tuple[int, ...],
    column_indexes: dict[str, int],
    diagnostics: list[EligibilityDiagnostic],
) -> int | None:
    if context.request.clustering.kind != "clustered":
        return None
    cluster_column = context.binding.clustering_unit_column
    if cluster_column is None or cluster_column not in column_indexes:
        return None
    cluster_index = column_indexes[cluster_column]
    values = tuple(context.table.rows[row_index][cluster_index] for row_index in indexes)
    missing_count = sum(value is None for value in values)
    if missing_count:
        diagnostics.append(
            _blocking(
                code="unit.cluster_identifier_missing",
                category=ValidationCategory.UNIT,
                message="Cluster identifiers must be present for selected rows.",
                context={"missing_count": missing_count},
            )
        )
    cluster_count = len(_exact_values(value for value in values if value is not None))
    if cluster_count < context.policy.minimum_clusters:
        diagnostics.append(
            _needs_more_data(
                code="sample.cluster_insufficient",
                category=ValidationCategory.SAMPLE,
                message="The observed cluster count is below the operational minimum.",
                context={
                    "observed": cluster_count,
                    "threshold": context.policy.minimum_clusters,
                },
            )
        )
    elif cluster_count < context.policy.weak_clusters:
        diagnostics.append(
            _warning(
                code="sample.cluster_weak",
                category=ValidationCategory.SAMPLE,
                message="The observed cluster count is below the advisory threshold.",
                context={
                    "observed": cluster_count,
                    "threshold": context.policy.weak_clusters,
                },
            )
        )
    return cluster_count


def _recognized_assignments(
    context: ValidationContext,
    row_indexes: tuple[int, ...],
    treatment_index: int,
) -> tuple[object, ...]:
    declared = (
        context.request.treatment.assignment_value,
        context.request.control.assignment_value,
    )
    return _exact_values(
        value
        for row_index in row_indexes
        for value in (context.table.rows[row_index][treatment_index],)
        if any(_typed_equal(value, candidate) for candidate in declared)
    )


def _exact_groups(
    indexed_values: tuple[tuple[int, object], ...],
) -> tuple[tuple[object, tuple[int, ...]], ...]:
    groups: list[tuple[object, list[int]]] = []
    for row_index, value in indexed_values:
        if value is None:
            continue
        for candidate, candidate_indexes in groups:
            if _typed_equal(value, candidate):
                candidate_indexes.append(row_index)
                break
        else:
            groups.append((value, [row_index]))
    return tuple((value, tuple(row_indexes)) for value, row_indexes in groups)


def _exact_values(values: Iterable[object]) -> tuple[object, ...]:
    unique: list[object] = []
    for value in values:
        if not any(_typed_equal(value, candidate) for candidate in unique):
            unique.append(value)
    return tuple(unique)


def _typed_equal(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


def _blocking(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
) -> EligibilityDiagnostic:
    return _diagnostic(
        code=code,
        category=category,
        message=message,
        context=context,
        severity=DiagnosticSeverity.ERROR,
        outcome=DiagnosticOutcome.FAILED,
        disposition=DiagnosticDisposition.BLOCKING,
    )


def _warning(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
) -> EligibilityDiagnostic:
    return _diagnostic(
        code=code,
        category=category,
        message=message,
        context=context,
        severity=DiagnosticSeverity.WARNING,
        outcome=DiagnosticOutcome.FAILED,
        disposition=DiagnosticDisposition.WARNING,
    )


def _needs_more_data(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
) -> EligibilityDiagnostic:
    return _diagnostic(
        code=code,
        category=category,
        message=message,
        context=context,
        severity=DiagnosticSeverity.WARNING,
        outcome=DiagnosticOutcome.UNAVAILABLE,
        disposition=DiagnosticDisposition.NEEDS_MORE_DATA,
    )


def _diagnostic(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
    severity: DiagnosticSeverity,
    outcome: DiagnosticOutcome,
    disposition: DiagnosticDisposition,
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": code,
            "category": category,
            "severity": severity,
            "outcome": outcome,
            "disposition": disposition,
            "message": message,
            "context": context,
        }
    )
