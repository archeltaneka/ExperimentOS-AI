"""Auditable derived scenarios, with distinct statistical and operational uncertainty."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from ..base import AnalysisStatus, ContractModel, FiniteFloat, NonEmptyStr
from ..estimates import ConclusionType
from ..metrics import MetricUnit
from ..provenance import AnalysisWarning, Diagnostic
from ..results import AbstentionReason
from ..uncertainty import ConfidenceInterval, CredibleInterval
from .inputs import BusinessImpactRequest, input_evidence
from .source_models import SourceEffect
from .units import Entity, TimeBasis


class ScenarioBand(ContractModel):
    """Deterministic bounds with no implied probability or confidence level."""

    lower: FiniteFloat
    upper: FiniteFloat
    method: Literal["deterministic_interval_arithmetic_v1"] = "deterministic_interval_arithmetic_v1"

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("scenario bounds must be ordered")
        return self


class DerivedQuantity(ContractModel):
    """Derived amount with separate statistical and operational uncertainty."""

    category: Literal["derived"] = "derived"
    central: FiniteFloat | None
    unit: MetricUnit
    entity: Entity | None
    horizon: TimeBasis
    statistical: ConfidenceInterval | CredibleInterval | None
    statistical_unavailable_reason: NonEmptyStr | None
    business_inputs: ScenarioBand
    combined: ScenarioBand

    @model_validator(mode="after")
    def uncertainty_shape(self) -> Self:
        if (self.statistical is None) != (self.statistical_unavailable_reason is not None):
            raise ValueError(
                "statistical interval requires exactly one availability representation"
            )
        if (
            self.central is not None
            and not self.combined.lower <= self.central <= self.combined.upper
        ):
            raise ValueError("central impact must lie inside combined bounds")
        return self


class CostBreakdown(ContractModel):
    """One named declared cost with its own derived uncertainty bands."""

    cost_id: NonEmptyStr
    amount: DerivedQuantity


class Derivation(ContractModel):
    """A versioned formula and input references explaining a derived quantity."""

    field: NonEmptyStr
    formula_id: NonEmptyStr
    formula: NonEmptyStr
    input_references: tuple[NonEmptyStr, ...]
    result: DerivedQuantity


class BusinessImpactResult(ContractModel):
    """Auditable scenario or refusal preserving its source evidence and inputs."""

    outcome_type: Literal["business_impact_scenario"] = "business_impact_scenario"
    schema_version: Literal["1"] = "1"
    request_id: NonEmptyStr | None
    status: Literal[AnalysisStatus.COMPLETED, AnalysisStatus.INCONCLUSIVE, AnalysisStatus.ABSTAINED]
    conclusion_type: Literal[ConclusionType.PROJECTION] = ConclusionType.PROJECTION
    source: SourceEffect
    inputs: BusinessImpactRequest | None
    horizon_kind: Literal["observed", "extrapolated"] | None = None
    population_multiplier: FiniteFloat | None = None
    exposed_population: DerivedQuantity | None = None
    gross_incremental_outcome: DerivedQuantity | None = None
    gross_monetary_impact: DerivedQuantity | None = None
    declared_costs: DerivedQuantity | None = None
    cost_breakdown: tuple[CostBreakdown, ...] = ()
    net_monetary_impact: DerivedQuantity | None = None
    derivations: tuple[Derivation, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    warnings: tuple[AnalysisWarning, ...] = ()
    abstention_reason: AbstentionReason | None = None

    @model_validator(mode="after")
    def disposition(self) -> Self:
        outputs = (
            self.exposed_population,
            self.gross_incremental_outcome,
            self.gross_monetary_impact,
            self.declared_costs,
            self.net_monetary_impact,
        )
        if self.status is AnalysisStatus.ABSTAINED:
            if any(v is not None for v in outputs) or self.derivations or self.cost_breakdown:
                raise ValueError("abstention must suppress derived numeric results")
            if self.abstention_reason is None:
                raise ValueError("abstention requires a reason")
        elif (
            self.abstention_reason is not None
            or self.inputs is None
            or self.gross_incremental_outcome is None
        ):
            raise ValueError("calculable scenarios require inputs and outcome")
        if self.status is not AnalysisStatus.ABSTAINED:
            assert self.inputs is not None
            if self.status is AnalysisStatus.COMPLETED and (
                self.source.conditional
                or self.horizon_kind == "extrapolated"
                or any(e.status == "assumed" for e in input_evidence(self.inputs))
            ):
                raise ValueError("conditional evidence/inputs cannot become completed scenarios")
            if not self.source.calculable:
                raise ValueError("calculable scenario requires calculable source evidence")
            if self.exposed_population is None or self.horizon_kind is None:
                raise ValueError("calculable scenario requires exposure and horizon")
            if self.inputs.output in {"gross", "net"} and self.gross_monetary_impact is None:
                raise ValueError("monetary request requires gross monetary output")
            if self.inputs.output == "net":
                if self.declared_costs is None or self.net_monetary_impact is None:
                    raise ValueError("net request requires declared costs and net output")
                if self.inputs.costs is None or tuple(
                    c.cost_id for c in self.cost_breakdown
                ) != tuple(c.cost_id for c in self.inputs.costs.items):
                    raise ValueError("cost breakdown must cover declared costs")
            elif (
                self.net_monetary_impact is not None
                or self.declared_costs is not None
                or self.cost_breakdown
            ):
                raise ValueError("net outputs require a net request")
            if self.inputs.output == "outcome" and self.gross_monetary_impact is not None:
                raise ValueError("outcome-only request cannot contain monetary output")
        return self
