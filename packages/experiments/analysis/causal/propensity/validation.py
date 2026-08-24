"""Deterministic identification and table validation for propensity diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real

from ...provenance import DiagnosticSeverity
from ...validation.table import AnalysisTable
from ..adjustment import AdjustmentSet, AdjustmentValidationStatus
from ..designs import ObservationalDesignType
from ..estimands import CausalEstimandKind, TargetPopulationKind
from ..models import IdentificationStatus
from ..service import CausalIdentificationService
from .models import (
    PropensityDiagnostic,
    PropensityDiagnosticCategory,
    PropensityDiagnosticStatus,
    PropensityExecutionRequest,
    PropensityFeatureKind,
    PropensitySampleCounts,
)


class PropensityValidationDisposition(StrEnum):
    """Terminal state of propensity-specific input validation."""

    VALID = "valid"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ValidatedCovariate:
    """One issue-97 adjustment variable with an explicit table binding."""

    variable_id: str
    column: str
    feature_kind: PropensityFeatureKind


@dataclass(frozen=True, slots=True)
class ValidatedPropensityRow:
    """One complete-case model row retained only inside estimator implementation."""

    unit_id: object
    treated: bool
    covariate_values: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class PropensityValidationResult:
    """Internal validated model data and safe aggregate validation evidence."""

    disposition: PropensityValidationDisposition
    rows: tuple[ValidatedPropensityRow, ...]
    covariates: tuple[ValidatedCovariate, ...]
    sample_counts: PropensitySampleCounts
    diagnostics: tuple[PropensityDiagnostic, ...]


def _diagnostic(
    code: str,
    category: PropensityDiagnosticCategory,
    message: str,
    *,
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR,
    unavailable: bool = False,
) -> PropensityDiagnostic:
    return PropensityDiagnostic(
        code=code,
        category=category,
        severity=severity,
        status=(
            PropensityDiagnosticStatus.UNAVAILABLE
            if unavailable
            else PropensityDiagnosticStatus.FAILED
        ),
        message=message,
    )


def _result(
    disposition: PropensityValidationDisposition,
    *,
    rows: tuple[ValidatedPropensityRow, ...] = (),
    covariates: tuple[ValidatedCovariate, ...] = (),
    sample_counts: PropensitySampleCounts | None = None,
    diagnostics: tuple[PropensityDiagnostic, ...] = (),
) -> PropensityValidationResult:
    return PropensityValidationResult(
        disposition=disposition,
        rows=rows,
        covariates=covariates,
        sample_counts=sample_counts or PropensitySampleCounts(),
        diagnostics=diagnostics,
    )


def validate_propensity_input(
    execution: PropensityExecutionRequest,
    table: AnalysisTable,
) -> PropensityValidationResult:
    """Validate identification, bindings, treatment coding, and complete-case model rows."""
    identification = CausalIdentificationService().identify(execution.analysis_request)
    if identification.status is not IdentificationStatus.IDENTIFIED:
        diagnostics = tuple(
            _diagnostic(
                item.code.value,
                PropensityDiagnosticCategory.IDENTIFICATION,
                item.message,
                severity=item.severity,
                unavailable=item.status.value == "unavailable",
            )
            for item in identification.diagnostics
        )
        disposition = (
            PropensityValidationDisposition.UNSUPPORTED
            if identification.status is IdentificationStatus.UNSUPPORTED
            else PropensityValidationDisposition.ABSTAINED
        )
        return _result(disposition, diagnostics=diagnostics)

    declaration_diagnostics = _validate_declarations(execution, identification.adjustment_set)
    if declaration_diagnostics:
        unsupported = any(
            item.code == "propensity.unsupported_request" for item in declaration_diagnostics
        )
        return _result(
            PropensityValidationDisposition.UNSUPPORTED
            if unsupported
            else PropensityValidationDisposition.INVALID,
            diagnostics=declaration_diagnostics,
        )

    binding = execution.binding
    bound_columns = (
        binding.unit_column,
        binding.treatment_column,
        *(item.column for item in binding.covariates),
    )
    missing = tuple(column for column in bound_columns if column not in table.columns)
    if missing:
        return _result(
            PropensityValidationDisposition.INVALID,
            sample_counts=PropensitySampleCounts(raw=len(table.rows)),
            diagnostics=(
                _diagnostic(
                    "propensity.missing_column",
                    PropensityDiagnosticCategory.BINDING,
                    "Every explicitly bound propensity column must exist.",
                ),
            ),
        )

    covariates = tuple(
        ValidatedCovariate(
            variable_id=item.variable_id,
            column=item.column,
            feature_kind=item.feature_kind,
        )
        for item in binding.covariates
    )
    return _validate_rows(execution, table, covariates)


def _validate_declarations(
    execution: PropensityExecutionRequest,
    adjustment: AdjustmentSet | None,
) -> tuple[PropensityDiagnostic, ...]:
    request = execution.analysis_request.identification
    estimand = request.estimand
    supported_designs = {
        ObservationalDesignType.GENERIC,
        ObservationalDesignType.PROPENSITY_WEIGHTING,
    }
    supported_estimands = {CausalEstimandKind.ATE, CausalEstimandKind.ATT}
    if (
        request.design.design_type not in supported_designs
        or estimand is None
        or estimand.estimand_type not in supported_estimands
        or (
            estimand.estimand_type is CausalEstimandKind.ATE
            and estimand.target_population.kind is not TargetPopulationKind.FULL
        )
        or (
            estimand.estimand_type is CausalEstimandKind.ATT
            and estimand.target_population.kind is not TargetPopulationKind.TREATED
        )
    ):
        return (
            _diagnostic(
                "propensity.unsupported_request",
                PropensityDiagnosticCategory.IDENTIFICATION,
                "V1 supports identified generic or propensity-weighting ATE and ATT requests.",
                unavailable=True,
            ),
        )

    if adjustment is None or adjustment.validation_status is not AdjustmentValidationStatus.VALID:
        return (
            _diagnostic(
                "propensity.invalid_adjustment_set",
                PropensityDiagnosticCategory.COVARIATE,
                "A non-empty issue-97 validated adjustment set is required.",
            ),
        )
    adjustment_ids = adjustment.variable_ids
    binding_ids = tuple(item.variable_id for item in execution.binding.covariates)
    if not adjustment_ids or tuple(sorted(binding_ids)) != tuple(sorted(adjustment_ids)):
        return (
            _diagnostic(
                "propensity.adjustment_binding_mismatch",
                PropensityDiagnosticCategory.BINDING,
                "Covariate bindings must exactly match the declared adjustment set.",
            ),
        )
    return ()


def _validate_rows(
    execution: PropensityExecutionRequest,
    table: AnalysisTable,
    covariates: tuple[ValidatedCovariate, ...],
) -> PropensityValidationResult:
    binding = execution.binding
    contrast = execution.analysis_request.identification.treatment
    if contrast is None:
        return _result(PropensityValidationDisposition.ABSTAINED)
    indexes = {column: table.columns.index(column) for column in table.columns}
    rows: list[ValidatedPropensityRow] = []
    diagnostics: list[PropensityDiagnostic] = []
    treated_raw = control_raw = treated_excluded = control_excluded = 0
    seen_units: list[object] = []

    for source in table.rows:
        treatment = source[indexes[binding.treatment_column]]
        if _typed_equal(treatment, contrast.treated_value):
            treated = True
            treated_raw += 1
        elif _typed_equal(treatment, contrast.control_value):
            treated = False
            control_raw += 1
        else:
            diagnostics.append(
                _diagnostic(
                    "propensity.invalid_treatment_value",
                    PropensityDiagnosticCategory.TREATMENT,
                    "Treatment values must exactly match the declared treated or control value.",
                )
            )
            continue

        unit_id = source[indexes[binding.unit_column]]
        if not _valid_unit_id(unit_id) or any(_typed_equal(unit_id, item) for item in seen_units):
            diagnostics.append(
                _diagnostic(
                    "propensity.invalid_unit",
                    PropensityDiagnosticCategory.SAMPLE,
                    "Unit identifiers must be unique, non-null, hashable scalar values.",
                )
            )
            continue
        seen_units.append(unit_id)

        values = tuple(source[indexes[item.column]] for item in covariates)
        if any(value is None for value in values):
            if treated:
                treated_excluded += 1
            else:
                control_excluded += 1
            continue
        invalid_code = _invalid_covariate_code(covariates, values)
        if invalid_code is not None:
            diagnostics.append(
                _diagnostic(
                    invalid_code,
                    PropensityDiagnosticCategory.COVARIATE,
                    "Non-missing covariates must satisfy their explicitly bound feature kind.",
                )
            )
            continue
        rows.append(
            ValidatedPropensityRow(
                unit_id=unit_id,
                treated=treated,
                covariate_values=values,
            )
        )

    model_treated = sum(row.treated for row in rows)
    model_control = len(rows) - model_treated
    counts = PropensitySampleCounts(
        raw=len(table.rows),
        raw_treated=treated_raw,
        raw_control=control_raw,
        model=len(rows),
        model_treated=model_treated,
        model_control=model_control,
        complete_case_excluded=treated_excluded + control_excluded,
        treated_excluded=treated_excluded,
        control_excluded=control_excluded,
        retention_proportion=(len(rows) / len(table.rows) if table.rows else 0.0),
    )
    if diagnostics:
        return _result(
            PropensityValidationDisposition.INVALID,
            sample_counts=counts,
            diagnostics=tuple(diagnostics),
        )
    if model_treated == 0 or model_control == 0:
        return _result(
            PropensityValidationDisposition.ABSTAINED,
            sample_counts=counts,
            diagnostics=(
                _diagnostic(
                    "propensity.missing_model_arm",
                    PropensityDiagnosticCategory.SAMPLE,
                    "Complete-case selection must retain treated and control units.",
                    unavailable=True,
                ),
            ),
        )
    return _result(
        PropensityValidationDisposition.VALID,
        rows=tuple(rows),
        covariates=covariates,
        sample_counts=counts,
    )


def _invalid_covariate_code(
    covariates: tuple[ValidatedCovariate, ...],
    values: tuple[object, ...],
) -> str | None:
    for covariate, value in zip(covariates, values, strict=True):
        if covariate.feature_kind is PropensityFeatureKind.NUMERIC:
            if isinstance(value, bool) or not isinstance(value, Real):
                return "propensity.invalid_numeric_covariate"
            if not math.isfinite(float(value)):
                return "propensity.invalid_numeric_covariate"
        elif not _valid_category(value):
            return "propensity.invalid_categorical_covariate"
    return None


def _valid_category(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool | int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _valid_unit_id(value: object) -> bool:
    if value is None or isinstance(value, bool | tuple | list | dict | set):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    try:
        hash(value)
    except TypeError:
        return False
    return isinstance(value, str | int | float)


def _typed_equal(actual: object, expected: object) -> bool:
    return type(actual) is type(expected) and actual == expected


__all__ = [
    "PropensityValidationDisposition",
    "PropensityValidationResult",
    "ValidatedCovariate",
    "ValidatedPropensityRow",
    "validate_propensity_input",
]
