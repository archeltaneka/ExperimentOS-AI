"""Owned contracts for deterministic Double Machine Learning."""

from __future__ import annotations

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
from ...provenance import DiagnosticSeverity
from ...uncertainty import ConfidenceInterval
from ..models import IdentificationResult
from ..propensity.models import (
    CommonSupportDiagnostic,
    DistributionSummary,
    OverlapStatus,
    PropensityScoreDiagnostics,
)

type NonNegativeFiniteFloat = Annotated[
    float,
    Field(strict=True, ge=0.0, allow_inf_nan=False),
]
type PositiveCount = Annotated[int, Field(strict=True, gt=0)]
type NonNegativeCount = Annotated[int, Field(strict=True, ge=0)]


class DMLConfig(ContractModel):
    """Central deterministic folding, numerical, overlap, and inference policy."""

    fold_count: Annotated[int, Field(strict=True, ge=2)]
    random_seed: Annotated[int, Field(strict=True, ge=0)]
    confidence_level: OpenProbability = 0.95
    complete_case: Literal[True] = True
    minimum_training_rows: PositiveCount = 4
    minimum_scoring_rows: PositiveCount = 2
    treatment_residual_tolerance: NonNegativeFiniteFloat = 1e-12
    outcome_residual_variance_tolerance: NonNegativeFiniteFloat = 1e-12
    extreme_score_threshold: Annotated[Probability, Field(gt=0.0, lt=0.5)] = 0.05
    weak_extreme_score_fraction: Probability = 0.05
    severe_extreme_score_fraction: Probability = 0.20
    weak_outside_support_fraction: Probability = 0.10
    severe_outside_support_fraction: Probability = 0.25
    weak_support_width: Annotated[Probability, Field(gt=0.0)] = 0.20
    severe_support_width: Annotated[Probability, Field(gt=0.0)] = 0.05
    score_quantiles: tuple[Probability, ...] = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)
    metric_probability_clip: Annotated[float, Field(strict=True, gt=0.0, lt=0.5)] = 1e-15
    analysis_version: Literal["dml-v1"] = "dml-v1"

    @field_validator("score_quantiles")
    @classmethod
    def validate_quantiles(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value or tuple(sorted(value)) != value or len(value) != len(set(value)):
            raise ValueError("DML score quantiles must be unique and sorted")
        return value

    @model_validator(mode="after")
    def validate_policy_ordering(self) -> Self:
        if self.severe_extreme_score_fraction <= self.weak_extreme_score_fraction:
            raise ValueError("severe extreme-score fraction must exceed weak fraction")
        if self.severe_outside_support_fraction <= self.weak_outside_support_fraction:
            raise ValueError("severe outside-support fraction must exceed weak fraction")
        if self.severe_support_width >= self.weak_support_width:
            raise ValueError("severe support width must be smaller than weak width")
        return self


class DMLVarianceMethod(StrEnum):
    """Supported orthogonal-score influence variance convention."""

    ORTHOGONAL_SCORE_INFLUENCE_HC1 = "orthogonal_score_influence_hc1"


class DMLTestResult(ContractModel):
    """Frequentist inference for the supported partialling-out score."""

    variance_method: DMLVarianceMethod
    finite_sample_correction: Literal["n_over_n_minus_one"] = "n_over_n_minus_one"
    reference_distribution: Literal["standard_normal"] = "standard_normal"
    standard_error: NonNegativeFiniteFloat
    statistic: FiniteFloat
    p_value: Probability
    null_effect: FiniteFloat = 0.0
    alternative: Literal["two_sided"] = "two_sided"
    confidence_interval: ConfidenceInterval
    interval_method: Literal["standard_normal_influence_function"] = (
        "standard_normal_influence_function"
    )


class DMLResidualSummary(ContractModel):
    """Aggregate residual distribution and variation diagnostics."""

    count: PositiveCount
    mean: FiniteFloat
    standard_deviation: NonNegativeFiniteFloat
    minimum: FiniteFloat
    maximum: FiniteFloat
    variance: NonNegativeFiniteFloat
    squared_norm: NonNegativeFiniteFloat
    nonfinite_count: NonNegativeCount


class DMLInfluenceDiagnostics(ContractModel):
    """Safe aggregate influence diagnostics without observation-level values."""

    count: PositiveCount
    variance: NonNegativeFiniteFloat
    maximum_absolute: NonNegativeFiniteFloat
    nonfinite_count: NonNegativeCount


class DMLOutcomeNuisanceDiagnostics(ContractModel):
    """Cross-fitted outcome predictive metrics, not causal-validity evidence."""

    rmse: NonNegativeFiniteFloat
    mae: NonNegativeFiniteFloat
    r_squared: FiniteFloat | None


class DMLTreatmentNuisanceDiagnostics(ContractModel):
    """Cross-fitted treatment predictive metrics and score distribution."""

    log_loss: NonNegativeFiniteFloat
    brier_score: NonNegativeFiniteFloat
    roc_auc: Probability | None
    score_distribution: DistributionSummary


class DMLNuisanceDiagnostics(ContractModel):
    """Predictive diagnostics kept explicitly separate from identification evidence."""

    outcome: DMLOutcomeNuisanceDiagnostics
    treatment: DMLTreatmentNuisanceDiagnostics
    interpretation: NonEmptyStr


class DMLOverlapDiagnostic(ContractModel):
    """DML-specific interpretation of cross-fitted treatment-score overlap."""

    status: OverlapStatus
    common_support: CommonSupportDiagnostic
    score_diagnostics: PropensityScoreDiagnostics
    target_outside_support_fraction: Probability | None
    extreme_score_count: NonNegativeCount
    extreme_score_fraction: Probability
    diagnostic_codes: tuple[NonEmptyStr, ...]


class DMLCovariateBinding(ContractModel):
    """Map one declared numeric adjustment variable to a table column."""

    variable_id: NonEmptyStr
    column: NonEmptyStr


class DMLDataBinding(ContractModel):
    """Explicit table columns used by the supported DML design."""

    observation_id_column: NonEmptyStr
    treatment_variable_id: NonEmptyStr
    treatment_column: NonEmptyStr
    outcome_variable_id: NonEmptyStr
    outcome_column: NonEmptyStr
    covariates: Annotated[tuple[DMLCovariateBinding, ...], Field(min_length=1)]

    @field_validator("covariates")
    @classmethod
    def require_unique_covariates(
        cls,
        value: tuple[DMLCovariateBinding, ...],
    ) -> tuple[DMLCovariateBinding, ...]:
        if len(value) != len({item.variable_id for item in value}):
            raise ValueError("DML covariate variable IDs must be unique")
        if len(value) != len({item.column for item in value}):
            raise ValueError("DML covariate columns must be unique")
        return value

    @model_validator(mode="after")
    def require_distinct_role_columns(self) -> Self:
        role_columns = {
            self.observation_id_column,
            self.treatment_column,
            self.outcome_column,
        }
        if len(role_columns) != 3:
            raise ValueError("DML identity, treatment, and outcome columns must differ")
        if role_columns & {item.column for item in self.covariates}:
            raise ValueError("DML covariates cannot reuse identity, treatment, or outcome columns")
        variable_ids = {
            self.treatment_variable_id,
            self.outcome_variable_id,
            *(item.variable_id for item in self.covariates),
        }
        if len(variable_ids) != len(self.covariates) + 2:
            raise ValueError("DML treatment, outcome, and covariate variable IDs must differ")
        return self


class DMLExecutionRequest(ContractModel):
    """Estimator input that cannot omit issue #97 identification."""

    schema_version: Literal["1"] = "1"
    identification_result: IdentificationResult
    binding: DMLDataBinding
    configuration: DMLConfig

    @property
    def request_id(self) -> str:
        return self.identification_result.request_id


class DMLDiagnosticCategory(StrEnum):
    """Stable diagnostic families for the DML estimator."""

    IDENTIFICATION = "identification"
    BINDING = "binding"
    TREATMENT = "treatment"
    OUTCOME = "outcome"
    COVARIATE = "covariate"
    SAMPLE = "sample"
    FOLD = "fold"
    NUISANCE = "nuisance"
    OVERLAP = "overlap"
    RESIDUAL = "residual"
    INFERENCE = "inference"


class DMLDiagnosticStatus(StrEnum):
    """Observed state of one DML diagnostic."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class DMLDiagnostic(ContractModel):
    """Privacy-safe structured DML diagnostic."""

    code: NonEmptyStr
    category: DMLDiagnosticCategory
    severity: DiagnosticSeverity
    status: DMLDiagnosticStatus
    message: NonEmptyStr


class DMLSampleCounts(ContractModel):
    """Raw and complete-case DML population counts."""

    raw_count: NonNegativeCount
    retained_count: NonNegativeCount
    treated_count: NonNegativeCount
    control_count: NonNegativeCount
    complete_case_excluded_count: NonNegativeCount

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        if self.treated_count + self.control_count != self.retained_count:
            raise ValueError("DML arm counts must equal retained count")
        if self.retained_count + self.complete_case_excluded_count != self.raw_count:
            raise ValueError("DML retained and excluded counts must equal raw count")
        return self


class DMLFoldAssignment(ContractModel):
    """Stable observation-to-score-fold membership."""

    observation_id: ScalarValue
    fold_index: NonNegativeCount


class DMLFoldSummary(ContractModel):
    """Aggregate score and training-complement counts for one fold."""

    fold_index: NonNegativeCount
    score_count: PositiveCount
    score_treated_count: PositiveCount
    score_control_count: PositiveCount
    train_count: PositiveCount
    train_treated_count: PositiveCount
    train_control_count: PositiveCount


class DMLFoldPlan(ContractModel):
    """Complete deterministic cross-fitting plan and mutation fingerprint."""

    fold_count: Annotated[int, Field(strict=True, ge=2)]
    random_seed: Annotated[int, Field(strict=True, ge=0)]
    split_method: Literal["deterministic_stratified_sha256_round_robin"] = (
        "deterministic_stratified_sha256_round_robin"
    )
    split_version: Literal["dml-stratified-sha256-v1"] = "dml-stratified-sha256-v1"
    stratification_policy: Literal["binary_treatment"] = "binary_treatment"
    assignments: tuple[DMLFoldAssignment, ...]
    summaries: tuple[DMLFoldSummary, ...]
    fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


__all__ = [
    "DMLConfig",
    "DMLCovariateBinding",
    "DMLDataBinding",
    "DMLDiagnostic",
    "DMLDiagnosticCategory",
    "DMLDiagnosticStatus",
    "DMLExecutionRequest",
    "DMLFoldAssignment",
    "DMLFoldPlan",
    "DMLFoldSummary",
    "DMLInfluenceDiagnostics",
    "DMLNuisanceDiagnostics",
    "DMLOverlapDiagnostic",
    "DMLOutcomeNuisanceDiagnostics",
    "DMLResidualSummary",
    "DMLSampleCounts",
    "DMLTestResult",
    "DMLTreatmentNuisanceDiagnostics",
    "DMLVarianceMethod",
]
