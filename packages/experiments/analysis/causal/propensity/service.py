"""Service orchestration for deterministic propensity-score diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Protocol, cast

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ...base import ScalarValue
from ...provenance import (
    AnalysisWarning,
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceRecords,
    ProvenanceSourceType,
)
from ...validation.table import AnalysisTable
from ..diagnostics import EvidenceLimitation, EvidenceLimitationCode
from ..estimands import CausalEstimandKind
from .adapter import SklearnLogisticPropensityAdapter
from .encoding import EncodedPropensityData, encode_propensity_features
from .models import (
    CappedWeightDiagnostics,
    CommonSupportDiagnostic,
    CommonSupportStatus,
    OverlapDiagnostic,
    OverlapStatus,
    PropensityAbstentionReason,
    PropensityConfig,
    PropensityDiagnostic,
    PropensityDiagnosticCategory,
    PropensityDiagnosticStatus,
    PropensityExecutionRequest,
    PropensityFitStatus,
    PropensityModelFit,
    PropensityModelProvenance,
    PropensityResult,
    PropensitySampleCounts,
    PropensityScore,
    PropensityStatus,
    PropensityWeight,
    RetainedPopulationDiagnostics,
)
from .numerics import (
    PropensityNumericalError,
    assess_overlap,
    build_balance_diagnostics,
    build_ess_diagnostic,
    build_score_diagnostics,
    build_weight_diagnostics,
    common_support_diagnostic,
    compute_weight_values,
    summarize_distribution,
)
from .validation import PropensityValidationDisposition, validate_propensity_input


class _PropensityModelAdapter(Protocol):
    def fit_predict(
        self,
        encoded: EncodedPropensityData,
        config: PropensityConfig,
    ) -> PropensityModelFit: ...


class DeterministicLogisticPropensityEstimator:
    """Fit one baseline score model and return design diagnostics, never an effect."""

    def __init__(
        self,
        *,
        adapter: _PropensityModelAdapter | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.adapter = adapter or SklearnLogisticPropensityAdapter()
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    @staticmethod
    def supports(execution: PropensityExecutionRequest) -> bool:
        """Return whether the declared request has a supported ATE/ATT shape."""
        estimand = execution.analysis_request.identification.estimand
        return estimand is not None and estimand.estimand_type in {
            CausalEstimandKind.ATE,
            CausalEstimandKind.ATT,
        }

    def fit_predict(
        self,
        execution: PropensityExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> PropensityResult:
        """Return aligned scores and aggregate diagnostics or a typed abstention."""
        started = perf_counter()
        span = _start_span(self.observability_provider, row_count=len(table.rows))
        try:
            result = self._fit_predict(execution, table, provenance=provenance)
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

    def _fit_predict(
        self,
        execution: PropensityExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> PropensityResult:
        validated = validate_propensity_input(execution, table)
        result_provenance = _result_provenance(provenance)
        if validated.disposition is not PropensityValidationDisposition.VALID:
            status = {
                PropensityValidationDisposition.ABSTAINED: PropensityStatus.ABSTAINED,
                PropensityValidationDisposition.INVALID: PropensityStatus.INVALID,
                PropensityValidationDisposition.UNSUPPORTED: PropensityStatus.UNSUPPORTED,
            }[validated.disposition]
            return _non_fitted_result(
                execution,
                status=status,
                sample_counts=validated.sample_counts,
                diagnostics=validated.diagnostics,
                provenance=result_provenance,
            )

        encoded = encode_propensity_features(validated, execution.configuration)
        model_fit = self.adapter.fit_predict(encoded, execution.configuration)
        if model_fit.status is not PropensityFitStatus.CONVERGED:
            diagnostics = tuple(
                _diagnostic(
                    code,
                    PropensityDiagnosticCategory.MODEL,
                    "The baseline propensity model did not produce valid converged scores.",
                    severity=DiagnosticSeverity.FATAL,
                )
                for code in model_fit.warning_codes
            )
            return _non_fitted_result(
                execution,
                status=PropensityStatus.ABSTAINED,
                sample_counts=validated.sample_counts,
                diagnostics=diagnostics,
                provenance=result_provenance,
                encoding=encoded,
                model_fit=model_fit,
            )

        estimand = execution.analysis_request.identification.estimand
        assert estimand is not None
        estimand_kind = estimand.estimand_type
        scores = tuple(
            PropensityScore(
                unit_id=cast(ScalarValue, unit_id),
                treated=treated,
                score=score,
            )
            for unit_id, treated, score in zip(
                encoded.unit_ids,
                encoded.treated,
                model_fit.scores,
                strict=True,
            )
        )
        try:
            weight_values = compute_weight_values(
                model_fit.scores,
                encoded.treated,
                estimand_kind,
            )
            raw_weights = tuple(
                PropensityWeight(
                    unit_id=cast(ScalarValue, unit_id),
                    treated=treated,
                    value=value,
                )
                for unit_id, treated, value in zip(
                    encoded.unit_ids,
                    encoded.treated,
                    weight_values,
                    strict=True,
                )
            )
            weight_diagnostics = build_weight_diagnostics(
                raw_weights,
                estimand_kind,
                execution.configuration,
            )
        except PropensityNumericalError:
            diagnostic = _diagnostic(
                "weight.impossible",
                PropensityDiagnosticCategory.WEIGHT,
                "Declared estimand weights are non-finite or have an impossible denominator.",
                severity=DiagnosticSeverity.FATAL,
            )
            return _non_fitted_result(
                execution,
                status=PropensityStatus.ABSTAINED,
                sample_counts=validated.sample_counts,
                diagnostics=(diagnostic,),
                provenance=result_provenance,
                encoding=encoded,
                model_fit=model_fit.model_copy(update={"scores": ()}),
            )

        support = common_support_diagnostic(model_fit.scores, encoded.treated)
        overlap = assess_overlap(
            scores=model_fit.scores,
            treated=encoded.treated,
            support=support,
            model_fit=model_fit,
            weights=weight_diagnostics,
            estimand=estimand_kind,
            config=execution.configuration,
        )
        balance = build_balance_diagnostics(encoded, weight_values, execution.configuration)
        retained = _retained_diagnostics(execution, scores)
        capped_weights = _capped_weight_diagnostics(
            execution,
            weight_diagnostics,
        )
        diagnostics = (*_overlap_diagnostics(overlap), *_encoding_diagnostics(encoded))
        blocked = overlap.status in {OverlapStatus.SEVERE, OverlapStatus.UNAVAILABLE}
        status = PropensityStatus.ABSTAINED if blocked else PropensityStatus.COMPLETED
        warnings = tuple(
            AnalysisWarning(code=item.code, message=item.message, scope="propensity")
            for item in diagnostics
            if item.severity is DiagnosticSeverity.WARNING
        )
        return PropensityResult(
            request_id=execution.request_id,
            analysis_request=execution.analysis_request,
            binding=execution.binding,
            configuration=execution.configuration,
            status=status,
            estimand=estimand_kind,
            adjustment_covariates=_adjustment_covariates(execution),
            encoding=encoded.metadata,
            model_fit=model_fit,
            model_provenance=_model_provenance(execution, encoded, model_fit, estimand_kind),
            sample_counts=validated.sample_counts,
            scores=scores,
            score_diagnostics=build_score_diagnostics(
                model_fit.scores,
                encoded.treated,
                execution.configuration,
            ),
            common_support=support,
            overlap=overlap,
            weights=weight_diagnostics,
            retained=retained,
            capped_weights=capped_weights,
            balance=balance,
            assumptions=execution.analysis_request.identification.assumptions,
            evidence_limitations=_evaluated_limitations(execution),
            diagnostics=diagnostics,
            warnings=warnings,
            provenance=result_provenance,
            abstention_reason=(_abstention(diagnostics, "overlap.severe") if blocked else None),
        )


def _non_fitted_result(
    execution: PropensityExecutionRequest,
    *,
    status: PropensityStatus,
    sample_counts: PropensitySampleCounts,
    diagnostics: tuple[PropensityDiagnostic, ...],
    provenance: ProvenanceRecords,
    encoding: EncodedPropensityData | None = None,
    model_fit: PropensityModelFit | None = None,
) -> PropensityResult:
    estimand = execution.analysis_request.identification.estimand
    fit = model_fit or PropensityModelFit(
        status=PropensityFitStatus.FAILED,
        converged=False,
        scores=(),
        classes=(),
        iteration_count=None,
        solver=execution.configuration.solver,
        warning_codes=("model.not_fitted",),
        sklearn_version="not_fitted",
    )
    primary = diagnostics[0] if diagnostics else None
    return PropensityResult(
        request_id=execution.request_id,
        analysis_request=execution.analysis_request,
        binding=execution.binding,
        configuration=execution.configuration,
        status=status,
        estimand=estimand.estimand_type if estimand is not None else None,
        adjustment_covariates=_adjustment_covariates(execution),
        encoding=encoding.metadata if encoding is not None else None,
        model_fit=fit,
        model_provenance=None,
        sample_counts=sample_counts,
        scores=(),
        score_diagnostics=None,
        common_support=CommonSupportDiagnostic(status=CommonSupportStatus.UNAVAILABLE),
        overlap=OverlapDiagnostic(
            status=OverlapStatus.UNAVAILABLE,
            target_outside_support_fraction=None,
            comparator_inside_support_count=None,
            comparator_inside_support_fraction=None,
            extreme_score_count=0,
            extreme_score_fraction=None,
            separation_detected=False,
            diagnostic_codes=tuple(item.code for item in diagnostics),
        ),
        weights=None,
        retained=None,
        capped_weights=None,
        balance=None,
        assumptions=execution.analysis_request.identification.assumptions,
        evidence_limitations=execution.analysis_request.identification.evidence_limitations,
        diagnostics=diagnostics,
        warnings=(),
        provenance=provenance,
        abstention_reason=PropensityAbstentionReason(
            code=primary.code if primary is not None else "propensity.unavailable",
            message=(
                primary.message
                if primary is not None
                else "Propensity diagnostics are unavailable for this request."
            ),
        ),
    )


def _diagnostic(
    code: str,
    category: PropensityDiagnosticCategory,
    message: str,
    *,
    severity: DiagnosticSeverity,
) -> PropensityDiagnostic:
    return PropensityDiagnostic(
        code=code,
        category=category,
        severity=severity,
        status=PropensityDiagnosticStatus.FAILED,
        message=message,
    )


def _overlap_diagnostics(overlap: OverlapDiagnostic) -> tuple[PropensityDiagnostic, ...]:
    severity = (
        DiagnosticSeverity.FATAL
        if overlap.status in {OverlapStatus.SEVERE, OverlapStatus.UNAVAILABLE}
        else DiagnosticSeverity.WARNING
    )
    return tuple(
        _diagnostic(
            code,
            PropensityDiagnosticCategory.OVERLAP,
            "Observed propensity overlap or weighting stability requires attention.",
            severity=severity,
        )
        for code in overlap.diagnostic_codes
    )


def _encoding_diagnostics(
    encoded: EncodedPropensityData,
) -> tuple[PropensityDiagnostic, ...]:
    if not any(item.zero_variance for item in encoded.metadata.numeric):
        return ()
    return (
        _diagnostic(
            "encoding.zero_variance_numeric",
            PropensityDiagnosticCategory.COVARIATE,
            "At least one numeric adjustment covariate has zero variance in the model sample.",
            severity=DiagnosticSeverity.WARNING,
        ),
    )


def _abstention(
    diagnostics: tuple[PropensityDiagnostic, ...],
    fallback: str,
) -> PropensityAbstentionReason:
    primary = diagnostics[0] if diagnostics else None
    return PropensityAbstentionReason(
        code=primary.code if primary is not None else fallback,
        message=(
            primary.message
            if primary is not None
            else "Overlap or effective sample size does not satisfy configured requirements."
        ),
    )


def _adjustment_covariates(execution: PropensityExecutionRequest) -> tuple[str, ...]:
    adjustment = execution.analysis_request.identification.adjustment_set
    return adjustment.variable_ids if adjustment is not None else ()


def _model_provenance(
    execution: PropensityExecutionRequest,
    encoded: EncodedPropensityData,
    fit: PropensityModelFit,
    estimand: CausalEstimandKind,
) -> PropensityModelProvenance:
    config = execution.configuration
    contrast = execution.analysis_request.identification.treatment
    assert contrast is not None
    return PropensityModelProvenance(
        model_family=config.model_family,
        link=config.link,
        penalty=config.penalty,
        l1_ratio=config.l1_ratio,
        inverse_regularization_strength=config.inverse_regularization_strength,
        solver=config.solver,
        tolerance=config.tolerance,
        maximum_iterations=config.maximum_iterations,
        fit_intercept=config.fit_intercept,
        numeric_scaling=config.numeric_scaling,
        categorical_encoding=config.categorical_encoding,
        categorical_ordering=config.categorical_ordering,
        unseen_category_policy=config.unseen_category_policy,
        feature_names=encoded.metadata.model_feature_names,
        random_seed=config.random_seed,
        treated_value=contrast.treated_value,
        control_value=contrast.control_value,
        estimand=estimand,
        trimming_enabled=config.trimming is not None,
        weight_capping_enabled=config.weight_cap is not None,
        sklearn_version=fit.sklearn_version,
    )


def _retained_diagnostics(
    execution: PropensityExecutionRequest,
    scores: tuple[PropensityScore, ...],
) -> RetainedPopulationDiagnostics | None:
    trimming = execution.configuration.trimming
    if trimming is None:
        return None
    retained = tuple(item for item in scores if trimming.lower <= item.score <= trimming.upper)
    treated_raw = sum(item.treated for item in scores)
    control_raw = len(scores) - treated_raw
    treated_retained = sum(item.treated for item in retained)
    control_retained = len(retained) - treated_retained
    support = common_support_diagnostic(
        tuple(item.score for item in retained),
        tuple(item.treated for item in retained),
    )
    score_diagnostics = None
    if retained and treated_retained and control_retained:
        score_diagnostics = build_score_diagnostics(
            tuple(item.score for item in retained),
            tuple(item.treated for item in retained),
            execution.configuration,
        )
    return RetainedPopulationDiagnostics(
        configuration=trimming,
        scores=retained,
        retained_count=len(retained),
        treated_retained=treated_retained,
        control_retained=control_retained,
        dropped_count=len(scores) - len(retained),
        treated_dropped=treated_raw - treated_retained,
        control_dropped=control_raw - control_retained,
        retained_proportion=len(retained) / len(scores) if scores else 0.0,
        common_support=support,
        score_diagnostics=score_diagnostics,
    )


def _capped_weight_diagnostics(
    execution: PropensityExecutionRequest,
    raw: object,
) -> CappedWeightDiagnostics | None:
    cap = execution.configuration.weight_cap
    if cap is None:
        return None
    assert hasattr(raw, "raw") and hasattr(raw, "ess")
    raw_weights = raw.raw
    capped = tuple(
        item.model_copy(update={"value": min(item.value, cap.maximum)}) for item in raw_weights
    )
    values = tuple(item.value for item in capped)
    treated_values = tuple(item.value for item in capped if item.treated)
    control_values = tuple(item.value for item in capped if not item.treated)
    affected = sum(item.value > cap.maximum for item in raw_weights)
    return CappedWeightDiagnostics(
        configuration=cap,
        weights=capped,
        overall=summarize_distribution(values, execution.configuration.weight_quantiles),
        treated=summarize_distribution(
            treated_values,
            execution.configuration.weight_quantiles,
        ),
        control=summarize_distribution(
            control_values,
            execution.configuration.weight_quantiles,
        ),
        affected_count=affected,
        affected_proportion=affected / len(raw_weights),
        ess_before=raw.ess,
        ess_after=build_ess_diagnostic(
            values,
            tuple(item.treated for item in capped),
            execution.configuration,
        ),
    )


def _evaluated_limitations(
    execution: PropensityExecutionRequest,
) -> tuple[EvidenceLimitation, ...]:
    return tuple(
        item
        for item in execution.analysis_request.identification.evidence_limitations
        if item.code is not EvidenceLimitationCode.OVERLAP_NOT_EVALUATED
    )


def _result_provenance(provenance: ProvenanceRecords) -> ProvenanceRecords:
    return (
        *provenance,
        ProvenanceRecord(
            source_type=ProvenanceSourceType.CONFIGURATION,
            source_id="propensity:configuration",
            source_version="1",
        ),
    )


def _start_span(
    provider: BaseObservabilityProvider,
    *,
    row_count: int,
) -> BufferedSpan | None:
    before = _failure_count(provider)
    try:
        return provider.start_root_span(
            "propensity_score_diagnostics",
            inputs={"row_count": row_count},
            metadata={"method": "propensity"},
            tags=("statistics", "causal", "propensity"),
        )
    except Exception:
        _increment_failure(provider, before)
        return None


def _finish_result(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: PropensityResult,
    duration_ms: float,
) -> None:
    if span is None:
        return
    ess_status = result.weights.ess.status.value if result.weights is not None else "unavailable"
    metadata: dict[str, object] = {
        "design": result.analysis_request.identification.design.design_type.value,
        "method": "propensity",
        "estimand": result.estimand.value if result.estimand is not None else "unavailable",
        "model_family": result.configuration.model_family,
        "status": result.status.value,
        "identification_status": (
            "identified" if result.status is PropensityStatus.COMPLETED else "not_identified"
        ),
        "convergence_status": result.model_fit.status.value,
        "overlap_status": result.overlap.status.value,
        "ess_status": ess_status,
        "balance_status": ("available" if result.balance is not None else "unavailable"),
        "raw_sample_count": result.sample_counts.raw,
        "model_sample_count": result.sample_counts.model,
        "retained_sample_count": (
            result.retained.retained_count
            if result.retained is not None
            else result.sample_counts.model
        ),
        "weighting_enabled": result.weights is not None,
        "trimming_enabled": result.configuration.trimming is not None,
        "capping_enabled": result.configuration.weight_cap is not None,
        "diagnostic_codes": tuple(item.code for item in result.diagnostics),
        "assumption_codes": tuple(item.code.value for item in result.assumptions),
        "duration_ms": duration_ms,
    }
    _observe(provider, lambda: span.add_metadata(metadata))
    _observe(
        provider,
        lambda: span.finish(
            outputs={
                "status": result.status.value,
                "scores_valid": result.model_fit.status is PropensityFitStatus.CONVERGED,
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
            "Propensity-score diagnostics failed.",
            details={"type": error.__class__.__name__},
        ),
    )
    _observe(
        provider,
        lambda: span.finish(outputs={"status": "failed", "scores_valid": False}),
    )


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


__all__ = ["DeterministicLogisticPropensityEstimator"]
