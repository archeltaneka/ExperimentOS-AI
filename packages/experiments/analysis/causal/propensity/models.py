"""ExperimentOS-owned contracts for propensity-score diagnostics."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self

from pydantic import Field, field_validator, model_validator

from ...base import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    PositiveFiniteFloat,
    Probability,
    ScalarValue,
)
from ...provenance import (
    AnalysisWarning,
    DiagnosticSeverity,
    ProvenanceRecords,
)
from ..assumptions import CausalAssumption
from ..diagnostics import EvidenceLimitation
from ..estimands import CausalEstimandKind
from ..models import ObservationalAnalysisRequest

type PositiveCount = Annotated[int, Field(strict=True, gt=0)]
type NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]


class PropensityFeatureKind(StrEnum):
    """Explicit feature semantics; values are never inferred from observed correlations."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class NumericScalingPolicy(StrEnum):
    """Supported numeric feature scaling policy."""

    STANDARDIZE = "standardize"


class PropensityDiagnosticCategory(StrEnum):
    """Stable diagnostic families for the propensity subsystem."""

    IDENTIFICATION = "identification"
    BINDING = "binding"
    TREATMENT = "treatment"
    COVARIATE = "covariate"
    SAMPLE = "sample"
    MODEL = "model"
    OVERLAP = "overlap"
    WEIGHT = "weight"
    BALANCE = "balance"


