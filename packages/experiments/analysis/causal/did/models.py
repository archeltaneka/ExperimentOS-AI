"""Owned contracts for bounded two-group, two-period DiD analysis."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ...base import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    OpenProbability,
    Probability,
    ScalarValue,
)
from ...metrics import AnalysisUnit
from ...populations import PopulationDefinition
from ...provenance import (
    AnalysisWarning,
    DiagnosticSeverity,
    ProvenanceRecords,
)
from ...study_designs import TimePeriod
from ...uncertainty import ConfidenceInterval
from ..assumptions import CausalAssumption
from ..designs import CausalOutcome, ObservationalDesign, TimeSemantics, UnitSemantics
from ..diagnostics import EvidenceLimitation
from ..estimands import CausalEstimand, TreatmentContrast
from ..models import ObservationalAnalysisRequest

type NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
type PositiveCount = Annotated[int, Field(strict=True, gt=0)]
type NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]


class DidStatus(StrEnum):
    """Terminal status of one DiD execution."""

    COMPLETED = "completed"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class DidPanelPolicy(StrEnum):
    """Supported canonical-panel retention behavior."""

    REQUIRE_BALANCED = "require_balanced"


class DidVarianceEstimator(StrEnum):
    """Supported DiD uncertainty convention."""

    CLUSTER_ROBUST_CR1 = "cluster_robust_cr1"


class DidDiagnosticCategory(StrEnum):
    """Stable families for DiD diagnostics."""

    IDENTIFICATION = "identification"
    DESIGN = "design"
    TIMING = "timing"
    GROUP = "group"
    PANEL = "panel"
    OUTCOME = "outcome"
    INFERENCE = "inference"
    ASSUMPTION = "assumption"
    PRETREND = "pretrend"


class DidDiagnosticStatus(StrEnum):
    """Observed state of one deterministic DiD check."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class DidPretrendAvailability(StrEnum):
    """Whether diagnostic-only pre-trend inference is represented."""

    NOT_REQUESTED = "not_requested"
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"


class DidDiagnosticContext(ContractModel):
    """One canonical privacy-safe DiD diagnostic context entry."""

    key: NonEmptyStr
    value: ScalarValue

    @field_validator("value")
    @classmethod
    def reject_nonfinite_float(cls, value: ScalarValue) -> ScalarValue:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("diagnostic context floats must be finite")
        return value


class DidDiagnostic(ContractModel):
    """Structured DiD validation or inference diagnostic."""

    code: NonEmptyStr
    category: DidDiagnosticCategory
    severity: DiagnosticSeverity
    status: DidDiagnosticStatus
    message: NonEmptyStr
    context: tuple[DidDiagnosticContext, ...] = ()
    recommended_action: NonEmptyStr | None = None

    @field_validator("context", mode="before")
    @classmethod
    def expand_context_mapping(cls, value: object) -> object:
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("diagnostic context keys must be strings")
            return tuple({"key": key, "value": item} for key, item in value.items())
        return value

    @field_validator("context")
    @classmethod
    def canonicalize_context(
        cls,
        value: tuple[DidDiagnosticContext, ...],
    ) -> tuple[DidDiagnosticContext, ...]:
        canonical = tuple(sorted(value, key=lambda entry: entry.key))
        keys = tuple(entry.key for entry in canonical)
        if len(keys) != len(set(keys)):
            raise ValueError("diagnostic context keys must be unique")
        return canonical


class DifferenceInDifferencesDataBinding(ContractModel):
    """Explicit mapping from DiD analytical roles to table columns."""

    unit_column: NonEmptyStr
    time_column: NonEmptyStr
    group_column: NonEmptyStr
    treatment_column: NonEmptyStr
    treatment_start_column: NonEmptyStr
    outcome_column: NonEmptyStr
    treated_group_value: ScalarValue
    control_group_value: ScalarValue

    @model_validator(mode="after")
    def validate_distinct_roles(self) -> Self:
        columns = (
            self.unit_column,
            self.time_column,
            self.group_column,
            self.treatment_column,
            self.treatment_start_column,
            self.outcome_column,
        )
        if len(columns) != len(set(columns)):
            raise ValueError("binding columns must be unique")
        if type(self.treated_group_value) is not type(self.control_group_value) or (
            self.treated_group_value == self.control_group_value
        ):
            raise ValueError("treated and control group values must differ")
        return self


