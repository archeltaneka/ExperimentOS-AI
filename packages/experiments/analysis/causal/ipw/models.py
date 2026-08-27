"""ExperimentOS-owned contracts for inverse-probability-weighted effects."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ...base import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    OpenProbability,
    PositiveFiniteFloat,
    Probability,
)
from ...provenance import AnalysisWarning, DiagnosticSeverity, ProvenanceRecords
from ...uncertainty import ConfidenceInterval
from ..adjustment import AdjustmentSet
from ..assumptions import CausalAssumption
from ..designs import CausalOutcome
from ..diagnostics import EvidenceLimitation
from ..estimands import (
    CausalEstimand,
    CausalEstimandKind,
    EffectScale,
    TargetPopulation,
    TreatmentContrast,
)
from ..models import IdentificationResult, ObservationalAnalysisRequest
from ..propensity import (
    BalanceDiagnostics,
    DistributionSummary,
    EffectiveSampleSizeDiagnostic,
    OverlapDiagnostic,
    PropensityConfig,
    PropensityDiagnosticStatus,
    PropensityEncodingMetadata,
    PropensityFitStatus,
    PropensityModelProvenance,
    PropensityResult,
    PropensityScoreDiagnostics,
    PropensityWeight,
)

type NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class IPWVarianceMethod(StrEnum):
    """Supported V1 analytic variance convention."""

    FIXED_PROPENSITY_HAJEK_HC1 = "fixed_propensity_hajek_hc1"


class IPWStatus(StrEnum):
    """Terminal state of one observational weighting execution."""

    COMPLETED = "completed"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class IPWCausalStatus(StrEnum):
    """Interpretation state kept separate from numerical availability."""

    CONDITIONAL_ON_DECLARED_ASSUMPTIONS = "conditional_on_declared_assumptions"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class IPWBalanceStatus(StrEnum):
    """Aggregate interpretation of post-weighting measured-covariate balance."""

    ACCEPTABLE = "acceptable"
    CONCERN = "concern"
    SEVERE = "severe"
    UNAVAILABLE = "unavailable"


class IPWWeightSetKind(StrEnum):
    """Stable label for each retained weight representation."""

    RAW = "raw"
    STABILIZED = "stabilized"
    PRE_CLIPPING = "pre_clipping"
    ESTIMATION = "estimation"


class IPWDiagnosticCategory(StrEnum):
    """Stable diagnostic families for observational weighting."""

    IDENTIFICATION = "identification"
    PROPENSITY = "propensity"
    BINDING = "binding"
    OUTCOME = "outcome"
    OVERLAP = "overlap"
    WEIGHT = "weight"
    BALANCE = "balance"
    INFERENCE = "inference"


class IPWSensitivityCode(StrEnum):
    """Structured diagnostics that do not correct the estimate."""

    EXTREME_WEIGHTS = "extreme_weights"
    POOR_OVERLAP = "poor_overlap"
    LOW_ESS = "low_ess"
    RESIDUAL_IMBALANCE = "residual_imbalance"
    HEAVY_CLIPPING = "heavy_clipping"
    TREATMENT_PREVALENCE_IMBALANCE = "treatment_prevalence_imbalance"
    PROPENSITY_CONVERGENCE_CONCERNS = "propensity_convergence_concerns"
    IDENTIFICATION_ASSUMPTIONS_UNVERIFIED = "identification_assumptions_unverified"


class IPWWeightClippingConfig(ContractModel):
    """Explicit upper cap for the configured estimation weights."""

    maximum: PositiveFiniteFloat


class IPWOutcomeBinding(ContractModel):
    """Explicit mapping from the declared outcome to one table column."""

    outcome_column: NonEmptyStr


class IPWConfig(ContractModel):
    """Central deterministic weighting and interpretation policy."""

    stabilized: bool = False
    clipping: IPWWeightClippingConfig | None = None
    confidence_level: OpenProbability = 0.95
    severe_balance_threshold: NonNegativeFiniteFloat = 0.25
    heavy_clipping_fraction: Probability = 0.10
    prevalence_warning_lower: Probability = 0.10
    prevalence_warning_upper: Probability = 0.90
    analysis_version: Literal["ipw-v1"] = "ipw-v1"

    @model_validator(mode="after")
    def validate_policy_ordering(self) -> Self:
        if self.severe_balance_threshold <= 0.10:
            raise ValueError("severe balance threshold must exceed the advisory threshold")
        if self.prevalence_warning_lower >= self.prevalence_warning_upper:
            raise ValueError("prevalence warning lower bound must be less than upper bound")
        return self


class IPWExecutionRequest(ContractModel):
    """Estimator input that cannot omit identification or propensity diagnostics."""

    schema_version: Literal["1"] = "1"
    identification_result: IdentificationResult
    propensity_result: PropensityResult
    binding: IPWOutcomeBinding
    configuration: IPWConfig = IPWConfig()

    @property
    def request_id(self) -> str:
        """Return the identity supplied by causal identification."""
        return self.identification_result.request_id


class IPWTestResult(ContractModel):
    """Owned frequentist inference conditional on fitted propensity scores."""

    variance_method: IPWVarianceMethod
    propensity_scores_treated_as_fixed: Literal[True] = True
    finite_sample_correction: Literal["arm_n_over_n_minus_one"] = (
        "arm_n_over_n_minus_one"
    )
    reference_distribution: Literal["standard_normal"] = "standard_normal"
    degrees_of_freedom: None = None
    standard_error: NonNegativeFiniteFloat
    statistic: FiniteFloat
    p_value: Probability
    null_effect: FiniteFloat = 0.0
    alternative: Literal["two_sided"] = "two_sided"
    confidence_interval: ConfidenceInterval


class IPWSampleCounts(ContractModel):
    """Raw, propensity-model, and selected estimation population counts."""

    raw_count: Annotated[int, Field(strict=True, ge=0)]
    model_count: Annotated[int, Field(strict=True, ge=0)]
    model_treated_count: Annotated[int, Field(strict=True, ge=0)]
    model_control_count: Annotated[int, Field(strict=True, ge=0)]
    complete_case_excluded_count: Annotated[int, Field(strict=True, ge=0)]
    selected_count: Annotated[int, Field(strict=True, ge=0)]
    selected_treated_count: Annotated[int, Field(strict=True, ge=0)]
    selected_control_count: Annotated[int, Field(strict=True, ge=0)]
    upstream_trimming_enabled: bool
    upstream_trimmed_count: Annotated[int, Field(strict=True, ge=0)] = 0

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        if self.model_treated_count + self.model_control_count != self.model_count:
            raise ValueError("model arm counts must equal model count")
        if self.selected_treated_count + self.selected_control_count != self.selected_count:
            raise ValueError("selected arm counts must equal selected count")
        if self.selected_count > self.model_count:
            raise ValueError("selected count must not exceed propensity model count")
        if self.upstream_trimmed_count != self.model_count - self.selected_count:
            raise ValueError("upstream trimmed count must match model minus selected count")
        return self


class IPWWeightSetDiagnostics(ContractModel):
    """One explicitly labelled unit-aligned weight set and aggregate diagnostics."""

    kind: IPWWeightSetKind
    weights: Annotated[tuple[PropensityWeight, ...], Field(min_length=1)]
    overall: DistributionSummary
    treated: DistributionSummary
    control: DistributionSummary
    ess: EffectiveSampleSizeDiagnostic


class IPWClippingDiagnostics(ContractModel):
    """Visible impact of an optional explicit maximum-weight cap."""

    enabled: bool
    configuration: IPWWeightClippingConfig | None
    affected_count: Annotated[int, Field(strict=True, ge=0)]
    treated_affected_count: Annotated[int, Field(strict=True, ge=0)]
    control_affected_count: Annotated[int, Field(strict=True, ge=0)]
    affected_proportion: Probability
    maximum_before: NonNegativeFiniteFloat
    maximum_after: NonNegativeFiniteFloat
    ess_before: EffectiveSampleSizeDiagnostic
    ess_after: EffectiveSampleSizeDiagnostic

    @model_validator(mode="after")
    def validate_configuration_shape(self) -> Self:
        if self.enabled != (self.configuration is not None):
            raise ValueError("clipping configuration is required exactly when clipping is enabled")
        if self.affected_count != self.treated_affected_count + self.control_affected_count:
            raise ValueError("arm clipping counts must equal affected count")
        return self


class IPWWeightDiagnostics(ContractModel):
    """Raw and configured estimation weights with no hidden transformations."""

    estimand: CausalEstimandKind
    treatment_prevalence: Probability
    raw_treated_formula: NonEmptyStr
    raw_control_formula: NonEmptyStr
    stabilization_rule: NonEmptyStr | None
    raw: IPWWeightSetDiagnostics
    stabilized: IPWWeightSetDiagnostics | None
    pre_clipping: IPWWeightSetDiagnostics
    estimation: IPWWeightSetDiagnostics
    clipping: IPWClippingDiagnostics


class IPWScoreModelReference(ContractModel):
    """Complete compact reference to the exact supplied propensity output."""

    fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    configuration: PropensityConfig
    model_provenance: PropensityModelProvenance | None
    encoding: PropensityEncodingMetadata | None
    score_diagnostics: PropensityScoreDiagnostics | None
    fit_status: PropensityFitStatus
    converged: bool
    score_model_version: NonEmptyStr


class IPWDiagnostic(ContractModel):
    """Privacy-safe structured estimator diagnostic."""

    code: NonEmptyStr
    category: IPWDiagnosticCategory
    severity: DiagnosticSeverity
    status: PropensityDiagnosticStatus
    message: NonEmptyStr


class IPWSensitivityFlag(ContractModel):
    """Active sensitivity evidence that is not an estimator correction."""

    code: IPWSensitivityCode
    severity: DiagnosticSeverity
    message: NonEmptyStr


class IPWAbstentionReason(ContractModel):
    """Primary reason a treatment effect was not produced."""

    code: NonEmptyStr
    message: NonEmptyStr
    missing_or_invalid_information: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]


def _canonical_model_key(model: ContractModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class TreatmentEffectResult(ContractModel):
    """Complete owned observational IPW treatment-effect result."""

    outcome_type: Literal["observational_treatment_effect"] = "observational_treatment_effect"
    schema_version: Literal["1"] = "1"
    method: Literal["ipw"] = "ipw"
    weighting_method: Literal["inverse_probability_weighting"] = (
        "inverse_probability_weighting"
    )
    request_id: NonEmptyStr
    analysis_request: ObservationalAnalysisRequest
    binding: IPWOutcomeBinding
    configuration: IPWConfig
    status: IPWStatus
    causal_status: IPWCausalStatus
    estimand: CausalEstimand | None
    treatment: TreatmentContrast | None
    outcome: CausalOutcome | None
    target_population: TargetPopulation | None
    effect_scale: EffectScale | None
    adjustment_set: AdjustmentSet | None
    point_estimate: FiniteFloat | None = None
    treatment_mean: FiniteFloat | None = None
    control_mean: FiniteFloat | None = None
    test_result: IPWTestResult | None = None
    weights: IPWWeightDiagnostics | None = None
    score_model: IPWScoreModelReference | None = None
    overlap: OverlapDiagnostic
    balance: BalanceDiagnostics | None
    balance_status: IPWBalanceStatus
    sample_counts: IPWSampleCounts
    assumptions: tuple[CausalAssumption, ...]
    evidence_limitations: tuple[EvidenceLimitation, ...]
    sensitivity_flags: tuple[IPWSensitivityFlag, ...]
    diagnostics: tuple[IPWDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    abstention_reason: IPWAbstentionReason | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> Self:
        if self.estimand is not None and self.effect_scale is not self.estimand.effect_scale:
            raise ValueError("effect scale must match the declared estimand")
        numerical_results = (
            self.point_estimate,
            self.treatment_mean,
            self.control_mean,
            self.test_result,
            self.weights,
        )
        if self.status is IPWStatus.COMPLETED:
            if any(item is None for item in numerical_results) or self.score_model is None:
                raise ValueError("completed IPW results require estimates and inference")
            if self.causal_status is not IPWCausalStatus.CONDITIONAL_ON_DECLARED_ASSUMPTIONS:
                raise ValueError("completed IPW results require conditional causal status")
            if self.abstention_reason is not None:
                raise ValueError("completed IPW results cannot contain abstention")
        else:
            if any(item is not None for item in numerical_results):
                raise ValueError("non-completed IPW results cannot contain estimates")
            if self.abstention_reason is None:
                raise ValueError("non-completed IPW results require abstention")
        return self


__all__ = [
    "IPWConfig",
    "IPWAbstentionReason",
    "IPWBalanceStatus",
    "IPWCausalStatus",
    "IPWClippingDiagnostics",
    "IPWDiagnostic",
    "IPWDiagnosticCategory",
    "IPWExecutionRequest",
    "IPWOutcomeBinding",
    "IPWSampleCounts",
    "IPWScoreModelReference",
    "IPWSensitivityCode",
    "IPWSensitivityFlag",
    "IPWStatus",
    "IPWTestResult",
    "IPWVarianceMethod",
    "IPWWeightClippingConfig",
    "IPWWeightDiagnostics",
    "IPWWeightSetDiagnostics",
    "IPWWeightSetKind",
    "TreatmentEffectResult",
]
