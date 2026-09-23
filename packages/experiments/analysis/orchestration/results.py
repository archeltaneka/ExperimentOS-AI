"""Versioned, public workflow evidence; no third-party objects or raw datasets."""

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..base import ContractModel, NonEmptyStr
from ..causal.advanced.models import AdvancedCausalResult
from ..causal.did.models import DifferenceInDifferencesResult
from ..causal.dml.results import DMLResult
from ..causal.dowhy.models import DoWhyAnalysisResult
from ..causal.hte.results import HeterogeneousEffectResult
from ..causal.ipw.models import TreatmentEffectResult
from ..causal.models import IdentificationResult
from ..causal.propensity.models import PropensityResult
from ..provenance import Diagnostic, ProvenanceRecord
from ..randomized.bayesian.models import BayesianAnalysisResult
from ..randomized.cuped.models import CupedAnalysisResult
from ..randomized.models import RandomizedAnalysisResult
from ..randomized.sequential.models import SequentialAnalysisHistory
from ..results import AbstentionReason
from .business import BusinessImpactEvidence
from .evidence_causal import (
    AdvancedEvidence,
    CausalContext,
    DidEvidence,
    DMLEvidence,
    DoWhyEvidence,
    HTEEvidence,
    IdentificationEvidence,
    IPWEvidence,
    PropensityEvidence,
)
from .evidence_randomized import (
    BayesianEvidence,
    CupedEvidence,
    RandomizedEvidence,
    SequentialEvidence,
    SequentialLookEvidence,
    project_randomized,
)

type OwnedAnalysisResult = (
    RandomizedAnalysisResult
    | BayesianAnalysisResult
    | CupedAnalysisResult
    | SequentialAnalysisHistory
    | DifferenceInDifferencesResult
    | PropensityResult
    | TreatmentEffectResult
    | DMLResult
    | HeterogeneousEffectResult
    | IdentificationResult
    | AdvancedCausalResult
    | DoWhyAnalysisResult
)
type AnalysisEvidence = Annotated[
    RandomizedEvidence
    | BayesianEvidence
    | CupedEvidence
    | SequentialEvidence
    | DidEvidence
    | PropensityEvidence
    | IPWEvidence
    | DMLEvidence
    | HTEEvidence
    | IdentificationEvidence
    | AdvancedEvidence
    | DoWhyEvidence,
    Field(discriminator="evidence_type"),
]
type ExecutionStatus = Literal[
    "completed", "inconclusive", "invalid", "abstained", "unavailable", "failed"
]


class AnalysisFailure(ContractModel):
    code: NonEmptyStr
    error_type: NonEmptyStr


class AnalysisIntegrityFinding(ContractModel):
    code: NonEmptyStr
    node: NonEmptyStr
    severity: Literal["fail", "warning"] = "fail"
    message: Literal[
        "Candidate update rejected; authoritative evidence and presentation retained."
    ] = "Candidate update rejected; authoritative evidence and presentation retained."


class AnalysisArtifactReference(ContractModel):
    artifact_id: NonEmptyStr
    kind: Literal["request", "analysis", "business_impact", "dataset", "evaluation"]
    version: NonEmptyStr
    provenance: tuple[ProvenanceRecord, ...] = ()
    evidence_fingerprint: str | None = None


