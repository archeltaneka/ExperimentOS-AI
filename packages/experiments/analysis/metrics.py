"""Metric definitions, normalized units, measured values, and sample contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from .base import (
    ContractModel,
    CurrencyCode,
    FiniteFloat,
    NonEmptyStr,
    PositiveFiniteFloat,
    PositiveInt,
)


class UnitDimension(StrEnum):
    """Physical or semantic dimension represented by a metric unit."""

    DIMENSIONLESS = "dimensionless"
    PROPORTION = "proportion"
    COUNT = "count"
    CURRENCY = "currency"
    DURATION = "duration"
    RATE = "rate"
    RATIO = "ratio"
    CUSTOM = "custom"


class ValueScale(StrEnum):
    """Encoding scale used to interpret a numeric metric value."""

    RAW = "raw"
    PROPORTION = "proportion"
    PERCENT = "percent"
    PERCENTAGE_POINT = "percentage_point"
    BASIS_POINT = "basis_point"
    CUSTOM = "custom"


class MetricType(StrEnum):
    """Statistical shape of a declared metric."""

    CONTINUOUS = "continuous"
    BINARY = "binary"
    COUNT = "count"
    PROPORTION = "proportion"
    RATE = "rate"
    RATIO = "ratio"


class OutcomeDirection(StrEnum):
    """Explicit direction of improvement for an outcome metric."""

    INCREASE = "increase"
    DECREASE = "decrease"
    NO_PREFERENCE = "no_preference"


class MetricUnit(ContractModel):
    """Structured unit with an explicit conversion multiplier to its base unit."""

    dimension: UnitDimension
    value_scale: ValueScale
    symbol: NonEmptyStr
    scale_to_base_unit: PositiveFiniteFloat
    currency_code: CurrencyCode | None = None
    custom_dimension_name: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_dimension_metadata(self) -> Self:
        if self.dimension is UnitDimension.CURRENCY:
            if self.currency_code is None:
                raise ValueError("currency dimensions require currency_code")
        elif self.currency_code is not None:
            raise ValueError("currency_code is only valid for currency dimensions")

        if self.dimension is UnitDimension.CUSTOM:
            if self.custom_dimension_name is None:
                raise ValueError("custom dimensions require custom_dimension_name")
        elif self.custom_dimension_name is not None:
            raise ValueError("custom_dimension_name is only valid for custom dimensions")

        proportion_scales = {
            ValueScale.PROPORTION,
            ValueScale.PERCENT,
            ValueScale.PERCENTAGE_POINT,
            ValueScale.BASIS_POINT,
        }
        if self.value_scale in proportion_scales and self.dimension is not UnitDimension.PROPORTION:
            raise ValueError("percentage-like scales require a proportion dimension")

        standardized_multipliers = {
            ValueScale.PROPORTION: 1.0,
            ValueScale.PERCENT: 0.01,
            ValueScale.PERCENTAGE_POINT: 0.01,
            ValueScale.BASIS_POINT: 0.0001,
        }
        expected_multiplier = standardized_multipliers.get(self.value_scale)
        if expected_multiplier is not None and self.scale_to_base_unit != expected_multiplier:
            raise ValueError(
                f"scale_to_base_unit must be {expected_multiplier} for {self.value_scale.value}"
            )

        return self


class MetricDefinition(ContractModel):
    """Stable identity, statistical type, and unit for a metric."""

    metric_id: NonEmptyStr
    label: NonEmptyStr
    metric_type: MetricType
    unit: MetricUnit


class OutcomeMetric(ContractModel):
    """A metric paired with its explicit desired outcome direction."""

    metric: MetricDefinition
    direction: OutcomeDirection


class MeasuredValue(ContractModel):
    """A finite numeric value interpreted by a structured metric unit."""

    value: FiniteFloat
    unit: MetricUnit


class AnalysisUnit(ContractModel):
    """Stable identifier and label for an analysis or assignment unit."""

    unit_id: NonEmptyStr
    label: NonEmptyStr


class SampleCounts(ContractModel):
    """Positive treatment, control, and consistent total sample counts."""

    total: PositiveInt
    treatment: PositiveInt
    control: PositiveInt

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if self.total != self.treatment + self.control:
            raise ValueError("total must equal treatment plus control")
        return self