class DifferenceInDifferencesConfig(ContractModel):
    """Centralized bounded-panel and cluster-inference policy."""

    panel_policy: DidPanelPolicy = DidPanelPolicy.REQUIRE_BALANCED
    variance_estimator: DidVarianceEstimator = DidVarianceEstimator.CLUSTER_ROBUST_CR1
    confidence_level: OpenProbability = 0.95
    minimum_cluster_count: Annotated[int, Field(strict=True)] = 8
    minimum_cluster_count_per_group: Annotated[int, Field(strict=True)] = 4
    few_cluster_warning_threshold: Annotated[int, Field(strict=True)] = 30

    @model_validator(mode="after")
    def validate_cluster_policy(self) -> Self:
        if self.minimum_cluster_count < 2:
            raise ValueError("minimum_cluster_count must be at least two")
        if self.minimum_cluster_count_per_group < 2:
            raise ValueError("minimum_cluster_count_per_group must be at least two")
        if self.few_cluster_warning_threshold < 3:
            raise ValueError("few_cluster_warning_threshold must be at least three")
        if self.few_cluster_warning_threshold <= self.minimum_cluster_count:
            raise ValueError(
                "few-cluster warning threshold must exceed the minimum cluster count"
            )
        if self.minimum_cluster_count < 2 * self.minimum_cluster_count_per_group:
            raise ValueError("total minimum clusters must cover both group minima")
        return self


class DifferenceInDifferencesExecutionRequest(ContractModel):
    """Estimator-facing request that cannot bypass issue #97 identification."""

    schema_version: Literal["1"] = "1"
    analysis_request: ObservationalAnalysisRequest
    binding: DifferenceInDifferencesDataBinding
    configuration: DifferenceInDifferencesConfig = DifferenceInDifferencesConfig()
    extra_pre_periods: tuple[TimePeriod, ...] = ()

    @property
    def request_id(self) -> str:
        """Return the identity owned by the observational request envelope."""
        return self.analysis_request.request_id

    @model_validator(mode="after")
    def validate_extra_pre_periods(self) -> Self:
        for earlier, later in zip(
            self.extra_pre_periods,
            self.extra_pre_periods[1:],
            strict=False,
        ):
            if earlier.end > later.start:
                raise ValueError("extra pre-periods must be ordered and non-overlapping")
        canonical_pre = self.analysis_request.identification.time.pre_period
        if canonical_pre is not None and any(
            period.end > canonical_pre.start for period in self.extra_pre_periods
        ):
            raise ValueError("extra pre-periods must end before the canonical pre-period")
        return self


class DidSampleCounts(ContractModel):
    """Canonical panel coverage, missingness, and retention counts."""

    rows: NonNegativeInt = 0
    total_units: NonNegativeInt = 0
    treated_units: NonNegativeInt = 0
    control_units: NonNegativeInt = 0
    units_with_both_periods: NonNegativeInt = 0
    units_missing_pre: NonNegativeInt = 0
    units_missing_post: NonNegativeInt = 0
    retained_units: NonNegativeInt = 0
    incomplete_units: NonNegativeInt = 0
    excluded_units: NonNegativeInt = 0
    treated_retained_units: NonNegativeInt = 0
    control_retained_units: NonNegativeInt = 0
    treated_pre_rows: NonNegativeInt = 0
    treated_post_rows: NonNegativeInt = 0
    control_pre_rows: NonNegativeInt = 0
    control_post_rows: NonNegativeInt = 0
    treated_missing_pre_outcomes: NonNegativeInt = 0
    treated_missing_post_outcomes: NonNegativeInt = 0
    control_missing_pre_outcomes: NonNegativeInt = 0
    control_missing_post_outcomes: NonNegativeInt = 0
    retention_rate: Probability = 0.0
    treated_retention_rate: Probability = 0.0
    control_retention_rate: Probability = 0.0

    @model_validator(mode="after")
    def validate_count_relationships(self) -> Self:
        if self.treated_units + self.control_units > self.total_units:
            raise ValueError("treated and control units must not exceed total units")
        if self.retained_units > self.total_units:
            raise ValueError("retained units must not exceed total units")
        if self.treated_retained_units + self.control_retained_units != self.retained_units:
            raise ValueError("retained group counts must sum to retained units")
        return self


class DidCellMeans(ContractModel):
    """Four canonical cell means and their DiD contrast."""

    treated_pre_mean: FiniteFloat
    treated_post_mean: FiniteFloat
    control_pre_mean: FiniteFloat
    control_post_mean: FiniteFloat
    treated_change: FiniteFloat
    control_change: FiniteFloat
    did_estimate: FiniteFloat
    treated_pre_count: PositiveCount
    treated_post_count: PositiveCount
    control_pre_count: PositiveCount
    control_post_count: PositiveCount


class DidTestResult(ContractModel):
    """Owned frequentist CR1 interaction-effect inference."""

    variance_estimator: DidVarianceEstimator
    cluster_unit: AnalysisUnit
    cluster_count: PositiveCount
    standard_error: NonNegativeFiniteFloat
    statistic: FiniteFloat
    degrees_of_freedom: PositiveCount
    p_value: Probability
    null_hypothesis: Literal["ATT_DiD = 0"] = "ATT_DiD = 0"
    alternative: Literal["two_sided"] = "two_sided"
    confidence_interval: ConfidenceInterval

    @model_validator(mode="after")
    def validate_cluster_degrees_of_freedom(self) -> Self:
        if self.degrees_of_freedom != self.cluster_count - 1:
            raise ValueError("degrees_of_freedom must equal cluster_count minus one")
        return self


