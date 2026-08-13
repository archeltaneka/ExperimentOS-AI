"""Frozen contracts for pre-registered sequential randomized analysis."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ...base import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    OpenProbability,
    PositiveInt,
    Probability,
)
from ...metrics import SampleCounts
from ...provenance import (
    AnalysisWarning,
    AssumptionAssessment,
    DiagnosticSeverity,
    ProvenanceRecords,
)
from ...requests import AnalysisRequest
from ...study_designs import RandomizedAnalysisMethod, RandomizedExperimentDesign
from ..models import RandomizedAnalysisResult, RandomizedDiagnosticContext, RandomizedTestType

INFORMATION_TIME_TOLERANCE = 1e-12


class SequentialSidedness(StrEnum):
    """Supported sequential alternative direction."""

    TWO_SIDED = "two_sided"


class SequentialBoundaryMethod(StrEnum):
    """The single deterministic v1 boundary family."""

    OBRIEN_FLEMING_WEIGHTED_BONFERRONI = "obrien_fleming_weighted_bonferroni"


class SequentialLookDefinition(ContractModel):
    """One discrete look declared before sequential analysis begins."""

    look_index: PositiveInt
    information_time: Annotated[float, Field(strict=True, gt=0.0, le=1.0, allow_inf_nan=False)]
    expected_cumulative_sample_counts: SampleCounts | None = None


class SequentialAnalysisPlan(ContractModel):
    """Immutable statistical plan registered before the first observed look."""

    schema_version: Literal["1"] = "1"
    plan_version: Literal["1"] = "1"
    method_version: Literal["1"] = "1"
    plan_id: NonEmptyStr
    experiment_id: NonEmptyStr | None = None
    analysis_request: AnalysisRequest
    total_alpha: OpenProbability
    sidedness: SequentialSidedness = SequentialSidedness.TWO_SIDED
    boundary_method: SequentialBoundaryMethod = (
        SequentialBoundaryMethod.OBRIEN_FLEMING_WEIGHTED_BONFERRONI
    )
    planned_looks: Annotated[tuple[SequentialLookDefinition, ...], Field(min_length=1)]
    registration_marker: NonEmptyStr
    registered_at: datetime | None = None
    provenance: ProvenanceRecords
    plan_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None

    @field_validator("registered_at")
    @classmethod
    def require_aware_registration_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("registered_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        design = self.analysis_request.study_design
        if not isinstance(design, RandomizedExperimentDesign) or (
            design.method is not RandomizedAnalysisMethod.SEQUENTIAL_AB
        ):
            raise ValueError("sequential plans require a randomized sequential_ab design")

        indexes = tuple(look.look_index for look in self.planned_looks)
        expected_indexes = tuple(range(1, len(self.planned_looks) + 1))
        if indexes != expected_indexes:
            raise ValueError("planned look indexes must be consecutive and start at one")

        information_times = tuple(look.information_time for look in self.planned_looks)
        if any(
            current <= previous
            for previous, current in zip(
                information_times,
                information_times[1:],
                strict=False,
            )
        ):
            raise ValueError("planned information times must be strictly increasing")
        if not math.isclose(
            information_times[-1],
            1.0,
            rel_tol=0.0,
            abs_tol=INFORMATION_TIME_TOLERANCE,
        ):
            raise ValueError("final planned information time must equal one")

        expected_counts = tuple(
            look.expected_cumulative_sample_counts
            for look in self.planned_looks
            if look.expected_cumulative_sample_counts is not None
        )
        if len(expected_counts) not in {0, len(self.planned_looks)}:
            raise ValueError(
                "planned cumulative sample counts must be declared for every look or none"
            )
        if expected_counts and any(
            current.total <= previous.total
            or current.treatment < previous.treatment
            or current.control < previous.control
            for previous, current in zip(expected_counts, expected_counts[1:], strict=False)
        ):
            raise ValueError("planned cumulative sample counts must increase monotonically")

        from .fingerprint import sequential_plan_fingerprint

        expected_fingerprint = sequential_plan_fingerprint(self)
        if self.plan_fingerprint is None:
            object.__setattr__(self, "plan_fingerprint", expected_fingerprint)
        elif self.plan_fingerprint != expected_fingerprint:
            raise ValueError("plan_fingerprint does not match the statistical plan")
        return self


class SequentialPlanAudit(ContractModel):
    """Immutable supplied-plan metadata retained even when integrity validation fails."""

    schema_version: Literal["1"] = "1"
    plan_version: NonEmptyStr
    method_version: NonEmptyStr
    plan_id: NonEmptyStr
    experiment_id: NonEmptyStr | None = None
    analysis_request: AnalysisRequest
    total_alpha: OpenProbability
    sidedness: SequentialSidedness
    boundary_method: SequentialBoundaryMethod
    planned_looks: tuple[SequentialLookDefinition, ...]
    registration_marker: NonEmptyStr
    registered_at: datetime | None = None
    provenance: ProvenanceRecords
    plan_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SequentialBoundary(ContractModel):
    """One planned critical value and its explicit alpha accounting."""

    look_index: PositiveInt
    information_time: Annotated[float, Field(strict=True, gt=0.0, le=1.0, allow_inf_nan=False)]
    critical_boundary: Annotated[FiniteFloat, Field(gt=0.0)]
    nominal_alpha: Probability
    cumulative_alpha_spent: Probability
    remaining_alpha: Probability
    method: SequentialBoundaryMethod
    method_version: Literal["1"] = "1"
    total_alpha: OpenProbability

    @model_validator(mode="after")
    def validate_alpha_accounting(self) -> Self:
        if self.cumulative_alpha_spent > self.total_alpha + INFORMATION_TIME_TOLERANCE:
            raise ValueError("cumulative alpha cannot exceed total alpha")
        if not math.isclose(
            self.cumulative_alpha_spent + self.remaining_alpha,
            self.total_alpha,
            rel_tol=0.0,
            abs_tol=INFORMATION_TIME_TOLERANCE,
        ):
            raise ValueError("spent and remaining alpha must equal total alpha")
        return self


class SequentialStoppingStatus(StrEnum):
    """Statistical status only; never an automatic product action."""

    EFFICACY = "efficacy"
    CONTINUE = "continue"
    INVALID = "invalid"
    ABSTAIN = "abstain"


class PlanIntegrityStatus(StrEnum):
    """Whether the observed history remains compatible with registration."""

    VALID = "valid"
    INVALID = "invalid"


class SequentialDiagnosticCategory(StrEnum):
    """Stable diagnostic families for sequential execution."""

    PLAN = "plan"
    LOOK = "look"
    SAMPLE = "sample"
    CONFIGURATION = "configuration"
    COMPUTATION = "computation"


class SequentialDiagnostic(ContractModel):
    """Structured plan-deviation or sequential-computation diagnostic."""

    code: NonEmptyStr
    category: SequentialDiagnosticCategory
    severity: DiagnosticSeverity
    message: NonEmptyStr
    context: tuple[RandomizedDiagnosticContext, ...] = ()

    @field_validator("context", mode="before")
    @classmethod
    def expand_context_mapping(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return tuple({"key": key, "value": item} for key, item in value.items())
        return value

    @field_validator("context")
    @classmethod
    def canonicalize_context(
        cls,
        value: tuple[RandomizedDiagnosticContext, ...],
    ) -> tuple[RandomizedDiagnosticContext, ...]:
        canonical = tuple(sorted(value, key=lambda item: item.key))
        if len({item.key for item in canonical}) != len(canonical):
            raise ValueError("sequential diagnostic context keys must be unique")
        return canonical


class SequentialAlphaSummary(ContractModel):
    """Planned alpha accounting through the latest valid evaluated look."""

    method: SequentialBoundaryMethod
    total_alpha: OpenProbability
    cumulative_alpha_spent: Probability
    remaining_alpha: Probability
    evaluated_look_count: Annotated[int, Field(strict=True, ge=0)]

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if not math.isclose(
            self.cumulative_alpha_spent + self.remaining_alpha,
            self.total_alpha,
            rel_tol=0.0,
            abs_tol=INFORMATION_TIME_TOLERANCE,
        ):
            raise ValueError("alpha summary spent and remaining values must equal total alpha")
        return self


class SequentialLookResult(ContractModel):
    """One immutable look artifact without raw row-level input."""

    schema_version: Literal["1"] = "1"
    plan_id: NonEmptyStr
    plan_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    look_index: PositiveInt
    information_time: Annotated[float, Field(strict=True, gt=0.0, le=1.0, allow_inf_nan=False)]
    cumulative_sample_count: Annotated[int, Field(strict=True, ge=0)]
    treatment_count: Annotated[int, Field(strict=True, ge=0)]
    control_count: Annotated[int, Field(strict=True, ge=0)]
    estimator_method: RandomizedTestType | None = None
    look_level_analysis: RandomizedAnalysisResult | None = None
    standardized_statistic: FiniteFloat | None = None
    sequential_boundary: Annotated[FiniteFloat, Field(gt=0.0)]
    cumulative_alpha_spent: Probability
    nominal_alpha: Probability
    boundary_crossed: bool
    stopping_status: SequentialStoppingStatus
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[SequentialDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    executed_at: datetime | None = None
    duration_ms: Annotated[FiniteFloat, Field(ge=0.0)] | None = None
    provenance: ProvenanceRecords

    @field_validator("executed_at")
    @classmethod
    def require_aware_execution_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.cumulative_sample_count != self.treatment_count + self.control_count:
            raise ValueError("cumulative sample count must equal treatment plus control")
        if self.stopping_status is SequentialStoppingStatus.ABSTAIN:
            if self.look_level_analysis is None:
                raise ValueError("abstained looks must retain the underlying randomized result")
            if self.standardized_statistic is not None or self.boundary_crossed:
                raise ValueError("abstained looks cannot cross a sequential boundary")
        else:
            if self.look_level_analysis is None or self.standardized_statistic is None:
                raise ValueError("numerical looks require look-level analysis and statistic")
        return self


class SequentialLookMetadata(ContractModel):
    """Compact first/latest look audit metadata."""

    look_index: PositiveInt
    information_time: Annotated[float, Field(strict=True, gt=0.0, le=1.0, allow_inf_nan=False)]
    cumulative_sample_count: Annotated[int, Field(strict=True, ge=0)]
    treatment_count: Annotated[int, Field(strict=True, ge=0)]
    control_count: Annotated[int, Field(strict=True, ge=0)]
    executed_at: datetime | None = None


class SequentialAnalysisHistory(ContractModel):
    """Complete immutable audit history for one registered sequential run."""

    schema_version: Literal["1"] = "1"
    plan: SequentialPlanAudit
    boundaries: tuple[SequentialBoundary, ...]
    looks: tuple[SequentialLookResult, ...]
    current_look: SequentialLookResult | None = None
    current_status: SequentialStoppingStatus
    plan_integrity: PlanIntegrityStatus
    alpha_summary: SequentialAlphaSummary
    deviations: tuple[SequentialDiagnostic, ...]
    first_look: SequentialLookMetadata | None = None
    latest_look: SequentialLookMetadata | None = None
    provenance: ProvenanceRecords

    @field_validator("deviations")
    @classmethod
    def canonicalize_deviations(
        cls,
        value: tuple[SequentialDiagnostic, ...],
    ) -> tuple[SequentialDiagnostic, ...]:
        return tuple(
            sorted(
                value,
                key=lambda diagnostic: json.dumps(
                    diagnostic.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_history(self) -> Self:
        indexes = tuple(look.look_index for look in self.looks)
        if indexes != tuple(sorted(set(indexes))):
            raise ValueError("sequential history looks must be ordered and duplicate-free")
        expected_current = self.looks[-1] if self.looks else None
        if self.current_look != expected_current:
            raise ValueError("current_look must be the latest retained look")
        if self.boundaries:
            from .boundaries import generate_sequential_boundaries

            registered_plan = SequentialAnalysisPlan.model_validate(
                self.plan.model_dump(mode="python")
            )
            if self.boundaries != generate_sequential_boundaries(registered_plan):
                raise ValueError(
                    "boundary schedule must match deterministic registered values"
                )
            if len(self.boundaries) != len(self.plan.planned_looks):
                raise ValueError("boundary schedule must cover every registered look")
            for boundary, planned in zip(
                self.boundaries,
                self.plan.planned_looks,
                strict=True,
            ):
                if (
                    boundary.look_index != planned.look_index
                    or boundary.information_time != planned.information_time
                    or boundary.method is not self.plan.boundary_method
                    or boundary.method_version != self.plan.method_version
                    or boundary.total_alpha != self.plan.total_alpha
                ):
                    raise ValueError("boundary schedule must match the registered plan")
        elif self.looks:
            raise ValueError("retained looks require a registered boundary schedule")
        for look in self.looks:
            if look.plan_id != self.plan.plan_id or (
                look.plan_fingerprint != self.plan.plan_fingerprint
            ):
                raise ValueError("retained looks must match the registered plan identity")
            if look.look_index > len(self.boundaries):
                raise ValueError("retained look is outside the boundary schedule")
            boundary = self.boundaries[look.look_index - 1]
            if (
                look.information_time != boundary.information_time
                or look.sequential_boundary != boundary.critical_boundary
                or look.cumulative_alpha_spent != boundary.cumulative_alpha_spent
                or look.nominal_alpha != boundary.nominal_alpha
            ):
                raise ValueError("retained look must match its registered boundary")
        expected_alpha = self.boundaries[len(self.looks) - 1].cumulative_alpha_spent if (
            self.looks
        ) else 0.0
        if (
            self.alpha_summary.method is not self.plan.boundary_method
            or self.alpha_summary.total_alpha != self.plan.total_alpha
            or self.alpha_summary.evaluated_look_count != len(self.looks)
            or self.alpha_summary.cumulative_alpha_spent != expected_alpha
        ):
            raise ValueError("alpha summary must match the retained look history")
        expected_first = _history_look_metadata(self.looks[0]) if self.looks else None
        expected_latest = _history_look_metadata(self.looks[-1]) if self.looks else None
        if self.first_look != expected_first or self.latest_look != expected_latest:
            raise ValueError("first and latest look metadata must match retained history")
        if self.plan_integrity is PlanIntegrityStatus.INVALID:
            if self.current_status is not SequentialStoppingStatus.INVALID or not self.deviations:
                raise ValueError("invalid plan integrity requires invalid status and deviations")
        elif self.current_status is SequentialStoppingStatus.INVALID:
            raise ValueError("valid plan integrity cannot have invalid status")
        elif self.current_status is not (
            self.looks[-1].stopping_status
            if self.looks
            else SequentialStoppingStatus.CONTINUE
        ):
            raise ValueError("current status must match the latest retained look")
        return self


def _history_look_metadata(look: SequentialLookResult) -> SequentialLookMetadata:
    return SequentialLookMetadata(
        look_index=look.look_index,
        information_time=look.information_time,
        cumulative_sample_count=look.cumulative_sample_count,
        treatment_count=look.treatment_count,
        control_count=look.control_count,
        executed_at=look.executed_at,
    )


__all__ = [
    "INFORMATION_TIME_TOLERANCE",
    "PlanIntegrityStatus",
    "SequentialAlphaSummary",
    "SequentialAnalysisHistory",
    "SequentialAnalysisPlan",
    "SequentialBoundary",
    "SequentialBoundaryMethod",
    "SequentialDiagnostic",
    "SequentialDiagnosticCategory",
    "SequentialLookDefinition",
    "SequentialLookMetadata",
    "SequentialLookResult",
    "SequentialPlanAudit",
    "SequentialSidedness",
    "SequentialStoppingStatus",
]
