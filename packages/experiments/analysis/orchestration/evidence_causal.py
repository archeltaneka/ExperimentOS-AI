"""Explicit aggregate causal evidence, excluding graphs, row scores and fold assignments."""

from typing import Literal

from ..base import ContractModel
from ..causal.advanced import models as advanced
from ..causal.assumptions import CausalAssumption
from ..causal.diagnostics import CausalDiagnostic, EvidenceLimitation
from ..causal.did import models as did
from ..causal.dml import models as dml
from ..causal.dml import results as dml_results
from ..causal.dowhy import models as dowhy
from ..causal.estimands import CausalEstimand, CausalEstimandKind
from ..causal.hte import models as hte
from ..causal.hte import results as hte_results
from ..causal.ipw import models as ipw
from ..causal.models import CausalAbstentionReason, IdentificationStatus
from ..causal.propensity import models as ps
from ..provenance import AnalysisWarning, ProvenanceRecords


class CausalEvidenceBase(ContractModel):
    request_id: str
    assumptions: tuple[CausalAssumption, ...]
    evidence_limitations: tuple[EvidenceLimitation, ...]
    provenance: ProvenanceRecords


class IdentificationEvidence(CausalEvidenceBase):
    evidence_type: Literal["identification"] = "identification"
    status: IdentificationStatus
    estimand: CausalEstimand | None
    diagnostics: tuple[CausalDiagnostic, ...]
    warnings: tuple[CausalDiagnostic, ...]
    abstention_reason: CausalAbstentionReason | None


class DidEvidence(CausalEvidenceBase):
    evidence_type: Literal["did"] = "did"
    status: did.DidStatus
    estimand: CausalEstimand | None
    configuration: did.DifferenceInDifferencesConfig
    sample_counts: did.DidSampleCounts
    cell_means: did.DidCellMeans | None
    test_result: did.DidTestResult | None
    pretrend: did.DidPretrendDiagnostic
    diagnostics: tuple[did.DidDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    abstention_reason: did.DidAbstentionReason | None


class PropensityEvidence(CausalEvidenceBase):
    evidence_type: Literal["propensity"] = "propensity"
    status: ps.PropensityStatus
    estimand: CausalEstimandKind | None
    configuration: ps.PropensityConfig
    adjustment_covariates: tuple[str, ...]
    sample_counts: ps.PropensitySampleCounts
    score_diagnostics: ps.PropensityScoreDiagnostics | None
    common_support: ps.CommonSupportDiagnostic
    overlap: ps.OverlapDiagnostic
    balance: ps.BalanceDiagnostics | None
    diagnostics: tuple[ps.PropensityDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    abstention_reason: ps.PropensityAbstentionReason | None


class WeightSetEvidence(ContractModel):
    kind: ipw.IPWWeightSetKind
    overall: ps.DistributionSummary
    treated: ps.DistributionSummary
    control: ps.DistributionSummary
    ess: ps.EffectiveSampleSizeDiagnostic


class IPWWeightEvidence(ContractModel):
    estimand: CausalEstimandKind
    treatment_prevalence: float
    raw_treated_formula: str
    raw_control_formula: str
    stabilization_rule: str | None
    raw: WeightSetEvidence
    stabilized: WeightSetEvidence | None
    pre_clipping: WeightSetEvidence
    estimation: WeightSetEvidence
    clipping: ipw.IPWClippingDiagnostics


class IPWEvidence(CausalEvidenceBase):
    evidence_type: Literal["ipw"] = "ipw"
    status: ipw.IPWStatus
    causal_status: ipw.IPWCausalStatus
    estimand: CausalEstimand | None
    configuration: ipw.IPWConfig
    point_estimate: float | None
    treatment_mean: float | None
    control_mean: float | None
    test_result: ipw.IPWTestResult | None
    weights: IPWWeightEvidence | None
    overlap: ps.OverlapDiagnostic
    balance: ps.BalanceDiagnostics | None
    balance_status: ipw.IPWBalanceStatus
    sample_counts: ipw.IPWSampleCounts
    sensitivity_flags: tuple[ipw.IPWSensitivityFlag, ...]
    diagnostics: tuple[ipw.IPWDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    abstention_reason: ipw.IPWAbstentionReason | None


class DMLEvidence(CausalEvidenceBase):
    evidence_type: Literal["dml"] = "dml"
    status: dml_results.DMLStatus
    causal_status: dml_results.DMLCausalStatus
    estimand: CausalEstimand | None
    configuration: dml.DMLConfig
    configuration_fingerprint_sha256: str | None
    point_estimate: float | None
    test_result: dml.DMLTestResult | None
    nuisance_diagnostics: dml.DMLNuisanceDiagnostics | None
    outcome_residual_diagnostics: dml.DMLResidualSummary | None
    treatment_residual_diagnostics: dml.DMLResidualSummary | None
    influence_diagnostics: dml.DMLInfluenceDiagnostics | None
    overlap: dml.DMLOverlapDiagnostic | None
    sample_counts: dml.DMLSampleCounts
    sensitivity_flags: tuple[dml_results.DMLSensitivityFlag, ...]
    diagnostics: tuple[dml.DMLDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    abstention_reason: dml_results.DMLAbstentionReason | None


class HTEEvidence(CausalEvidenceBase):
    evidence_type: Literal["hte"] = "hte"
    status: hte_results.HTEStatus
    analysis_semantics: hte.HTEPreSpecificationStatus
    estimand: CausalEstimand | None
    configuration_fingerprint_sha256: str | None
    modifier: hte.EffectModifierDefinition
    subgroup_results: tuple[hte_results.SubgroupEffectResult, ...]
    interactions: tuple[hte_results.InteractionEffectResult, ...]
    global_heterogeneity: hte_results.GlobalHeterogeneityEvidence
    multiplicity: hte_results.MultiplicityContext
    global_overlap: dml.DMLOverlapDiagnostic | None
    nuisance_diagnostics: dml.DMLNuisanceDiagnostics | None
    raw_count: int
    retained_count: int
    unassigned_count: int
    diagnostics: tuple[hte_results.HTEDiagnostic, ...]
    abstention_reason: str | None
    adapter_provenance: advanced.AdvancedAdapterProvenance | None


class AdvancedEvidence(CausalEvidenceBase):
    evidence_type: Literal["advanced"] = "advanced"
    status: dml_results.DMLStatus
    estimand: CausalEstimand | None
    configuration: advanced.AdvancedEstimatorConfig
    configuration_fingerprint_sha256: str | None
    point_estimate: float | None
    inference: advanced.AdvancedInference | None
    sample_counts: dml.DMLSampleCounts
    overlap: dml.DMLOverlapDiagnostic | None
    nuisance_diagnostics: dml.DMLNuisanceDiagnostics | None
    diagnostics: tuple[dml.DMLDiagnostic, ...]
    adapter_provenance: advanced.AdvancedAdapterProvenance | None
    abstention_reason: dml_results.DMLAbstentionReason | None


class DoWhyEvidence(CausalEvidenceBase):
    evidence_type: Literal["dowhy"] = "dowhy"
    status: dowhy.DoWhyOperationStatus
    estimand: CausalEstimand | None
    configuration_fingerprint_sha256: str | None
    identification: dowhy.DoWhyIdentificationEvidence
    estimate: dowhy.DoWhyEstimateEvidence | None
    refutations: tuple[dowhy.DoWhyRefutationResult, ...]
    diagnostics: tuple[dowhy.DoWhyDiagnostic, ...]
    adapter_provenance: dowhy.DoWhyAdapterProvenance | None
    abstention_reason: dowhy.DoWhyAbstentionReason | None
