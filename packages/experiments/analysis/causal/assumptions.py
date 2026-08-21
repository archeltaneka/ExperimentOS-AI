"""Machine-readable causal assumptions that distinguish assertion from evidence."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import field_validator, model_validator

from ..base import ContractModel, NonEmptyStr
from ..provenance import ProvenanceRecords


class CausalAssumptionCode(StrEnum):
    """Stable vocabulary for supported observational identifying assumptions."""

    CONSISTENCY = "consistency"
    INTERFERENCE_LIMITATION = "interference_limitation"
    EXCHANGEABILITY = "exchangeability"
    POSITIVITY = "positivity"
    TEMPORAL_ORDERING = "temporal_ordering"
    PARALLEL_TRENDS = "parallel_trends"
    NO_ANTICIPATION = "no_anticipation"
    STABLE_TREATMENT_DEFINITION = "stable_treatment_definition"
    STABLE_UNIT_POPULATION = "stable_unit_population"


class CausalAssumptionStatus(StrEnum):
    """Evidence state that never equates a declaration with causal proof."""

    ASSERTED = "asserted"
    SUPPORTED_BY_DIAGNOSTICS = "supported_by_diagnostics"
    VIOLATED = "violated"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


class AssumptionApplicability(StrEnum):
    """Whether an assumption is required for the declared design."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"


class AssumptionTestability(StrEnum):
    """Extent to which observed-data diagnostics can assess an assumption."""

    FULLY_TESTABLE = "fully_testable"
    PARTIALLY_TESTABLE = "partially_testable"
    NOT_FULLY_TESTABLE = "not_fully_testable"
    UNTESTABLE = "untestable"


class CausalAssumption(ContractModel):
    """One declared assumption, its evidence state, and retained limitations."""

    code: CausalAssumptionCode
    description: NonEmptyStr
    applicability: AssumptionApplicability
    status: CausalAssumptionStatus
    testability: AssumptionTestability
    evidence: ProvenanceRecords
    diagnostic_references: tuple[NonEmptyStr, ...] = ()
    limitations: tuple[NonEmptyStr, ...] = ()

    @field_validator("diagnostic_references", "limitations")
    @classmethod
    def canonicalize_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        canonical = tuple(sorted(value))
        if len(canonical) != len(set(canonical)):
            raise ValueError("assumption references and limitations must be unique")
        return canonical

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        is_not_applicable = self.status is CausalAssumptionStatus.NOT_APPLICABLE
        if is_not_applicable != (
            self.applicability is AssumptionApplicability.NOT_APPLICABLE
        ):
            raise ValueError("not_applicable status and applicability must match")
        if (
            self.code is CausalAssumptionCode.EXCHANGEABILITY
            and self.testability is AssumptionTestability.FULLY_TESTABLE
        ):
            raise ValueError("exchangeability is not fully testable from observed data")
        return self


__all__ = [
    "AssumptionApplicability",
    "AssumptionTestability",
    "CausalAssumption",
    "CausalAssumptionCode",
    "CausalAssumptionStatus",
]
