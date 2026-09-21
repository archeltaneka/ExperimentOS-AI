"""Public typed inference projections, excluding native execution requests."""

from typing import Literal

from ..base import ContractModel
from ..estimands import EstimandDefinition
from ..metrics import MetricDefinition
from ..provenance import AnalysisWarning, AssumptionAssessment, ProvenanceRecord, ProvenanceRecords
from ..randomized.config import RandomizedAnalysisConfig
from ..randomized.models import (
    BinaryArmSummary,
    ComputationStatus,
    Conclusion,
    ContinuousArmSummary,
    EvidenceCategory,
    PointEffect,
    PracticalSignificance,
    RandomizedAbstentionReason,
    RandomizedAnalysisResult,
    RandomizedDiagnostic,
    RandomizedHypothesis,
    RandomizedTestResult,
)


class RandomizedEvidence(ContractModel):
    evidence_type: Literal["randomized"] = "randomized"
    request_id: str
    metric: MetricDefinition
    estimand: EstimandDefinition
    hypothesis: RandomizedHypothesis
    status: ComputationStatus
    conclusion: Conclusion
    practical_significance: PracticalSignificance
    evidence_category: EvidenceCategory
    treatment_summary: ContinuousArmSummary | BinaryArmSummary | None
    control_summary: ContinuousArmSummary | BinaryArmSummary | None
    point_effect: PointEffect | None
    test_result: RandomizedTestResult | None
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[RandomizedDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    configuration: RandomizedAnalysisConfig
    configuration_provenance: ProvenanceRecord | None
    abstention_reason: RandomizedAbstentionReason | None


def project_randomized(native: RandomizedAnalysisResult) -> RandomizedEvidence:
    return RandomizedEvidence.model_validate(
        {
            field: getattr(native, field)
            for field in RandomizedEvidence.model_fields
            if field != "evidence_type"
        }
    ).model_copy(deep=True)
