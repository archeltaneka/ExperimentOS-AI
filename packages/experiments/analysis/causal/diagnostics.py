"""Stable causal-identification diagnostics and evidence limitations."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import field_validator

from ..base import ContractModel, NonEmptyStr, ScalarValue
from ..provenance import DiagnosticSeverity, ProvenanceRecords
from .assumptions import CausalAssumptionCode


class CausalDiagnosticCode(StrEnum):
    """Stable codes emitted by deterministic identification validation."""

    MISSING_ESTIMAND = "identification.missing_estimand"
    MISSING_TREATMENT = "identification.missing_treatment"
    MISSING_OUTCOME = "identification.missing_outcome"
    MISSING_UNIT_SEMANTICS = "identification.missing_unit_semantics"
    CONTRADICTORY_ROLE = "variable.contradictory_role"
    DUPLICATE_VARIABLE = "variable.duplicate"
    DUPLICATE_COVARIATE = "variable.duplicate_covariate"
    POST_TREATMENT_ADJUSTMENT = "adjustment.post_treatment"
    TREATMENT_LEAKAGE = "adjustment.treatment_leakage"
    OUTCOME_LEAKAGE = "adjustment.outcome_leakage"
    IDENTIFIER_MISUSE = "adjustment.identifier_misuse"
    INVALID_ADJUSTMENT_ROLE = "adjustment.invalid_role"
    UNKNOWN_COVARIATE_TIMING = "adjustment.unknown_timing"
    MALFORMED_ADJUSTMENT_SET = "adjustment.malformed"
    DUPLICATE_ADJUSTMENT_VARIABLE = "adjustment.duplicate_variable"
    MISSING_ADJUSTMENT_VARIABLE = "adjustment.missing_variable"
    MISSING_ADJUSTMENT_INFORMATION = "identification.missing_adjustment_information"
    POST_TREATMENT_EFFECT_MODIFIER = "effect_modifier.post_treatment"
    UNKNOWN_EFFECT_MODIFIER_TIMING = "effect_modifier.unknown_timing"
    DUPLICATE_EFFECT_MODIFIER = "effect_modifier.duplicate"
    MISSING_EFFECT_MODIFIER = "effect_modifier.missing_variable"
    GRAPH_DUPLICATE_NODE = "graph.duplicate_node"
    GRAPH_DUPLICATE_EDGE = "graph.duplicate_edge"
    GRAPH_SELF_LOOP = "graph.self_loop"
    GRAPH_UNKNOWN_NODE = "graph.unknown_node"
    GRAPH_UNKNOWN_VARIABLE = "graph.unknown_variable"
    GRAPH_CYCLE = "graph.cycle"
    GRAPH_ADJUSTMENT_INCONSISTENCY = "graph.adjustment_inconsistency"
    MISSING_REQUIRED_ASSUMPTION = "assumption.missing_required"
    CONTRADICTORY_ASSUMPTION = "assumption.contradictory"
    VIOLATED_ASSUMPTION = "assumption.violated"
    UNVERIFIED_ASSUMPTION = "assumption.unverified"
    UNSUPPORTED_DESIGN = "design.unsupported"
    UNSUPPORTED_ESTIMAND = "estimand.unsupported"
    ESTIMAND_DESIGN_MISMATCH = "estimand.design_mismatch"
    ESTIMAND_REQUEST_MISMATCH = "estimand.request_mismatch"
    MISSING_PRE_PERIOD = "did.missing_pre_period"
    MISSING_POST_PERIOD = "did.missing_post_period"
    REVERSED_TIMING = "time.reversed"
    MISSING_TREATMENT_TIME = "time.missing_treatment_start"
    MISSING_DID_GROUP = "did.missing_group"
    MISSING_STABLE_ADOPTION = "did.missing_stable_adoption"
    INSUFFICIENT_IDENTIFICATION_EVIDENCE = "identification.insufficient_evidence"


class CausalDiagnosticCategory(StrEnum):
    """Contract areas to which identification diagnostics belong."""

    REQUEST = "request"
    ESTIMAND = "estimand"
    VARIABLE = "variable"
    TIMING = "timing"
    ADJUSTMENT = "adjustment"
    GRAPH = "graph"
    ASSUMPTION = "assumption"
    DESIGN = "design"
    EVIDENCE = "evidence"


class CausalDiagnosticStatus(StrEnum):
    """Observed state of one identification diagnostic."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class CausalDiagnosticContext(ContractModel):
    """One canonical privacy-safe diagnostic context entry."""

    key: NonEmptyStr
    value: ScalarValue


class CausalDiagnostic(ContractModel):
    """Structured identification evidence without row-level data."""

    code: CausalDiagnosticCode
    category: CausalDiagnosticCategory
    severity: DiagnosticSeverity
    status: CausalDiagnosticStatus
    message: NonEmptyStr
    context: tuple[CausalDiagnosticContext, ...] = ()

    @field_validator("context", mode="before")
    @classmethod
    def expand_context_mapping(cls, value: object) -> object:
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("diagnostic context keys must be strings")
            return tuple({"key": key, "value": item} for key, item in value.items())
        return value

    @field_validator("context")
    @classmethod
    def canonicalize_context(
        cls,
        value: tuple[CausalDiagnosticContext, ...],
    ) -> tuple[CausalDiagnosticContext, ...]:
        canonical = tuple(sorted(value, key=lambda entry: entry.key))
        if len(canonical) != len({entry.key for entry in canonical}):
            raise ValueError("diagnostic context keys must be unique")
        return canonical


class EvidenceLimitationCode(StrEnum):
    """Stable first-class limitations retained with identification results."""

    EXCHANGEABILITY_ASSERTED = "exchangeability_asserted_not_proven"
    UNMEASURED_CONFOUNDING_POSSIBLE = "unmeasured_confounding_possible"
    OVERLAP_NOT_EVALUATED = "overlap_not_evaluated"
    PARALLEL_TRENDS_UNVERIFIED = "parallel_trends_unverified"
    NO_SENSITIVITY_ANALYSIS = "no_sensitivity_analysis"
    ADJUSTMENT_SET_NOT_GRAPH_VALIDATED = "adjustment_set_not_graph_validated"
    USER_SUPPLIED_GRAPH = "user_supplied_graph"


class EvidenceLimitation(ContractModel):
    """Structured caveat retained for reports, policy, telemetry, and CI."""

    code: EvidenceLimitationCode
    description: NonEmptyStr
    assumption_codes: tuple[CausalAssumptionCode, ...] = ()
    provenance: ProvenanceRecords

    @field_validator("assumption_codes")
    @classmethod
    def canonicalize_assumptions(
        cls,
        value: tuple[CausalAssumptionCode, ...],
    ) -> tuple[CausalAssumptionCode, ...]:
        canonical = tuple(sorted(value, key=lambda code: code.value))
        if len(canonical) != len(set(canonical)):
            raise ValueError("limitation assumption codes must be unique")
        return canonical


__all__ = [
    "CausalDiagnostic",
    "CausalDiagnosticCategory",
    "CausalDiagnosticCode",
    "CausalDiagnosticContext",
    "CausalDiagnosticStatus",
    "EvidenceLimitation",
    "EvidenceLimitationCode",
]
