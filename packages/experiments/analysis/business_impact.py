"""Fully sourced business-impact input and projection contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from .base import (
    SCHEMA_VERSION,
    AnalysisStatus,
    ContractModel,
    CurrencyCode,
    FiniteFloat,
    PositiveInt,
    Probability,
)
from .estimates import ConclusionType, EffectEstimate
from .metrics import MeasuredValue, MetricUnit, UnitDimension, ValueScale
from .provenance import (
    AnalysisWarning,
    AssumptionAssessment,
    Diagnostic,
    ProvenanceRecords,
)
from .study_designs import TimePeriod
from .uncertainty import UncertaintyBundle


class SourcedCount(ContractModel):
    """Positive count supported by explicit provenance."""

    value: PositiveInt
    provenance: ProvenanceRecords


class SourcedQuantity(ContractModel):
    """Finite unit-bearing quantity supported by explicit provenance."""

    value: FiniteFloat
    unit: MetricUnit
    provenance: ProvenanceRecords


class SourcedProportion(ContractModel):
    """Canonical normalized proportion supported by explicit provenance."""

    value: Probability
    unit: MetricUnit
    provenance: ProvenanceRecords

    @model_validator(mode="after")
    def validate_proportion_unit(self) -> Self:
        if (
            self.unit.dimension is not UnitDimension.PROPORTION
            or self.unit.value_scale is not ValueScale.PROPORTION
            or self.unit.scale_to_base_unit != 1.0
        ):
            raise ValueError(
                "sourced proportion requires a canonical proportion unit "
                "with proportion scale and scale_to_base_unit 1.0"
            )
        return self


class SourcedMoney(ContractModel):
    """Finite monetary value with an explicit currency unit and provenance."""

    value: FiniteFloat
    unit: MetricUnit
    provenance: ProvenanceRecords

    @model_validator(mode="after")
    def validate_currency_unit(self) -> Self:
        if self.unit.dimension is not UnitDimension.CURRENCY:
            raise ValueError("sourced money requires a currency unit")
        return self


class SourcedCurrency(ContractModel):
    """Explicit ISO-style currency code supported by provenance."""

    value: CurrencyCode
    provenance: ProvenanceRecords


class SourcedTimePeriod(ContractModel):
    """Ordered, timezone-aware period supported by provenance."""

    value: TimePeriod
    provenance: ProvenanceRecords


class BusinessImpactInputs(ContractModel):
    """Complete sourced inputs required before business impact can be projected."""

    eligible_population: SourcedCount
    exposure_frequency: SourcedQuantity
    baseline_rate: SourcedProportion
    average_order_value: SourcedMoney
    contribution_margin: SourcedProportion | SourcedMoney
    rollout_proportion: SourcedProportion
    analysis_horizon: SourcedTimePeriod
    currency: SourcedCurrency

    @model_validator(mode="after")
    def validate_input_currencies(self) -> Self:
        if self.exposure_frequency.value < 0:
            raise ValueError("exposure_frequency must be greater than or equal to zero")
        currency = self.currency.value
        if self.average_order_value.unit.currency_code != currency:
            raise ValueError("average order value currency must match sourced currency")
        if (
            isinstance(self.contribution_margin, SourcedMoney)
            and self.contribution_margin.unit.currency_code != currency
        ):
            raise ValueError("currency-valued contribution margin must match sourced currency")
        return self


class ProjectedValue(ContractModel):
    """One projected measured value paired with uncertainty for that output."""

    value: MeasuredValue
    uncertainty: UncertaintyBundle


class BusinessImpactProjection(ContractModel):
    """Projected business impact that preserves its source estimate's evidence category."""

    projection_type: Literal["business_impact_projection"] = "business_impact_projection"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: Literal[AnalysisStatus.COMPLETED, AnalysisStatus.INCONCLUSIVE]
    conclusion_type: Literal[ConclusionType.PROJECTION]
    inputs: BusinessImpactInputs
    source_estimate: EffectEstimate
    projected_incremental_outcome: ProjectedValue
    projected_financial_impact: ProjectedValue
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords

    @model_validator(mode="after")
    def validate_projected_currency(self) -> Self:
        unit = self.projected_financial_impact.value.unit
        if unit.dimension is not UnitDimension.CURRENCY:
            raise ValueError("projected financial impact requires a currency unit")
        if unit.currency_code != self.inputs.currency.value:
            raise ValueError("projected financial impact currency must match sourced currency")
        return self
