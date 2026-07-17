"""Eligibility assessments and terminal analysis outcome contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import SCHEMA_VERSION, AnalysisStatus, ContractModel, NonEmptyStr
from .estimates import AnalysisFinding, DescriptiveStatistic
from .provenance import (
    AnalysisFailure,
    AnalysisWarning,
    Diagnostic,
    ProvenanceRecords,
)

type EligibilityStatus = Literal[
    AnalysisStatus.ELIGIBLE,
    AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
    AnalysisStatus.INELIGIBLE,
    AnalysisStatus.NEEDS_MORE_DATA,
]


class AbstentionReason(ContractModel):
    """Typed explanation for refusing to manufacture an analysis finding."""

    code: NonEmptyStr
    message: NonEmptyStr
    missing_or_invalid_information: Annotated[
        tuple[NonEmptyStr, ...],
        Field(min_length=1),
    ]


class EligibilityAssessment(ContractModel):
    """Pre-analysis eligibility outcome without eligibility-policy behavior."""

    outcome_type: Literal["eligibility"] = "eligibility"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: EligibilityStatus
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    required_data: tuple[NonEmptyStr, ...]
    provenance: ProvenanceRecords


def _finding_status(finding: AnalysisFinding) -> AnalysisStatus:
    if isinstance(finding, DescriptiveStatistic):
        return finding.status
    return finding.estimate.status


class CompletedAnalysisResult(ContractModel):
    """Terminal successful outcome containing completed typed findings."""

    outcome_type: Literal["completed"] = "completed"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: Literal[AnalysisStatus.COMPLETED]
    findings: Annotated[tuple[AnalysisFinding, ...], Field(min_length=1)]
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords

    @model_validator(mode="after")
    def validate_finding_statuses(self) -> Self:
        if any(_finding_status(finding) is not self.status for finding in self.findings):
            raise ValueError("finding status must match completed result status")
        return self


class InconclusiveAnalysisResult(ContractModel):
    """Terminal inconclusive outcome containing inconclusive numerical findings."""

    outcome_type: Literal["inconclusive"] = "inconclusive"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: Literal[AnalysisStatus.INCONCLUSIVE]
    findings: Annotated[tuple[AnalysisFinding, ...], Field(min_length=1)]
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords

    @model_validator(mode="after")
    def validate_finding_statuses(self) -> Self:
        if any(_finding_status(finding) is not self.status for finding in self.findings):
            raise ValueError("finding status must match inconclusive result status")
        return self


class AbstainedAnalysisResult(ContractModel):
    """Terminal abstention carrying reasons rather than fabricated findings."""

    outcome_type: Literal["abstained"] = "abstained"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: Literal[AnalysisStatus.ABSTAINED]
    reason: AbstentionReason
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords


class FailedAnalysisResult(ContractModel):
    """Terminal execution failure carrying non-empty typed failures."""

    outcome_type: Literal["failed"] = "failed"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: Literal[AnalysisStatus.FAILED]
    failures: Annotated[tuple[AnalysisFailure, ...], Field(min_length=1)]
    diagnostics: tuple[Diagnostic, ...]
    provenance: ProvenanceRecords


type AnalysisOutcome = Annotated[
    EligibilityAssessment
    | CompletedAnalysisResult
    | InconclusiveAnalysisResult
    | AbstainedAnalysisResult
    | FailedAnalysisResult,
    Field(discriminator="outcome_type"),
]
