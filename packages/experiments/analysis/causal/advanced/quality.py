"""Minimal policy-compatible safety review for explicit advanced adapter results."""

from __future__ import annotations

import math

from ...base import ContractModel
from ...provenance import Diagnostic, DiagnosticOutcome, DiagnosticSeverity
from ..hte.quality import evaluate_hte_quality
from ..hte.results import HeterogeneousEffectResult
from ..models import IdentificationStatus
from ..propensity.models import OverlapStatus
from .models import AdvancedCausalResult


class AdvancedQualityAssessment(ContractModel):
    blocking_findings: tuple[Diagnostic, ...]


def evaluate_advanced_quality(
    result: AdvancedCausalResult | HeterogeneousEffectResult,
) -> AdvancedQualityAssessment:
    """Check only adapter safety invariants; no estimator selection or conformance suite."""
    codes: set[str] = set()
    if result.status.value != "completed":
        return AdvancedQualityAssessment(blocking_findings=())
    identification = result.execution_request.identification_result
    provenance = result.adapter_provenance
    if identification.status is not IdentificationStatus.IDENTIFIED:
        codes.add("advanced.quality.invalid_identification")
    if provenance is None or provenance.econml_version != "0.17.0":
        codes.add("advanced.quality.dependency_provenance_missing")
    if provenance is not None:
        if (
            provenance.seed != provenance.random_state
            or provenance.seed != provenance.nuisance_seed
        ):
            codes.add("advanced.quality.nondeterministic_configuration")
        if provenance.nuisance_configuration.inference_mode != "statsmodels_hc1":
            codes.add("advanced.quality.unsupported_inference")
    if any(
        d.code
        in (
            "OPTIONAL_DEPENDENCY_UNAVAILABLE",
            "INCOMPATIBLE_DEPENDENCY_RUNTIME",
            "UNSUPPORTED_INFERENCE",
        )
        for d in result.diagnostics
    ):
        codes.add("advanced.quality.unsupported_success")
    if isinstance(result, AdvancedCausalResult):
        if (
            not result.configuration.constant_effect_assumption
            or provenance is None
            or not provenance.nuisance_configuration.constant_effect_assumption
        ):
            codes.add("advanced.quality.unsupported_estimand")
        if result.configuration.inference_mode != "statsmodels_hc1":
            codes.add("advanced.quality.unsupported_inference")
        if result.point_estimate is None or not math.isfinite(result.point_estimate):
            codes.add("advanced.quality.nonfinite_estimate")
        if result.inference is None:
            codes.add("advanced.quality.uncertainty_missing")
        elif (
            not math.isfinite(result.inference.standard_error)
            or result.inference.standard_error <= 0
        ):
            codes.add("advanced.quality.uncertainty_missing")
        if result.overlap is None or result.overlap.status is OverlapStatus.SEVERE:
            codes.add("advanced.quality.overlap_invalid")
    else:
        codes.update(f.code for f in evaluate_hte_quality(result).blocking_findings)
        if result.global_overlap is None or result.global_overlap.status is OverlapStatus.SEVERE:
            codes.add("advanced.quality.overlap_invalid")
    return AdvancedQualityAssessment(
        blocking_findings=tuple(
            Diagnostic(
                code=code,
                severity=DiagnosticSeverity.FATAL,
                outcome=DiagnosticOutcome.FAILED,
                message="Conclusive advanced adapter result violates a required safety invariant.",
            )
            for code in sorted(codes)
        )
    )
