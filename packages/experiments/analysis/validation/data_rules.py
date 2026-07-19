"""Schema, population, treatment, outcome, missingness, and sample data rules."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from fractions import Fraction
from typing import TypeGuard

from ..metrics import MetricType
from ..provenance import DiagnosticOutcome, DiagnosticSeverity
from ..study_designs import RandomizedExperimentDesign
from .context import ValidationContext
from .criteria import evaluate_criteria
from .models import (
    DatasetSummary,
    DiagnosticDisposition,
    EligibilityDiagnostic,
    MissingnessSummary,
    OutcomeSummary,
    TreatmentSummary,
    ValidationCategory,
)


@dataclass(frozen=True, slots=True)
class ObservedAllocation:
    """Observed exact assignment rates within the selected population."""

    assigned_count: int
    treatment_rate: float | None
    control_rate: float | None


@dataclass(frozen=True, slots=True)
class DataRuleResult:
    """Immutable validation evidence plus derived row indexes, never a rewritten table."""

    diagnostics: tuple[EligibilityDiagnostic, ...]
    dataset_summary: DatasetSummary
    treatment_summary: TreatmentSummary
    outcome_summary: OutcomeSummary
    missingness_summary: tuple[MissingnessSummary, ...]
    observed_allocation: ObservedAllocation
    population_row_indexes: tuple[int, ...]
    valid_row_indexes: tuple[int, ...]


def validate_data(context: ValidationContext) -> DataRuleResult:
    """Validate immutable table data in deterministic rule-family order."""
    table = context.table
    duplicate_columns = _duplicates(table.columns)
    if duplicate_columns:
        schema_diagnostics = tuple(
            _blocking(
                code="schema.duplicate_column",
                category=ValidationCategory.SCHEMA,
                message="Table column names must be unique before analytical indexing.",
                context={"column": column},
            )
            for column in duplicate_columns
        )
        return _empty_result(context, schema_diagnostics)

    if not table.rows:
        return _empty_result(
            context,
            (
                _blocking(
                    code="schema.empty_dataset",
                    category=ValidationCategory.SCHEMA,
                    message="Analysis data must contain at least one row.",
                    context={"row_count": 0},
                ),
            ),
        )

    required_columns = _required_columns(context)
    missing_columns = tuple(column for column in required_columns if column not in table.columns)
    if missing_columns:
        schema_diagnostics = tuple(
            _blocking(
                code="schema.required_column_missing",
                category=ValidationCategory.SCHEMA,
                message="A column required by the analysis request or binding is missing.",
                context={"column": column},
            )
            for column in missing_columns
        )
        return _empty_result(context, schema_diagnostics)

    column_indexes = {column: index for index, column in enumerate(table.columns)}
    population_row_indexes = tuple(
        row_index
        for row_index, row in enumerate(table.rows)
        if evaluate_criteria(
            {column: row[index] for column, index in column_indexes.items()},
            context.request.population.criteria,
        )
    )
    dataset_summary = DatasetSummary(
        input_row_count=len(table.rows),
        population_row_count=len(population_row_indexes),
        column_count=len(table.columns),
    )

    if context.request.population.criteria and not population_row_indexes:
        return DataRuleResult(
            diagnostics=(
                _blocking(
                    code="population.empty",
                    category=ValidationCategory.POPULATION,
                    message="The explicitly selected analysis population contains no rows.",
                    context={"input_row_count": len(table.rows)},
                ),
            ),
            dataset_summary=dataset_summary,
            treatment_summary=_empty_treatment_summary(),
            outcome_summary=_empty_outcome_summary(),
            missingness_summary=(),
            observed_allocation=ObservedAllocation(
                assigned_count=0,
                treatment_rate=None,
                control_rate=None,
            ),
            population_row_indexes=(),
            valid_row_indexes=(),
        )

    treatment_index = column_indexes[context.binding.treatment_column]
    treatment_value = context.request.treatment.assignment_value
    control_value = context.request.control.assignment_value
    treatment_count = 0
    control_count = 0
    missing_count = 0
    unknown_count = 0
    treatment_row_indexes: list[int] = []
    control_row_indexes: list[int] = []
    for row_index in population_row_indexes:
        assignment = table.rows[row_index][treatment_index]
        if assignment is None:
            missing_count += 1
        elif _typed_equal(assignment, treatment_value):
            treatment_count += 1
            treatment_row_indexes.append(row_index)
        elif _typed_equal(assignment, control_value):
            control_count += 1
            control_row_indexes.append(row_index)
        else:
            unknown_count += 1

    treatment_summary = TreatmentSummary(
        treatment_count=treatment_count,
        control_count=control_count,
        missing_count=missing_count,
        unknown_count=unknown_count,
    )
    diagnostics: list[EligibilityDiagnostic] = []
    if missing_count:
        diagnostics.append(
            _blocking(
                code="treatment.assignment_missing",
                category=ValidationCategory.TREATMENT,
                message="Treatment assignment is missing for selected population rows.",
                context={"missing_count": missing_count},
            )
        )
    if unknown_count:
        diagnostics.append(
            _blocking(
                code="treatment.unexpected_value",
                category=ValidationCategory.TREATMENT,
                message="Treatment assignment contains values outside the declared arms.",
                context={"unknown_count": unknown_count},
            )
        )
    if treatment_count == 0 or control_count == 0:
        diagnostics.append(
            _blocking(
                code="treatment.arm_missing",
                category=ValidationCategory.TREATMENT,
                message="Both declared treatment and control arms must contain rows.",
                context={
                    "control_missing": control_count == 0,
                    "treatment_missing": treatment_count == 0,
                },
            )
        )

    assigned_count = treatment_count + control_count
    observed_allocation = ObservedAllocation(
        assigned_count=assigned_count,
        treatment_rate=treatment_count / assigned_count if assigned_count else None,
        control_rate=control_count / assigned_count if assigned_count else None,
    )
    outcome_diagnostics, outcome_summary, valid_row_indexes = _validate_outcome(
        context,
        column_indexes,
        population_row_indexes,
        tuple(treatment_row_indexes),
        tuple(control_row_indexes),
    )
    diagnostics.extend(outcome_diagnostics)
    missingness_summary, missingness_diagnostics = _summarize_missingness(
        context,
        column_indexes,
        population_row_indexes,
        tuple(treatment_row_indexes),
        tuple(control_row_indexes),
        outcome_summary,
    )
    diagnostics.extend(missingness_diagnostics)
    diagnostics.extend(_sample_diagnostics(context, outcome_summary))
    diagnostics.extend(_allocation_diagnostics(context, observed_allocation))
    return DataRuleResult(
        diagnostics=tuple(diagnostics),
        dataset_summary=dataset_summary,
        treatment_summary=treatment_summary,
        outcome_summary=outcome_summary,
        missingness_summary=missingness_summary,
        observed_allocation=observed_allocation,
        population_row_indexes=population_row_indexes,
        valid_row_indexes=valid_row_indexes,
    )


def _validate_outcome(
    context: ValidationContext,
    column_indexes: dict[str, int],
    population_row_indexes: tuple[int, ...],
    treatment_row_indexes: tuple[int, ...],
    control_row_indexes: tuple[int, ...],
) -> tuple[tuple[EligibilityDiagnostic, ...], OutcomeSummary, tuple[int, ...]]:
    binding = context.binding.outcome
    metric_type = context.request.outcome.metric.metric_type
    outcome_column_indexes = tuple(column_indexes[column] for column in binding.columns)
    treatment_rows = set(treatment_row_indexes)
    control_rows = set(control_row_indexes)

    missing_count = 0
    invalid_type_count = 0
    non_finite_count = 0
    invalid_binary_count = 0
    negative_count = 0
    bounds_invalid_count = 0
    denominator_zero_count = 0
    denominator_invalid_sign_count = 0
    valid_outcome_indexes: list[int] = []
    valid_row_indexes: list[int] = []
    valid_values: list[int | float | Fraction] = []

    for row_index in population_row_indexes:
        raw_values = tuple(context.table.rows[row_index][index] for index in outcome_column_indexes)
        if any(value is None for value in raw_values):
            missing_count += 1
            continue
        numeric_values: list[int | float] = []
        if any(not _append_numeric(numeric_values, value) for value in raw_values):
            invalid_type_count += 1
            continue
        if any(not _is_finite(value) for value in numeric_values):
            non_finite_count += 1
            continue

        value: int | float | Fraction = numeric_values[0]
        if len(numeric_values) == 2:
            denominator = numeric_values[1]
            if denominator == 0:
                denominator_zero_count += 1
                continue
            if denominator < 0:
                denominator_invalid_sign_count += 1
                continue
            value = Fraction(numeric_values[0]) / Fraction(denominator)
            if abs(value) > sys.float_info.max:
                non_finite_count += 1
                continue

        if metric_type is MetricType.BINARY and value not in {0, 1}:
            invalid_binary_count += 1
            continue
        if (metric_type is MetricType.COUNT or not binding.allow_negative) and value < 0:
            negative_count += 1
            continue

        lower_bound = binding.lower_bound
        upper_bound = binding.upper_bound
        if metric_type is MetricType.PROPORTION:
            lower_bound = 0.0 if lower_bound is None else lower_bound
            upper_bound = 1.0 if upper_bound is None else upper_bound
        if (lower_bound is not None and value < lower_bound) or (
            upper_bound is not None and value > upper_bound
        ):
            bounds_invalid_count += 1
            continue

        valid_outcome_indexes.append(row_index)
        if row_index in treatment_rows or row_index in control_rows:
            valid_row_indexes.append(row_index)
            valid_values.append(value)

    treatment_valid_count = sum(index in treatment_rows for index in valid_row_indexes)
    control_valid_count = sum(index in control_rows for index in valid_row_indexes)
    has_variation = None if not valid_values else len(set(valid_values)) > 1
    invalid_value_count = (
        invalid_binary_count
        + negative_count
        + bounds_invalid_count
        + denominator_zero_count
        + denominator_invalid_sign_count
    )
    summary = OutcomeSummary(
        valid_count=len(valid_outcome_indexes),
        missing_count=missing_count,
        invalid_type_count=invalid_type_count,
        non_finite_count=non_finite_count,
        invalid_value_count=invalid_value_count,
        treatment_valid_count=treatment_valid_count,
        control_valid_count=control_valid_count,
        has_variation=has_variation,
    )

    diagnostics: list[EligibilityDiagnostic] = []
    if invalid_type_count:
        diagnostics.append(
            _blocking(
                code="schema.outcome_not_numeric",
                category=ValidationCategory.SCHEMA,
                message="Outcome values must be numeric without coercion.",
                context={"invalid_type_count": invalid_type_count},
            )
        )
    if non_finite_count:
        diagnostics.append(
            _blocking(
                code="outcome.non_finite",
                category=ValidationCategory.OUTCOME,
                message="Outcome values must be finite.",
                context={"non_finite_count": non_finite_count},
            )
        )
    if invalid_binary_count:
        diagnostics.append(
            _blocking(
                code="outcome.invalid_binary",
                category=ValidationCategory.OUTCOME,
                message="Binary outcomes must contain only numeric zero and one values.",
                context={"invalid_value_count": invalid_binary_count},
            )
        )
    if negative_count:
        diagnostics.append(
            _blocking(
                code="outcome.negative",
                category=ValidationCategory.OUTCOME,
                message="The declared outcome does not permit negative values.",
                context={"negative_count": negative_count},
            )
        )
    if bounds_invalid_count:
        diagnostics.append(
            _blocking(
                code="outcome.out_of_bounds",
                category=ValidationCategory.OUTCOME,
                message="Outcome values fall outside the explicitly valid bounds.",
                context={"invalid_value_count": bounds_invalid_count},
            )
        )
    if denominator_zero_count:
        diagnostics.append(
            _blocking(
                code="outcome.denominator_zero",
                category=ValidationCategory.OUTCOME,
                message="Ratio outcome denominators must be non-zero.",
                context={"zero_count": denominator_zero_count},
            )
        )
    if denominator_invalid_sign_count:
        diagnostics.append(
            _blocking(
                code="outcome.denominator_invalid_sign",
                category=ValidationCategory.OUTCOME,
                message="Ratio outcome denominators must be positive.",
                context={"invalid_sign_count": denominator_invalid_sign_count},
            )
        )
    if has_variation is False:
        diagnostics.append(
            _blocking(
                code="outcome.zero_variance",
                category=ValidationCategory.OUTCOME,
                message="Valid outcome values must contain observed variation.",
                context={"valid_count": len(valid_values)},
            )
        )
    return tuple(diagnostics), summary, tuple(valid_row_indexes)


def _summarize_missingness(
    context: ValidationContext,
    column_indexes: dict[str, int],
    population_row_indexes: tuple[int, ...],
    treatment_row_indexes: tuple[int, ...],
    control_row_indexes: tuple[int, ...],
    outcome_summary: OutcomeSummary,
) -> tuple[tuple[MissingnessSummary, ...], tuple[EligibilityDiagnostic, ...]]:
    total_count = len(population_row_indexes)
    treatment_rows = set(treatment_row_indexes)
    control_rows = set(control_row_indexes)
    summaries: list[MissingnessSummary] = []
    diagnostics: list[EligibilityDiagnostic] = []

    for role, column in _role_columns(context):
        column_index = column_indexes[column]
        missing_rows = {
            row_index
            for row_index in population_row_indexes
            if context.table.rows[row_index][column_index] is None
        }
        treatment_missing_rate = _rate(len(missing_rows & treatment_rows), len(treatment_rows))
        control_missing_rate = _rate(len(missing_rows & control_rows), len(control_rows))
        differential = (
            abs(treatment_missing_rate - control_missing_rate)
            if treatment_missing_rate is not None and control_missing_rate is not None
            else None
        )
        summaries.append(
            MissingnessSummary(
                role=role,
                column=column,
                total_count=total_count,
                missing_count=len(missing_rows),
                missing_rate=len(missing_rows) / total_count,
                treatment_missing_rate=treatment_missing_rate,
                control_missing_rate=control_missing_rate,
                differential_missingness=differential,
            )
        )

        threshold = context.policy.maximum_differential_missingness
        if threshold is not None and differential is not None and differential > threshold:
            diagnostics.append(
                _warning(
                    code="missingness.differential",
                    category=ValidationCategory.MISSINGNESS,
                    message="Arm-level missingness differs by more than the configured threshold.",
                    context={
                        "column": column,
                        "differential": differential,
                        "threshold": threshold,
                    },
                )
            )

    outcome_threshold = context.policy.maximum_outcome_missingness
    outcome_missing_rate = outcome_summary.missing_count / total_count
    if outcome_threshold is not None and outcome_missing_rate > outcome_threshold:
        diagnostics.append(
            _blocking(
                code="missingness.outcome_exceeds_threshold",
                category=ValidationCategory.MISSINGNESS,
                message="Outcome missingness exceeds the configured maximum.",
                context={
                    "missing_rate": outcome_missing_rate,
                    "threshold": outcome_threshold,
                },
            )
        )
    return tuple(summaries), tuple(diagnostics)


def _role_columns(context: ValidationContext) -> tuple[tuple[str, str], ...]:
    binding = context.binding
    outcome_roles = (
        (("outcome", binding.outcome.value_column),)
        if binding.outcome.value_column is not None
        else (
            ("outcome_numerator", binding.outcome.numerator_column),
            ("outcome_denominator", binding.outcome.denominator_column),
        )
    )
    segment_attributes = (
        tuple(dict.fromkeys(criterion.attribute for criterion in context.request.segment.criteria))
        if context.request.segment is not None
        else ()
    )
    candidates = (
        ("treatment", binding.treatment_column),
        *outcome_roles,
        ("observation_unit", binding.observation_unit_column),
        ("randomization_unit", binding.randomization_unit_column),
        ("clustering_unit", binding.clustering_unit_column),
        ("timestamp", binding.timestamp_column),
        *((f"covariate:{item.metric_id}", item.column) for item in binding.covariates),
        ("treatment_timestamp", binding.treatment_timestamp_column),
        *((f"segment:{attribute}", attribute) for attribute in segment_attributes),
    )
    available_columns = set(context.table.columns)
    return tuple(
        (role, column)
        for role, column in candidates
        if column is not None and column in available_columns
    )


def _sample_diagnostics(
    context: ValidationContext,
    outcome_summary: OutcomeSummary,
) -> tuple[EligibilityDiagnostic, ...]:
    treatment_count = outcome_summary.treatment_valid_count
    control_count = outcome_summary.control_valid_count
    total_count = treatment_count + control_count
    policy = context.policy
    diagnostics: list[EligibilityDiagnostic] = []

    if total_count < policy.minimum_total:
        diagnostics.append(
            _needs_more_data(
                code="sample.total_insufficient",
                category=ValidationCategory.SAMPLE,
                message="The usable sample is below the configured minimum total.",
                context={"observed": total_count, "threshold": policy.minimum_total},
            )
        )
    elif total_count < policy.weak_total:
        diagnostics.append(
            _warning(
                code="sample.total_weak",
                category=ValidationCategory.SAMPLE,
                message="The usable sample is below the configured advisory total.",
                context={"observed": total_count, "threshold": policy.weak_total},
            )
        )

    weakest_arm = min(treatment_count, control_count)
    if weakest_arm < policy.minimum_per_arm:
        diagnostics.append(
            _needs_more_data(
                code="sample.arm_insufficient",
                category=ValidationCategory.SAMPLE,
                message="At least one arm is below the configured minimum usable sample.",
                context={
                    "control_count": control_count,
                    "threshold": policy.minimum_per_arm,
                    "treatment_count": treatment_count,
                },
            )
        )
    elif weakest_arm < policy.weak_per_arm:
        diagnostics.append(
            _warning(
                code="sample.arm_weak",
                category=ValidationCategory.SAMPLE,
                message="At least one arm is below the configured advisory sample threshold.",
                context={
                    "control_count": control_count,
                    "threshold": policy.weak_per_arm,
                    "treatment_count": treatment_count,
                },
            )
        )
    return tuple(diagnostics)


def _allocation_diagnostics(
    context: ValidationContext,
    observed: ObservedAllocation,
) -> tuple[EligibilityDiagnostic, ...]:
    design = context.request.study_design
    if not isinstance(design, RandomizedExperimentDesign):
        return ()
    if observed.treatment_rate is None:
        return ()

    deviation = abs(observed.treatment_rate - design.treatment_allocation)
    if _meets_threshold(deviation, context.policy.allocation_blocking_deviation):
        return (
            _blocking(
                code="allocation.deviation_blocking",
                category=ValidationCategory.ALLOCATION,
                message="Observed allocation deviates beyond the configured blocking threshold.",
                context={
                    "declared_treatment_rate": design.treatment_allocation,
                    "deviation": deviation,
                    "observed_treatment_rate": observed.treatment_rate,
                    "threshold": context.policy.allocation_blocking_deviation,
                },
            ),
        )
    if _meets_threshold(deviation, context.policy.allocation_warning_deviation):
        return (
            _warning(
                code="allocation.deviation_warning",
                category=ValidationCategory.ALLOCATION,
                message="Observed allocation deviates beyond the configured advisory threshold.",
                context={
                    "declared_treatment_rate": design.treatment_allocation,
                    "deviation": deviation,
                    "observed_treatment_rate": observed.treatment_rate,
                    "threshold": context.policy.allocation_warning_deviation,
                },
            ),
        )
    return ()


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _meets_threshold(observed: float, threshold: float) -> bool:
    return observed > threshold or math.isclose(
        observed,
        threshold,
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def _is_numeric(value: object) -> TypeGuard[int | float]:
    return type(value) is int or type(value) is float


def _append_numeric(values: list[int | float], value: object) -> bool:
    if not _is_numeric(value):
        return False
    values.append(value)
    return True


def _is_finite(value: int | float) -> bool:
    return type(value) is int or math.isfinite(value)


def _required_columns(context: ValidationContext) -> tuple[str, ...]:
    binding = context.binding
    candidates = (
        binding.treatment_column,
        *binding.outcome.columns,
        binding.observation_unit_column,
        binding.randomization_unit_column,
        binding.clustering_unit_column,
        binding.timestamp_column,
        *(covariate.column for covariate in binding.covariates),
        *(
            column
            for metric_binding in binding.pre_treatment_metrics
            for column in metric_binding.columns
        ),
        binding.treatment_timestamp_column,
        *(criterion.attribute for criterion in context.request.population.criteria),
    )
    return tuple(dict.fromkeys(column for column in candidates if column is not None))


def _empty_result(
    context: ValidationContext,
    diagnostics: tuple[EligibilityDiagnostic, ...],
) -> DataRuleResult:
    return DataRuleResult(
        diagnostics=diagnostics,
        dataset_summary=DatasetSummary(
            input_row_count=len(context.table.rows),
            population_row_count=0,
            column_count=len(context.table.columns),
        ),
        treatment_summary=_empty_treatment_summary(),
        outcome_summary=_empty_outcome_summary(),
        missingness_summary=(),
        observed_allocation=ObservedAllocation(
            assigned_count=0,
            treatment_rate=None,
            control_rate=None,
        ),
        population_row_indexes=(),
        valid_row_indexes=(),
    )


def _empty_treatment_summary() -> TreatmentSummary:
    return TreatmentSummary(
        treatment_count=0,
        control_count=0,
        missing_count=0,
        unknown_count=0,
    )


def _empty_outcome_summary() -> OutcomeSummary:
    return OutcomeSummary(
        valid_count=0,
        missing_count=0,
        invalid_type_count=0,
        non_finite_count=0,
        invalid_value_count=0,
        treatment_valid_count=0,
        control_valid_count=0,
        has_variation=None,
    )


def _blocking(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": code,
            "category": category,
            "severity": DiagnosticSeverity.ERROR,
            "outcome": DiagnosticOutcome.FAILED,
            "disposition": DiagnosticDisposition.BLOCKING,
            "message": message,
            "context": context,
        }
    )


def _warning(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": code,
            "category": category,
            "severity": DiagnosticSeverity.WARNING,
            "outcome": DiagnosticOutcome.FAILED,
            "disposition": DiagnosticDisposition.WARNING,
            "message": message,
            "context": context,
        }
    )


def _needs_more_data(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": code,
            "category": category,
            "severity": DiagnosticSeverity.WARNING,
            "outcome": DiagnosticOutcome.UNAVAILABLE,
            "disposition": DiagnosticDisposition.NEEDS_MORE_DATA,
            "message": message,
            "context": context,
        }
    )


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _typed_equal(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right
