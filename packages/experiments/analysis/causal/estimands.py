"""Typed observational estimands and treatment contrasts."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import field_validator, model_validator

from ..base import ContractModel, NonEmptyStr, ScalarValue
from ..populations import PopulationDefinition
from ..provenance import ProvenanceRecords


class CausalEstimandKind(StrEnum):
    """Stable observational causal quantities supported by the contract."""

    ATE = "ate"
    ATT = "att"
    DID_ATT = "did_att"
    CATE = "cate"


class EffectScale(StrEnum):
    """Declared scale on which a future effect would be estimated."""

    MEAN_DIFFERENCE = "mean_difference"
    RISK_DIFFERENCE = "risk_difference"
    RISK_RATIO = "risk_ratio"
    LOG_ODDS_RATIO = "log_odds_ratio"


class TargetPopulationKind(StrEnum):
    """Population semantics that distinguish ATE, ATT, and conditional targets."""

    FULL = "full"
    TREATED = "treated"
    CONDITIONED = "conditioned"


class TreatmentContrast(ContractModel):
    """Treatment/control values and the exposure they represent."""

    treatment_variable: NonEmptyStr
    treated_value: ScalarValue
    control_value: ScalarValue
    exposure_definition: NonEmptyStr
    provenance: ProvenanceRecords

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if self.treated_value == self.control_value:
            raise ValueError("treated and control values must differ")
        return self


class TargetPopulation(ContractModel):
    """Explicit target population semantics for an observational estimand."""

    kind: TargetPopulationKind
    population: PopulationDefinition


class CausalEstimand(ContractModel):
    """Complete requested observational estimand without estimator configuration."""

    estimand_type: CausalEstimandKind
    treatment_contrast: TreatmentContrast
    target_population: TargetPopulation
    outcome_variable: NonEmptyStr
    effect_scale: EffectScale
    effect_modifiers: tuple[NonEmptyStr, ...] = ()
    conditioning_definition: NonEmptyStr | None = None
    provenance: ProvenanceRecords

    @field_validator("effect_modifiers")
    @classmethod
    def canonicalize_modifiers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        canonical = tuple(sorted(value))
        if len(canonical) != len(set(canonical)):
            raise ValueError("effect modifier identifiers must be unique")
        return canonical

    @model_validator(mode="after")
    def validate_estimand_shape(self) -> Self:
        treated_targets = {CausalEstimandKind.ATT, CausalEstimandKind.DID_ATT}
        if self.estimand_type in treated_targets:
            if self.target_population.kind is not TargetPopulationKind.TREATED:
                raise ValueError("ATT estimands require treated target population semantics")
        elif self.estimand_type is CausalEstimandKind.ATE:
            if self.target_population.kind is not TargetPopulationKind.FULL:
                raise ValueError("ATE requires full target population semantics")
        elif self.target_population.kind is not TargetPopulationKind.CONDITIONED:
            raise ValueError("CATE requires conditioned target population semantics")

        if self.estimand_type is CausalEstimandKind.CATE:
            if not self.effect_modifiers:
                raise ValueError("CATE requires at least one effect modifier")
            if self.conditioning_definition is None:
                raise ValueError("CATE requires a conditioning definition")
        elif self.effect_modifiers or self.conditioning_definition is not None:
            raise ValueError("effect modifiers and conditioning are only valid for CATE")
        return self


__all__ = [
    "CausalEstimand",
    "CausalEstimandKind",
    "EffectScale",
    "TargetPopulation",
    "TargetPopulationKind",
    "TreatmentContrast",
]
