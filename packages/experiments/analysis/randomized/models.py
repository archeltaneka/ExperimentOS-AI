"""Frozen result contracts for unadjusted randomized analyses."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ..base import ContractModel, FiniteFloat, NonEmptyStr, PositiveInt, Probability, ScalarValue
from ..estimands import EstimandDefinition
from ..metrics import MeasuredValue, MetricDefinition
from ..provenance import (
    AnalysisWarning,
    AssumptionAssessment,
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceRecords,
)
from ..requests import AnalysisRequest
from ..uncertainty import ConfidenceInterval
from .config import RandomizedAnalysisConfig

type NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]
type ArmSummary = "ContinuousArmSummary | BinaryArmSummary"


class ComputationStatus(StrEnum):
    """Terminal state of one requested randomized calculation."""

    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"


class Conclusion(StrEnum):
    """Statistical conclusion distinct from design-based evidence."""

    STATISTICALLY_SIGNIFICANT = "statistically_significant"
    NOT_STATISTICALLY_SIGNIFICANT = "not_statistically_significant"
    INCONCLUSIVE = "inconclusive"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"


class PracticalSignificance(StrEnum):
    """Explicit practical-significance assessment state."""

    NOT_ASSESSED = "not_assessed"
    EXCEEDED = "exceeded"
    NOT_EXCEEDED = "not_exceeded"


class EvidenceCategory(StrEnum):
    """Evidence category determined from the randomized design and assumptions only."""

    RANDOMIZED_DESIGN_WITH_SUPPORTED_ASSUMPTIONS = "randomized_design_with_supported_assumptions"
    RANDOMIZED_DESIGN_WITH_LIMITED_ASSUMPTIONS = "randomized_design_with_limited_assumptions"
    RANDOMIZED_DESIGN_WITH_VIOLATED_ASSUMPTIONS = "randomized_design_with_violated_assumptions"
    NO_RANDOMIZED_EVIDENCE = "no_randomized_evidence"


class RelativeEffectAvailability(StrEnum):
    """Whether a relative effect has a meaningful finite representation."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class RelativeEffectReason(StrEnum):
    """Declared reason a relative effect cannot be represented."""

    ZERO_CONTROL_BASELINE = "zero_control_baseline"
    NON_POSITIVE_CONTROL_BASELINE = "non_positive_control_baseline"


class AlternativeHypothesis(StrEnum):
    """Declared alternative hypothesis; v1 estimates only two-sided alternatives."""

    TWO_SIDED = "two_sided"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"


class RandomizedHypothesis(ContractModel):
    """Explicit null and alternative hypotheses for a randomized estimate."""

    null_value: FiniteFloat = 0.0
    alternative: AlternativeHypothesis = AlternativeHypothesis.TWO_SIDED


class RandomizedTestType(StrEnum):
    """Frequentist test families supported by the unadjusted contract."""

    WELCH_T = "welch_t"
    TWO_PROPORTION_Z = "two_proportion_z"


class RandomizedDiagnosticCategory(StrEnum):
    """Stable families for randomized-analysis diagnostics."""

    CONFIGURATION = "configuration"
    INPUT = "input"
    SAMPLE = "sample"
    ASSUMPTION = "assumption"
    COMPUTATION = "computation"
    RESULT = "result"


