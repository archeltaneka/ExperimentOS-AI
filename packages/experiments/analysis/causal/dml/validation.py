"""Identification, binding, and complete-case validation for DML."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeGuard

from ...base import ScalarValue
from ...metrics import MetricType
from ...provenance import DiagnosticSeverity
from ...validation.table import AnalysisTable
from ..adjustment import AdjustmentValidationStatus
from ..assumptions import (
    AssumptionApplicability,
    CausalAssumptionCode,
    CausalAssumptionStatus,
)
from ..designs import ObservationalDesignType
from ..estimands import CausalEstimandKind, EffectScale, TargetPopulationKind
from ..models import IdentificationStatus
from ..variables import MeasurementTiming, VariableRole
from .folds import canonical_observation_key
from .models import (
    DMLDiagnostic,
    DMLDiagnosticCategory,
    DMLDiagnosticStatus,
    DMLExecutionRequest,
    DMLSampleCounts,
)


class DMLValidationDisposition(StrEnum):
    """Whether validated input can proceed to deterministic fold planning."""

    VALID = "valid"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ValidatedDMLRow:
    """One canonical complete-case row using only declared DML features."""

    observation_id: ScalarValue
    treated: bool
    outcome: float
    features: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DMLValidationResult:
    """Validated rows, sample accounting, and normalized diagnostics."""

    disposition: DMLValidationDisposition
    rows: tuple[ValidatedDMLRow, ...]
    sample_counts: DMLSampleCounts
    diagnostics: tuple[DMLDiagnostic, ...]


def validate_dml_input(
    execution: DMLExecutionRequest,
    table: AnalysisTable,
) -> DMLValidationResult:
    """Validate the bounded DML design before constructing any folds."""
    declaration_diagnostics, declaration_disposition = _validate_declarations(execution)
    empty_counts = DMLSampleCounts(
        raw_count=len(table.rows),
        retained_count=0,
        treated_count=0,
        control_count=0,
        complete_case_excluded_count=len(table.rows),
    )
    if declaration_diagnostics:
        return DMLValidationResult(
            disposition=declaration_disposition,
            rows=(),
            sample_counts=empty_counts,
            diagnostics=declaration_diagnostics,
        )

    missing_columns = tuple(
        column for column in _required_columns(execution) if column not in table.columns
    )
    if missing_columns:
        return _invalid(
            table,
            "dml.binding.missing_column",
            DMLDiagnosticCategory.BINDING,
            "Every DML binding must reference a table column.",
        )

    indexes = {name: table.columns.index(name) for name in _required_columns(execution)}
    contrast = execution.identification_result.treatment
    assert contrast is not None
    seen: set[str] = set()
    retained: list[ValidatedDMLRow] = []
    excluded = 0
    for source in table.rows:
        observation_id = source[indexes[execution.binding.observation_id_column]]
        try:
            identity = canonical_observation_key(observation_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return _invalid(
                table,
                "dml.sample.invalid_observation_id",
                DMLDiagnosticCategory.SAMPLE,
                "Observation IDs must be finite supported scalar values.",
            )
        if identity in seen:
            return _invalid(
                table,
                "dml.sample.duplicate_observation_id",
                DMLDiagnosticCategory.SAMPLE,
                "Stable observation IDs must be unique by type and value.",
            )
        seen.add(identity)

        treatment = source[indexes[execution.binding.treatment_column]]
        outcome = source[indexes[execution.binding.outcome_column]]
        feature_values = tuple(
            source[indexes[item.column]] for item in execution.binding.covariates
        )
        if treatment is None or outcome is None or any(value is None for value in feature_values):
            excluded += 1
            continue
        if _strict_equal(treatment, contrast.treated_value):
            treated = True
        elif _strict_equal(treatment, contrast.control_value):
            treated = False
        else:
            return _invalid(
                table,
                "dml.treatment.invalid",
                DMLDiagnosticCategory.TREATMENT,
                "Treatment values must match the declared binary contrast.",
            )
        if not _finite_real(outcome):
            return _invalid(
                table,
                "dml.outcome.invalid",
                DMLDiagnosticCategory.OUTCOME,
                "DML outcomes must be finite real values.",
            )
        checked_features: list[float] = []
        for value in feature_values:
            if not _finite_real(value):
                return _invalid(
                    table,
                    "dml.covariate.invalid",
                    DMLDiagnosticCategory.COVARIATE,
                    "DML covariates must be finite real values.",
                )
            checked_features.append(float(value))
        retained.append(
            ValidatedDMLRow(
                observation_id=observation_id,  # type: ignore[arg-type]
                treated=treated,
                outcome=float(outcome),
                features=tuple(checked_features),
            )
        )

    retained.sort(key=lambda row: canonical_observation_key(row.observation_id))
    treated_count = sum(row.treated for row in retained)
    counts = DMLSampleCounts(
        raw_count=len(table.rows),
        retained_count=len(retained),
        treated_count=treated_count,
        control_count=len(retained) - treated_count,
        complete_case_excluded_count=excluded,
    )
    if min(counts.treated_count, counts.control_count) < execution.configuration.fold_count:
        diagnostic = _diagnostic(
            "dml.fold.inadequate_class_count",
            DMLDiagnosticCategory.FOLD,
            "Each treatment class must contain at least one observation per scoring fold.",
        )
        return DMLValidationResult(
            disposition=DMLValidationDisposition.ABSTAINED,
            rows=(),
            sample_counts=counts,
            diagnostics=(diagnostic,),
        )
    return DMLValidationResult(
        disposition=DMLValidationDisposition.VALID,
        rows=tuple(retained),
        sample_counts=counts,
        diagnostics=(),
    )


def _validate_declarations(
    execution: DMLExecutionRequest,
) -> tuple[tuple[DMLDiagnostic, ...], DMLValidationDisposition]:
    result = execution.identification_result
    if result.status is not IdentificationStatus.IDENTIFIED:
        disposition = {
            IdentificationStatus.UNSUPPORTED: DMLValidationDisposition.UNSUPPORTED,
            IdentificationStatus.INVALID: DMLValidationDisposition.INVALID,
            IdentificationStatus.PARTIALLY_IDENTIFIED: DMLValidationDisposition.ABSTAINED,
            IdentificationStatus.INSUFFICIENT_EVIDENCE: DMLValidationDisposition.ABSTAINED,
        }[result.status]
        return (
            (
                _diagnostic(
                    f"dml.identification.{result.status.value}",
                    DMLDiagnosticCategory.IDENTIFICATION,
                    "Issue #97 identification is incompatible with conclusive DML estimation.",
                ),
            ),
            disposition,
        )
    if result.design_type is not ObservationalDesignType.DML:
        return _unsupported(
            "dml.design.unsupported",
            DMLDiagnosticCategory.IDENTIFICATION,
            "DML V1 requires the declared double-machine-learning design.",
        )
    if result.identification_request.design.method != "partialling_out_dml":
        return _unsupported(
            "dml.score.unsupported",
            DMLDiagnosticCategory.IDENTIFICATION,
            "DML V1 supports only the declared partialling-out score formulation.",
        )
    required_assumptions = {
        CausalAssumptionCode.CONSISTENCY,
        CausalAssumptionCode.INTERFERENCE_LIMITATION,
        CausalAssumptionCode.EXCHANGEABILITY,
        CausalAssumptionCode.POSITIVITY,
        CausalAssumptionCode.TEMPORAL_ORDERING,
    }
    acceptable = {
        item.code
        for item in result.assumptions
        if item.applicability is AssumptionApplicability.REQUIRED
        and item.status
        in {
            CausalAssumptionStatus.ASSERTED,
            CausalAssumptionStatus.SUPPORTED_BY_DIAGNOSTICS,
        }
    }
    if not required_assumptions <= acceptable:
        return (
            (
                _diagnostic(
                    "dml.assumption.insufficient",
                    DMLDiagnosticCategory.IDENTIFICATION,
                    "DML requires all generic observational identification assumptions.",
                ),
            ),
            DMLValidationDisposition.INVALID,
        )
    estimand = result.estimand
    if (
        estimand is None
        or estimand.estimand_type is not CausalEstimandKind.ATE
        or estimand.target_population.kind is not TargetPopulationKind.FULL
        or estimand.effect_scale is not EffectScale.MEAN_DIFFERENCE
    ):
        return _unsupported(
            "dml.estimand.unsupported",
            DMLDiagnosticCategory.IDENTIFICATION,
            "DML V1 requires a full-population ATE on the mean-difference scale.",
        )
    outcome = result.outcome
    if outcome is None or outcome.metric.metric.metric_type is not MetricType.CONTINUOUS:
        return _unsupported(
            "dml.outcome.unsupported",
            DMLDiagnosticCategory.OUTCOME,
            "DML V1 requires a continuous outcome.",
        )
    contrast = result.treatment
    if contrast is None or execution.binding.treatment_variable_id != contrast.treatment_variable:
        return (
            (
                _diagnostic(
                    "dml.binding.treatment_mismatch",
                    DMLDiagnosticCategory.BINDING,
                    "The treatment binding must name the identified treatment variable.",
                ),
            ),
            DMLValidationDisposition.INVALID,
        )
    if execution.binding.outcome_variable_id != outcome.variable_id:
        return (
            (
                _diagnostic(
                    "dml.binding.outcome_mismatch",
                    DMLDiagnosticCategory.BINDING,
                    "The outcome binding must name the identified outcome variable.",
                ),
            ),
            DMLValidationDisposition.INVALID,
        )
    adjustment = result.adjustment_set
    if (
        adjustment is None
        or not adjustment.variable_ids
        or adjustment.validation_status is not AdjustmentValidationStatus.VALID
    ):
        return (
            (
                _diagnostic(
                    "dml.adjustment.invalid",
                    DMLDiagnosticCategory.COVARIATE,
                    "DML requires a non-empty validated adjustment set.",
                ),
            ),
            DMLValidationDisposition.INVALID,
        )
    bound_ids = tuple(item.variable_id for item in execution.binding.covariates)
    if bound_ids != adjustment.variable_ids:
        return (
            (
                _diagnostic(
                    "dml.binding.covariate_mismatch",
                    DMLDiagnosticCategory.BINDING,
                    "Bound DML covariates must exactly match the validated adjustment set.",
                ),
            ),
            DMLValidationDisposition.INVALID,
        )
    by_id = {item.variable_id: item for item in result.identification_request.variables}
    for variable_id in bound_ids:
        variable = by_id.get(variable_id)
        if (
            variable is None
            or VariableRole.ADJUSTMENT not in variable.roles
            or variable.timing.measurement_timing
            not in {MeasurementTiming.PRE_TREATMENT, MeasurementTiming.TIME_INVARIANT}
        ):
            return (
                (
                    _diagnostic(
                        "dml.covariate.ineligible",
                        DMLDiagnosticCategory.COVARIATE,
                        "DML features must be declared pre-treatment adjustment variables.",
                    ),
                ),
                DMLValidationDisposition.INVALID,
            )
    return (), DMLValidationDisposition.VALID


def _required_columns(execution: DMLExecutionRequest) -> tuple[str, ...]:
    binding = execution.binding
    return (
        binding.observation_id_column,
        binding.treatment_column,
        binding.outcome_column,
        *(item.column for item in binding.covariates),
    )


def _invalid(
    table: AnalysisTable,
    code: str,
    category: DMLDiagnosticCategory,
    message: str,
) -> DMLValidationResult:
    return DMLValidationResult(
        disposition=DMLValidationDisposition.INVALID,
        rows=(),
        sample_counts=DMLSampleCounts(
            raw_count=len(table.rows),
            retained_count=0,
            treated_count=0,
            control_count=0,
            complete_case_excluded_count=len(table.rows),
        ),
        diagnostics=(_diagnostic(code, category, message),),
    )


def _unsupported(
    code: str,
    category: DMLDiagnosticCategory,
    message: str,
) -> tuple[tuple[DMLDiagnostic, ...], DMLValidationDisposition]:
    return (
        (_diagnostic(code, category, message),),
        DMLValidationDisposition.UNSUPPORTED,
    )


def _diagnostic(
    code: str,
    category: DMLDiagnosticCategory,
    message: str,
) -> DMLDiagnostic:
    return DMLDiagnostic(
        code=code,
        category=category,
        severity=DiagnosticSeverity.FATAL,
        status=DMLDiagnosticStatus.FAILED,
        message=message,
    )


def _strict_equal(actual: object, expected: object) -> bool:
    return type(actual) is type(expected) and actual == expected


def _finite_real(value: object) -> TypeGuard[int | float]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


__all__ = [
    "DMLValidationDisposition",
    "DMLValidationResult",
    "ValidatedDMLRow",
    "validate_dml_input",
]
