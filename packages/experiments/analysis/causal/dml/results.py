"""Owned public contracts for bounded partialling-out DML results."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ...base import ContractModel, FiniteFloat, NonEmptyStr
from ...provenance import AnalysisWarning, DiagnosticSeverity, ProvenanceRecords
from ..adjustment import AdjustmentSet
from ..assumptions import CausalAssumption
from ..designs import CausalOutcome
from ..diagnostics import EvidenceLimitation
from ..estimands import CausalEstimand, EffectScale, TargetPopulation, TreatmentContrast
from ..models import ObservationalAnalysisRequest
from .models import (
    DMLConfig,
    DMLDataBinding,
    DMLDiagnostic,
    DMLFoldPlan,
    DMLInfluenceDiagnostics,
    DMLNuisanceDiagnostics,
    DMLOverlapDiagnostic,
    DMLResidualSummary,
    DMLSampleCounts,
    DMLTestResult,
)
from .protocols import NuisanceAdapterMetadata, NuisanceFitReport, NuisanceRole

type NonNegativeCount = Annotated[int, Field(strict=True, ge=0)]
type PositiveCount = Annotated[int, Field(strict=True, gt=0)]


class DMLStatus(StrEnum):
    """Terminal execution state for one DML analysis."""

    COMPLETED = "completed"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class DMLCausalStatus(StrEnum):
    """Causal interpretation state kept separate from numerical availability."""

    CONDITIONAL_ON_DECLARED_ASSUMPTIONS = "conditional_on_declared_assumptions"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class DMLSensitivityCode(StrEnum):
    """Structured DML warnings that do not repair identification."""

    IDENTIFICATION_ASSUMPTIONS_UNVERIFIED = "identification_assumptions_unverified"
    WEAK_OVERLAP = "weak_overlap"


class DMLSensitivityFlag(ContractModel):
    """One active non-fatal DML sensitivity warning."""

    code: DMLSensitivityCode
    severity: DiagnosticSeverity
    message: NonEmptyStr


class DMLAbstentionReason(ContractModel):
    """Primary normalized reason a conclusive DML estimate was withheld."""

    code: NonEmptyStr
    message: NonEmptyStr
    fold_index: NonNegativeCount | None = None
    nuisance_role: NuisanceRole | None = None


class DMLFoldFitProvenance(ContractModel):
    """Fold-level fit evidence without estimator objects or row identities."""

    fold_index: NonNegativeCount
    train_count: PositiveCount
    score_count: PositiveCount
    outcome_adapter: NuisanceAdapterMetadata
    treatment_adapter: NuisanceAdapterMetadata
    outcome_fit: NuisanceFitReport
    treatment_fit: NuisanceFitReport


class DMLResult(ContractModel):
    """Complete public result for the explicitly supported DML V1 design."""

    outcome_type: Literal["double_machine_learning"] = "double_machine_learning"
    schema_version: Literal["1"] = "1"
    configuration_fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    method: Literal["dml"] = "dml"
    score_method: Literal["partialling_out_orthogonal_score"] = "partialling_out_orthogonal_score"
    request_id: NonEmptyStr
    analysis_request: ObservationalAnalysisRequest
    binding: DMLDataBinding
    configuration: DMLConfig
    status: DMLStatus
    causal_status: DMLCausalStatus
    estimand: CausalEstimand | None
    treatment: TreatmentContrast | None
    outcome: CausalOutcome | None
    covariates: tuple[NonEmptyStr, ...]
    target_population: TargetPopulation | None
    effect_scale: EffectScale | None
    adjustment_set: AdjustmentSet | None
    point_estimate: FiniteFloat | None = None
    test_result: DMLTestResult | None = None
    fold_plan: DMLFoldPlan | None = None
    fold_fits: tuple[DMLFoldFitProvenance, ...] = ()
    nuisance_diagnostics: DMLNuisanceDiagnostics | None = None
    outcome_residual_diagnostics: DMLResidualSummary | None = None
    treatment_residual_diagnostics: DMLResidualSummary | None = None
    influence_diagnostics: DMLInfluenceDiagnostics | None = None
    overlap: DMLOverlapDiagnostic | None = None
    sample_counts: DMLSampleCounts
    assumptions: tuple[CausalAssumption, ...]
    evidence_limitations: tuple[EvidenceLimitation, ...]
    sensitivity_flags: tuple[DMLSensitivityFlag, ...]
    diagnostics: tuple[DMLDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    abstention_reason: DMLAbstentionReason | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> Self:
        if self.fold_plan is not None and (
            self.fold_plan.fold_count != self.configuration.fold_count
            or self.fold_plan.random_seed != self.configuration.random_seed
        ):
            raise ValueError("DML fold provenance must match the execution configuration")
        if self.fold_fits and (
            self.fold_plan is None or len(self.fold_fits) != self.fold_plan.fold_count
        ):
            raise ValueError("DML fold fit provenance must cover every configured fold")
        required = (
            self.point_estimate,
            self.test_result,
            self.fold_plan,
            self.nuisance_diagnostics,
            self.outcome_residual_diagnostics,
            self.treatment_residual_diagnostics,
            self.influence_diagnostics,
            self.overlap,
        )
        if self.status is DMLStatus.COMPLETED:
            if any(item is None for item in required) or not self.fold_fits:
                raise ValueError("completed DML results require full cross-fit evidence")
            if self.causal_status is not DMLCausalStatus.CONDITIONAL_ON_DECLARED_ASSUMPTIONS:
                raise ValueError("completed DML results require conditional causal status")
            if self.abstention_reason is not None:
                raise ValueError("completed DML results cannot contain abstention")
        else:
            if self.point_estimate is not None or self.test_result is not None:
                raise ValueError("non-completed DML results cannot contain estimates")
            if self.abstention_reason is None:
                raise ValueError("non-completed DML results require abstention")
        return self


__all__ = [
    "DMLAbstentionReason",
    "DMLCausalStatus",
    "DMLFoldFitProvenance",
    "DMLResult",
    "DMLSensitivityCode",
    "DMLSensitivityFlag",
    "DMLStatus",
]