class PropensityDiagnosticStatus(StrEnum):
    """Observed state of one propensity diagnostic."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class PropensityDiagnostic(ContractModel):
    """Privacy-safe owned diagnostic without raw row values."""

    code: NonEmptyStr
    category: PropensityDiagnosticCategory
    severity: DiagnosticSeverity
    status: PropensityDiagnosticStatus
    message: NonEmptyStr


class QuantileValue(ContractModel):
    """One deterministic linear-interpolation quantile."""

    level: Probability
    value: FiniteFloat


class DistributionSummary(ContractModel):
    """Finite aggregate distribution summary with no unit-level payload."""

    count: PositiveCount
    mean: FiniteFloat
    standard_deviation: NonNegativeFiniteFloat | None
    minimum: FiniteFloat
    maximum: FiniteFloat
    median: FiniteFloat
    quantiles: tuple[QuantileValue, ...]
    total: FiniteFloat


class CommonSupportStatus(StrEnum):
    """Availability of the observed-range common-support intersection."""

    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


class CommonSupportDiagnostic(ContractModel):
    """Observed-range intersection and arm-specific support retention."""

    status: CommonSupportStatus
    lower: Probability | None = None
    upper: Probability | None = None
    width: Probability = 0.0
    treated_inside: Annotated[int, Field(strict=True, ge=0)] = 0
    control_inside: Annotated[int, Field(strict=True, ge=0)] = 0
    treated_outside: Annotated[int, Field(strict=True, ge=0)] = 0
    control_outside: Annotated[int, Field(strict=True, ge=0)] = 0
    total_outside: Annotated[int, Field(strict=True, ge=0)] = 0
    treated_inside_proportion: Probability = 0.0
    control_inside_proportion: Probability = 0.0


class StandardizedMeanDifference(ContractModel):
    """Owned weighted or unweighted standardized-mean-difference calculation."""

    available: bool
    treated_mean: FiniteFloat
    control_mean: FiniteFloat
    treated_variance: NonNegativeFiniteFloat
    control_variance: NonNegativeFiniteFloat
    smd: FiniteFloat | None
    warning_code: NonEmptyStr | None = None


class NumericFeatureEncoding(ContractModel):
    """Owned population-scaling metadata for one numeric adjustment feature."""

    variable_id: NonEmptyStr
    feature_name: NonEmptyStr
    mean: FiniteFloat
    scale: PositiveFiniteFloat
    zero_variance: bool


class CategoricalFeatureEncoding(ContractModel):
    """Owned deterministic one-hot semantics for one categorical adjustment feature."""

    variable_id: NonEmptyStr
    categories: Annotated[tuple[ScalarValue, ...], Field(min_length=1)]
    reference_category: ScalarValue
    model_feature_names: tuple[NonEmptyStr, ...]
    balance_feature_names: tuple[NonEmptyStr, ...]
    unseen_category_policy: Literal["error"] = "error"


class PropensityEncodingMetadata(ContractModel):
    """Complete reproducible feature order and transformations."""

    numeric: tuple[NumericFeatureEncoding, ...]
    categorical: tuple[CategoricalFeatureEncoding, ...]
    model_feature_names: tuple[NonEmptyStr, ...]
    balance_feature_names: tuple[NonEmptyStr, ...]


class PropensityFitStatus(StrEnum):
    """Normalized logistic-adapter fit state."""

    CONVERGED = "converged"
    NON_CONVERGED = "non_converged"
    FAILED = "failed"


class PropensityModelFit(ContractModel):
    """Owned scalar fit evidence with no estimator, array, or coefficient vector."""

    status: PropensityFitStatus
    converged: bool
    scores: tuple[Probability, ...]
    classes: tuple[int, ...]
    iteration_count: Annotated[int, Field(strict=True, ge=0)] | None
    solver: NonEmptyStr
    warning_codes: tuple[NonEmptyStr, ...]
    sklearn_version: NonEmptyStr
    training_accuracy: Probability | None = None
    maximum_absolute_coefficient: NonNegativeFiniteFloat | None = None
    extreme_score_fraction: Probability | None = None

    @model_validator(mode="after")
    def validate_fit_shape(self) -> Self:
        if self.status is PropensityFitStatus.CONVERGED:
            if not self.converged or not self.scores or self.classes != (0, 1):
                raise ValueError("converged fits require oriented scores and binary classes")
        elif self.converged or self.scores:
            raise ValueError("invalid fits must not expose unstable scores")
        return self


class PropensityStatus(StrEnum):
    """Terminal status of one propensity diagnostic execution."""

    COMPLETED = "completed"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class OverlapStatus(StrEnum):
    """Estimand-specific overlap policy status."""

    ACCEPTABLE = "acceptable"
    WEAK = "weak"
    SEVERE = "severe"
    UNAVAILABLE = "unavailable"


class EffectiveSampleSizeStatus(StrEnum):
    """Whether raw weights retain adequate configured information."""

    ACCEPTABLE = "acceptable"
    COLLAPSED = "collapsed"
    UNAVAILABLE = "unavailable"


class BalanceStatus(StrEnum):
    """Advisory balance state for one encoded adjustment feature."""

    BALANCED = "balanced"
    IMBALANCED = "imbalanced"
    UNAVAILABLE = "unavailable"


class PropensityScoreDiagnostics(ContractModel):
    """Aggregate score distributions for the model population and both arms."""

    overall: DistributionSummary
    treated: DistributionSummary
    control: DistributionSummary


class EffectiveSampleSizeDiagnostic(ContractModel):
    """Kish ESS overall and by treatment arm with raw-count ratios."""

    status: EffectiveSampleSizeStatus
    overall: NonNegativeFiniteFloat | None
    treated: NonNegativeFiniteFloat | None
    control: NonNegativeFiniteFloat | None
    raw_count: Annotated[int, Field(strict=True, ge=0)]
    treated_raw_count: Annotated[int, Field(strict=True, ge=0)]
    control_raw_count: Annotated[int, Field(strict=True, ge=0)]
    overall_ratio: Probability | None
    treated_ratio: Probability | None
    control_ratio: Probability | None


class PropensityWeightDiagnostics(ContractModel):
    """Unmodified estimand weights, tails, and effective sample size."""

    estimand: CausalEstimandKind
    raw: tuple[PropensityWeight, ...]
    overall: DistributionSummary
    treated: DistributionSummary
    control: DistributionSummary
    extreme_weight_count: Annotated[int, Field(strict=True, ge=0)]
    extreme_weight_proportion: Probability
    ess: EffectiveSampleSizeDiagnostic


class RetainedPopulationDiagnostics(ContractModel):
    """Population remaining after an explicit propensity-bound trimming request."""

    configuration: PropensityTrimmingConfig
    scores: tuple[PropensityScore, ...]
    retained_count: Annotated[int, Field(strict=True, ge=0)]
    treated_retained: Annotated[int, Field(strict=True, ge=0)]
    control_retained: Annotated[int, Field(strict=True, ge=0)]
    dropped_count: Annotated[int, Field(strict=True, ge=0)]
    treated_dropped: Annotated[int, Field(strict=True, ge=0)]
    control_dropped: Annotated[int, Field(strict=True, ge=0)]
    retained_proportion: Probability
    common_support: CommonSupportDiagnostic
    score_diagnostics: PropensityScoreDiagnostics | None


class CappedWeightDiagnostics(ContractModel):
    """Separately labelled weights and ESS after an explicit cap request."""

    configuration: PropensityWeightCapConfig
    weights: tuple[PropensityWeight, ...]
    overall: DistributionSummary
    treated: DistributionSummary
    control: DistributionSummary
    affected_count: Annotated[int, Field(strict=True, ge=0)]
    affected_proportion: Probability
    ess_before: EffectiveSampleSizeDiagnostic
    ess_after: EffectiveSampleSizeDiagnostic


class CovariateBalanceDiagnostic(ContractModel):
    """Raw and weighted SMD for one numeric or categorical-indicator feature."""

    variable_id: NonEmptyStr
    feature_name: NonEmptyStr
    raw: StandardizedMeanDifference
    weighted: StandardizedMeanDifference
    status: BalanceStatus
    warnings: tuple[NonEmptyStr, ...] = ()


class BalanceDiagnostics(ContractModel):
    """Feature-level balance with deterministic aggregate advisory counts."""

    features: tuple[CovariateBalanceDiagnostic, ...]
    raw_max_absolute_smd: NonNegativeFiniteFloat
    weighted_max_absolute_smd: NonNegativeFiniteFloat
    raw_above_threshold_count: Annotated[int, Field(strict=True, ge=0)]
    weighted_above_threshold_count: Annotated[int, Field(strict=True, ge=0)]
    improved_count: Annotated[int, Field(strict=True, ge=0)]
    worsened_count: Annotated[int, Field(strict=True, ge=0)]


class OverlapDiagnostic(ContractModel):
    """Central policy interpretation of common support, scores, weights, and ESS."""

    status: OverlapStatus
    target_outside_support_fraction: Probability | None
    comparator_inside_support_count: Annotated[int, Field(strict=True, ge=0)] | None
    comparator_inside_support_fraction: Probability | None
    extreme_score_count: Annotated[int, Field(strict=True, ge=0)]
    extreme_score_fraction: Probability | None
    separation_detected: bool
    diagnostic_codes: tuple[NonEmptyStr, ...]


class PropensityModelProvenance(ContractModel):
    """Reproducibility-critical score-model and encoding choices."""

    model_family: NonEmptyStr
    link: NonEmptyStr
    penalty: NonEmptyStr
    l1_ratio: FiniteFloat
    inverse_regularization_strength: PositiveFiniteFloat
    solver: NonEmptyStr
    tolerance: PositiveFiniteFloat
    maximum_iterations: PositiveCount
    fit_intercept: bool
    numeric_scaling: NumericScalingPolicy
    categorical_encoding: NonEmptyStr
    categorical_ordering: NonEmptyStr
    unseen_category_policy: NonEmptyStr
    feature_names: tuple[NonEmptyStr, ...]
    random_seed: Annotated[int, Field(strict=True, ge=0)]
    treated_value: ScalarValue
    control_value: ScalarValue
    score_orientation: Literal["P(T=1 | X), T=1 is treated_value"] = (
        "P(T=1 | X), T=1 is treated_value"
    )
    estimand: CausalEstimandKind
    trimming_enabled: bool
    weight_capping_enabled: bool
    sklearn_version: NonEmptyStr


class PropensityAbstentionReason(ContractModel):
    """Typed primary reason propensity diagnostics cannot support downstream estimation."""

    code: NonEmptyStr
    message: NonEmptyStr


class PropensityResult(ContractModel):
    """Complete owned propensity diagnostic result containing no treatment-effect estimate."""

    outcome_type: Literal["propensity_score_diagnostics"] = "propensity_score_diagnostics"
    schema_version: Literal["1"] = "1"
    method: Literal["propensity"] = "propensity"
    request_id: NonEmptyStr
    analysis_request: ObservationalAnalysisRequest
    binding: PropensityDataBinding
    configuration: PropensityConfig
    status: PropensityStatus
    estimand: CausalEstimandKind | None
    adjustment_covariates: tuple[NonEmptyStr, ...]
    encoding: PropensityEncodingMetadata | None
    model_fit: PropensityModelFit
    model_provenance: PropensityModelProvenance | None
    sample_counts: PropensitySampleCounts
    scores: tuple[PropensityScore, ...]
    score_diagnostics: PropensityScoreDiagnostics | None
    common_support: CommonSupportDiagnostic
    overlap: OverlapDiagnostic
    weights: PropensityWeightDiagnostics | None
    retained: RetainedPopulationDiagnostics | None = None
    capped_weights: CappedWeightDiagnostics | None = None
    balance: BalanceDiagnostics | None
    assumptions: tuple[CausalAssumption, ...]
    evidence_limitations: tuple[EvidenceLimitation, ...]
    diagnostics: tuple[PropensityDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    abstention_reason: PropensityAbstentionReason | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> Self:
        if self.status is PropensityStatus.COMPLETED and self.abstention_reason is not None:
            raise ValueError("completed propensity results cannot contain abstention")
        if self.status is not PropensityStatus.COMPLETED and self.abstention_reason is None:
            raise ValueError("non-completed propensity results require abstention")
        if self.model_fit.status is not PropensityFitStatus.CONVERGED:
            if self.scores or self.score_diagnostics is not None or self.weights is not None:
                raise ValueError("invalid fits must not expose scores or weights")
        if self.status is PropensityStatus.COMPLETED:
            if self.model_fit.status is not PropensityFitStatus.CONVERGED:
                raise ValueError("completed propensity results require a converged model")
            if self.overlap.status not in {OverlapStatus.ACCEPTABLE, OverlapStatus.WEAK}:
                raise ValueError("completed propensity results require usable overlap")
            if (
                self.weights is None
                or self.weights.ess.status is not EffectiveSampleSizeStatus.ACCEPTABLE
            ):
                raise ValueError("completed propensity results require acceptable weighted ESS")
            if any(item.severity is DiagnosticSeverity.FATAL for item in self.diagnostics):
                raise ValueError("completed propensity results cannot contain fatal diagnostics")
        return self


class PropensityEstimator(Protocol):
    """ExperimentOS-owned estimator abstraction independent of fitting libraries."""

    def supports(self, execution: PropensityExecutionRequest) -> bool:
        """Return whether the declared estimand/design is in the estimator's bounded scope."""

    def fit_predict(
        self,
        execution: PropensityExecutionRequest,
        table: object,
        **kwargs: object,
    ) -> PropensityResult:
        """Fit scores and return owned diagnostics without estimating a treatment effect."""


