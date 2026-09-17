"""Minimal safety policy for normalized DoWhy evidence."""

from __future__ import annotations

from ...base import ContractModel
from ...provenance import Diagnostic, DiagnosticOutcome, DiagnosticSeverity
from .models import DoWhyAnalysisResult, DoWhyOperationStatus


class DoWhyQualityAssessment(ContractModel):
    blocking_findings: tuple[Diagnostic, ...]
    advisory_findings: tuple[Diagnostic, ...] = ()


def evaluate_dowhy_quality(result: DoWhyAnalysisResult) -> DoWhyQualityAssessment:
    blocking: set[str] = set()
    advisory: set[str] = set()
    if result.status is DoWhyOperationStatus.COMPLETED:
        if result.identification.status is not DoWhyOperationStatus.COMPLETED:
            blocking.add("dowhy.quality.invalid_identification")
        if result.adapter_provenance is None:
            blocking.add("dowhy.quality.provenance_missing")
        text = " ".join(item.interpretation.lower() for item in result.refutations)
        if "causal effect is validated" in text or "proves" in text:
            blocking.add("dowhy.quality.proof_language")
        if any(item.status.value in {"warning", "fail"} for item in result.refutations):
            advisory.add("dowhy.quality.refuter_sensitivity")
    return DoWhyQualityAssessment(
        blocking_findings=tuple(
            _finding(code, DiagnosticSeverity.FATAL) for code in sorted(blocking)
        ),
        advisory_findings=tuple(
            _finding(code, DiagnosticSeverity.WARNING) for code in sorted(advisory)
        ),
    )


def _finding(code: str, severity: DiagnosticSeverity) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=severity,
        outcome=DiagnosticOutcome.FAILED,
        message="Normalized DoWhy evidence requires review under causal safety policy.",
    )
