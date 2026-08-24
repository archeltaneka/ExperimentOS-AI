"""Service orchestration for bounded two-group, two-period DiD analysis."""

from __future__ import annotations

import math
from collections.abc import Callable
from time import perf_counter

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ...provenance import (
    AnalysisWarning,
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceRecords,
    ProvenanceSourceType,
)
from ...validation.table import AnalysisTable
from .models import (
    DidAbstentionReason,
    DidCellMeans,
    DidDiagnostic,
    DidDiagnosticCategory,
    DidDiagnosticStatus,
    DidPretrendAvailability,
    DidPretrendDiagnostic,
    DidStatus,
    DidTestResult,
    DifferenceInDifferencesExecutionRequest,
    DifferenceInDifferencesResult,
)
from .numerics import (
    DidNumericalError,
    assess_cluster_policy,
    cluster_robust_inference,
    fit_interaction_ols,
    manual_did,
)
from .pretrends import evaluate_pretrend
from .validation import DidValidationDisposition, DidValidationResult, validate_did_input


class DifferenceInDifferencesService:
    """Validate and estimate only the supported deterministic DiD ATT design."""

    def __init__(
        self,
        *,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: DifferenceInDifferencesExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> DifferenceInDifferencesResult:
        """Return a typed estimate or a typed refusal without leaking source rows."""
        started = perf_counter()
        span = _start_span(self.observability_provider, row_count=len(table.rows))
        try:
            result = self._analyze(execution, table, provenance=provenance)
        except Exception as error:
            _finish_failure(
                self.observability_provider,
                span,
                error=error,
                duration_ms=(perf_counter() - started) * 1000.0,
            )
            raise
        _finish_result(
            self.observability_provider,
            span,
            result=result,
            duration_ms=(perf_counter() - started) * 1000.0,
        )
        return result

    def _analyze(
        self,
        execution: DifferenceInDifferencesExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> DifferenceInDifferencesResult:
        validated = validate_did_input(execution, table)
        result_provenance = _analysis_provenance(execution, provenance)
        if validated.disposition is not DidValidationDisposition.VALID:
            status = {
                DidValidationDisposition.ABSTAINED: DidStatus.ABSTAINED,
                DidValidationDisposition.INVALID: DidStatus.INVALID,
                DidValidationDisposition.UNSUPPORTED: DidStatus.UNSUPPORTED,
            }[validated.disposition]
            return _noncompleted_result(
                execution,
                validated,
                status=status,
                diagnostics=validated.diagnostics,
                provenance=result_provenance,
            )

        policy = assess_cluster_policy(validated.sample_counts, execution.configuration)
        diagnostics = validated.diagnostics + policy.diagnostics
        if not policy.inference_supported:
            return _noncompleted_result(
                execution,
                validated,
                status=DidStatus.ABSTAINED,
                diagnostics=diagnostics,
                provenance=result_provenance,
            )

        units = execution.analysis_request.identification.units
        if units is None:
            raise RuntimeError("identified DiD request omitted unit semantics")
        try:
            cells = manual_did(validated.observations)
            fit = fit_interaction_ols(validated.observations)
            if not math.isclose(
                cells.did_estimate,
                fit.coefficients[3],
                rel_tol=0.0,
                abs_tol=1e-10,
            ):
                raise DidNumericalError("manual and interaction DiD estimates disagree")
            inference = cluster_robust_inference(
                fit,
                cluster_unit=units.analysis_unit,
                config=execution.configuration,
            )
        except DidNumericalError:
            numerical = _diagnostic(
                "did.inference_unavailable",
                DidDiagnosticCategory.INFERENCE,
                "Finite clustered DiD inference is unavailable for the supplied panel.",
                DiagnosticSeverity.ERROR,
                unavailable=True,
            )
            return _noncompleted_result(
                execution,
                validated,
                status=DidStatus.ABSTAINED,
                diagnostics=diagnostics + (numerical,),
                provenance=result_provenance,
            )

        pretrend = evaluate_pretrend(validated, execution)
        if pretrend.evidence_concern:
            diagnostics += (
                _diagnostic(
                    "did.parallel_trends_evidence_concern",
                    DidDiagnosticCategory.PRETREND,
                    "Diagnostic evidence indicates divergent pre-treatment trends.",
                    DiagnosticSeverity.WARNING,
                ),
            )
        return _build_result(
            execution,
            validated,
            status=DidStatus.COMPLETED,
            diagnostics=diagnostics,
            provenance=result_provenance,
            pretrend=pretrend,
            cell_means=cells,
            test_result=inference,
        )


def _noncompleted_result(
    execution: DifferenceInDifferencesExecutionRequest,
    validated: DidValidationResult,
    *,
    status: DidStatus,
    diagnostics: tuple[DidDiagnostic, ...],
    provenance: ProvenanceRecords,
) -> DifferenceInDifferencesResult:
    pretrend = DidPretrendDiagnostic(
        availability=(
            DidPretrendAvailability.UNAVAILABLE
            if execution.extra_pre_periods
            else DidPretrendAvailability.NOT_REQUESTED
        ),
        message=(
            "Pre-trend evidence was not evaluated because canonical DiD estimation abstained."
            if execution.extra_pre_periods
            else "No extra pre-treatment periods were requested."
        ),
        period_count=(len(execution.extra_pre_periods) + 1 if execution.extra_pre_periods else 0),
    )
    primary = sorted(diagnostics, key=lambda item: item.code)[0]
    reason = DidAbstentionReason(
        code=primary.code,
        message=primary.message,
        missing_or_invalid_information=tuple(sorted({item.code for item in diagnostics})),
    )
    return _build_result(
        execution,
        validated,
        status=status,
        diagnostics=diagnostics,
        provenance=provenance,
        pretrend=pretrend,
        abstention_reason=reason,
    )


def _build_result(
    execution: DifferenceInDifferencesExecutionRequest,
    validated: DidValidationResult,
    *,
    status: DidStatus,
    diagnostics: tuple[DidDiagnostic, ...],
    provenance: ProvenanceRecords,
    pretrend: DidPretrendDiagnostic,
    cell_means: DidCellMeans | None = None,
    test_result: DidTestResult | None = None,
    abstention_reason: DidAbstentionReason | None = None,
) -> DifferenceInDifferencesResult:
    identification = execution.analysis_request.identification
    warnings = tuple(
        AnalysisWarning(
            code=item.code,
            message=item.message,
            scope="difference_in_differences",
        )
        for item in diagnostics
        if item.severity is DiagnosticSeverity.WARNING
    )
    return DifferenceInDifferencesResult.model_validate(
        {
            "request_id": execution.request_id,
            "analysis_request": execution.analysis_request,
            "binding": execution.binding,
            "configuration": execution.configuration,
            "status": status,
            "estimand": identification.estimand,
            "design": identification.design,
            "treatment": identification.treatment,
            "outcome": identification.outcome,
            "population": identification.population,
            "units": identification.units,
            "time": identification.time,
            "sample_counts": validated.sample_counts,
            "cell_means": cell_means,
            "test_result": test_result,
            "assumptions": identification.assumptions,
            "evidence_limitations": validated.identification_result.evidence_limitations,
            "pretrend": pretrend,
            "diagnostics": diagnostics,
            "warnings": warnings,
            "provenance": provenance,
            "abstention_reason": abstention_reason,
        }
    )


def _analysis_provenance(
    execution: DifferenceInDifferencesExecutionRequest,
    provenance: ProvenanceRecords,
) -> ProvenanceRecords:
    return provenance + (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.ANALYSIS_REQUEST,
            source_id=execution.request_id,
            source_version="did_contract=1",
        ),
        ProvenanceRecord(
            source_type=ProvenanceSourceType.DERIVED,
            source_id="difference_in_differences",
            source_version="2x2_att;variance=cluster_robust_cr1;df=clusters_minus_one",
        ),
    )


def _diagnostic(
    code: str,
    category: DidDiagnosticCategory,
    message: str,
    severity: DiagnosticSeverity,
    *,
    unavailable: bool = False,
) -> DidDiagnostic:
    return DidDiagnostic(
        code=code,
        category=category,
        severity=severity,
        status=(DidDiagnosticStatus.UNAVAILABLE if unavailable else DidDiagnosticStatus.FAILED),
        message=message,
    )


def _start_span(
    provider: BaseObservabilityProvider,
    *,
    row_count: int,
) -> BufferedSpan | None:
    before = _failure_count(provider)
    try:
        return provider.start_root_span(
            "difference_in_differences",
            inputs={"row_count": row_count},
            metadata={"method": "did"},
            tags=("statistics", "causal", "did"),
        )
    except Exception:
        _increment_failure(provider, before)
        return None


def _finish_result(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: DifferenceInDifferencesResult,
    duration_ms: float,
) -> None:
    if span is None:
        return
    diagnostic_codes = tuple(item.code for item in result.diagnostics)
    metadata: dict[str, object] = {
        "method": "did",
        "status": result.status.value,
        "estimand_type": (
            result.estimand.estimand_type.value if result.estimand is not None else "unavailable"
        ),
        "panel_type": "balanced",
        "cluster_robust": result.test_result is not None,
        "cluster_count": result.sample_counts.retained_units,
        "pretrend_available": (result.pretrend.availability is DidPretrendAvailability.AVAILABLE),
        "diagnostic_codes": diagnostic_codes,
        "duration_ms": duration_ms,
    }
    _observe(provider, lambda: span.add_metadata(metadata))
    _observe(
        provider,
        lambda: span.finish(
            outputs={
                "status": result.status.value,
                "did_completed": result.status is DidStatus.COMPLETED,
            }
        ),
    )


def _finish_failure(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    error: Exception,
    duration_ms: float,
) -> None:
    if span is None:
        return
    _observe(provider, lambda: span.add_metadata({"status": "failed", "duration_ms": duration_ms}))
    _observe(
        provider,
        lambda: span.record_error(
            "Difference-in-Differences analysis failed.",
            details={"type": error.__class__.__name__},
        ),
    )
    _observe(provider, lambda: span.finish(outputs={"status": "failed", "did_completed": False}))


def _observe(provider: BaseObservabilityProvider, operation: Callable[[], object]) -> None:
    before = _failure_count(provider)
    try:
        operation()
    except Exception:
        _increment_failure(provider, before)


def _failure_count(provider: BaseObservabilityProvider) -> int | None:
    try:
        return provider.failure_count
    except Exception:
        return None


def _increment_failure(provider: BaseObservabilityProvider, before: int | None) -> None:
    try:
        current = provider.failure_count
    except Exception:
        current = None
    try:
        if before is None or current is None or current == before:
            provider.increment_failure()
    except Exception:
        return


__all__ = ["DifferenceInDifferencesService"]