class RandomizedDiagnosticStatus(StrEnum):
    """Observed state of a randomized-analysis diagnostic."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class RandomizedDiagnosticContext(ContractModel):
    """One canonical JSON-safe randomized diagnostic context value."""

    key: NonEmptyStr
    value: ScalarValue

    @field_validator("value")
    @classmethod
    def reject_nonfinite_floats(cls, value: ScalarValue) -> ScalarValue:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("diagnostic context floats must be finite")
        return value


class ContinuousArmSummary(ContractModel):
    """Observed continuous-outcome summary for a single analysis arm."""

    arm_type: Literal["continuous"] = "continuous"
    arm_id: NonEmptyStr
    n: PositiveInt
    mean: FiniteFloat
    sample_variance: NonNegativeFiniteFloat


class BinaryArmSummary(ContractModel):
    """Observed binary-outcome summary for a single analysis arm."""

    arm_type: Literal["binary"] = "binary"
    arm_id: NonEmptyStr
    n: PositiveInt
    successes: Annotated[int, Field(strict=True, ge=0)]
    failures: Annotated[int, Field(strict=True, ge=0)]
    rate: Probability

    @model_validator(mode="after")
    def validate_counts_and_rate(self) -> Self:
        if self.successes + self.failures != self.n:
            raise ValueError("successes plus failures must equal n")
        if self.rate != self.successes / self.n:
            raise ValueError("rate must equal successes divided by n")
        return self


class PointEffect(ContractModel):
    """Absolute effect plus a separately available-or-unavailable relative effect."""

    absolute_effect: MeasuredValue
    relative_effect: FiniteFloat | None
    relative_effect_availability: RelativeEffectAvailability
    relative_effect_reason: RelativeEffectReason | None = None

    @model_validator(mode="after")
    def validate_relative_effect_shape(self) -> Self:
        if self.relative_effect_availability is RelativeEffectAvailability.AVAILABLE:
            if self.relative_effect is None:
                raise ValueError("available relative effects require a finite value")
            if self.relative_effect_reason is not None:
                raise ValueError("available relative effects must not include a reason")
        elif self.relative_effect is not None:
            raise ValueError("unavailable relative effects must not include a value")
        elif self.relative_effect_reason is None:
            raise ValueError("unavailable relative effects require a reason")
        return self


class RandomizedTestResult(ContractModel):
    """Typed frequentist test statistics and confidence interval."""

    test_type: RandomizedTestType
    standard_error: NonNegativeFiniteFloat
    confidence_interval_standard_error: NonNegativeFiniteFloat | None = None
    statistic: FiniteFloat
    degrees_of_freedom: NonNegativeFiniteFloat | None = None
    p_value: Probability
    confidence_interval: ConfidenceInterval


class RandomizedDiagnostic(ContractModel):
    """Structured diagnostic with sorted, duplicate-free context."""

    code: NonEmptyStr
    category: RandomizedDiagnosticCategory
    severity: DiagnosticSeverity
    status: RandomizedDiagnosticStatus
    message: NonEmptyStr
    context: tuple[RandomizedDiagnosticContext, ...] = ()
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
        value: tuple[RandomizedDiagnosticContext, ...],
    ) -> tuple[RandomizedDiagnosticContext, ...]:
        canonical = tuple(sorted(value, key=lambda entry: entry.key))
        keys = tuple(entry.key for entry in canonical)
        if len(keys) != len(set(keys)):
            raise ValueError("diagnostic context keys must be unique")
        return canonical


class RandomizedAbstentionReason(ContractModel):
    """Typed reason that a randomized result has no numerical estimate."""

    code: NonEmptyStr
    message: NonEmptyStr
    missing_or_invalid_information: tuple[NonEmptyStr, ...] = ()


class RandomizedAnalysisResult(ContractModel):
    """Complete contract for an unadjusted randomized-analysis result."""

    outcome_type: Literal["randomized_analysis"] = "randomized_analysis"
    schema_version: Literal["1"] = "1"
    request_id: NonEmptyStr
    analysis_request: AnalysisRequest | None = None
    metric: MetricDefinition
    estimand: EstimandDefinition
    hypothesis: RandomizedHypothesis = RandomizedHypothesis()
    status: ComputationStatus
    conclusion: Conclusion
    practical_significance: PracticalSignificance
    evidence_category: EvidenceCategory
    treatment_summary: ContinuousArmSummary | BinaryArmSummary | None = None
    control_summary: ContinuousArmSummary | BinaryArmSummary | None = None
    point_effect: PointEffect | None = None
    test_result: RandomizedTestResult | None = None
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[RandomizedDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    configuration: RandomizedAnalysisConfig
    configuration_provenance: ProvenanceRecord | None = None
    abstention_reason: RandomizedAbstentionReason | None = None

    @field_validator("diagnostics")
    @classmethod
    def canonicalize_diagnostics(
        cls,
        value: tuple[RandomizedDiagnostic, ...],
    ) -> tuple[RandomizedDiagnostic, ...]:
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
    def validate_result_shape(self) -> Self:
        if self.analysis_request is not None:
            if self.metric != self.analysis_request.outcome.metric:
                raise ValueError("metric must match analysis_request outcome metric")
            if self.estimand != self.analysis_request.estimand:
                raise ValueError("estimand must match analysis_request estimand")

        expected_configuration_provenance = self.configuration.configuration_provenance()
        if self.configuration_provenance is None:
            object.__setattr__(self, "configuration_provenance", expected_configuration_provenance)
        elif self.configuration_provenance != expected_configuration_provenance:
            raise ValueError("configuration_provenance must match configuration")

        non_numerical_statuses = {
            ComputationStatus.ABSTAINED,
            ComputationStatus.UNSUPPORTED,
            ComputationStatus.INVALID,
        }
        if self.status in non_numerical_statuses:
            if self.treatment_summary is not None or self.control_summary is not None:
                raise ValueError(
                    "abstained, unsupported, and invalid results must not include arm summaries"
                )
            if self.point_effect is not None or self.test_result is not None:
                raise ValueError(
                    "abstained, unsupported, and invalid results must not include point_effect "
                    "or test_result"
                )
            if self.abstention_reason is None:
                raise ValueError("non-numerical results require an abstention_reason")
        else:
            if self.treatment_summary is None or self.control_summary is None:
                raise ValueError("completed and inconclusive results require arm summaries")
            if self.treatment_summary.arm_id == self.control_summary.arm_id:
                raise ValueError("treatment and control arm identifiers must differ")
            if type(self.treatment_summary) is not type(self.control_summary):
                raise ValueError("treatment and control summaries must have the same arm type")
            if self.point_effect is None or self.test_result is None:
                raise ValueError(
                    "completed and inconclusive results require point_effect and test_result"
                )
            if (
                self.test_result.confidence_interval.confidence_level
                != self.configuration.confidence_level
            ):
                raise ValueError(
                    "test_result confidence_interval confidence_level must match configuration"
                )
            if self.abstention_reason is not None:
                raise ValueError("numerical results must not include an abstention_reason")

        expected_conclusions = {
            ComputationStatus.INCONCLUSIVE: Conclusion.INCONCLUSIVE,
            ComputationStatus.UNSUPPORTED: Conclusion.UNSUPPORTED,
            ComputationStatus.INVALID: Conclusion.INVALID,
            ComputationStatus.ABSTAINED: Conclusion.INCONCLUSIVE,
        }
        expected_conclusion = expected_conclusions.get(self.status)
        if expected_conclusion is not None and self.conclusion is not expected_conclusion:
            raise ValueError("conclusion must match the computation status")
        if self.status is ComputationStatus.COMPLETED and self.conclusion not in {
            Conclusion.STATISTICALLY_SIGNIFICANT,
            Conclusion.NOT_STATISTICALLY_SIGNIFICANT,
        }:
            raise ValueError("completed results require a statistical conclusion")
        return self
