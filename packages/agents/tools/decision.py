from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from packages.agents.tools.schemas import ToolSpec


class EvidenceValidationInput(BaseModel):
    has_experiment_analysis: bool
    has_business_impact: bool
    has_risk_assessment: bool
    has_statistical_significance: bool
    citation_count: int


class EvidenceValidationOutput(BaseModel):
    is_valid: bool
    missing_requirements: list[str]


def validate_required_evidence(
    input_model: EvidenceValidationInput,
) -> EvidenceValidationOutput:
    missing: list[str] = []
    if not input_model.has_experiment_analysis:
        missing.append("experiment_analysis")
    if not input_model.has_business_impact:
        missing.append("business_impact")
    if not input_model.has_risk_assessment:
        missing.append("risk_assessment")
    if not input_model.has_statistical_significance:
        missing.append("statistical_significance")
    if input_model.citation_count <= 0:
        missing.append("citations")
    return EvidenceValidationOutput(
        is_valid=not missing,
        missing_requirements=missing,
    )


class DecisionConfidenceInput(BaseModel):
    analysis_confidence: str
    business_confidence: str
    risk_confidence: str
    overall_risk_level: str
    has_statistical_support: bool
    has_citations: bool


class DecisionConfidenceOutput(BaseModel):
    confidence: Literal["high", "medium", "low", "unknown"]


def score_decision_confidence(
    input_model: DecisionConfidenceInput,
) -> DecisionConfidenceOutput:
    normalized = {
        input_model.analysis_confidence.strip().lower(),
        input_model.business_confidence.strip().lower(),
        input_model.risk_confidence.strip().lower(),
    }
    if (
        normalized == {"high"}
        and input_model.overall_risk_level == "low"
        and input_model.has_statistical_support
        and input_model.has_citations
    ):
        return DecisionConfidenceOutput(confidence="high")
    if "low" in normalized or "unknown" in normalized or input_model.overall_risk_level == "high":
        return DecisionConfidenceOutput(confidence="medium")
    return DecisionConfidenceOutput(confidence="medium")


EVIDENCE_VALIDATION_TOOL = ToolSpec(
    name="validate_required_evidence",
    input_model=EvidenceValidationInput,
    output_model=EvidenceValidationOutput,
    handler=validate_required_evidence,
)

DECISION_CONFIDENCE_TOOL = ToolSpec(
    name="score_decision_confidence",
    input_model=DecisionConfidenceInput,
    output_model=DecisionConfidenceOutput,
    handler=score_decision_confidence,
)
