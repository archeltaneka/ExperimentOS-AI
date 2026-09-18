"""Owned public result contracts for bounded heterogeneous effects."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ...base import ContractModel, FiniteFloat, NonEmptyStr, Probability
from ...provenance import DiagnosticSeverity, ProvenanceRecords
from ...uncertainty import ConfidenceInterval
from ..advanced.models import AdvancedAdapterProvenance
from ..assumptions import CausalAssumption
from ..dml.models import DMLFoldPlan, DMLNuisanceDiagnostics, DMLOverlapDiagnostic
from ..dml.results import DMLFoldFitProvenance
from ..estimands import CausalEstimand, TreatmentContrast
from .models import (
    EffectModifierDefinition,
    HTEExecutionRequest,
    HTEMultiplicityMethod,
    HTEPreSpecificationStatus,
)

type NonNegativeCount = Annotated[int, Field(strict=True, ge=0)]
type PositiveCount = Annotated[int, Field(strict=True, gt=0)]
type NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class HTEStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class HTESubgroupStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"


class HTEEvidenceStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class HTEDiagnosticStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class HTEDiagnostic(ContractModel):
    code: NonEmptyStr
    severity: DiagnosticSeverity
    status: HTEDiagnosticStatus
    message: NonEmptyStr
    subgroup_id: NonEmptyStr | None = None


class SubgroupSampleCounts(ContractModel):
    raw_count: NonNegativeCount
    retained_count: NonNegativeCount
    treated_count: NonNegativeCount
    control_count: NonNegativeCount
    dropped_count: NonNegativeCount

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        if self.treated_count + self.control_count != self.retained_count:
            raise ValueError("subgroup arm counts must equal retained count")
        if self.retained_count + self.dropped_count != self.raw_count:
            raise ValueError("subgroup retained and dropped counts must equal raw count")
        return self


class SubgroupEffectResult(ContractModel):
    """Normalized subgroup effect and support with explicit uncertainty."""

    subgroup_id: NonEmptyStr
    label: NonEmptyStr
    rule: NonEmptyStr
    sample_counts: SubgroupSampleCounts
    status: HTESubgroupStatus
    estimate: FiniteFloat | None = None
    standard_error: NonNegativeFiniteFloat | None = None
    confidence_interval: ConfidenceInterval | None = None
    p_value: Probability | None = None
    adjusted_p_value: Probability | None = None
    uncertainty_method: (
        Literal["orthogonal_score_influence_hc1", "doubly_robust_statsmodels_hc1"] | None
    ) = None
    effective_sample_size: None = None
    overlap: DMLOverlapDiagnostic | None = None
    diagnostics: tuple[HTEDiagnostic, ...] = ()
    abstention_reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> Self:
        inference = (
            self.estimate,
            self.standard_error,
            self.confidence_interval,
            self.p_value,
            self.adjusted_p_value,
            self.uncertainty_method,
        )
        if self.status is HTESubgroupStatus.COMPLETED:
            if any(value is None for value in inference):
                raise ValueError("completed subgroup effects require uncertainty and inference")
            if self.abstention_reason is not None:
                raise ValueError("completed subgroup effects cannot include abstention")
        elif any(value is not None for value in inference) or self.abstention_reason is None:
            raise ValueError("abstained subgroup effects must suppress estimates and give a reason")
        return self


class InteractionEffectResult(ContractModel):
    reference_subgroup_id: NonEmptyStr
    comparison_subgroup_id: NonEmptyStr
    estimate: FiniteFloat
    standard_error: NonNegativeFiniteFloat
    confidence_interval: ConfidenceInterval
    p_value: Probability
    adjusted_p_value: Probability
    null_hypothesis: Literal["equal_subgroup_treatment_effects"] = (
        "equal_subgroup_treatment_effects"
    )


class GlobalHeterogeneityEvidence(ContractModel):
    status: HTEEvidenceStatus
    null_hypothesis: Literal["all_supported_subgroup_effects_are_equal"] = (
        "all_supported_subgroup_effects_are_equal"
    )
    method: Literal[
        "joint_orthogonal_interaction_wald_chi_square",
        "doubly_robust_interaction_wald_chi_square",
    ] = "joint_orthogonal_interaction_wald_chi_square"
    statistic: NonNegativeFiniteFloat | None = None
    degrees_of_freedom: PositiveCount | None = None
    p_value: Probability | None = None
    detected: bool | None = None
    unavailable_reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> Self:
        evidence = (self.statistic, self.degrees_of_freedom, self.p_value, self.detected)
        if self.status is HTEEvidenceStatus.AVAILABLE:
            if any(value is None for value in evidence) or self.unavailable_reason is not None:
                raise ValueError("available heterogeneity evidence requires complete inference")
        elif any(value is not None for value in evidence) or self.unavailable_reason is None:
            raise ValueError("unavailable heterogeneity evidence requires a reason only")
        return self


class MultiplicityContext(ContractModel):
    subgroup_effect_tests: NonNegativeCount
    interaction_tests: NonNegativeCount
    pairwise_tests: Literal[0] = 0
    global_tests: Annotated[int, Field(strict=True, ge=0, le=1)]
    correction_method: Literal[HTEMultiplicityMethod.HOLM] = HTEMultiplicityMethod.HOLM
    corrected_families: tuple[Literal["subgroup_effects", "reference_interactions"], ...]
    global_p_value_adjusted: Literal[False] = False


class HeterogeneousEffectResult(ContractModel):
    """Owned aggregate HTE evidence without individualized recommendations."""

    outcome_type: Literal["heterogeneous_treatment_effects"] = "heterogeneous_treatment_effects"
    schema_version: Literal["1"] = "1"
    configuration_fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    method: Literal["dml_orthogonal_subgroup_interactions", "doubly_robust_subgroup_effects"] = (
        "dml_orthogonal_subgroup_interactions"
    )
    request_id: NonEmptyStr
    execution_request: HTEExecutionRequest
    status: HTEStatus
    analysis_semantics: HTEPreSpecificationStatus
    estimand: CausalEstimand | None
    treatment: TreatmentContrast | None
    modifier: EffectModifierDefinition
    subgroup_results: tuple[SubgroupEffectResult, ...]
    interactions: tuple[InteractionEffectResult, ...]
    global_heterogeneity: GlobalHeterogeneityEvidence
    multiplicity: MultiplicityContext
    global_overlap: DMLOverlapDiagnostic | None
    fold_plan: DMLFoldPlan | None
    fold_fits: tuple[DMLFoldFitProvenance, ...]
    nuisance_diagnostics: DMLNuisanceDiagnostics | None
    assignment_fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None
    raw_count: NonNegativeCount
    retained_count: NonNegativeCount
    unassigned_count: NonNegativeCount
    assumptions: tuple[CausalAssumption, ...]
    diagnostics: tuple[HTEDiagnostic, ...]
    provenance: ProvenanceRecords
    adapter_provenance: AdvancedAdapterProvenance | None = None
    abstention_reason: NonEmptyStr | None = None


__all__ = [
    "GlobalHeterogeneityEvidence",
    "HTEDiagnostic",
    "HTEDiagnosticStatus",
    "HTEEvidenceStatus",
    "HTEStatus",
    "HTESubgroupStatus",
    "HeterogeneousEffectResult",
    "InteractionEffectResult",
    "MultiplicityContext",
    "SubgroupEffectResult",
    "SubgroupSampleCounts",
]
