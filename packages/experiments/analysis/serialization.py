"""Canonical JSON serialization for the public internal analysis boundary."""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from .base import ContractModel
from .business_impact import BusinessImpactProjection, ProjectedValue
from .causal.models import (
    CausalIdentificationRequest,
    IdentificationResult,
    ObservationalAnalysisRequest,
)
from .descriptive.models import DescriptiveStatisticsResult
from .estimands import EstimandDefinition
from .estimates import AnalysisFinding, EffectEstimate
from .randomized.bayesian.models import BayesianAnalysisResult
from .randomized.sequential.models import SequentialAnalysisHistory
from .requests import AnalysisRequest
from .results import AnalysisOutcome
from .study_designs import StudyDesign
from .validation.models import EligibilityValidationResult

ANALYSIS_REQUEST_ADAPTER: TypeAdapter[AnalysisRequest] = TypeAdapter(AnalysisRequest)
STUDY_DESIGN_ADAPTER: TypeAdapter[StudyDesign] = TypeAdapter(StudyDesign)
ESTIMAND_ADAPTER: TypeAdapter[EstimandDefinition] = TypeAdapter(EstimandDefinition)
EFFECT_ESTIMATE_ADAPTER: TypeAdapter[EffectEstimate] = TypeAdapter(EffectEstimate)
ANALYSIS_FINDING_ADAPTER: TypeAdapter[AnalysisFinding] = TypeAdapter(AnalysisFinding)
ANALYSIS_OUTCOME_ADAPTER: TypeAdapter[AnalysisOutcome] = TypeAdapter(AnalysisOutcome)
BUSINESS_IMPACT_PROJECTION_ADAPTER: TypeAdapter[BusinessImpactProjection] = TypeAdapter(
    BusinessImpactProjection
)
PROJECTED_VALUE_ADAPTER: TypeAdapter[ProjectedValue] = TypeAdapter(ProjectedValue)
ELIGIBILITY_VALIDATION_RESULT_ADAPTER: TypeAdapter[EligibilityValidationResult] = TypeAdapter(
    EligibilityValidationResult
)
DESCRIPTIVE_STATISTICS_RESULT_ADAPTER: TypeAdapter[DescriptiveStatisticsResult] = TypeAdapter(
    DescriptiveStatisticsResult
)
SEQUENTIAL_ANALYSIS_HISTORY_ADAPTER: TypeAdapter[SequentialAnalysisHistory] = TypeAdapter(
    SequentialAnalysisHistory
)
BAYESIAN_ANALYSIS_RESULT_ADAPTER: TypeAdapter[BayesianAnalysisResult] = TypeAdapter(
    BayesianAnalysisResult
)
CAUSAL_IDENTIFICATION_REQUEST_ADAPTER: TypeAdapter[CausalIdentificationRequest] = TypeAdapter(
    CausalIdentificationRequest
)
OBSERVATIONAL_ANALYSIS_REQUEST_ADAPTER: TypeAdapter[ObservationalAnalysisRequest] = TypeAdapter(
    ObservationalAnalysisRequest
)
IDENTIFICATION_RESULT_ADAPTER: TypeAdapter[IdentificationResult] = TypeAdapter(IdentificationResult)


def to_canonical_json(model: ContractModel) -> str:
    """Serialize an ExperimentOS analysis contract to deterministic JSON."""
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def analysis_request_from_json(payload: str | bytes) -> AnalysisRequest:
    """Validate JSON as an analysis request."""
    return ANALYSIS_REQUEST_ADAPTER.validate_json(payload)


def study_design_from_json(payload: str | bytes) -> StudyDesign:
    """Validate JSON through the study-design discriminator."""
    return STUDY_DESIGN_ADAPTER.validate_json(payload)


def estimand_from_json(payload: str | bytes) -> EstimandDefinition:
    """Validate JSON as an estimand definition."""
    return ESTIMAND_ADAPTER.validate_json(payload)


def effect_estimate_from_json(payload: str | bytes) -> EffectEstimate:
    """Validate JSON through the effect-estimate discriminator."""
    return EFFECT_ESTIMATE_ADAPTER.validate_json(payload)


def analysis_finding_from_json(payload: str | bytes) -> AnalysisFinding:
    """Validate JSON through the analysis-finding discriminator."""
    return ANALYSIS_FINDING_ADAPTER.validate_json(payload)


def analysis_outcome_from_json(payload: str | bytes) -> AnalysisOutcome:
    """Validate JSON through the analysis-outcome discriminator."""
    return ANALYSIS_OUTCOME_ADAPTER.validate_json(payload)


def business_impact_projection_from_json(payload: str | bytes) -> BusinessImpactProjection:
    """Validate JSON as a business-impact projection."""
    return BUSINESS_IMPACT_PROJECTION_ADAPTER.validate_json(payload)


def projected_value_from_json(payload: str | bytes) -> ProjectedValue:
    """Validate JSON as one independently uncertain projected value."""
    return PROJECTED_VALUE_ADAPTER.validate_json(payload)


def eligibility_validation_result_from_json(
    payload: str | bytes,
) -> EligibilityValidationResult:
    """Validate JSON as a pre-estimator eligibility validation result."""
    return ELIGIBILITY_VALIDATION_RESULT_ADAPTER.validate_json(payload)


def descriptive_statistics_result_from_json(payload: str | bytes) -> DescriptiveStatisticsResult:
    """Validate JSON as a canonical descriptive-statistics result."""
    return DESCRIPTIVE_STATISTICS_RESULT_ADAPTER.validate_json(payload)


def sequential_analysis_history_from_json(payload: str | bytes) -> SequentialAnalysisHistory:
    """Validate JSON as one immutable sequential-analysis audit history."""
    return SEQUENTIAL_ANALYSIS_HISTORY_ADAPTER.validate_json(payload)


def bayesian_analysis_result_from_json(payload: str | bytes) -> BayesianAnalysisResult:
    """Validate JSON as one Bayesian randomized-analysis result."""
    return BAYESIAN_ANALYSIS_RESULT_ADAPTER.validate_json(payload)


def causal_identification_request_from_json(
    payload: str | bytes,
) -> CausalIdentificationRequest:
    """Validate JSON as an observational causal-identification request."""
    return CAUSAL_IDENTIFICATION_REQUEST_ADAPTER.validate_json(payload)


def observational_analysis_request_from_json(
    payload: str | bytes,
) -> ObservationalAnalysisRequest:
    """Validate JSON as a future estimator-facing observational request."""
    return OBSERVATIONAL_ANALYSIS_REQUEST_ADAPTER.validate_json(payload)


def identification_result_from_json(payload: str | bytes) -> IdentificationResult:
    """Validate JSON as an identification-only result."""
    return IDENTIFICATION_RESULT_ADAPTER.validate_json(payload)