def evidence_fingerprint(evidence: AnalysisEvidence | None) -> str:
    canonical = json.dumps(
        evidence.model_dump(mode="json") if evidence is not None else None,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class AnalysisResultEnvelope(ContractModel):
    schema_version: Literal["1"] = "1"
    analysis_id: NonEmptyStr
    request_id: str | None
    method: str | None
    capability: str
    status: ExecutionStatus
    created_at: datetime
    evidence: AnalysisEvidence | None = None
    evidence_fingerprint: str = ""
    diagnostics: tuple[Diagnostic, ...] = ()
    abstention: AbstentionReason | None = None
    failure: AnalysisFailure | None = None
    artifacts: tuple[AnalysisArtifactReference, ...] = ()
    integrity_findings: tuple[AnalysisIntegrityFinding, ...] = ()
    business_impact: BusinessImpactEvidence | None = None

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        digest = evidence_fingerprint(self.evidence)
        if self.evidence_fingerprint and self.evidence_fingerprint != digest:
            raise ValueError("evidence fingerprint mismatch")
        object.__setattr__(self, "evidence_fingerprint", digest)
        if self.status in {"completed", "inconclusive"} and self.evidence is None:
            raise ValueError("successful analysis requires evidence")
        if self.created_at.utcoffset() is None:
            raise ValueError("artifact timestamp must be timezone aware")
        return self


def _causal_context(native: OwnedAnalysisResult) -> CausalContext:
    if isinstance(native, IdentificationResult):
        declaration = native.identification_request
    elif isinstance(native, AdvancedCausalResult | DoWhyAnalysisResult | HeterogeneousEffectResult):
        declaration = native.execution_request.identification_result.identification_request
    elif isinstance(
        native, DifferenceInDifferencesResult | PropensityResult | TreatmentEffectResult | DMLResult
    ):
        declaration = native.analysis_request.identification
    else:
        raise TypeError("causal context requires causal evidence")
    return CausalContext.model_validate(
        {field: getattr(declaration, field) for field in CausalContext.model_fields}
    )


def project_evidence(native: OwnedAnalysisResult) -> AnalysisEvidence:
    if isinstance(native, TreatmentEffectResult):
        values = {
            field: getattr(native, field)
            for field in IPWEvidence.model_fields
            if field not in {"evidence_type", "context"}
        }
        values["context"] = _causal_context(native)
        if native.weights is not None:
            values["weights"] = native.weights.model_dump(
                exclude={
                    name: {"weights"}
                    for name in ("raw", "stabilized", "pre_clipping", "estimation")
                }
            )
        return IPWEvidence.model_validate(values)
    if isinstance(native, AdvancedCausalResult | DoWhyAnalysisResult):
        projection = AdvancedEvidence if isinstance(native, AdvancedCausalResult) else DoWhyEvidence
        identification = native.execution_request.identification_result
        values = {
            field: getattr(native, field)
            for field in projection.model_fields
            if field
            not in {
                "evidence_type",
                "request_id",
                "estimand",
                "assumptions",
                "evidence_limitations",
                "context",
            }
        }
        values.update(
            context=_causal_context(native),
            request_id=identification.request_id,
            estimand=identification.estimand,
            assumptions=identification.assumptions,
            evidence_limitations=(
                native.evidence_limitations
                if isinstance(native, AdvancedCausalResult)
                else identification.evidence_limitations
            ),
        )
        return projection.model_validate(values)
    for native_type, evidence_type in (
        (DifferenceInDifferencesResult, DidEvidence),
        (PropensityResult, PropensityEvidence),
        (DMLResult, DMLEvidence),
        (IdentificationResult, IdentificationEvidence),
    ):
        if isinstance(native, native_type):
            values = {
                field: getattr(native, field)
                for field in evidence_type.model_fields
                if field not in {"evidence_type", "context"}
            }
            values["context"] = _causal_context(native)
            if isinstance(native, PropensityResult):
                for name, excluded in (
                    ("model_fit", "scores"),
                    ("weights", "raw"),
                    ("retained", "scores"),
                    ("capped_weights", "weights"),
                ):
                    value = getattr(native, name)
                    values[name] = value.model_dump(exclude={excluded}) if value else None
            if isinstance(native, DMLResult) and native.fold_plan is not None:
                values["fold_plan"] = native.fold_plan.model_dump(exclude={"assignments"})
            return evidence_type.model_validate(values)
    if isinstance(native, HeterogeneousEffectResult):
        values = {
            field: getattr(native, field)
            for field in HTEEvidence.model_fields
            if field not in {"evidence_type", "evidence_limitations", "context"}
        }
        values["context"] = _causal_context(native)
        if native.fold_plan is not None:
            values["fold_plan"] = native.fold_plan.model_dump(exclude={"assignments"})
        values["evidence_limitations"] = (
            native.execution_request.identification_result.evidence_limitations
        )
        return HTEEvidence.model_validate(values)
    if isinstance(native, RandomizedAnalysisResult):
        return project_randomized(native)
    if isinstance(native, BayesianAnalysisResult):
        return BayesianEvidence.model_validate(
            {
                field: getattr(native, field)
                for field in BayesianEvidence.model_fields
                if field != "evidence_type"
            }
        )
    if isinstance(native, CupedAnalysisResult):
        values = {
            field: getattr(native, field)
            for field in CupedEvidence.model_fields
            if field != "evidence_type"
        }
        for name in (
            "adjusted_result",
            "comparable_unadjusted_result",
            "full_sample_unadjusted_result",
        ):
            result = getattr(native, name)
            values[name] = project_randomized(result) if result is not None else None
        return CupedEvidence.model_validate(values)
    if not isinstance(native, SequentialAnalysisHistory):
        raise TypeError("unsupported owned result")
    looks = []
    for look in native.looks:
        values = {field: getattr(look, field) for field in SequentialLookEvidence.model_fields}
        values["look_level_analysis"] = (
            project_randomized(look.look_level_analysis) if look.look_level_analysis else None
        )
        looks.append(SequentialLookEvidence.model_validate(values))
    return SequentialEvidence(
        plan_id=native.plan.plan_id,
        plan_fingerprint=native.plan.plan_fingerprint,
        estimand=native.plan.analysis_request.estimand,
        current_status=native.current_status,
        plan_integrity=native.plan_integrity,
        alpha_summary=native.alpha_summary,
        boundaries=native.boundaries,
        looks=tuple(looks),
        deviations=native.deviations,
        first_look=native.first_look,
        latest_look=native.latest_look,
        provenance=native.provenance,
    )


def native_status(native: OwnedAnalysisResult) -> ExecutionStatus:
    reason = getattr(native, "abstention_reason", None)
    code = reason if isinstance(reason, str) else getattr(reason, "code", None)
    if code == "OPTIONAL_DEPENDENCY_UNAVAILABLE":
        return "unavailable"
    if code == "INCOMPATIBLE_DEPENDENCY_RUNTIME":
        return "failed"
    if isinstance(native, SequentialAnalysisHistory):
        if native.current_status.value == "invalid":
            return "invalid"
        if not native.looks or native.current_status.value == "abstain":
            return "abstained"
        return "completed" if native.current_status.value == "efficacy" else "inconclusive"
    value = native.status.value
    if value == "error":
        return "failed"
    if value in {"no_improvement", "degraded_precision"}:
        return "completed"
    if value in {"completed", "inconclusive", "invalid", "abstained"}:
        return value  # type: ignore[return-value]
    return "abstained"