class PropensityTrimmingConfig(ContractModel):
    """Explicit inclusive score bounds for an optional retained population."""

    lower: Probability
    upper: Probability

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.lower >= self.upper:
            raise ValueError("trimming lower bound must be less than upper bound")
        return self


class PropensityWeightCapConfig(ContractModel):
    """Explicit optional upper bound for a separately labelled capped weight population."""

    maximum: PositiveFiniteFloat


class PropensityConfig(ContractModel):
    """Central deterministic model and diagnostic policy."""

    model_family: Literal["regularized_logistic_regression"] = "regularized_logistic_regression"
    link: Literal["logit"] = "logit"
    penalty: Literal["l2"] = "l2"
    l1_ratio: FiniteFloat = 0.0
    inverse_regularization_strength: PositiveFiniteFloat = 1.0
    solver: Literal["lbfgs"] = "lbfgs"
    tolerance: PositiveFiniteFloat = 1e-8
    maximum_iterations: PositiveCount = 1000
    fit_intercept: Literal[True] = True
    numeric_scaling: NumericScalingPolicy = NumericScalingPolicy.STANDARDIZE
    categorical_encoding: Literal["one_hot_drop_first"] = "one_hot_drop_first"
    categorical_ordering: Literal["typed_canonical_ascending"] = "typed_canonical_ascending"
    unseen_category_policy: Literal["error"] = "error"
    complete_case: Literal[True] = True
    random_seed: Annotated[int, Field(strict=True, ge=0)] = 0
    score_quantiles: tuple[Probability, ...] = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)
    weight_quantiles: tuple[Probability, ...] = (0.5, 0.9, 0.95, 0.99)
    extreme_score_threshold: Annotated[Probability, Field(gt=0, lt=0.5)] = 0.05
    weak_extreme_score_fraction: Probability = 0.05
    severe_extreme_score_fraction: Probability = 0.20
    weak_outside_support_fraction: Probability = 0.10
    severe_outside_support_fraction: Probability = 0.25
    weak_support_width: Annotated[Probability, Field(gt=0)] = 0.20
    severe_support_width: Annotated[Probability, Field(gt=0)] = 0.05
    extreme_weight_threshold: PositiveFiniteFloat = 10.0
    weak_extreme_weight_fraction: Probability = 0.01
    severe_extreme_weight_fraction: Probability = 0.20
    minimum_att_control_support_count: PositiveCount = 1
    minimum_att_control_support_proportion: Probability = 0.10
    minimum_effective_sample_size: PositiveFiniteFloat = 10.0
    minimum_ess_ratio: Probability = 0.25
    balance_threshold: NonNegativeFiniteFloat = 0.10
    separation_accuracy_threshold: Annotated[Probability, Field(gt=0)] = 0.99
    separation_coefficient_threshold: PositiveFiniteFloat = 20.0
    separation_extreme_fraction: Probability = 0.20
    trimming: PropensityTrimmingConfig | None = None
    weight_cap: PropensityWeightCapConfig | None = None

    @field_validator("score_quantiles", "weight_quantiles")
    @classmethod
    def validate_quantiles(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value or tuple(sorted(value)) != value or len(set(value)) != len(value):
            raise ValueError("quantile levels must be unique and sorted")
        return value

    @model_validator(mode="after")
    def validate_policy_ordering(self) -> Self:
        if self.l1_ratio != 0.0:
            raise ValueError("V1 requires l1_ratio 0.0 for L2 regularization")
        if self.severe_outside_support_fraction <= self.weak_outside_support_fraction:
            raise ValueError("severe outside-support threshold must exceed weak threshold")
        if self.severe_support_width >= self.weak_support_width:
            raise ValueError("severe support width must be smaller than weak support width")
        if self.severe_extreme_score_fraction <= self.weak_extreme_score_fraction:
            raise ValueError("severe extreme-score threshold must exceed weak threshold")
        if self.severe_extreme_weight_fraction <= self.weak_extreme_weight_fraction:
            raise ValueError("severe extreme-weight threshold must exceed weak threshold")
        return self


class PropensityCovariateBinding(ContractModel):
    """Explicit mapping from one declared adjustment variable to one table column."""

    variable_id: NonEmptyStr
    column: NonEmptyStr
    feature_kind: PropensityFeatureKind


class PropensityDataBinding(ContractModel):
    """Explicit table roles for one propensity-score execution."""

    unit_column: NonEmptyStr
    treatment_column: NonEmptyStr
    covariates: Annotated[tuple[PropensityCovariateBinding, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_roles(self) -> Self:
        variable_ids = tuple(item.variable_id for item in self.covariates)
        columns = tuple(item.column for item in self.covariates)
        if len(variable_ids) != len(set(variable_ids)):
            raise ValueError("covariate variable identifiers must be unique")
        if len(columns) != len(set(columns)):
            raise ValueError("covariate columns must be unique")
        role_columns = (self.unit_column, self.treatment_column, *columns)
        if len(role_columns) != len(set(role_columns)):
            raise ValueError("unit, treatment, and covariate columns must be unique")
        return self


class PropensityExecutionRequest(ContractModel):
    """Estimator request that cannot bypass the observational identification envelope."""

    schema_version: Literal["1"] = "1"
    analysis_request: ObservationalAnalysisRequest
    binding: PropensityDataBinding
    configuration: PropensityConfig = PropensityConfig()

    @property
    def request_id(self) -> str:
        """Return the identity owned by the observational request."""
        return self.analysis_request.request_id


class PropensitySampleCounts(ContractModel):
    """Raw and complete-case model-population counts kept explicitly separate."""

    raw: Annotated[int, Field(strict=True, ge=0)] = 0
    raw_treated: Annotated[int, Field(strict=True, ge=0)] = 0
    raw_control: Annotated[int, Field(strict=True, ge=0)] = 0
    model: Annotated[int, Field(strict=True, ge=0)] = 0
    model_treated: Annotated[int, Field(strict=True, ge=0)] = 0
    model_control: Annotated[int, Field(strict=True, ge=0)] = 0
    complete_case_excluded: Annotated[int, Field(strict=True, ge=0)] = 0
    treated_excluded: Annotated[int, Field(strict=True, ge=0)] = 0
    control_excluded: Annotated[int, Field(strict=True, ge=0)] = 0
    retention_proportion: Probability = 0.0

    @model_validator(mode="after")
    def validate_count_relationships(self) -> Self:
        if self.raw_treated + self.raw_control > self.raw:
            raise ValueError("raw arm counts must not exceed raw count")
        if self.model_treated + self.model_control != self.model:
            raise ValueError("model arm counts must equal model count")
        if self.model + self.complete_case_excluded > self.raw:
            raise ValueError("model and excluded counts must not exceed raw count")
        return self


class PropensityScore(ContractModel):
    """One aligned internal/result propensity score with explicit treatment orientation."""

    unit_id: ScalarValue
    treated: bool
    score: Probability


class PropensityWeight(ContractModel):
    """One aligned nonnegative diagnostic weight; never an effect contribution."""

    unit_id: ScalarValue
    treated: bool
    value: NonNegativeFiniteFloat


__all__ = [
    "CommonSupportDiagnostic",
    "CommonSupportStatus",
    "DistributionSummary",
    "BalanceDiagnostics",
    "BalanceStatus",
    "CovariateBalanceDiagnostic",
    "CappedWeightDiagnostics",
    "EffectiveSampleSizeDiagnostic",
    "EffectiveSampleSizeStatus",
    "CategoricalFeatureEncoding",
    "NumericScalingPolicy",
    "NumericFeatureEncoding",
    "PropensityConfig",
    "PropensityAbstentionReason",
    "PropensityCovariateBinding",
    "PropensityDataBinding",
    "PropensityDiagnostic",
    "PropensityDiagnosticCategory",
    "PropensityDiagnosticStatus",
    "PropensityExecutionRequest",
    "PropensityEstimator",
    "PropensityFeatureKind",
    "PropensityFitStatus",
    "PropensityEncodingMetadata",
    "PropensityModelFit",
    "PropensityModelProvenance",
    "PropensityResult",
    "RetainedPopulationDiagnostics",
    "PropensitySampleCounts",
    "PropensityScore",
    "PropensityScoreDiagnostics",
    "PropensityStatus",
    "PropensityTrimmingConfig",
    "PropensityWeight",
    "PropensityWeightDiagnostics",
    "PropensityWeightCapConfig",
    "QuantileValue",
    "StandardizedMeanDifference",
    "OverlapDiagnostic",
    "OverlapStatus",
]