class DidPretrendDiagnostic(ContractModel):
    """Diagnostic evidence about differential pre-treatment trends, never proof."""

    availability: DidPretrendAvailability
    message: NonEmptyStr
    period_count: NonNegativeInt = 0
    trend_difference: FiniteFloat | None = None
    standard_error: NonNegativeFiniteFloat | None = None
    statistic: FiniteFloat | None = None
    degrees_of_freedom: PositiveCount | None = None
    p_value: Probability | None = None
    confidence_interval: ConfidenceInterval | None = None
    evidence_concern: bool = False

    @model_validator(mode="after")
    def validate_availability_shape(self) -> Self:
        numerical = (
            self.trend_difference,
            self.standard_error,
            self.statistic,
            self.degrees_of_freedom,
            self.p_value,
            self.confidence_interval,
        )
        if self.availability is DidPretrendAvailability.AVAILABLE:
            if self.period_count < 3 or any(item is None for item in numerical):
                raise ValueError("available pre-trend diagnostics require complete inference")
        elif any(item is not None for item in numerical):
            raise ValueError("unavailable pre-trend diagnostics must not contain inference")
        if self.availability is not DidPretrendAvailability.AVAILABLE and self.evidence_concern:
            raise ValueError("unavailable pre-trend diagnostics cannot flag evidence concern")
        return self


class DidAbstentionReason(ContractModel):
    """Typed reason the bounded DiD estimator did not return a finding."""

    code: NonEmptyStr
    message: NonEmptyStr
    missing_or_invalid_information: Annotated[
        tuple[NonEmptyStr, ...],
        Field(min_length=1),
    ]


class DifferenceInDifferencesResult(ContractModel):
    """Complete ExperimentOS-owned result for the bounded DiD estimator."""

    outcome_type: Literal["difference_in_differences"] = "difference_in_differences"
    schema_version: Literal["1"] = "1"
    method: Literal["did"] = "did"
    request_id: NonEmptyStr
    analysis_request: ObservationalAnalysisRequest
    binding: DifferenceInDifferencesDataBinding
    configuration: DifferenceInDifferencesConfig
    status: DidStatus
    estimand: CausalEstimand | None
    design: ObservationalDesign
    treatment: TreatmentContrast | None
    outcome: CausalOutcome | None
    population: PopulationDefinition
    units: UnitSemantics | None
    time: TimeSemantics
    sample_counts: DidSampleCounts
    cell_means: DidCellMeans | None = None
    test_result: DidTestResult | None = None
    assumptions: tuple[CausalAssumption, ...]
    evidence_limitations: tuple[EvidenceLimitation, ...]
    pretrend: DidPretrendDiagnostic
    diagnostics: tuple[DidDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    abstention_reason: DidAbstentionReason | None = None

    @field_validator("diagnostics")
    @classmethod
    def canonicalize_diagnostics(
        cls,
        value: tuple[DidDiagnostic, ...],
    ) -> tuple[DidDiagnostic, ...]:
        return tuple(
            sorted(
                value,
                key=lambda item: json.dumps(
                    item.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_request_echoes_and_status_shape(self) -> Self:
        source = self.analysis_request.identification
        echoes = {
            "request_id": self.analysis_request.request_id,
            "estimand": source.estimand,
            "design": source.design,
            "treatment": source.treatment,
            "outcome": source.outcome,
            "population": source.population,
            "units": source.units,
            "time": source.time,
            "assumptions": source.assumptions,
        }
        for field, expected in echoes.items():
            if getattr(self, field) != expected:
                raise ValueError(f"{field} must match analysis_request identification")

        if self.status is DidStatus.COMPLETED:
            if any(
                item is None
                for item in (self.estimand, self.treatment, self.outcome, self.units)
            ):
                raise ValueError("completed results require complete identification echoes")
            if self.cell_means is None or self.test_result is None:
                raise ValueError("completed results require estimates and inference")
            if self.abstention_reason is not None:
                raise ValueError("completed results must not contain an abstention reason")
            if (
                self.test_result.confidence_interval.confidence_level
                != self.configuration.confidence_level
            ):
                raise ValueError("confidence interval level must match configuration")
        else:
            if self.cell_means is not None or self.test_result is not None:
                raise ValueError("non-completed results must not contain estimates")
            if self.abstention_reason is None:
                raise ValueError("non-completed results require an abstention reason")
        return self


__all__ = [
    "DidPanelPolicy",
    "DidAbstentionReason",
    "DidCellMeans",
    "DidDiagnostic",
    "DidDiagnosticCategory",
    "DidDiagnosticContext",
    "DidDiagnosticStatus",
    "DidPretrendAvailability",
    "DidPretrendDiagnostic",
    "DidSampleCounts",
    "DidStatus",
    "DidTestResult",
    "DidVarianceEstimator",
    "DifferenceInDifferencesConfig",
    "DifferenceInDifferencesDataBinding",
    "DifferenceInDifferencesExecutionRequest",
    "DifferenceInDifferencesResult",
]
