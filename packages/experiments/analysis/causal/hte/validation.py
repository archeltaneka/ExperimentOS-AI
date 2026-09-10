"""Identification, modifier, binding, and complete-case validation for HTE."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeGuard, cast

from ...base import ScalarValue
from ...metrics import MetricType
from ...provenance import DiagnosticSeverity
from ...validation.table import AnalysisTable
from ..adjustment import AdjustmentValidationStatus
from ..designs import ObservationalDesignType
from ..dml.folds import canonical_observation_key
from ..dml.validation import ValidatedDMLRow
from ..estimands import CausalEstimandKind, EffectScale, TargetPopulationKind
from ..models import IdentificationStatus
from ..variables import MeasurementTiming, VariableRole
from .assignment import HTEAssignmentError, assign_subgroups
from .models import (
    HTEExecutionRequest,
    HTEModifierDerivation,
    HTEPreSpecificationStatus,
    HTERegistrationStatus,
)
from .results import (
    HTEDiagnostic,
    HTEDiagnosticStatus,
    SubgroupSampleCounts,
)


class HTEValidationDisposition(StrEnum):
    VALID = "valid"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ValidatedHTERow:
    observation_id: ScalarValue
    treated: bool
    outcome: float
    features: tuple[float, ...]
    subgroup_id: str

    def as_dml_row(self) -> ValidatedDMLRow:
        return ValidatedDMLRow(
            observation_id=self.observation_id,
            treated=self.treated,
            outcome=self.outcome,
            features=self.features,
        )


@dataclass(frozen=True, slots=True)
class ValidatedSubgroupCounts:
    subgroup_id: str
    raw_count: int
    retained_count: int
    treated_count: int
    control_count: int
    dropped_count: int

    def as_public_counts(self) -> SubgroupSampleCounts:
        return SubgroupSampleCounts(
            raw_count=self.raw_count,
            retained_count=self.retained_count,
            treated_count=self.treated_count,
            control_count=self.control_count,
            dropped_count=self.dropped_count,
        )


@dataclass(frozen=True, slots=True)
class HTEValidationResult:
    disposition: HTEValidationDisposition
    rows: tuple[ValidatedHTERow, ...]
    feature_names: tuple[str, ...]
    subgroup_counts: tuple[ValidatedSubgroupCounts, ...]
    subgroup_ids: tuple[str, ...]
    unassigned_count: int
    assignment_fingerprint_sha256: str | None
    diagnostics: tuple[HTEDiagnostic, ...]


def validate_hte_input(
    execution: HTEExecutionRequest,
    table: AnalysisTable,
) -> HTEValidationResult:
    """Validate HTE eligibility before constructing folds or fitting nuisances."""
    diagnostics, disposition = _validate_declarations(execution)
    if diagnostics:
        return _empty(execution, table, disposition, diagnostics)
    required = _required_columns(execution)
    if any(column not in table.columns for column in required):
        return _empty(
            execution,
            table,
            HTEValidationDisposition.INVALID,
            (_diagnostic("hte.binding.missing_column", "Every HTE binding must exist."),),
        )
    try:
        assignment = assign_subgroups(execution, table)
    except HTEAssignmentError as error:
        return _empty(
            execution,
            table,
            HTEValidationDisposition.INVALID,
            (_diagnostic(error.code, str(error)),),
        )
    indexes = {column: table.columns.index(column) for column in required}
    rows_by_key = {
        canonical_observation_key(
            cast(ScalarValue, row[indexes[execution.binding.observation_id_column]])
        ): row
        for row in table.rows
    }
    contrast = execution.identification_result.treatment
    assert contrast is not None
    retained: list[ValidatedHTERow] = []
    for assigned in assignment.assignments:
        if assigned.subgroup_id is None:
            continue
        source = rows_by_key[canonical_observation_key(assigned.observation_id)]
        treatment = source[indexes[execution.binding.treatment_column]]
        outcome = source[indexes[execution.binding.outcome_column]]
        covariates = tuple(source[indexes[item.column]] for item in execution.binding.covariates)
        if treatment is None or outcome is None or any(value is None for value in covariates):
            continue
        if _strict_equal(treatment, contrast.treated_value):
            treated = True
        elif _strict_equal(treatment, contrast.control_value):
            treated = False
        else:
            return _empty(
                execution,
                table,
                HTEValidationDisposition.INVALID,
                (_diagnostic("hte.treatment.invalid", "Treatment values must match contrast."),),
            )
        if not _finite_real(outcome) or any(not _finite_real(value) for value in covariates):
            return _empty(
                execution,
                table,
                HTEValidationDisposition.INVALID,
                (
                    _diagnostic(
                        "hte.sample.invalid_value", "Outcome and covariates must be finite."
                    ),
                ),
            )
        indicators = tuple(
            float(assigned.subgroup_id == subgroup.subgroup_id)
            for subgroup in execution.modifier.subgroups[1:]
        )
        retained.append(
            ValidatedHTERow(
                observation_id=assigned.observation_id,
                treated=treated,
                outcome=float(outcome),
                features=tuple(float(cast(int | float, value)) for value in covariates)
                + indicators,
                subgroup_id=assigned.subgroup_id,
            )
        )
    retained_by_group = {
        subgroup.subgroup_id: tuple(
            row for row in retained if row.subgroup_id == subgroup.subgroup_id
        )
        for subgroup in execution.modifier.subgroups
    }
    raw_by_group = {item.subgroup_id: item.raw_count for item in assignment.groups}
    counts = tuple(
        ValidatedSubgroupCounts(
            subgroup_id=subgroup.subgroup_id,
            raw_count=raw_by_group[subgroup.subgroup_id],
            retained_count=len(group_rows),
            treated_count=sum(row.treated for row in group_rows),
            control_count=sum(not row.treated for row in group_rows),
            dropped_count=raw_by_group[subgroup.subgroup_id] - len(group_rows),
        )
        for subgroup in execution.modifier.subgroups
        for group_rows in (retained_by_group[subgroup.subgroup_id],)
    )
    feature_names = (
        *(item.variable_id for item in execution.binding.covariates),
        *(
            f"{execution.modifier.variable_id}::{item.subgroup_id}"
            for item in execution.modifier.subgroups[1:]
        ),
    )
    treated_count = sum(row.treated for row in retained)
    fold_count = execution.configuration.dml.fold_count
    if min(treated_count, len(retained) - treated_count) < fold_count:
        return HTEValidationResult(
            disposition=HTEValidationDisposition.ABSTAINED,
            rows=(),
            feature_names=feature_names,
            subgroup_counts=counts,
            subgroup_ids=tuple(item.subgroup_id for item in execution.modifier.subgroups),
            unassigned_count=assignment.unassigned_count,
            assignment_fingerprint_sha256=assignment.fingerprint_sha256,
            diagnostics=(
                _diagnostic(
                    "hte.fold.inadequate_class_count",
                    "Each treatment arm needs one observation per scoring fold.",
                ),
            ),
        )
    return HTEValidationResult(
        disposition=HTEValidationDisposition.VALID,
        rows=tuple(retained),
        feature_names=feature_names,
        subgroup_counts=counts,
        subgroup_ids=tuple(item.subgroup_id for item in execution.modifier.subgroups),
        unassigned_count=assignment.unassigned_count,
        assignment_fingerprint_sha256=assignment.fingerprint_sha256,
        diagnostics=(),
    )


def _validate_declarations(
    execution: HTEExecutionRequest,
) -> tuple[tuple[HTEDiagnostic, ...], HTEValidationDisposition]:
    result = execution.identification_result
    if result.status is not IdentificationStatus.IDENTIFIED:
        return (
            _diagnostic("hte.identification.invalid", "HTE requires identified input."),
        ), HTEValidationDisposition.INVALID
    if (
        result.design_type is not ObservationalDesignType.HETEROGENEOUS_EFFECTS
        or result.identification_request.design.method
        != "partialling_out_dml_subgroup_interactions"
    ):
        return (
            _diagnostic(
                "hte.design.unsupported", "HTE v1 requires its declared DML interaction design."
            ),
        ), HTEValidationDisposition.UNSUPPORTED
    estimand = result.estimand
    if (
        estimand is None
        or estimand.estimand_type is not CausalEstimandKind.CATE
        or estimand.target_population.kind is not TargetPopulationKind.CONDITIONED
        or estimand.effect_scale is not EffectScale.MEAN_DIFFERENCE
    ):
        return (
            _diagnostic(
                "hte.estimand.unsupported",
                "HTE v1 requires a conditioned mean-difference CATE request.",
            ),
        ), HTEValidationDisposition.UNSUPPORTED
    modifier = execution.modifier
    if modifier.measurement_timing is MeasurementTiming.POST_TREATMENT:
        return (
            _diagnostic("hte.modifier.post_treatment", "Post-treatment modifiers are forbidden."),
        ), HTEValidationDisposition.INVALID
    if modifier.measurement_timing is not MeasurementTiming.PRE_TREATMENT:
        return (
            _diagnostic(
                "hte.modifier.unknown_timing", "Modifiers must be explicitly pre-treatment."
            ),
        ), HTEValidationDisposition.INVALID
    derivation_codes = {
        HTEModifierDerivation.OUTCOME_DERIVED: "hte.modifier.outcome_derived",
        HTEModifierDerivation.TREATMENT_DERIVED: "hte.modifier.treatment_derived",
        HTEModifierDerivation.DATA_MINED: "hte.modifier.data_mined",
    }
    if modifier.derivation in derivation_codes:
        return (
            _diagnostic(
                derivation_codes[modifier.derivation],
                "Derived or data-mined modifiers are unsupported.",
            ),
        ), HTEValidationDisposition.ABSTAINED
    if (
        modifier.pre_specification is not HTEPreSpecificationStatus.CONFIRMATORY_PRE_SPECIFIED
        or modifier.registration_status is not HTERegistrationStatus.REGISTERED
    ):
        return (
            _diagnostic(
                "hte.modifier.exploratory",
                "Exploratory or unregistered groups cannot be confirmatory.",
            ),
        ), HTEValidationDisposition.ABSTAINED
    if (
        result.identification_request.effect_modifiers != (modifier.variable_id,)
        or estimand.effect_modifiers != (modifier.variable_id,)
        or execution.binding.modifier_variable_id != modifier.variable_id
        or execution.binding.modifier_column != modifier.column
    ):
        return (
            _diagnostic(
                "hte.modifier.binding_mismatch", "Modifier declarations and bindings must agree."
            ),
        ), HTEValidationDisposition.INVALID
    by_id = {item.variable_id: item for item in result.identification_request.variables}
    declared = by_id.get(modifier.variable_id)
    if (
        declared is None
        or VariableRole.EFFECT_MODIFIER not in declared.roles
        or declared.timing.measurement_timing is not MeasurementTiming.PRE_TREATMENT
    ):
        return (
            _diagnostic(
                "hte.modifier.ineligible",
                "The identified modifier must have a pre-treatment effect-modifier role.",
            ),
        ), HTEValidationDisposition.INVALID
    outcome = result.outcome
    if outcome is None or outcome.metric.metric.metric_type is not MetricType.CONTINUOUS:
        return (
            _diagnostic("hte.outcome.unsupported", "HTE DML requires a continuous outcome."),
        ), HTEValidationDisposition.UNSUPPORTED
    if (
        execution.binding.outcome_variable_id != outcome.variable_id
        or result.treatment is None
        or execution.binding.treatment_variable_id != result.treatment.treatment_variable
    ):
        return (
            _diagnostic(
                "hte.binding.role_mismatch",
                "Treatment and outcome bindings must match identification.",
            ),
        ), HTEValidationDisposition.INVALID
    adjustment = result.adjustment_set
    bound = tuple(item.variable_id for item in execution.binding.covariates)
    if (
        adjustment is None
        or adjustment.validation_status is not AdjustmentValidationStatus.VALID
        or bound != adjustment.variable_ids
    ):
        return (
            _diagnostic("hte.adjustment.invalid", "HTE requires the validated adjustment set."),
        ), HTEValidationDisposition.INVALID
    return (), HTEValidationDisposition.VALID


def _required_columns(execution: HTEExecutionRequest) -> tuple[str, ...]:
    binding = execution.binding
    return (
        binding.observation_id_column,
        binding.treatment_column,
        binding.outcome_column,
        binding.modifier_column,
        *(item.column for item in binding.covariates),
    )


def _empty(
    execution: HTEExecutionRequest,
    table: AnalysisTable,
    disposition: HTEValidationDisposition,
    diagnostics: tuple[HTEDiagnostic, ...],
) -> HTEValidationResult:
    return HTEValidationResult(
        disposition=disposition,
        rows=(),
        feature_names=(),
        subgroup_counts=tuple(
            ValidatedSubgroupCounts(
                subgroup_id=subgroup.subgroup_id,
                raw_count=0,
                retained_count=0,
                treated_count=0,
                control_count=0,
                dropped_count=0,
            )
            for subgroup in execution.modifier.subgroups
        ),
        subgroup_ids=tuple(item.subgroup_id for item in execution.modifier.subgroups),
        unassigned_count=len(table.rows),
        assignment_fingerprint_sha256=None,
        diagnostics=diagnostics,
    )


def _diagnostic(code: str, message: str) -> HTEDiagnostic:
    return HTEDiagnostic(
        code=code,
        severity=DiagnosticSeverity.FATAL,
        status=HTEDiagnosticStatus.FAILED,
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
    "HTEValidationDisposition",
    "HTEValidationResult",
    "ValidatedHTERow",
    "ValidatedSubgroupCounts",
    "validate_hte_input",
]
