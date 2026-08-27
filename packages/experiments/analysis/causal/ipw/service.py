"""Deterministic orchestration for observational IPW treatment effects."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

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
from ..assumptions import CausalAssumptionStatus
from ..estimands import CausalEstimandKind
from ..propensity import (
    EffectiveSampleSizeStatus,
    OverlapStatus,
    PropensityFitStatus,
    PropensityResult,
    PropensityWeight,
)
from ..propensity.numerics import build_ess_diagnostic, summarize_distribution
from .models import (
    IPWAbstentionReason,
    IPWBalanceStatus,
    IPWCausalStatus,
    IPWClippingDiagnostics,
    IPWDiagnostic,
    IPWDiagnosticCategory,
    IPWExecutionRequest,
    IPWSampleCounts,
    IPWScoreModelReference,
    IPWSensitivityCode,
    IPWSensitivityFlag,
    IPWStatus,
    IPWTestResult,
    IPWWeightDiagnostics,
    IPWWeightSetDiagnostics,
    IPWWeightSetKind,
    TreatmentEffectResult,
)
from .numerics import (
    IPWNumericalError,
    clip_weights,
    compute_raw_weights,
    stabilize_weights,
    weighted_mean,
)
from .uncertainty import compute_fixed_score_robust_inference
from .validation import (
    IPWValidationDisposition,
    IPWValidationResult,
    ValidatedIPWRow,
    validate_ipw_input,
)


@dataclass(frozen=True, slots=True)
class IPWComputation:
    """Internal separation between numerical estimation and result interpretation."""

    treatment_mean: float
    control_mean: float
    effect: float
    test_result: IPWTestResult
    weights: IPWWeightDiagnostics


class IPWCalculationEngine(Protocol):
    """Owned injection boundary used after every fatal design gate passes."""

    def estimate(
        self,
        rows: tuple[ValidatedIPWRow, ...],
        execution: IPWExecutionRequest,
    ) -> IPWComputation:
        """Compute weights, arm means, effect, and uncertainty."""


class AnalyticIPWCalculationEngine:
    """Pure analytic ATE/ATT calculation using supplied propensity scores."""

    def estimate(
        self,
        rows: tuple[ValidatedIPWRow, ...],
        execution: IPWExecutionRequest,
    ) -> IPWComputation:
        propensity = execution.propensity_result
        estimand = propensity.estimand
        if estimand not in {CausalEstimandKind.ATE, CausalEstimandKind.ATT}:
            raise IPWNumericalError("only ATE and ATT are supported")
        treated = tuple(row.treated for row in rows)
        prevalence = sum(treated) / len(treated)
        raw_values = compute_raw_weights(
            tuple(row.score for row in rows),
            treated,
            estimand,
        )
        raw = _weight_set(IPWWeightSetKind.RAW, rows, raw_values, propensity)
        stabilized = None
        pre_clipping_values = raw_values
        stabilization_rule = None
        if execution.configuration.stabilized:
            pre_clipping_values = stabilize_weights(
                raw_values,
                treated,
                estimand,
                treatment_prevalence=prevalence,
            )
            stabilized = _weight_set(
                IPWWeightSetKind.STABILIZED,
                rows,
                pre_clipping_values,
                propensity,
            )
            stabilization_rule = (
                "ATE: treated=p/e, control=(1-p)/(1-e)"
                if estimand is CausalEstimandKind.ATE
                else "ATT: treated=1, control=e/(1-e)*(1-p)/p"
            )
        pre_clipping = _weight_set(
            IPWWeightSetKind.PRE_CLIPPING,
            rows,
            pre_clipping_values,
            propensity,
        )
        final_values, clipping_diagnostics = _apply_clipping(
            execution,
            rows,
            pre_clipping_values,
        )
        estimation = _weight_set(
            IPWWeightSetKind.ESTIMATION,
            rows,
            final_values,
            propensity,
        )
        weights = IPWWeightDiagnostics(
            estimand=estimand,
            treatment_prevalence=prevalence,
            raw_treated_formula="1/e(X)" if estimand is CausalEstimandKind.ATE else "1",
            raw_control_formula=(
                "1/(1-e(X))" if estimand is CausalEstimandKind.ATE else "e(X)/(1-e(X))"
            ),
            stabilization_rule=stabilization_rule,
            raw=raw,
            stabilized=stabilized,
            pre_clipping=pre_clipping,
            estimation=estimation,
            clipping=clipping_diagnostics,
        )
        treatment_outcomes = tuple(row.outcome for row in rows if row.treated)
        control_outcomes = tuple(row.outcome for row in rows if not row.treated)
        treatment_weights = tuple(
            weight for weight, arm in zip(final_values, treated, strict=True) if arm
        )
        control_weights = tuple(
            weight for weight, arm in zip(final_values, treated, strict=True) if not arm
        )
        treatment_mean = weighted_mean(treatment_outcomes, treatment_weights)
        control_mean = weighted_mean(control_outcomes, control_weights)
        effect = treatment_mean - control_mean
        if not math.isfinite(effect):
            raise IPWNumericalError("treatment effect must be finite")
        test_result = compute_fixed_score_robust_inference(
            treatment_outcomes=treatment_outcomes,
            treatment_weights=treatment_weights,
            control_outcomes=control_outcomes,
            control_weights=control_weights,
            treatment_mean=treatment_mean,
            control_mean=control_mean,
            effect=effect,
            confidence_level=execution.configuration.confidence_level,
        )
        return IPWComputation(
            treatment_mean=treatment_mean,
            control_mean=control_mean,
            effect=effect,
            test_result=test_result,
            weights=weights,
        )


class IPWTreatmentEffectEstimator:
    """Gate and estimate ATE/ATT from completed upstream owned results."""

    def __init__(
        self,
        *,
        engine: IPWCalculationEngine | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.engine = engine or AnalyticIPWCalculationEngine()
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: IPWExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> TreatmentEffectResult:
        """Return a completed estimate or a typed refusal with no fabricated inference."""
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
        execution: IPWExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> TreatmentEffectResult:
        validated = validate_ipw_input(execution, table)
        result_provenance = _analysis_provenance(execution, provenance)
        if validated.disposition is not IPWValidationDisposition.VALID:
            return _noncompleted_result(execution, validated, result_provenance)
        try:
            computation = self.engine.estimate(validated.rows, execution)
        except IPWNumericalError:
            numerical = validated.__class__(
                disposition=IPWValidationDisposition.ABSTAINED,
                rows=(),
                balance_status=validated.balance_status,
                diagnostics=(
                    _inference_diagnostic(),
                ),
                balance=validated.balance,
                overlap=validated.overlap,
            )
            return _noncompleted_result(execution, numerical, result_provenance)
        return _completed_result(execution, validated, computation, result_provenance)


def _completed_result(
    execution: IPWExecutionRequest,
    validated: IPWValidationResult,
    computation: IPWComputation,
    provenance: ProvenanceRecords,
) -> TreatmentEffectResult:
    identification = execution.identification_result
    estimand = identification.estimand
    if estimand is None:
        raise RuntimeError("validated identification omitted estimand")
    diagnostics = validated.diagnostics + (_fixed_score_diagnostic(),)
    return TreatmentEffectResult(
        request_id=execution.request_id,
        analysis_request=execution.propensity_result.analysis_request,
        binding=execution.binding,
        configuration=execution.configuration,
        status=IPWStatus.COMPLETED,
        causal_status=IPWCausalStatus.CONDITIONAL_ON_DECLARED_ASSUMPTIONS,
        estimand=estimand,
        treatment=identification.treatment,
        outcome=identification.outcome,
        target_population=estimand.target_population,
        effect_scale=estimand.effect_scale,
        adjustment_set=identification.adjustment_set,
        point_estimate=computation.effect,
        treatment_mean=computation.treatment_mean,
        control_mean=computation.control_mean,
        test_result=computation.test_result,
        weights=computation.weights,
        score_model=_score_model_reference(execution.propensity_result),
        overlap=validated.overlap or execution.propensity_result.overlap,
        balance=validated.balance,
        balance_status=validated.balance_status,
        sample_counts=_sample_counts(execution),
        assumptions=identification.assumptions,
        evidence_limitations=identification.evidence_limitations,
        sensitivity_flags=_sensitivity_flags(execution, validated, computation.weights),
        diagnostics=diagnostics,
        warnings=_warnings(diagnostics),
        provenance=provenance,
    )


def _noncompleted_result(
    execution: IPWExecutionRequest,
    validated: IPWValidationResult,
    provenance: ProvenanceRecords,
) -> TreatmentEffectResult:
    status = {
        IPWValidationDisposition.ABSTAINED: IPWStatus.ABSTAINED,
        IPWValidationDisposition.INVALID: IPWStatus.INVALID,
        IPWValidationDisposition.UNSUPPORTED: IPWStatus.UNSUPPORTED,
    }[validated.disposition]
    causal_status = {
        IPWStatus.ABSTAINED: IPWCausalStatus.ABSTAINED,
        IPWStatus.INVALID: IPWCausalStatus.INVALID,
        IPWStatus.UNSUPPORTED: IPWCausalStatus.UNSUPPORTED,
    }[status]
    primary = validated.diagnostics[0]
    identification = execution.identification_result
    estimand = identification.estimand
    return TreatmentEffectResult(
        request_id=execution.request_id,
        analysis_request=execution.propensity_result.analysis_request,
        binding=execution.binding,
        configuration=execution.configuration,
        status=status,
        causal_status=causal_status,
        estimand=estimand,
        treatment=identification.treatment,
        outcome=identification.outcome,
        target_population=estimand.target_population if estimand is not None else None,
        effect_scale=estimand.effect_scale if estimand is not None else None,
        adjustment_set=identification.adjustment_set,
        overlap=validated.overlap or execution.propensity_result.overlap,
        balance=validated.balance or execution.propensity_result.balance,
        balance_status=validated.balance_status,
        sample_counts=_sample_counts(execution),
        assumptions=identification.assumptions,
        evidence_limitations=identification.evidence_limitations,
        sensitivity_flags=_sensitivity_flags(execution, validated, None),
        diagnostics=validated.diagnostics,
        warnings=_warnings(validated.diagnostics),
        provenance=provenance,
        score_model=_score_model_reference(execution.propensity_result),
        abstention_reason=IPWAbstentionReason(
            code=primary.code,
            message=primary.message,
            missing_or_invalid_information=tuple(
                sorted({item.code for item in validated.diagnostics})
            ),
        ),
    )


def _apply_clipping(
    execution: IPWExecutionRequest,
    rows: tuple[ValidatedIPWRow, ...],
    weights: tuple[float, ...],
) -> tuple[tuple[float, ...], IPWClippingDiagnostics]:
    treated = tuple(row.treated for row in rows)
    before = build_ess_diagnostic(
        weights,
        treated,
        execution.propensity_result.configuration,
    )
    clipping = execution.configuration.clipping
    if clipping is None:
        return weights, IPWClippingDiagnostics(
            enabled=False,
            configuration=None,
            affected_count=0,
            treated_affected_count=0,
            control_affected_count=0,
            affected_proportion=0.0,
            maximum_before=max(weights),
            maximum_after=max(weights),
            ess_before=before,
            ess_after=before,
        )
    clipped = clip_weights(weights, treated, maximum=clipping.maximum)
    after = build_ess_diagnostic(
        clipped.weights,
        treated,
        execution.propensity_result.configuration,
    )
    return clipped.weights, IPWClippingDiagnostics(
        enabled=True,
        configuration=clipping,
        affected_count=clipped.affected_count,
        treated_affected_count=clipped.treated_affected_count,
        control_affected_count=clipped.control_affected_count,
        affected_proportion=clipped.affected_proportion,
        maximum_before=clipped.maximum_before,
        maximum_after=clipped.maximum_after,
        ess_before=before,
        ess_after=after,
    )


def _weight_set(
    kind: IPWWeightSetKind,
    rows: tuple[ValidatedIPWRow, ...],
    values: tuple[float, ...],
    propensity: PropensityResult,
) -> IPWWeightSetDiagnostics:
    weights = tuple(
        PropensityWeight(unit_id=row.unit_id, treated=row.treated, value=value)
        for row, value in zip(rows, values, strict=True)
    )
    treated_values = tuple(item.value for item in weights if item.treated)
    control_values = tuple(item.value for item in weights if not item.treated)
    return IPWWeightSetDiagnostics(
        kind=kind,
        weights=weights,
        overall=summarize_distribution(values, propensity.configuration.weight_quantiles),
        treated=summarize_distribution(treated_values, propensity.configuration.weight_quantiles),
        control=summarize_distribution(control_values, propensity.configuration.weight_quantiles),
        ess=build_ess_diagnostic(
            values,
            tuple(row.treated for row in rows),
            propensity.configuration,
        ),
    )


def _score_model_reference(propensity: PropensityResult) -> IPWScoreModelReference:
    payload = {
        "request_id": propensity.request_id,
        "estimand": propensity.estimand,
        "adjustment_covariates": propensity.adjustment_covariates,
        "configuration": propensity.configuration.model_dump(mode="json"),
        "model_fit": propensity.model_fit.model_dump(mode="json"),
        "model_provenance": (
            propensity.model_provenance.model_dump(mode="json")
            if propensity.model_provenance is not None
            else None
        ),
        "encoding": (
            propensity.encoding.model_dump(mode="json")
            if propensity.encoding is not None
            else None
        ),
        "scores": tuple(item.model_dump(mode="json") for item in propensity.scores),
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return IPWScoreModelReference(
        fingerprint_sha256=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        configuration=propensity.configuration,
        model_provenance=propensity.model_provenance,
        encoding=propensity.encoding,
        score_diagnostics=propensity.score_diagnostics,
        fit_status=propensity.model_fit.status,
        converged=propensity.model_fit.converged,
        score_model_version=propensity.model_fit.sklearn_version,
    )


def _sample_counts(execution: IPWExecutionRequest) -> IPWSampleCounts:
    propensity = execution.propensity_result
    source = propensity.sample_counts
    selected = propensity.retained.scores if propensity.retained is not None else propensity.scores
    selected_treated = sum(item.treated for item in selected)
    return IPWSampleCounts(
        raw_count=source.raw,
        model_count=source.model,
        model_treated_count=source.model_treated,
        model_control_count=source.model_control,
        complete_case_excluded_count=source.complete_case_excluded,
        selected_count=len(selected),
        selected_treated_count=selected_treated,
        selected_control_count=len(selected) - selected_treated,
        upstream_trimming_enabled=propensity.retained is not None,
        upstream_trimmed_count=source.model - len(selected),
    )


def _analysis_provenance(
    execution: IPWExecutionRequest,
    provenance: ProvenanceRecords,
) -> ProvenanceRecords:
    clipping = execution.configuration.clipping
    propensity_config = execution.propensity_result.configuration
    formula = (
        "ate_inverse_probability"
        if execution.propensity_result.estimand is CausalEstimandKind.ATE
        else "att_control_odds"
    )
    records = (
        execution.identification_result.provenance
        + execution.propensity_result.provenance
        + provenance
        + (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.ANALYSIS_REQUEST,
            source_id=execution.request_id,
            source_version="ipw_contract=1",
        ),
        ProvenanceRecord(
            source_type=ProvenanceSourceType.DERIVED,
            source_id="inverse_probability_weighting",
            source_version=(
                "analysis=ipw-v1;variance=fixed_propensity_hajek_hc1;"
                f"formula={formula};"
                f"stabilized={str(execution.configuration.stabilized).lower()};"
                f"clip_max={clipping.maximum if clipping is not None else 'disabled'};"
                "overlap_policy=propensity-v1;"
                f"balance_threshold={propensity_config.balance_threshold};"
                f"severe_balance_threshold={execution.configuration.severe_balance_threshold};"
                f"minimum_ess={propensity_config.minimum_effective_sample_size};"
                f"minimum_ess_ratio={propensity_config.minimum_ess_ratio};"
                f"confidence_level={execution.configuration.confidence_level}"
            ),
        ),
        )
    )
    keyed = {
        json.dumps(
            item.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ): item
        for item in records
    }
    return tuple(keyed[key] for key in sorted(keyed))


def _warnings(diagnostics: tuple[IPWDiagnostic, ...]) -> tuple[AnalysisWarning, ...]:
    return tuple(
        AnalysisWarning(code=item.code, message=item.message, scope="ipw")
        for item in diagnostics
        if item.severity is DiagnosticSeverity.WARNING
    )


def _sensitivity_flags(
    execution: IPWExecutionRequest,
    validated: IPWValidationResult,
    weights: IPWWeightDiagnostics | None,
) -> tuple[IPWSensitivityFlag, ...]:
    """Return deterministic, diagnostic-only flags without modifying estimation."""
    propensity = execution.propensity_result
    active: list[IPWSensitivityFlag] = []

    def add(
        code: IPWSensitivityCode,
        message: str,
        *,
        severity: DiagnosticSeverity = DiagnosticSeverity.WARNING,
    ) -> None:
        active.append(
            IPWSensitivityFlag(
                code=code,
                severity=severity,
                message=message,
            )
        )

    raw_maximum = (
        weights.raw.overall.maximum
        if weights is not None
        else propensity.weights.overall.maximum
        if propensity.weights is not None
        else None
    )
    if (
        raw_maximum is not None
        and raw_maximum > propensity.configuration.extreme_weight_threshold
    ):
        add(IPWSensitivityCode.EXTREME_WEIGHTS, "Raw IPW weights exceed the configured threshold.")
    overlap = validated.overlap or propensity.overlap
    if overlap.status in {OverlapStatus.WEAK, OverlapStatus.SEVERE, OverlapStatus.UNAVAILABLE}:
        severe = overlap.status in {OverlapStatus.SEVERE, OverlapStatus.UNAVAILABLE}
        add(
            IPWSensitivityCode.POOR_OVERLAP,
            (
                "Overlap failed the configured fatal policy."
                if severe
                else "Overlap is weak but remains above the fatal policy."
            ),
            severity=DiagnosticSeverity.FATAL if severe else DiagnosticSeverity.WARNING,
        )
    source_ess_collapsed = (
        propensity.weights is not None
        and propensity.weights.ess.status is EffectiveSampleSizeStatus.COLLAPSED
    )
    selected_ess_collapsed = any(
        item.code in {"weight.source_ess_collapsed", "weight.selected_ess_collapsed"}
        for item in validated.diagnostics
    )
    if source_ess_collapsed or selected_ess_collapsed:
        add(
            IPWSensitivityCode.LOW_ESS,
            "Weighted effective sample size failed the configured minimum policy.",
            severity=DiagnosticSeverity.FATAL,
        )
    if validated.balance_status in {IPWBalanceStatus.CONCERN, IPWBalanceStatus.SEVERE}:
        add(
            IPWSensitivityCode.RESIDUAL_IMBALANCE,
            (
                "Post-weighting measured-covariate balance failed the fatal threshold."
                if validated.balance_status is IPWBalanceStatus.SEVERE
                else (
                    "Post-weighting measured-covariate balance remains above the advisory "
                    "threshold."
                )
            ),
            severity=(
                DiagnosticSeverity.FATAL
                if validated.balance_status is IPWBalanceStatus.SEVERE
                else DiagnosticSeverity.WARNING
            ),
        )
    clipping = weights.clipping if weights is not None else None
    if clipping is not None and (
        clipping.enabled
        and clipping.affected_proportion >= execution.configuration.heavy_clipping_fraction
    ):
        add(
            IPWSensitivityCode.HEAVY_CLIPPING,
            "The explicit clipping rule affected a substantial share of selected units.",
        )
    selected_scores = (
        propensity.retained.scores if propensity.retained is not None else propensity.scores
    )
    prevalence = (
        weights.treatment_prevalence
        if weights is not None
        else sum(item.treated for item in selected_scores) / len(selected_scores)
        if selected_scores
        else None
    )
    if prevalence is not None and not (
        execution.configuration.prevalence_warning_lower
        <= prevalence
        <= execution.configuration.prevalence_warning_upper
    ):
        add(
            IPWSensitivityCode.TREATMENT_PREVALENCE_IMBALANCE,
            "Treatment prevalence is outside the configured advisory range.",
        )
    if (
        propensity.model_fit.status is not PropensityFitStatus.CONVERGED
        or not propensity.model_fit.converged
        or propensity.model_fit.warning_codes
    ):
        add(
            IPWSensitivityCode.PROPENSITY_CONVERGENCE_CONCERNS,
            "The propensity model did not converge cleanly without fit concerns.",
            severity=(
                DiagnosticSeverity.FATAL
                if propensity.model_fit.status is not PropensityFitStatus.CONVERGED
                or not propensity.model_fit.converged
                else DiagnosticSeverity.WARNING
            ),
        )
    if any(
        assumption.status
        in {CausalAssumptionStatus.ASSERTED, CausalAssumptionStatus.UNVERIFIED}
        for assumption in execution.identification_result.assumptions
    ):
        add(
            IPWSensitivityCode.IDENTIFICATION_ASSUMPTIONS_UNVERIFIED,
            "Required causal assumptions remain asserted or unverified.",
        )
    return tuple(sorted(active, key=lambda item: item.code.value))


def _inference_diagnostic() -> IPWDiagnostic:
    from ..propensity import PropensityDiagnosticStatus

    return IPWDiagnostic(
        code="inference.unavailable",
        category=IPWDiagnosticCategory.INFERENCE,
        severity=DiagnosticSeverity.FATAL,
        status=PropensityDiagnosticStatus.UNAVAILABLE,
        message="Finite fixed-propensity robust inference is unavailable.",
    )


def _fixed_score_diagnostic() -> IPWDiagnostic:
    from ..propensity import PropensityDiagnosticStatus

    return IPWDiagnostic(
        code="inference.propensity_scores_treated_as_fixed",
        category=IPWDiagnosticCategory.INFERENCE,
        severity=DiagnosticSeverity.WARNING,
        status=PropensityDiagnosticStatus.PASSED,
        message=(
            "Analytic uncertainty conditions on fitted propensity scores and may understate "
            "propensity-estimation uncertainty."
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
            "ipw_treatment_effect",
            inputs={"row_count": row_count},
            metadata={"method": "ipw"},
            tags=("statistics", "causal", "ipw"),
        )
    except Exception:
        _increment_failure(provider, before)
        return None


def _finish_result(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: TreatmentEffectResult,
    duration_ms: float,
) -> None:
    if span is None:
        return
    weights = result.weights
    ess_status = weights.estimation.ess.status.value if weights is not None else "unavailable"
    outcome_type = (
        result.outcome.metric.metric.metric_type.value
        if result.outcome is not None
        else "unavailable"
    )
    metadata: dict[str, object] = {
        "method": "ipw",
        "estimand": result.estimand.estimand_type.value if result.estimand else "unavailable",
        "stabilization_enabled": result.configuration.stabilized,
        "clipping_enabled": result.configuration.clipping is not None,
        "overlap_status": result.overlap.status.value,
        "ess_status": ess_status,
        "balance_status": result.balance_status.value,
        "outcome_type": outcome_type,
        "status": result.status.value,
        "diagnostic_codes": tuple(item.code for item in result.diagnostics),
        "duration_ms": duration_ms,
    }
    _observe(provider, lambda: span.add_metadata(metadata))
    _observe(
        provider,
        lambda: span.finish(
            outputs={
                "status": result.status.value,
                "estimate_available": result.status is IPWStatus.COMPLETED,
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
            "IPW treatment-effect estimation failed.",
            details={"type": error.__class__.__name__},
        ),
    )
    _observe(
        provider,
        lambda: span.finish(outputs={"status": "failed", "estimate_available": False}),
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


__all__ = [
    "AnalyticIPWCalculationEngine",
    "IPWCalculationEngine",
    "IPWComputation",
    "IPWTreatmentEffectEstimator",
]
