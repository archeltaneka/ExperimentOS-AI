"""Frozen public contracts for single-covariate CUPED analysis."""

from __future__ import annotations

import json
import math
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ...base import ContractModel, FiniteFloat, NonEmptyStr, PositiveInt, Probability
from ...provenance import AnalysisWarning, AssumptionAssessment, ProvenanceRecords
from ...requests import AnalysisRequest
from ...study_designs import CovariateDefinition
from ..models import (
    AlternativeHypothesis,
    ComputationStatus,
    RandomizedAnalysisResult,
    RandomizedDiagnostic,
)

type NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
type NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]
type Correlation = Annotated[FiniteFloat, Field(ge=-1, le=1)]


class CupedStatus(StrEnum):
    """Terminal state of the requested CUPED calculation."""

    COMPLETED = "completed"
    NO_IMPROVEMENT = "no_improvement"
    DEGRADED_PRECISION = "degraded_precision"
    INCONCLUSIVE = "inconclusive"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"


class VarianceReductionStatus(StrEnum):
    """Sign or availability of the same-sample estimator variance comparison."""

    POSITIVE_REDUCTION = "positive_reduction"
    NO_REDUCTION = "no_reduction"
    NEGATIVE_REDUCTION = "negative_reduction"
    UNAVAILABLE = "unavailable"


class CovariateBalanceStatus(StrEnum):
    """Descriptive treatment-by-covariate mean-balance state."""

    EXACTLY_BALANCED = "exactly_balanced"
    OBSERVED_DIFFERENCE = "observed_difference"
    UNAVAILABLE = "unavailable"


class RetainedArmSummary(ContractModel):
    """Complete-case retention and CUPED missingness for one arm."""

    original_count: NonNegativeInt
    retained_count: NonNegativeInt
    removed_count: NonNegativeInt
    missing_covariate_count: NonNegativeInt
    retained_proportion: Probability
    missing_covariate_rate: Probability

    @model_validator(mode="after")
    def validate_counts_and_rates(self) -> Self:
        if self.retained_count + self.removed_count != self.original_count:
            raise ValueError("retained_count plus removed_count must equal original_count")
        if self.missing_covariate_count > self.removed_count:
            raise ValueError("missing_covariate_count must not exceed removed_count")
        expected_retention = (
            self.retained_count / self.original_count if self.original_count else 0.0
        )
        expected_missingness = (
            self.missing_covariate_count / self.original_count if self.original_count else 0.0
        )
        if not _same_probability(self.retained_proportion, expected_retention):
            raise ValueError("retained_proportion must match arm counts")
        if not _same_probability(self.missing_covariate_rate, expected_missingness):
            raise ValueError("missing_covariate_rate must match arm counts")
        return self


class CupedSampleRetention(ContractModel):
    """Original and complete-case analysis populations without row-level data."""

    policy: Literal["complete_case"] = "complete_case"
    original_total: NonNegativeInt
    retained_total: NonNegativeInt
    removed_total: NonNegativeInt
    retained_proportion: Probability
    treatment: RetainedArmSummary
    control: RetainedArmSummary

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        if self.retained_total + self.removed_total != self.original_total:
            raise ValueError("retained_total plus removed_total must equal original_total")
        if self.original_total != self.treatment.original_count + self.control.original_count:
            raise ValueError("original_total must equal the sum of original arm counts")
        if self.retained_total != self.treatment.retained_count + self.control.retained_count:
            raise ValueError("retained_total must equal the sum of retained arm counts")
        if self.removed_total != self.treatment.removed_count + self.control.removed_count:
            raise ValueError("removed_total must equal the sum of removed arm counts")
        expected = self.retained_total / self.original_total if self.original_total else 0.0
        if not _same_probability(self.retained_proportion, expected):
            raise ValueError("retained_proportion must match total counts")
        return self


