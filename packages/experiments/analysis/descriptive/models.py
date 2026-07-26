"""Immutable contracts for descriptive-statistics outputs."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..base import SCHEMA_VERSION, ContractModel, FiniteFloat, NonEmptyStr, PositiveInt, Probability
from ..metrics import OutcomeDirection

type NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class DescriptiveStatisticsConfig(ContractModel):
    """Requested descriptive-statistics settings without calculation behavior."""

    quantile_levels: tuple[Probability, ...] = (0.25, 0.5, 0.75)

    @model_validator(mode="after")
    def validate_quantile_levels(self) -> Self:
        if not self.quantile_levels:
            raise ValueError("quantile levels must be non-empty, unique ascending values")
        if any(
            earlier >= later
            for earlier, later in zip(self.quantile_levels, self.quantile_levels[1:], strict=False)
        ):
            raise ValueError("quantile levels must be non-empty, unique ascending values")
        return self


class Quantile(ContractModel):
    """One requested quantile level and its observed finite value, when available."""

    level: Probability
    value: FiniteFloat | None


class ContinuousSummary(ContractModel):
    """Descriptive summary for a continuous outcome or covariate."""

    summary_type: Literal["continuous"] = "continuous"
    sample_size: PositiveInt
    mean: FiniteFloat | None = None
    variance: FiniteFloat | None = None
    standard_deviation: FiniteFloat | None = None
    standard_error: FiniteFloat | None = None
    minimum: FiniteFloat | None = None
    maximum: FiniteFloat | None = None
    quantiles: tuple[Quantile, ...] = ()


class BinarySummary(ContractModel):
    """Descriptive summary for a binary outcome or covariate."""

    summary_type: Literal["binary"] = "binary"
    sample_size: PositiveInt
    positive_count: NonNegativeInt | None = None
    proportion: Probability | None = None
    success_count: NonNegativeInt | None = None
    failure_count: NonNegativeInt | None = None
    rate: Probability | None = None
    variance: FiniteFloat | None = None
    standard_error: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_positive_count(self) -> Self:
        if self.positive_count is not None and self.positive_count > self.sample_size:
            raise ValueError("positive_count must not exceed sample_size")
        if self.success_count is not None and self.success_count > self.sample_size:
            raise ValueError("success_count must not exceed sample_size")
        if self.failure_count is not None and self.failure_count > self.sample_size:
            raise ValueError("failure_count must not exceed sample_size")
        if (
            self.success_count is not None
            and self.failure_count is not None
            and self.success_count + self.failure_count != self.sample_size
        ):
            raise ValueError("success_count plus failure_count must equal sample_size")
        if (
            self.positive_count is not None
            and self.success_count is not None
            and self.positive_count != self.success_count
        ):
            raise ValueError("positive_count must match success_count")
        if self.proportion is not None and self.rate is not None and self.proportion != self.rate:
            raise ValueError("proportion must match rate")
        return self


class CountSummary(ContractModel):
    """Descriptive summary for a count outcome or covariate."""

    summary_type: Literal["count"] = "count"
    sample_size: PositiveInt
    total: NonNegativeInt | None = None
    mean: FiniteFloat | None = None
    variance: FiniteFloat | None = None
    standard_error: FiniteFloat | None = None
    minimum: NonNegativeInt | None = None
    maximum: NonNegativeInt | None = None


class UnavailableSummary(ContractModel):
    """Explicitly records why a requested descriptive summary is unavailable."""

    summary_type: Literal["unavailable"] = "unavailable"
    reason: NonEmptyStr


type DescriptiveSummary = Annotated[
    ContinuousSummary | BinarySummary | CountSummary | UnavailableSummary,
    Field(discriminator="summary_type"),
]


class PopulationSummary(ContractModel):
    """A named population paired with its typed descriptive summary."""

    population_id: NonEmptyStr
    label: NonEmptyStr
    row_count: NonNegativeInt = 0
    unique_unit_count: NonNegativeInt = 0
    valid_outcome_count: NonNegativeInt = 0
    missing_outcome_count: NonNegativeInt = 0
    summary: DescriptiveSummary

    @model_validator(mode="after")
    def validate_outcome_counts(self) -> Self:
        if self.unique_unit_count > self.row_count:
            raise ValueError("unique_unit_count must not exceed row_count")
        if self.valid_outcome_count + self.missing_outcome_count > self.row_count:
            raise ValueError("outcome counts must not exceed row_count")
        return self


class ComparisonAvailability(StrEnum):
    """Availability state for a raw treatment-control comparison."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class RawComparison(ContractModel):
    """Raw, unadjusted comparison with explicit outcome direction and availability."""

    comparison_type: Literal["raw_unadjusted"] = "raw_unadjusted"
    outcome_direction: OutcomeDirection
    availability: ComparisonAvailability
    unavailable_reason: NonEmptyStr | None = None
    absolute_difference: FiniteFloat | None = None
    relative_difference: FiniteFloat | None = None
    relative_difference_unavailable_reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if (
            self.availability is ComparisonAvailability.AVAILABLE
            and self.unavailable_reason is not None
        ):
            raise ValueError("available raw comparisons must not include an unavailable_reason")
        if (
            self.availability is ComparisonAvailability.UNAVAILABLE
            and self.unavailable_reason is None
        ):
            raise ValueError("unavailable raw comparisons require an unavailable_reason")
        if self.availability is ComparisonAvailability.UNAVAILABLE and (
            self.absolute_difference is not None
            or self.relative_difference is not None
            or self.relative_difference_unavailable_reason is not None
        ):
            raise ValueError("unavailable raw comparisons must not include numeric differences")
        if (
            self.relative_difference is not None
            and self.relative_difference_unavailable_reason is not None
        ):
            raise ValueError(
                "available relative differences must not include an unavailable reason"
            )
        return self


