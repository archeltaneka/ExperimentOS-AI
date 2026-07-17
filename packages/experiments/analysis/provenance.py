"""Typed evidence, diagnostic, failure, and provenance contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from .base import ContractModel, NonEmptyStr
from .metrics import MeasuredValue


class ProvenanceSourceType(StrEnum):
    """Stable categories for evidence sources."""

    EXPERIMENT_DATA = "experiment_data"
    ANALYSIS_REQUEST = "analysis_request"
    REPORT = "report"
    CONFIGURATION = "configuration"
    DERIVED = "derived"
    USER_SUPPLIED = "user_supplied"
    EXTERNAL_REFERENCE = "external_reference"


class AssumptionStatus(StrEnum):
    """Assessment state for an analytical assumption."""

    SUPPORTED = "supported"
    VIOLATED = "violated"
    UNASSESSED = "unassessed"
    UNTESTABLE = "untestable"


class DiagnosticSeverity(StrEnum):
    """Operational importance assigned to a diagnostic."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class DiagnosticOutcome(StrEnum):
    """Observed outcome of a diagnostic check."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class ProvenanceRecord(ContractModel):
    """Reference to one source that supports an analysis contract."""

    source_type: ProvenanceSourceType
    source_id: NonEmptyStr
    source_version: NonEmptyStr | None = None
    source_uri: NonEmptyStr | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_observed_at(self) -> Self:
        if self.observed_at is not None and self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return self


type ProvenanceRecords = Annotated[
    tuple[ProvenanceRecord, ...],
    Field(min_length=1),
]


class AssumptionAssessment(ContractModel):
    """Typed assessment of an assumption without calculating its status."""

    code: NonEmptyStr
    statement: NonEmptyStr
    status: AssumptionStatus


class Diagnostic(ContractModel):
    """Typed diagnostic result with optional unit-bearing values."""

    code: NonEmptyStr
    severity: DiagnosticSeverity
    outcome: DiagnosticOutcome
    message: NonEmptyStr
    observed_value: MeasuredValue | None = None
    threshold: MeasuredValue | None = None


class AnalysisWarning(ContractModel):
    """Non-fatal warning attached to a declared analysis scope."""

    code: NonEmptyStr
    message: NonEmptyStr
    scope: NonEmptyStr


class AnalysisFailure(ContractModel):
    """Typed failure record for a named analysis stage."""

    code: NonEmptyStr
    stage: NonEmptyStr
    message: NonEmptyStr
    retryable: bool
