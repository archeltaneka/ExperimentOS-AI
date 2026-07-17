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
    DIMENSIONLESS = "dimensionless"
    PROPORTION = "proportion"
    COUNT = "count"
    CURRENCY = "currency"
    DURATION = "duration"
    RATE = "rate"
    RATIO = "ratio"
    CUSTOM = "custom"


class ValueScale(StrEnum):
    RAW = "raw"
    PROPORTION = "proportion"
    PERCENT = "percent"
    PERCENTAGE_POINT = "percentage_point"
    BASIS_POINT = "basis_point"
    CUSTOM = "custom"


class MetricType(StrEnum):
    CONTINUOUS = "continuous"
    BINARY = "binary"
    COUNT = "count"
    PROPORTION = "proportion"
    RATE = "rate"
    RATIO = "ratio"


class OutcomeDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    NO_PREFERENCE = "no_preference"


class MetricUnit(ContractModel):
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

        return self


class MetricDefinition(ContractModel):
    metric_id: NonEmptyStr
    label: NonEmptyStr
    metric_type: MetricType
    unit: MetricUnit


class OutcomeMetric(ContractModel):
    metric: MetricDefinition
    direction: OutcomeDirection


class MeasuredValue(ContractModel):
    value: FiniteFloat
    unit: MetricUnit


class AnalysisUnit(ContractModel):
    unit_id: NonEmptyStr
    label: NonEmptyStr


class SampleCounts(ContractModel):
    total: PositiveInt
    treatment: PositiveInt
    control: PositiveInt

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if self.total != self.treatment + self.control:
            raise ValueError("total must equal treatment plus control")
        return self