class CovariateSummary(ContractModel):
    """A declared numeric pre-treatment covariate summarized by population and arm."""

    covariate_id: NonEmptyStr
    label: NonEmptyStr
    population: PopulationSummary
    treatment: PopulationSummary
    control: PopulationSummary


class SegmentSummary(ContractModel):
    """The one validated requested segment, without automatic segment discovery."""

    segment_id: NonEmptyStr
    label: NonEmptyStr
    population: PopulationSummary
    treatment: PopulationSummary | None = None
    control: PopulationSummary | None = None
    raw_comparison: RawComparison | None = None
    warnings: tuple[DescriptiveDiagnostic, ...] = ()


class PeriodSummary(ContractModel):
    """One explicit design period summarized without a time-series estimator."""

    period_id: NonEmptyStr
    label: NonEmptyStr
    population: PopulationSummary
    treatment: PopulationSummary | None = None
    control: PopulationSummary | None = None
    raw_comparison: RawComparison | None = None


class DescriptiveDiagnostic(ContractModel):
    """A non-calculating diagnostic emitted while building descriptive statistics."""

    code: NonEmptyStr
    message: NonEmptyStr


class DescriptiveStatisticsResult(ContractModel):
    """Canonical descriptive-statistics result without estimator or adjustment logic."""

    result_type: Literal["descriptive_statistics"] = "descriptive_statistics"
    schema_version: Literal["1"] = SCHEMA_VERSION
    outcome_id: NonEmptyStr
    outcome_label: NonEmptyStr
    outcome_direction: OutcomeDirection
    config: DescriptiveStatisticsConfig = DescriptiveStatisticsConfig()
    population: PopulationSummary
    treatment: PopulationSummary | None = None
    control: PopulationSummary | None = None
    raw_comparison: RawComparison | None = None
    covariates: tuple[CovariateSummary, ...] = ()
    segments: tuple[SegmentSummary, ...] = ()
    periods: tuple[PeriodSummary, ...] = ()
    diagnostics: tuple[DescriptiveDiagnostic, ...] = ()
