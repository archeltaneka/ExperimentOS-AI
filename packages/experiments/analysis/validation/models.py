"""Typed diagnostics, summaries, method support, and eligibility results."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from ..base import ContractModel, NonEmptyStr, Probability, ScalarValue
from ..provenance import DiagnosticOutcome, DiagnosticSeverity
from ..results import AbstentionReason, EligibilityStatus

type NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class ValidationCategory(StrEnum):
    """Stable rule families for reusable validation diagnostics."""

    REQUEST = "request"
    SCHEMA = "schema"
    POPULATION = "population"
    TREATMENT = "treatment"
    OUTCOME = "outcome"
    UNIT = "unit"
    COVARIATE = "covariate"
    MISSINGNESS = "missingness"
    SAMPLE = "sample"
    ALLOCATION = "allocation"
    TIME = "time"
    SEGMENT = "segment"
    METHOD = "method"


class DiagnosticDisposition(StrEnum):
    """How one diagnostic contributes to the final eligibility decision."""

    BLOCKING = "blocking"
    NEEDS_MORE_DATA = "needs_more_data"
    WARNING = "warning"
    INFORMATIONAL = "informational"


class MethodContractStatus(StrEnum):
    """Whether the Phase 4 contracts recognize a requested analysis method."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


class MethodImplementationStatus(StrEnum):
    """Whether an estimator implementation is registered as available."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class DiagnosticContextEntry(ContractModel):
    """One canonical JSON-safe diagnostic context value."""

    key: NonEmptyStr
    value: ScalarValue


def _context_key(value: object) -> str:
    if isinstance(value, DiagnosticContextEntry):
        return value.key
    if isinstance(value, Mapping):
        key = value.get("key")
        if isinstance(key, str):
            return key
    raise ValueError("diagnostic context entries require string keys")


class EligibilityDiagnostic(ContractModel):
    """Deterministic validation evidence without raw row-level values."""

    code: NonEmptyStr
    category: ValidationCategory
    severity: DiagnosticSeverity
    outcome: DiagnosticOutcome
    disposition: DiagnosticDisposition
    message: NonEmptyStr
    context: tuple[DiagnosticContextEntry, ...] = ()
    recommended_action: NonEmptyStr | None = None

    @field_validator("context", mode="before")
    @classmethod
    def canonicalize_context(cls, value: object) -> object:
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("diagnostic context keys must be strings")
            return tuple(
                {"key": key, "value": item}
                for key, item in sorted(value.items(), key=lambda entry: entry[0])
            )
        if isinstance(value, (list, tuple)):
            return tuple(sorted(value, key=_context_key))
        return value

    @model_validator(mode="after")
    def validate_unique_context_keys(self) -> Self:
        keys = tuple(entry.key for entry in self.context)
        if len(keys) != len(set(keys)):
            raise ValueError("diagnostic context keys must be unique")
        return self


class DatasetSummary(ContractModel):
    """Row and schema counts before and after explicit population selection."""

    input_row_count: NonNegativeInt
    population_row_count: NonNegativeInt
    column_count: NonNegativeInt

    @model_validator(mode="after")
    def validate_population_count(self) -> Self:
        if self.population_row_count > self.input_row_count:
            raise ValueError("population_row_count must not exceed input_row_count")
        return self


class TreatmentSummary(ContractModel):
    """Exact observed assignment counts without coercing treatment labels."""

    treatment_count: NonNegativeInt
    control_count: NonNegativeInt
    missing_count: NonNegativeInt
    unknown_count: NonNegativeInt


class OutcomeSummary(ContractModel):
    """Outcome usability counts derived without removing or replacing caller rows."""

    valid_count: NonNegativeInt
    missing_count: NonNegativeInt
    invalid_type_count: NonNegativeInt
    non_finite_count: NonNegativeInt
    invalid_value_count: NonNegativeInt
    treatment_valid_count: NonNegativeInt
    control_valid_count: NonNegativeInt
    has_variation: StrictBool | None


class MissingnessSummary(ContractModel):
    """Role-specific missingness counts and optional arm-level differences."""

    role: NonEmptyStr
    column: NonEmptyStr
    total_count: NonNegativeInt
    missing_count: NonNegativeInt
    missing_rate: Probability
    treatment_missing_rate: Probability | None = None
    control_missing_rate: Probability | None = None
    differential_missingness: Probability | None = None

    @model_validator(mode="after")
    def validate_missing_count(self) -> Self:
        if self.missing_count > self.total_count:
            raise ValueError("missing_count must not exceed total_count")
        return self


class UnitIntegritySummary(ContractModel):
    """Identifier, repetition, assignment-conflict, and cluster counts."""

    observation_unit_count: NonNegativeInt
    missing_identifier_count: NonNegativeInt
    duplicate_identifier_count: NonNegativeInt
    repeated_observation_count: NonNegativeInt
    assignment_conflict_count: NonNegativeInt
    cluster_count: NonNegativeInt | None


class TimeDesignSummary(ContractModel):
    """Timestamp validity and declared pre/post period coverage counts."""

    total_count: NonNegativeInt
    valid_count: NonNegativeInt
    missing_count: NonNegativeInt
    invalid_count: NonNegativeInt
    pre_period_count: NonNegativeInt
    post_period_count: NonNegativeInt


class SegmentEligibilitySummary(ContractModel):
    """Selected segment and arm-specific valid-outcome counts."""

    segment_id: NonEmptyStr
    selected_count: NonNegativeInt
    treatment_count: NonNegativeInt
    control_count: NonNegativeInt
    treatment_valid_outcome_count: NonNegativeInt
    control_valid_outcome_count: NonNegativeInt


class MethodSupportAssessment(ContractModel):
    """Separate contract, implementation, data, and execution support decisions."""

    requested_method: NonEmptyStr | None
    contract_status: MethodContractStatus
    implementation_status: MethodImplementationStatus
    data_eligible: StrictBool
    executable: StrictBool

    @model_validator(mode="after")
    def validate_executability(self) -> Self:
        can_execute = (
            self.contract_status is MethodContractStatus.SUPPORTED
            and self.implementation_status is MethodImplementationStatus.AVAILABLE
            and self.data_eligible
        )
        if self.executable != can_execute:
            raise ValueError("executable must match contract, implementation, and data support")
        return self


class EligibilityValidationResult(ContractModel):
    """Complete pre-estimator eligibility outcome containing no statistical estimate."""

    outcome_type: Literal["eligibility_validation"] = "eligibility_validation"
    validation_version: Literal["1"] = "1"
    status: EligibilityStatus
    requested_method: NonEmptyStr | None
    experiment_design: NonEmptyStr | None
    diagnostics: tuple[EligibilityDiagnostic, ...]
    blocking_diagnostics: tuple[EligibilityDiagnostic, ...]
    warnings: tuple[EligibilityDiagnostic, ...]
    dataset_summary: DatasetSummary
    treatment_summary: TreatmentSummary
    outcome_summary: OutcomeSummary
    missingness_summary: tuple[MissingnessSummary, ...]
    unit_integrity_summary: UnitIntegritySummary
    time_summary: TimeDesignSummary | None
    segment_summary: SegmentEligibilitySummary | None
    method_support: MethodSupportAssessment
    abstention_reason: AbstentionReason | None
    policy_version: NonEmptyStr
    configuration_provenance: NonEmptyStr

    @model_validator(mode="after")
    def validate_result_invariants(self) -> Self:
        expected_blocking = tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.disposition is DiagnosticDisposition.BLOCKING
        )
        if self.blocking_diagnostics != expected_blocking:
            raise ValueError(
                "blocking_diagnostics must exactly match blocking entries in diagnostics"
            )

        expected_warnings = tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.disposition is DiagnosticDisposition.WARNING
        )
        if self.warnings != expected_warnings:
            raise ValueError("warnings must exactly match warning entries in diagnostics")

        abstention_statuses = {"ineligible", "needs_more_data"}
        requires_abstention = self.status.value in abstention_statuses
        if requires_abstention != (self.abstention_reason is not None):
            raise ValueError(
                "abstention_reason is required only for ineligible or needs_more_data results"
            )

        if self.status.value == "ineligible" and self.method_support.executable:
            raise ValueError("ineligible results must not report executable method support")
        return self