class CupedCoefficient(ContractModel):
    """Reported pooled CUPED coefficient and its calculation convention."""

    theta: FiniteFloat
    covariance: FiniteFloat
    covariate_variance: Annotated[FiniteFloat, Field(gt=0)]
    covariate_mean: FiniteFloat
    outcome_variance: NonNegativeFiniteFloat
    correlation: Correlation | None
    sample_size: PositiveInt
    degrees_of_freedom_correction: Literal[1] = 1
    coefficient_provenance: Literal["pooled_complete_case_without_arm_specific_fit"] = (
        "pooled_complete_case_without_arm_specific_fit"
    )
    centering_convention: Literal["pooled_complete_case_covariate_mean"] = (
        "pooled_complete_case_covariate_mean"
    )
    covariance_convention: Literal["sample_n_minus_one"] = "sample_n_minus_one"
    variance_convention: Literal["sample_n_minus_one"] = "sample_n_minus_one"

    @model_validator(mode="after")
    def validate_correlation_availability(self) -> Self:
        if self.outcome_variance == 0.0 and self.correlation is not None:
            raise ValueError("zero outcome variance requires unavailable correlation")
        if self.sample_size < 2:
            raise ValueError("coefficient estimation requires at least two observations")
        return self


class CupedCovariateBalance(ContractModel):
    """Descriptive retained-sample treatment-by-covariate balance."""

    status: CovariateBalanceStatus
    treatment_count: PositiveInt
    control_count: PositiveInt
    treatment_mean: FiniteFloat
    control_mean: FiniteFloat
    treatment_variance: NonNegativeFiniteFloat
    control_variance: NonNegativeFiniteFloat
    pooled_standard_deviation: NonNegativeFiniteFloat
    standardized_mean_difference: FiniteFloat | None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        means_equal = self.treatment_mean == self.control_mean
        if self.status is CovariateBalanceStatus.EXACTLY_BALANCED and not means_equal:
            raise ValueError("exactly_balanced requires equal arm means")
        if self.status is CovariateBalanceStatus.OBSERVED_DIFFERENCE and means_equal:
            raise ValueError("observed_difference requires unequal arm means")
        if self.status is CovariateBalanceStatus.UNAVAILABLE:
            if self.standardized_mean_difference is not None:
                raise ValueError("unavailable balance must not include a standardized difference")
        elif self.pooled_standard_deviation > 0.0:
            if self.standardized_mean_difference is None:
                raise ValueError("positive pooled variation requires a standardized difference")
        return self


