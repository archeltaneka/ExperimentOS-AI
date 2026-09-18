"""Owned, estimator-independent effect evidence for business-impact scenarios."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import JsonValue, model_validator

from ..base import ContractModel, FiniteFloat, NonEmptyStr
from ..metrics import AnalysisUnit, OutcomeMetric
from ..populations import PopulationDefinition
from ..provenance import Diagnostic, ProvenanceRecord
from ..study_designs import TimePeriod
from ..uncertainty import ConfidenceInterval, CredibleInterval

type EffectInterval = ConfidenceInterval | CredibleInterval
type EffectScaleName = Literal["absolute_binary", "relative_binary", "continuous"]
type TargetKind = Literal["full", "treated", "conditioned"]


class SourceRecord(ContractModel):
    """Lossless JSON snapshot of one typed source evidence record."""

    scope: NonEmptyStr
    record_type: NonEmptyStr
    payload: dict[str, JsonValue]


class SourceEffect(ContractModel):
    """Auditable effect evidence normalized without business-value inference."""

    source_type: NonEmptyStr
    estimator: NonEmptyStr
    estimand: NonEmptyStr
    request_id: NonEmptyStr | None = None
    native_status: NonEmptyStr
    metric: OutcomeMetric | None = None
    population: PopulationDefinition | None = None
    analysis_unit: AnalysisUnit | None = None
    observed_period: TimePeriod | None = None
    point: FiniteFloat | None = None
    interval: EffectInterval | None = None
    effect_scale: EffectScaleName | None = None
    target_kind: TargetKind | None = None
    subgroup_id: NonEmptyStr | None = None
    subgroup_rule: NonEmptyStr | None = None
    conditional: bool = False
    provenance: tuple[ProvenanceRecord, ...] = ()
    fingerprint: NonEmptyStr | None = None
    blocking_diagnostics: tuple[Diagnostic, ...] = ()
    source_diagnostics: tuple[SourceRecord, ...] = ()
    source_warnings: tuple[SourceRecord, ...] = ()
    source_assumptions: tuple[SourceRecord, ...] = ()
    evidence_limitations: tuple[SourceRecord, ...] = ()
    source_metadata: tuple[SourceRecord, ...] = ()

    @model_validator(mode="after")
    def validate_effect_shape(self) -> Self:
        if self.blocking_diagnostics and (self.point is not None or self.interval is not None):
            raise ValueError("blocked source effects must suppress point and interval")
        if (self.point is None) != (self.interval is None):
            raise ValueError("point and interval must be present or absent together")
        if self.subgroup_id is None and self.subgroup_rule is not None:
            raise ValueError("subgroup_rule requires subgroup_id")
        return self

    @property
    def calculable(self) -> bool:
        return (
            self.point is not None
            and self.interval is not None
            and self.effect_scale is not None
            and not self.blocking_diagnostics
        )


__all__ = ["EffectInterval", "EffectScaleName", "SourceEffect", "SourceRecord", "TargetKind"]
