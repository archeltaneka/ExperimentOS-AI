"""Strict, explicitly sourced operational declarations for impact scenarios."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import JsonValue, model_validator

from ..base import ContractModel, CurrencyCode, FiniteFloat, NonEmptyStr, PositiveInt
from ..metrics import AnalysisUnit, MetricUnit
from ..populations import PopulationDefinition
from ..provenance import ProvenanceRecords, ProvenanceSourceType
from ..study_designs import TimePeriod
from .units import Entity, TimeBasis


class InputRange(ContractModel):
    """Finite bounds with an optional explicitly supplied central value."""

    lower: FiniteFloat
    upper: FiniteFloat
    central: FiniteFloat | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("range lower must not exceed upper")
        if self.central is not None and not self.lower <= self.central <= self.upper:
            raise ValueError("central must lie inside range")
        return self

    @classmethod
    def fixed(cls, value: float) -> Self:
        return cls(lower=value, upper=value, central=value)


class InputEvidence(ContractModel):
    """Structured origin and measured/assumed status for one operational input."""

    origin: Literal["user_supplied", "repository_evidence"]
    status: Literal["measured", "assumed"]
    provenance: ProvenanceRecords
    reference: NonEmptyStr | None = None

    @model_validator(mode="after")
    def explicit_origin(self) -> Self:
        if self.origin == "repository_evidence":
            if self.reference is None:
                raise ValueError("repository evidence requires an explicit record/field reference")
            if not any(
                self.reference.startswith(p.source_id + ":")
                and bool(self.reference[len(p.source_id) + 1 :].strip())
                for p in self.provenance
            ):
                raise ValueError("repository reference must identify a supplied record field")
            allowed = {
                ProvenanceSourceType.EXPERIMENT_DATA,
                ProvenanceSourceType.REPORT,
                ProvenanceSourceType.ANALYSIS_REQUEST,
            }
            if not any(p.source_type in allowed for p in self.provenance):
                raise ValueError("repository evidence requires a repository source record")
        elif not any(p.source_type is ProvenanceSourceType.USER_SUPPLIED for p in self.provenance):
            raise ValueError("user supplied evidence requires user supplied provenance")
        return self


class SourcedInput(ContractModel):
    """An operational declaration whose evidence cannot be omitted."""

    evidence: InputEvidence


class TimeHorizon(SourcedInput):
    """An actual period checked against an explicit calendar or duration basis."""

    period: TimePeriod
    basis: TimeBasis

    @model_validator(mode="after")
    def aligned(self) -> Self:
        try:
            end = self.basis.end_from(self.period.start)
        except (OverflowError, ValueError):
            raise ValueError("horizon exceeds supported calendar bounds") from None
        if end != self.period.end:
            raise ValueError("horizon period must match its declared calendar/duration basis")
        return self


class PopulationInput(SourcedInput):
    """Eligible or already-exposed population with entity, target and time semantics."""

    value: InputRange
    entity: Entity
    definition: PopulationDefinition
    target_kind: Literal["full", "treated", "conditioned"]
    basis: Literal["total", "per_period"]
    time_basis: TimeBasis
    exposure_basis: Literal["eligible", "already_exposed"]
    subgroup_id: NonEmptyStr | None = None
    subgroup_rule: NonEmptyStr | None = None

    @model_validator(mode="after")
    def nonnegative(self) -> Self:
        if self.value.lower < 0:
            raise ValueError("population must be nonnegative")
        if (self.subgroup_id is None) != (self.subgroup_rule is None):
            raise ValueError("subgroup identity and rule must be supplied together")
        return self


class ExposureInput(SourcedInput):
    """Explicit rollout, adoption or exposure fraction for the scenario horizon."""

    value: InputRange
    meaning: Literal["rollout", "adoption", "exposure", "already_exposed"]
    horizon: TimeBasis

    @model_validator(mode="after")
    def proportion(self) -> Self:
        if self.value.lower < 0 or self.value.upper > 1:
            raise ValueError("exposure rate must lie in [0, 1]")
        return self


class EffectBinding(SourcedInput):
    """Explicit business entity/outcome binding to an existing effect's metric."""

    analysis_unit: AnalysisUnit
    entity: Entity
    metric_id: NonEmptyStr
    outcome_unit: MetricUnit
    event: Entity | None = None
    observed_period: TimePeriod | None = None


class ExposureConversion(SourcedInput):
    """Sourced nonnegative conversion between population and exposure entities."""

    value: InputRange
    from_entity: Entity
    to_entity: Entity
    horizon: TimeBasis

    @model_validator(mode="after")
    def meaningful(self) -> Self:
        if self.value.lower < 0 or self.from_entity == self.to_entity:
            raise ValueError("exposure conversion requires nonnegative value and distinct units")
        return self


class BaselineRate(SourcedInput):
    """Explicit binary event probability per exposed entity for relative effects."""

    value: InputRange
    event: Entity
    per_entity: Entity
    horizon: TimeBasis

    @model_validator(mode="after")
    def probability(self) -> Self:
        if not 0 <= self.value.lower <= self.value.upper <= 1:
            raise ValueError("binary baseline rate must lie in [0, 1]")
        return self