class VarianceReduction(ContractModel):
    """Same-retained-sample comparison using squared Welch standard errors."""

    estimator_variance_convention: Literal["squared_standard_error"] = "squared_standard_error"
    status: VarianceReductionStatus
    unadjusted_estimator_variance: NonNegativeFiniteFloat | None
    adjusted_estimator_variance: NonNegativeFiniteFloat | None
    fraction: FiniteFloat | None
    percentage: FiniteFloat | None

    @model_validator(mode="after")
    def validate_shape_and_sign(self) -> Self:
        values = (
            self.unadjusted_estimator_variance,
            self.adjusted_estimator_variance,
            self.fraction,
            self.percentage,
        )
        if self.status is VarianceReductionStatus.UNAVAILABLE:
            if any(value is not None for value in values):
                raise ValueError("unavailable variance reduction must not include numeric values")
            return self
        if any(value is None for value in values):
            raise ValueError("available variance reduction requires every numeric value")
        if self.fraction is None or self.percentage is None:
            raise RuntimeError("validated variance reduction is missing values")
        if not math.isclose(
            self.percentage,
            self.fraction * 100.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("percentage must equal fraction multiplied by one hundred")
        expected_status = (
            VarianceReductionStatus.POSITIVE_REDUCTION
            if self.fraction > 0.0
            else VarianceReductionStatus.NEGATIVE_REDUCTION
            if self.fraction < 0.0
            else VarianceReductionStatus.NO_REDUCTION
        )
        if self.status is not expected_status:
            raise ValueError("variance-reduction status must match the fraction sign")
        return self


class CupedAbstentionReason(ContractModel):
    """Typed explanation for unavailable CUPED inference."""

    code: NonEmptyStr
    message: NonEmptyStr
    missing_or_invalid_information: tuple[NonEmptyStr, ...]


class CupedAnalysisExecutionRequest(ContractModel):
    """Explicit request envelope for the single-covariate CUPED service."""

    request_id: NonEmptyStr
    analysis_request: AnalysisRequest
    alternative: AlternativeHypothesis = AlternativeHypothesis.TWO_SIDED


class CupedAnalysisResult(ContractModel):
    """Complete CUPED result with retained and full-sample references."""

    outcome_type: Literal["cuped_analysis"] = "cuped_analysis"
    schema_version: Literal["1"] = "1"
    request_id: NonEmptyStr
    analysis_request: AnalysisRequest
    adjustment_method: Literal["cuped"] = "cuped"
    status: CupedStatus
    baseline_status: ComputationStatus
    covariate: CovariateDefinition | None
    retention: CupedSampleRetention | None
    coefficient: CupedCoefficient | None
    balance: CupedCovariateBalance | None
    adjusted_result: RandomizedAnalysisResult | None
    comparable_unadjusted_result: RandomizedAnalysisResult | None
    full_sample_unadjusted_result: RandomizedAnalysisResult
    variance_reduction: VarianceReduction
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[RandomizedDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    abstention_reason: CupedAbstentionReason | None = None

    @model_validator(mode="before")
    @classmethod
    def canonicalize_diagnostics(cls, data: object) -> object:
        if not isinstance(data, dict) or "diagnostics" not in data:
            return data
        copied = dict(data)
        copied["diagnostics"] = tuple(
            sorted(
                copied["diagnostics"],
                key=lambda diagnostic: json.dumps(
                    diagnostic.model_dump(mode="json")
                    if isinstance(diagnostic, RandomizedDiagnostic)
                    else diagnostic,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
        )
        return copied

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        if self.covariate is not None and self.covariate not in self.analysis_request.covariates:
            raise ValueError("covariate must be declared by analysis_request")
        if self.baseline_status is not self.full_sample_unadjusted_result.status:
            raise ValueError("baseline_status must match full_sample_unadjusted_result")
        nested_results = tuple(
            result
            for result in (
                self.adjusted_result,
                self.comparable_unadjusted_result,
                self.full_sample_unadjusted_result,
            )
            if result is not None
        )
        if any(result.estimand != self.analysis_request.estimand for result in nested_results):
            raise ValueError("CUPED and randomized references must preserve the declared estimand")

        expected_variance_status = {
            CupedStatus.COMPLETED: VarianceReductionStatus.POSITIVE_REDUCTION,
            CupedStatus.NO_IMPROVEMENT: VarianceReductionStatus.NO_REDUCTION,
            CupedStatus.DEGRADED_PRECISION: VarianceReductionStatus.NEGATIVE_REDUCTION,
            CupedStatus.INCONCLUSIVE: VarianceReductionStatus.UNAVAILABLE,
        }.get(self.status)
        is_numerical = expected_variance_status is not None
        if is_numerical:
            if self.variance_reduction.status is not expected_variance_status:
                raise ValueError("CUPED status must match variance-reduction status")
            required = (
                self.retention,
                self.coefficient,
                self.balance,
                self.adjusted_result,
                self.comparable_unadjusted_result,
            )
            if any(value is None for value in required):
                raise ValueError("numerical CUPED results require complete adjustment evidence")
            if self.abstention_reason is not None:
                raise ValueError("numerical CUPED results must not include an abstention reason")
        else:
            if (
                self.status
                in {
                    CupedStatus.ABSTAINED,
                    CupedStatus.UNSUPPORTED,
                    CupedStatus.INVALID,
                }
                and self.abstention_reason is None
            ):
                raise ValueError("non-numerical CUPED results require an abstention reason")
            if self.adjusted_result is not None:
                raise ValueError("non-numerical CUPED results must not include adjusted inference")
            if self.variance_reduction.status is not VarianceReductionStatus.UNAVAILABLE:
                raise ValueError(
                    "non-numerical CUPED results require unavailable variance reduction"
                )
        return self


def _same_probability(first: float, second: float) -> bool:
    return math.isclose(first, second, rel_tol=0.0, abs_tol=1e-12)


__all__ = [
    "CovariateBalanceStatus",
    "CupedAbstentionReason",
    "CupedAnalysisExecutionRequest",
    "CupedAnalysisResult",
    "CupedCoefficient",
    "CupedCovariateBalance",
    "CupedSampleRetention",
    "CupedStatus",
    "RetainedArmSummary",
    "VarianceReduction",
    "VarianceReductionStatus",
]
