"""Versioned, public workflow evidence; no third-party objects or raw datasets."""

import hashlib
import json
from datetime import datetime
from typing import Literal, Self

from pydantic import model_validator

from ..base import ContractModel, NonEmptyStr
from ..provenance import Diagnostic, ProvenanceRecord
from ..randomized.models import RandomizedAnalysisResult
from ..results import AbstentionReason
from .evidence_randomized import RandomizedEvidence, project_randomized

type OwnedAnalysisResult = RandomizedAnalysisResult
type AnalysisEvidence = RandomizedEvidence
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


def project_evidence(native: OwnedAnalysisResult) -> AnalysisEvidence:
    return project_randomized(native)


def native_status(native: OwnedAnalysisResult) -> ExecutionStatus:
    value = native.status.value
    if value in {"completed", "inconclusive", "invalid", "abstained"}:
        return value  # type: ignore[return-value]
    return "abstained"