class MonetaryConversion(SourcedInput):
    """Sourced currency value per added or avoided incremental outcome."""

    value: InputRange
    currency: CurrencyCode
    metric_id: NonEmptyStr
    per_unit: MetricUnit
    event: Entity | None = None
    orientation: Literal["added", "avoided"]
    meaning: Literal["revenue", "contribution", "retained_contribution", "avoided_cost", "value"]
    horizon: TimeBasis

    @model_validator(mode="after")
    def nonnegative(self) -> Self:
        if self.value.lower < 0:
            raise ValueError("monetary conversion rates must be nonnegative")
        return self


class PersistenceAssumption(SourcedInput):
    """Explicit user assumption extending effect applicability to a declared period."""

    period: TimePeriod
    statement: NonEmptyStr

    @model_validator(mode="after")
    def assumed(self) -> Self:
        if self.evidence.origin != "user_supplied" or self.evidence.status != "assumed":
            raise ValueError("extrapolated effect persistence must be an explicit user assumption")
        return self


class PopulationRepetition(SourcedInput):
    """Declared additive population opportunities across compatible periods."""

    source_basis: TimeBasis
    target_basis: TimeBasis
    repetitions: PositiveInt
    statement: NonEmptyStr


class CostInput(SourcedInput):
    """One nonnegative cost rate/amount with an explicit application basis."""

    cost_id: NonEmptyStr
    value: InputRange
    currency: CurrencyCode
    basis: Literal["implementation", "recurring", "per_exposure", "per_incremental_outcome"]
    horizon: TimeBasis
    entity: Entity | None = None
    metric_id: NonEmptyStr | None = None
    outcome_unit: MetricUnit | None = None
    event: Entity | None = None

    @model_validator(mode="after")
    def basis_fields(self) -> Self:
        if self.value.lower < 0:
            raise ValueError("declared cost amount/rate must be nonnegative")
        if (self.entity is not None) != (self.basis == "per_exposure"):
            raise ValueError("entity is required exactly for per-exposure costs")
        outcome_fields = (self.metric_id, self.outcome_unit)
        if self.basis == "per_incremental_outcome":
            if any(v is None for v in outcome_fields):
                raise ValueError("incremental outcome costs require metric and unit")
        elif any(v is not None for v in (*outcome_fields, self.event)):
            raise ValueError("outcome fields are only valid for incremental outcome costs")
        return self


class CostDeclaration(SourcedInput):
    """Complete declared costs; an empty sourced collection explicitly declares zero."""

    complete: Literal[True]
    items: tuple[CostInput, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({c.cost_id for c in self.items}) != len(self.items):
            raise ValueError("cost identifiers must be unique")
        return self


class RepositoryInputRecord(ContractModel):
    """Explicit structured evidence supplied by the repository evidence boundary.

    The service resolves references locally and checks exact values; it never
    searches prose or fetches missing records. Upstream storage owns authenticity.
    """

    reference: NonEmptyStr
    status: Literal["measured", "assumed"]
    provenance: ProvenanceRecords
    value: dict[str, JsonValue]


class BusinessImpactRequest(ContractModel):
    """Explicit operational inputs and requested output scope for an owned effect."""

    schema_version: Literal["1"] = "1"
    request_id: NonEmptyStr
    output: Literal["outcome", "gross", "net"]
    population: PopulationInput
    exposure: ExposureInput
    horizon: TimeHorizon
    binding: EffectBinding
    baseline: BaselineRate | None = None
    exposure_conversion: ExposureConversion | None = None
    conversion: MonetaryConversion | None = None
    costs: CostDeclaration | None = None
    persistence: PersistenceAssumption | None = None
    repetition: PopulationRepetition | None = None
    subgroup_id: NonEmptyStr | None = None
    repository_evidence: tuple[RepositoryInputRecord, ...] = ()

    @model_validator(mode="after")
    def subgroup_binding(self) -> Self:
        if self.subgroup_id != self.population.subgroup_id:
            raise ValueError("selected subgroup must match the population subgroup")
        records = {record.reference: record for record in self.repository_evidence}
        if len(records) != len(self.repository_evidence):
            raise ValueError("repository evidence references must be unique")
        for item in sourced_inputs(self):
            evidence = item.evidence
            if evidence.origin != "repository_evidence":
                continue
            record = records.get(evidence.reference or "")
            if record is None:
                raise ValueError("repository input requires resolved structured evidence")
            if (
                record.status != evidence.status
                or record.provenance != evidence.provenance
                or record.value != item.model_dump(mode="json", exclude={"evidence"})
            ):
                raise ValueError("repository input value/semantics must match its evidence record")
        return self


def sourced_inputs(request: BusinessImpactRequest) -> tuple[SourcedInput, ...]:
    """Enumerate all declarations, including separately sourced cost components."""
    entries = (
        request.population,
        request.exposure,
        request.horizon,
        request.binding,
        request.baseline,
        request.exposure_conversion,
        request.conversion,
        request.costs,
        request.persistence,
        request.repetition,
    )
    return tuple(e for e in entries if e is not None) + (
        request.costs.items if request.costs else ()
    )


def input_evidence(request: BusinessImpactRequest) -> tuple[InputEvidence, ...]:
    return tuple(item.evidence for item in sourced_inputs(request))
