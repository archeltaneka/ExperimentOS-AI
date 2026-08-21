"""Top-level causal-identification request and result contracts."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import field_validator, model_validator

from ..base import ContractModel, NonEmptyStr
from ..populations import PopulationDefinition
from ..provenance import ProvenanceRecords
from .adjustment import AdjustmentSet
from .assumptions import CausalAssumption
from .designs import (
    CausalOutcome,
    ObservationalDesign,
    ObservationalDesignType,
    TimeSemantics,
    UnitSemantics,
)
from .diagnostics import CausalDiagnostic, CausalDiagnosticCode, EvidenceLimitation
from .estimands import CausalEstimand, TreatmentContrast
from .graph import CausalGraph
from .variables import CausalVariable

CAUSAL_IDENTIFICATION_CONTRACT_VERSION: Literal["1"] = "1"


class IdentificationStatus(StrEnum):
    """Terminal structural status of a causal-identification request."""

    IDENTIFIED = "identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    INVALID = "invalid"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"


class CausalIdentificationRequest(ContractModel):
    """All declarations required before observational estimation can be considered."""

    request_version: Literal["1"] = "1"
    contract_version: Literal["1"] = CAUSAL_IDENTIFICATION_CONTRACT_VERSION
    design: ObservationalDesign
    estimand: CausalEstimand | None
    treatment: TreatmentContrast | None
    outcome: CausalOutcome | None
    population: PopulationDefinition
    units: UnitSemantics | None
    time: TimeSemantics
    variables: tuple[CausalVariable, ...]
    covariates: tuple[NonEmptyStr, ...] = ()
    adjustment_set: AdjustmentSet | None = None
    effect_modifiers: tuple[NonEmptyStr, ...] = ()
    causal_graph: CausalGraph | None = None
    assumptions: tuple[CausalAssumption, ...]
    evidence_limitations: tuple[EvidenceLimitation, ...]
    provenance: ProvenanceRecords

    @field_validator("variables")
    @classmethod
    def canonicalize_variables(
        cls,
        value: tuple[CausalVariable, ...],
    ) -> tuple[CausalVariable, ...]:
        return tuple(sorted(value, key=lambda item: item.variable_id))

    @field_validator("covariates", "effect_modifiers")
    @classmethod
    def canonicalize_variable_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("assumptions")
    @classmethod
    def canonicalize_assumptions(
        cls,
        value: tuple[CausalAssumption, ...],
    ) -> tuple[CausalAssumption, ...]:
        return tuple(sorted(value, key=lambda item: item.code.value))

    @field_validator("evidence_limitations")
    @classmethod
    def canonicalize_limitations(
        cls,
        value: tuple[EvidenceLimitation, ...],
    ) -> tuple[EvidenceLimitation, ...]:
        return tuple(sorted(value, key=lambda item: item.code.value))


class ObservationalAnalysisRequest(ContractModel):
    """Future estimator-facing envelope that cannot omit identification declarations."""

    schema_version: Literal["1"] = "1"
    request_id: NonEmptyStr
    identification: CausalIdentificationRequest


class CausalAbstentionReason(ContractModel):
    """Typed reason a request cannot proceed to future estimation."""

    code: CausalDiagnosticCode
    message: NonEmptyStr
    missing_or_invalid_information: tuple[NonEmptyStr, ...]


def _canonical_model_key(model: ContractModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class IdentificationResult(ContractModel):
    """Identification-only outcome containing no causal estimate."""

    outcome_type: Literal["causal_identification"] = "causal_identification"
    schema_version: Literal["1"] = "1"
    contract_version: Literal["1"] = CAUSAL_IDENTIFICATION_CONTRACT_VERSION
    request_id: NonEmptyStr
    identification_request: CausalIdentificationRequest
    design_type: ObservationalDesignType | None = None
    estimand: CausalEstimand | None = None
    treatment: TreatmentContrast | None = None
    outcome: CausalOutcome | None = None
    population: PopulationDefinition | None = None
    units: UnitSemantics | None = None
    time: TimeSemantics | None = None
    adjustment_set: AdjustmentSet | None = None
    causal_graph: CausalGraph | None = None
    assumptions: tuple[CausalAssumption, ...] = ()
    status: IdentificationStatus
    diagnostics: tuple[CausalDiagnostic, ...]
    warnings: tuple[CausalDiagnostic, ...]
    evidence_limitations: tuple[EvidenceLimitation, ...]
    provenance: ProvenanceRecords
    abstention_reason: CausalAbstentionReason | None = None

    @field_validator("diagnostics", "warnings")
    @classmethod
    def canonicalize_diagnostics(
        cls,
        value: tuple[CausalDiagnostic, ...],
    ) -> tuple[CausalDiagnostic, ...]:
        return tuple(sorted(value, key=_canonical_model_key))

    @field_validator("evidence_limitations")
    @classmethod
    def canonicalize_limitations(
        cls,
        value: tuple[EvidenceLimitation, ...],
    ) -> tuple[EvidenceLimitation, ...]:
        return tuple(sorted(value, key=lambda item: item.code.value))

    @model_validator(mode="after")
    def populate_echoes_and_validate_abstention(self) -> Self:
        source = self.identification_request
        echoes = {
            "design_type": source.design.design_type,
            "estimand": source.estimand,
            "treatment": source.treatment,
            "outcome": source.outcome,
            "population": source.population,
            "units": source.units,
            "time": source.time,
            "causal_graph": source.causal_graph,
            "assumptions": source.assumptions,
        }
        for field, expected in echoes.items():
            current = getattr(self, field)
            if current is None or (field == "assumptions" and not current):
                object.__setattr__(self, field, expected)
            elif current != expected:
                raise ValueError(f"{field} must match identification_request")

        if self.adjustment_set is None:
            object.__setattr__(self, "adjustment_set", source.adjustment_set)

        requires_abstention = self.status is not IdentificationStatus.IDENTIFIED
        if requires_abstention != (self.abstention_reason is not None):
            raise ValueError("abstention reason is required exactly for non-identified results")
        return self


__all__ = [
    "CAUSAL_IDENTIFICATION_CONTRACT_VERSION",
    "CausalAbstentionReason",
    "CausalIdentificationRequest",
    "IdentificationResult",
    "IdentificationStatus",
    "ObservationalAnalysisRequest",
]
