"""Public typed inference projections, excluding native execution requests."""

from datetime import datetime
from typing import Literal

from ..base import ContractModel
from ..estimands import EstimandDefinition
from ..metrics import MetricDefinition
from ..provenance import AnalysisWarning, AssumptionAssessment, ProvenanceRecord, ProvenanceRecords
from ..randomized.bayesian.models import (
    BayesianAbstentionReason,
    BayesianArmPosterior,
    BayesianComputationConfig,
    BayesianComputationStatus,
    BayesianDiagnostic,
    BayesianLikelihood,
    BayesianPrior,
    PosteriorEffectSummary,
)
from ..randomized.config import RandomizedAnalysisConfig
from ..randomized.cuped.models import (
    CupedAbstentionReason,
    CupedCoefficient,
    CupedCovariateBalance,
    CupedSampleRetention,
    CupedStatus,
    VarianceReduction,
)
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
from ..randomized.sequential.models import (
    PlanIntegrityStatus,
    SequentialAlphaSummary,
    SequentialBoundary,
    SequentialDiagnostic,
    SequentialLookMetadata,
    SequentialStoppingStatus,
)
from ..study_designs import CovariateDefinition


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


class BayesianEvidence(ContractModel):
    evidence_type: Literal["bayesian"] = "bayesian"
    request_id: str
    metric: MetricDefinition | None
    estimand: EstimandDefinition | None
    status: BayesianComputationStatus
    likelihood: BayesianLikelihood | None
    treatment_prior: BayesianPrior | None
    control_prior: BayesianPrior | None
    treatment_posterior: BayesianArmPosterior | None
    control_posterior: BayesianArmPosterior | None
    effect: PosteriorEffectSummary | None
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[BayesianDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    configuration: BayesianComputationConfig
    configuration_provenance: ProvenanceRecord | None
    abstention_reason: BayesianAbstentionReason | None


class CupedEvidence(ContractModel):
    evidence_type: Literal["cuped"] = "cuped"
    request_id: str
    status: CupedStatus
    baseline_status: ComputationStatus
    covariate: CovariateDefinition | None
    retention: CupedSampleRetention | None
    coefficient: CupedCoefficient | None
    balance: CupedCovariateBalance | None
    adjusted_result: RandomizedEvidence | None
    comparable_unadjusted_result: RandomizedEvidence | None
    full_sample_unadjusted_result: RandomizedEvidence
    variance_reduction: VarianceReduction
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[RandomizedDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    abstention_reason: CupedAbstentionReason | None


class SequentialLookEvidence(ContractModel):
    look_index: int
    information_time: float
    cumulative_sample_count: int
    treatment_count: int
    control_count: int
    look_level_analysis: RandomizedEvidence | None
    standardized_statistic: float | None
    sequential_boundary: float
    cumulative_alpha_spent: float
    nominal_alpha: float
    boundary_crossed: bool
    stopping_status: SequentialStoppingStatus
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[SequentialDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    executed_at: datetime | None
    provenance: ProvenanceRecords


class SequentialEvidence(ContractModel):
    evidence_type: Literal["sequential"] = "sequential"
    plan_id: str
    plan_fingerprint: str
    estimand: EstimandDefinition
    current_status: SequentialStoppingStatus
    plan_integrity: PlanIntegrityStatus
    alpha_summary: SequentialAlphaSummary
    boundaries: tuple[SequentialBoundary, ...]
    looks: tuple[SequentialLookEvidence, ...]
    deviations: tuple[SequentialDiagnostic, ...]
    first_look: SequentialLookMetadata | None
    latest_look: SequentialLookMetadata | None
    provenance: ProvenanceRecords
