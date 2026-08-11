"""Eligibility-gated orchestration for single-covariate CUPED analysis."""

from __future__ import annotations

import math
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from numbers import Real
from time import perf_counter

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ...base import AnalysisStatus
from ...metrics import MetricType
from ...provenance import (
    AnalysisWarning,
    AssumptionStatus,
    DiagnosticOutcome,
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceSourceType,
)
from ...requests import AnalysisRequest
from ...study_designs import (
    CovariateDefinition,
    CovariateRole,
    CovariateTiming,
    RandomizedAnalysisMethod,
    RandomizedExperimentDesign,
    TreatmentRelationship,
)
from ...uncertainty import RequestedConfidenceLevel
from ...validation import (
    AnalysisDataBinding,
    AnalysisEligibilityService,
    AnalysisTable,
    MethodCapabilityRegistry,
    ValidationPolicy,
)
from ...validation.context import ValidationContext
from ...validation.data_rules import validate_data
from ...validation.models import EligibilityDiagnostic, EligibilityValidationResult
from ..config import RandomizedAnalysisConfig
from ..continuous import analyze_continuous_welch
from ..models import (
    AlternativeHypothesis,
    ComputationStatus,
    RandomizedAnalysisResult,
    RandomizedDiagnostic,
    RandomizedDiagnosticCategory,
    RandomizedDiagnosticContext,
    RandomizedDiagnosticStatus,
)
from ..service import RandomizedAnalysisExecutionRequest, RandomizedAnalysisService
from .assumptions import cuped_assumptions
from .models import (
    CovariateBalanceStatus,
    CupedAbstentionReason,
    CupedAnalysisExecutionRequest,
    CupedAnalysisResult,
    CupedCoefficient,
    CupedCovariateBalance,
    CupedSampleRetention,
    CupedStatus,
    RetainedArmSummary,
    VarianceReduction,
    VarianceReductionStatus,
)
from .numerics import (
    CupedNumericalError,
    CupedVarianceError,
    adjust_outcomes,
    estimate_pooled_coefficient,
    summarize_covariate_balance,
)


@dataclass(frozen=True, slots=True)
class _CompleteCases:
    retention: CupedSampleRetention
    treatment_outcomes: tuple[float, ...]
    treatment_covariates: tuple[float, ...]
    control_outcomes: tuple[float, ...]
    control_covariates: tuple[float, ...]
    invalid_covariate_count: int


class CupedAnalysisService:
    """Compose baseline randomized analysis with one pooled CUPED adjustment."""

    def __init__(
        self,
        *,
        validation_policy: ValidationPolicy | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self._policy = validation_policy or ValidationPolicy()
        self._capability_registry = MethodCapabilityRegistry.with_implemented_methods(
            (RandomizedAnalysisMethod.CUPED,)
        )
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: CupedAnalysisExecutionRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> CupedAnalysisResult:
        """Return CUPED evidence while retaining an independently valid baseline."""
        started_at = perf_counter()
        span = _start_cuped_span(self.observability_provider, execution=execution, table=table)
        activation = span.activate() if span is not None else nullcontext()
        try:
            with activation:
                result = self._analyze(execution, table, binding, provenance=provenance)
        except Exception as error:
            _finish_cuped_failure(
                self.observability_provider,
                span,
                error=error,
                duration_ms=(perf_counter() - started_at) * 1000.0,
            )
            raise
        _finish_cuped_success(
            self.observability_provider,
            span,
            result=result,
            duration_ms=(perf_counter() - started_at) * 1000.0,
        )
        return result

    def _analyze(
        self,
        execution: CupedAnalysisExecutionRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> CupedAnalysisResult:
        request = execution.analysis_request
        result_provenance = provenance + (
            ProvenanceRecord(
                source_type=ProvenanceSourceType.DERIVED,
                source_id="cuped-adjustment",
                source_version="1",
            ),
        )
        baseline = self._full_sample_baseline(execution, table, binding, provenance=provenance)
        covariate = request.covariates[0] if len(request.covariates) == 1 else None

        if not isinstance(request.study_design, RandomizedExperimentDesign):
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.UNSUPPORTED,
                code="unsupported_study_design",
                message="CUPED requires a randomized experiment design.",
                category=RandomizedDiagnosticCategory.CONFIGURATION,
            )

        if execution.alternative is not AlternativeHypothesis.TWO_SIDED:
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.UNSUPPORTED,
                code="unsupported_alternative_hypothesis",
                message="Only a declared two-sided alternative hypothesis is supported.",
                category=RandomizedDiagnosticCategory.CONFIGURATION,
            )
        if not isinstance(request.uncertainty, RequestedConfidenceLevel):
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.UNSUPPORTED,
                code="unsupported_uncertainty",
                message="CUPED v1 supports frequentist confidence intervals only.",
                category=RandomizedDiagnosticCategory.CONFIGURATION,
            )
        if request.outcome.metric.metric_type is not MetricType.CONTINUOUS:
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.UNSUPPORTED,
                code="unsupported_outcome_type",
                message="CUPED v1 requires one continuous primary outcome.",
                category=RandomizedDiagnosticCategory.CONFIGURATION,
            )
        if len(request.covariates) != 1 or covariate is None:
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=None,
                provenance=result_provenance,
                status=CupedStatus.UNSUPPORTED,
                code="single_cuped_covariate_required",
                message="CUPED v1 requires exactly one declared covariate.",
                category=RandomizedDiagnosticCategory.CONFIGURATION,
            )
        if covariate.role is not CovariateRole.CUPED:
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.UNSUPPORTED,
                code="cuped_covariate_required",
                message="The single covariate must have the declared CUPED role.",
                category=RandomizedDiagnosticCategory.CONFIGURATION,
            )

        if baseline.status is ComputationStatus.UNSUPPORTED:
            baseline_reason = baseline.abstention_reason
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.UNSUPPORTED,
                code=(
                    baseline_reason.code
                    if baseline_reason is not None
                    else "randomized_baseline_unsupported"
                ),
                message=(
                    baseline_reason.message
                    if baseline_reason is not None
                    else "The randomized baseline does not support this request."
                ),
                category=RandomizedDiagnosticCategory.CONFIGURATION,
            )
        if baseline.status is not ComputationStatus.COMPLETED:
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="randomized_baseline_unavailable",
                message="CUPED requires a valid unadjusted randomized baseline.",
                category=RandomizedDiagnosticCategory.COMPUTATION,
            )

        eligibility = AnalysisEligibilityService(
            policy=self._policy,
            capability_registry=self._capability_registry,
            configuration_provenance="cuped-analysis-service-v1",
        ).validate(request, table, binding)
        diagnostics = list(_translate_eligibility_diagnostics(eligibility))

        complete_cases = _extract_complete_cases(request, table, binding)
        if complete_cases is None:
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.INVALID,
                code="cuped_covariate_binding_unavailable",
                message="The CUPED covariate requires one readable physical column binding.",
                category=RandomizedDiagnosticCategory.INPUT,
                diagnostics=tuple(diagnostics),
            )
        retention = complete_cases.retention

        if complete_cases.invalid_covariate_count:
            diagnostics.append(
                _diagnostic(
                    code="invalid_covariate_value",
                    category=RandomizedDiagnosticCategory.INPUT,
                    severity=DiagnosticSeverity.ERROR,
                    status=RandomizedDiagnosticStatus.FAILED,
                    message="Present CUPED covariates must be finite real numbers.",
                    context={"invalid_count": complete_cases.invalid_covariate_count},
                )
            )
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.INVALID,
                code="invalid_covariate_value",
                message="Present CUPED covariates must be finite real numbers.",
                category=RandomizedDiagnosticCategory.INPUT,
                diagnostics=tuple(diagnostics),
                retention=retention,
            )

        if eligibility.status not in {
            AnalysisStatus.ELIGIBLE,
            AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
        }:
            reason = eligibility.abstention_reason
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code=reason.code if reason is not None else "cuped_ineligible",
                message=(
                    reason.message
                    if reason is not None
                    else "The CUPED request did not pass eligibility validation."
                ),
                category=RandomizedDiagnosticCategory.ASSUMPTION,
                diagnostics=tuple(diagnostics),
                retention=retention,
                warnings=_translate_eligibility_warnings(eligibility),
            )
        if covariate.timing is not CovariateTiming.PRE_TREATMENT:
            diagnostics.append(
                _diagnostic(
                    code="cuped.covariate_not_pre_treatment",
                    category=RandomizedDiagnosticCategory.ASSUMPTION,
                    severity=DiagnosticSeverity.ERROR,
                    status=RandomizedDiagnosticStatus.FAILED,
                    message="CUPED requires an explicitly pre-treatment covariate.",
                    context={"timing": covariate.timing.value},
                )
            )
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="covariate_not_pre_treatment",
                message="CUPED requires an explicitly pre-treatment covariate.",
                category=RandomizedDiagnosticCategory.ASSUMPTION,
                diagnostics=tuple(diagnostics),
                retention=retention,
            )
        if covariate.treatment_relationship is not TreatmentRelationship.NONE_KNOWN:
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="covariate_treatment_relationship_conflict",
                message="CUPED covariates must not be treatment-derived or treatment proxies.",
                category=RandomizedDiagnosticCategory.ASSUMPTION,
                diagnostics=tuple(diagnostics),
                retention=retention,
            )

        if (
            retention.retained_total < self._policy.minimum_total
            or retention.treatment.retained_count < self._policy.minimum_per_arm
            or retention.control.retained_count < self._policy.minimum_per_arm
        ):
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="insufficient_retained_sample",
                message="Complete-case CUPED rows do not meet configured sample minima.",
                category=RandomizedDiagnosticCategory.SAMPLE,
                diagnostics=tuple(diagnostics),
                retention=retention,
            )

        config = _configuration(request)
        comparable = analyze_continuous_welch(
            request_id=f"{execution.request_id}-retained-unadjusted",
            metric=request.outcome.metric,
            estimand=request.estimand,
            treatment_arm_id=request.treatment.treatment_id,
            treatment_values=complete_cases.treatment_outcomes,
            control_arm_id=request.control.control_id,
            control_values=complete_cases.control_outcomes,
            provenance=result_provenance,
            configuration=config,
            alternative=execution.alternative,
        )
        try:
            balance = _balance(complete_cases)
        except CupedNumericalError:
            diagnostics.append(_computation_error_diagnostic())
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="cuped_computation_error",
                message="CUPED moments could not be represented as finite values.",
                category=RandomizedDiagnosticCategory.COMPUTATION,
                diagnostics=tuple(diagnostics),
                retention=retention,
                comparable=comparable,
            )
        if balance.status is CovariateBalanceStatus.OBSERVED_DIFFERENCE:
            diagnostics.append(
                _diagnostic(
                    code="cuped.covariate_arm_difference_observed",
                    category=RandomizedDiagnosticCategory.ASSUMPTION,
                    severity=DiagnosticSeverity.WARNING,
                    status=RandomizedDiagnosticStatus.PASSED,
                    message="Treatment and control covariate means differ in retained rows.",
                    context={
                        "control_mean": balance.control_mean,
                        "treatment_mean": balance.treatment_mean,
                    },
                )
            )

        combined_outcomes = (
            complete_cases.control_outcomes + complete_cases.treatment_outcomes
        )
        combined_covariates = (
            complete_cases.control_covariates + complete_cases.treatment_covariates
        )
        try:
            coefficient_values = estimate_pooled_coefficient(
                combined_outcomes,
                combined_covariates,
                minimum_variance=self._policy.minimum_covariate_variance,
            )
            adjusted_values = adjust_outcomes(
                combined_outcomes,
                combined_covariates,
                coefficient_values,
            )
        except CupedVarianceError:
            diagnostics.append(
                _diagnostic(
                    code="constant_or_near_zero_covariate",
                    category=RandomizedDiagnosticCategory.COMPUTATION,
                    severity=DiagnosticSeverity.ERROR,
                    status=RandomizedDiagnosticStatus.FAILED,
                    message=(
                        "Covariate variance must exceed the configured finite minimum."
                    ),
                    context={
                        "minimum_covariate_variance": (
                            self._policy.minimum_covariate_variance
                        )
                    },
                )
            )
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="constant_or_near_zero_covariate",
                message="CUPED requires finite covariate variance above the configured minimum.",
                category=RandomizedDiagnosticCategory.COMPUTATION,
                diagnostics=tuple(diagnostics),
                retention=retention,
                balance=balance,
                comparable=comparable,
            )
        except CupedNumericalError:
            diagnostics.append(_computation_error_diagnostic())
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="cuped_computation_error",
                message="CUPED moments could not be represented as finite values.",
                category=RandomizedDiagnosticCategory.COMPUTATION,
                diagnostics=tuple(diagnostics),
                retention=retention,
                balance=balance,
                comparable=comparable,
            )

        control_count = len(complete_cases.control_outcomes)
        adjusted_control = adjusted_values[:control_count]
        adjusted_treatment = adjusted_values[control_count:]
        adjusted = analyze_continuous_welch(
            request_id=f"{execution.request_id}-adjusted",
            metric=request.outcome.metric,
            estimand=request.estimand,
            treatment_arm_id=request.treatment.treatment_id,
            treatment_values=adjusted_treatment,
            control_arm_id=request.control.control_id,
            control_values=adjusted_control,
            provenance=result_provenance,
            configuration=config,
            alternative=execution.alternative,
        )
        coefficient = CupedCoefficient(
            theta=coefficient_values.theta,
            covariance=coefficient_values.covariance,
            covariate_variance=coefficient_values.covariate_variance,
            covariate_mean=coefficient_values.covariate_mean,
            outcome_variance=coefficient_values.outcome_variance,
            correlation=coefficient_values.correlation,
            sample_size=coefficient_values.sample_size,
        )
        if adjusted.status is not ComputationStatus.COMPLETED:
            code = (
                adjusted.abstention_reason.code
                if adjusted.abstention_reason is not None
                else "adjusted_inference_unavailable"
            )
            diagnostics.append(
                _diagnostic(
                    code=f"cuped.adjusted.{code}",
                    category=RandomizedDiagnosticCategory.COMPUTATION,
                    severity=DiagnosticSeverity.ERROR,
                    status=RandomizedDiagnosticStatus.FAILED,
                    message="Adjusted Welch inference was unavailable.",
                )
            )
            return _non_numerical_result(
                execution=execution,
                baseline=baseline,
                covariate=covariate,
                provenance=result_provenance,
                status=CupedStatus.ABSTAINED,
                code="adjusted_inference_unavailable",
                message="CUPED adjusted inference did not produce finite uncertainty.",
                category=RandomizedDiagnosticCategory.COMPUTATION,
                diagnostics=tuple(diagnostics),
                retention=retention,
                coefficient=coefficient,
                balance=balance,
                comparable=comparable,
            )

        variance_reduction = _variance_reduction(comparable, adjusted)
        status = {
            VarianceReductionStatus.POSITIVE_REDUCTION: CupedStatus.COMPLETED,
            VarianceReductionStatus.NO_REDUCTION: CupedStatus.NO_IMPROVEMENT,
            VarianceReductionStatus.NEGATIVE_REDUCTION: CupedStatus.DEGRADED_PRECISION,
            VarianceReductionStatus.UNAVAILABLE: CupedStatus.INCONCLUSIVE,
        }[variance_reduction.status]
        diagnostics.append(
            _diagnostic(
                code=f"cuped.variance_reduction.{variance_reduction.status.value}",
                category=RandomizedDiagnosticCategory.RESULT,
                severity=(
                    DiagnosticSeverity.INFO
                    if variance_reduction.status
                    in {
                        VarianceReductionStatus.POSITIVE_REDUCTION,
                        VarianceReductionStatus.NO_REDUCTION,
                    }
                    else DiagnosticSeverity.WARNING
                ),
                status=(
                    RandomizedDiagnosticStatus.UNAVAILABLE
                    if variance_reduction.status is VarianceReductionStatus.UNAVAILABLE
                    else RandomizedDiagnosticStatus.PASSED
                ),
                message="CUPED variance reduction was evaluated on identical retained rows.",
            )
        )
        return CupedAnalysisResult(
            request_id=execution.request_id,
            analysis_request=request,
            status=status,
            baseline_status=baseline.status,
            covariate=covariate,
            retention=retention,
            coefficient=coefficient,
            balance=balance,
            adjusted_result=adjusted,
            comparable_unadjusted_result=comparable,
            full_sample_unadjusted_result=baseline,
            variance_reduction=variance_reduction,
            assumptions=cuped_assumptions(),
            diagnostics=tuple(diagnostics),
            warnings=(
                _translate_eligibility_warnings(eligibility)
                + _cuped_warnings(balance, variance_reduction)
            ),
            provenance=result_provenance,
        )

    def _full_sample_baseline(
        self,
        execution: CupedAnalysisExecutionRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> RandomizedAnalysisResult:
        request = execution.analysis_request
        design = request.study_design
        baseline_design = (
            design.model_copy(update={"method": RandomizedAnalysisMethod.FIXED_HORIZON_AB})
            if isinstance(design, RandomizedExperimentDesign)
            else design
        )
        baseline_request = request.model_copy(
            update={
                "study_design": baseline_design,
                "covariates": (),
            }
        )
        baseline_binding = binding.model_copy(update={"covariates": ()})
        return RandomizedAnalysisService(validation_policy=self._policy).analyze(
            RandomizedAnalysisExecutionRequest(
                request_id=f"{execution.request_id}-full-unadjusted",
                analysis_request=baseline_request,
                alternative=execution.alternative,
            ),
            table,
            baseline_binding,
            provenance=provenance,
        )


def _extract_complete_cases(
    request: AnalysisRequest,
    table: AnalysisTable,
    binding: AnalysisDataBinding,
) -> _CompleteCases | None:
    if len(request.covariates) != 1:
        return None
    metric_id = request.covariates[0].metric.metric_id
    matching_bindings = tuple(item for item in binding.covariates if item.metric_id == metric_id)
    if len(matching_bindings) != 1:
        return None
    covariate_column = matching_bindings[0].column
    if covariate_column not in table.columns or binding.outcome.value_column is None:
        return None

    data = validate_data(
        ValidationContext(request=request, table=table, binding=binding, policy=ValidationPolicy())
    )
    columns = {column: index for index, column in enumerate(table.columns)}
    covariate_index = columns[covariate_column]
    outcome_index = columns[binding.outcome.value_column]
    treatment_index = columns[binding.treatment_column]
    treatment_outcomes: list[float] = []
    treatment_covariates: list[float] = []
    control_outcomes: list[float] = []
    control_covariates: list[float] = []
    treatment_original = 0
    control_original = 0
    treatment_missing = 0
    control_missing = 0
    invalid_count = 0
    for row_index in data.population_row_indexes:
        row = table.rows[row_index]
        assignment = row[treatment_index]
        is_treatment = _typed_equal(assignment, request.treatment.assignment_value)
        is_control = _typed_equal(assignment, request.control.assignment_value)
        if not is_treatment and not is_control:
            continue
        if is_treatment:
            treatment_original += 1
        else:
            control_original += 1
        covariate = row[covariate_index]
        if covariate is None:
            if is_treatment:
                treatment_missing += 1
            else:
                control_missing += 1
            continue
        outcome = row[outcome_index]
        checked_covariate = _finite_float(covariate)
        checked_outcome = _finite_float(outcome)
        if checked_covariate is None or checked_outcome is None:
            invalid_count += 1
            continue
        if is_treatment:
            treatment_outcomes.append(checked_outcome)
            treatment_covariates.append(checked_covariate)
        else:
            control_outcomes.append(checked_outcome)
            control_covariates.append(checked_covariate)

    treatment_retained = treatment_original - treatment_missing
    control_retained = control_original - control_missing
    treatment_summary = _arm_retention(
        original=treatment_original,
        retained=treatment_retained,
        missing=treatment_missing,
    )
    control_summary = _arm_retention(
        original=control_original,
        retained=control_retained,
        missing=control_missing,
    )
    original_total = treatment_original + control_original
    retained_total = treatment_retained + control_retained
    return _CompleteCases(
        retention=CupedSampleRetention(
            original_total=original_total,
            retained_total=retained_total,
            removed_total=original_total - retained_total,
            retained_proportion=retained_total / original_total if original_total else 0.0,
            treatment=treatment_summary,
            control=control_summary,
        ),
        treatment_outcomes=tuple(treatment_outcomes),
        treatment_covariates=tuple(treatment_covariates),
        control_outcomes=tuple(control_outcomes),
        control_covariates=tuple(control_covariates),
        invalid_covariate_count=invalid_count,
    )


def _start_cuped_span(
    provider: BaseObservabilityProvider,
    *,
    execution: CupedAnalysisExecutionRequest,
    table: AnalysisTable,
) -> BufferedSpan | None:
    request = execution.analysis_request
    before_failures = _provider_failure_count(provider)
    try:
        parent = provider.current_span()
        if parent is not None:
            return provider.start_span(
                "cuped_analysis",
                inputs={"total_row_count": len(table.rows)},
                metadata={
                    "capability": "cuped_analysis",
                    "analysis_method": "cuped",
                    "metric_type": request.outcome.metric.metric_type.value,
                },
                parent=parent,
            )
        return provider.start_root_span(
            "cuped_analysis",
            inputs={"total_row_count": len(table.rows)},
            metadata={
                "capability": "cuped_analysis",
                "analysis_method": "cuped",
                "metric_type": request.outcome.metric.metric_type.value,
            },
        )
    except Exception:
        _increment_provider_failure(provider, before_failures)
        return None


def _finish_cuped_success(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: CupedAnalysisResult,
    duration_ms: float,
) -> None:
    if span is None:
        return
    metadata: dict[str, object] = {
        "cuped_status": result.status.value,
        "baseline_status": result.baseline_status.value,
        "covariate_timing": (
            result.covariate.timing.value if result.covariate is not None else "unavailable"
        ),
        "variance_reduction_status": result.variance_reduction.status.value,
        "diagnostic_codes": tuple(diagnostic.code for diagnostic in result.diagnostics),
        "warning_count": len(result.warnings),
        "duration_ms": duration_ms,
    }
    if result.retention is not None:
        metadata.update(
            {
                "retained_count": result.retention.retained_total,
                "retained_proportion": result.retention.retained_proportion,
                "retained_treatment_count": result.retention.treatment.retained_count,
                "retained_control_count": result.retention.control.retained_count,
            }
        )
    _run_observability_operation(provider, lambda: span.add_metadata(metadata))
    _run_observability_operation(
        provider,
        lambda: span.finish(
            outputs={"status": result.status.value, "analysis_completed": True}
        ),
    )


def _finish_cuped_failure(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    error: Exception,
    duration_ms: float,
) -> None:
    if span is None:
        return
    _run_observability_operation(
        provider,
        lambda: span.add_metadata(
            {
                "cuped_status": "failed",
                "duration_ms": duration_ms,
                "failure_type": error.__class__.__name__,
            }
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.record_error(
            "CUPED analysis failed.",
            details={"failure_type": error.__class__.__name__},
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.finish(outputs={"status": "failed", "analysis_completed": False}),
    )


def _run_observability_operation(
    provider: BaseObservabilityProvider,
    operation: Callable[[], None],
) -> None:
    before_failures = _provider_failure_count(provider)
    try:
        operation()
    except Exception:
        _increment_provider_failure(provider, before_failures)


def _provider_failure_count(provider: BaseObservabilityProvider) -> int | None:
    try:
        return provider.failure_count
    except Exception:
        return None


def _increment_provider_failure(
    provider: BaseObservabilityProvider,
    before_failures: int | None,
) -> None:
    try:
        current_failures = provider.failure_count
    except Exception:
        current_failures = None
    try:
        if (
            before_failures is None
            or current_failures is None
            or current_failures == before_failures
        ):
            provider.increment_failure()
    except Exception:
        return


def _arm_retention(*, original: int, retained: int, missing: int) -> RetainedArmSummary:
    return RetainedArmSummary(
        original_count=original,
        retained_count=retained,
        removed_count=original - retained,
        missing_covariate_count=missing,
        retained_proportion=retained / original if original else 0.0,
        missing_covariate_rate=missing / original if original else 0.0,
    )


def _balance(complete_cases: _CompleteCases) -> CupedCovariateBalance:
    values = summarize_covariate_balance(
        complete_cases.treatment_covariates,
        complete_cases.control_covariates,
    )
    status = (
        CovariateBalanceStatus.EXACTLY_BALANCED
        if values.treatment_mean == values.control_mean
        else CovariateBalanceStatus.OBSERVED_DIFFERENCE
    )
    return CupedCovariateBalance(
        status=status,
        treatment_count=values.treatment_count,
        control_count=values.control_count,
        treatment_mean=values.treatment_mean,
        control_mean=values.control_mean,
        treatment_variance=values.treatment_variance,
        control_variance=values.control_variance,
        pooled_standard_deviation=values.pooled_standard_deviation,
        standardized_mean_difference=values.standardized_mean_difference,
    )


def _variance_reduction(
    comparable: RandomizedAnalysisResult,
    adjusted: RandomizedAnalysisResult,
) -> VarianceReduction:
    if comparable.test_result is None or adjusted.test_result is None:
        return _unavailable_variance_reduction()
    unadjusted_variance = comparable.test_result.standard_error**2
    adjusted_variance = adjusted.test_result.standard_error**2
    if (
        not math.isfinite(unadjusted_variance)
        or not math.isfinite(adjusted_variance)
        or unadjusted_variance <= 0.0
    ):
        return _unavailable_variance_reduction()
    fraction = 1.0 - adjusted_variance / unadjusted_variance
    if not math.isfinite(fraction):
        return _unavailable_variance_reduction()
    status = (
        VarianceReductionStatus.POSITIVE_REDUCTION
        if fraction > 0.0
        else VarianceReductionStatus.NEGATIVE_REDUCTION
        if fraction < 0.0
        else VarianceReductionStatus.NO_REDUCTION
    )
    return VarianceReduction(
        status=status,
        unadjusted_estimator_variance=unadjusted_variance,
        adjusted_estimator_variance=adjusted_variance,
        fraction=fraction,
        percentage=fraction * 100.0,
    )


def _unavailable_variance_reduction() -> VarianceReduction:
    return VarianceReduction(
        status=VarianceReductionStatus.UNAVAILABLE,
        unadjusted_estimator_variance=None,
        adjusted_estimator_variance=None,
        fraction=None,
        percentage=None,
    )


def _configuration(request: AnalysisRequest) -> RandomizedAnalysisConfig:
    uncertainty = request.uncertainty
    if not isinstance(uncertainty, RequestedConfidenceLevel):
        raise TypeError("frequentist confidence level required")
    return RandomizedAnalysisConfig(
        alpha=1.0 - uncertainty.level,
        confidence_level=uncertainty.level,
    )


def _translate_eligibility_diagnostics(
    eligibility: EligibilityValidationResult,
) -> tuple[RandomizedDiagnostic, ...]:
    return tuple(
        RandomizedDiagnostic(
            code=f"eligibility.{diagnostic.code}",
            category=_eligibility_category(diagnostic),
            severity=diagnostic.severity,
            status={
                DiagnosticOutcome.PASSED: RandomizedDiagnosticStatus.PASSED,
                DiagnosticOutcome.FAILED: RandomizedDiagnosticStatus.FAILED,
                DiagnosticOutcome.UNAVAILABLE: RandomizedDiagnosticStatus.UNAVAILABLE,
            }[diagnostic.outcome],
            message=diagnostic.message,
            context=tuple(
                RandomizedDiagnosticContext(key=entry.key, value=entry.value)
                for entry in diagnostic.context
            ),
            recommended_action=diagnostic.recommended_action,
        )
        for diagnostic in eligibility.diagnostics
    )


def _translate_eligibility_warnings(
    eligibility: EligibilityValidationResult,
) -> tuple[AnalysisWarning, ...]:
    return tuple(
        AnalysisWarning(
            code=f"eligibility.{diagnostic.code}",
            message=diagnostic.message,
            scope="cuped_eligibility",
        )
        for diagnostic in eligibility.warnings
    )


def _eligibility_category(
    diagnostic: EligibilityDiagnostic,
) -> RandomizedDiagnosticCategory:
    value = diagnostic.category.value
    if value in {"method", "request"}:
        return RandomizedDiagnosticCategory.CONFIGURATION
    if value == "sample":
        return RandomizedDiagnosticCategory.SAMPLE
    if value in {"design", "time", "unit", "covariate"}:
        return RandomizedDiagnosticCategory.ASSUMPTION
    return RandomizedDiagnosticCategory.INPUT


def _non_numerical_result(
    *,
    execution: CupedAnalysisExecutionRequest,
    baseline: RandomizedAnalysisResult,
    covariate: CovariateDefinition | None,
    provenance: tuple[ProvenanceRecord, ...],
    status: CupedStatus,
    code: str,
    message: str,
    category: RandomizedDiagnosticCategory,
    diagnostics: tuple[RandomizedDiagnostic, ...] = (),
    warnings: tuple[AnalysisWarning, ...] = (),
    retention: CupedSampleRetention | None = None,
    coefficient: CupedCoefficient | None = None,
    balance: CupedCovariateBalance | None = None,
    comparable: RandomizedAnalysisResult | None = None,
) -> CupedAnalysisResult:
    if not any(diagnostic.code == code for diagnostic in diagnostics):
        diagnostics = diagnostics + (
            _diagnostic(
                code=code,
                category=category,
                severity=DiagnosticSeverity.ERROR,
                status=RandomizedDiagnosticStatus.FAILED,
                message=message,
            ),
        )
    pre_treatment_status, unaffected_status = _cuped_assumption_statuses(
        execution.analysis_request,
        covariate,
    )
    return CupedAnalysisResult(
        request_id=execution.request_id,
        analysis_request=execution.analysis_request,
        status=status,
        baseline_status=baseline.status,
        covariate=covariate,
        retention=retention,
        coefficient=coefficient,
        balance=balance,
        adjusted_result=None,
        comparable_unadjusted_result=comparable,
        full_sample_unadjusted_result=baseline,
        variance_reduction=_unavailable_variance_reduction(),
        assumptions=cuped_assumptions(
            pre_treatment_status=pre_treatment_status,
            unaffected_by_treatment_status=unaffected_status,
        ),
        diagnostics=diagnostics,
        warnings=warnings,
        provenance=provenance,
        abstention_reason=CupedAbstentionReason(
            code=code,
            message=message,
            missing_or_invalid_information=(code,),
        ),
    )


def _cuped_assumption_statuses(
    request: AnalysisRequest,
    covariate: CovariateDefinition | None,
) -> tuple[AssumptionStatus, AssumptionStatus]:
    if covariate is None:
        return AssumptionStatus.UNASSESSED, AssumptionStatus.UNASSESSED

    design = request.study_design
    timing_is_contradictory = (
        isinstance(design, RandomizedExperimentDesign)
        and covariate.measurement_period.end > design.experiment_period.start
    )
    if covariate.timing is CovariateTiming.UNKNOWN:
        pre_treatment = AssumptionStatus.UNASSESSED
    elif covariate.timing is not CovariateTiming.PRE_TREATMENT or timing_is_contradictory:
        pre_treatment = AssumptionStatus.VIOLATED
    else:
        pre_treatment = AssumptionStatus.SUPPORTED

    if covariate.treatment_relationship is TreatmentRelationship.NONE_KNOWN:
        unaffected = AssumptionStatus.UNTESTABLE
    elif covariate.treatment_relationship is TreatmentRelationship.UNKNOWN:
        unaffected = AssumptionStatus.UNASSESSED
    else:
        unaffected = AssumptionStatus.VIOLATED
    return pre_treatment, unaffected


def _diagnostic(
    *,
    code: str,
    category: RandomizedDiagnosticCategory,
    severity: DiagnosticSeverity,
    status: RandomizedDiagnosticStatus,
    message: str,
    context: dict[str, int | float | str] | None = None,
) -> RandomizedDiagnostic:
    return RandomizedDiagnostic(
        code=code,
        category=category,
        severity=severity,
        status=status,
        message=message,
        context=tuple(
            RandomizedDiagnosticContext(key=key, value=value)
            for key, value in sorted((context or {}).items())
        ),
    )


def _computation_error_diagnostic() -> RandomizedDiagnostic:
    return _diagnostic(
        code="cuped_computation_error",
        category=RandomizedDiagnosticCategory.COMPUTATION,
        severity=DiagnosticSeverity.ERROR,
        status=RandomizedDiagnosticStatus.FAILED,
        message="CUPED moments could not be represented as finite values.",
    )


def _cuped_warnings(
    balance: CupedCovariateBalance,
    variance_reduction: VarianceReduction,
) -> tuple[AnalysisWarning, ...]:
    warnings: list[AnalysisWarning] = []
    if balance.status is CovariateBalanceStatus.OBSERVED_DIFFERENCE:
        warnings.append(
            AnalysisWarning(
                code="cuped.covariate_arm_difference_observed",
                message="Treatment and control covariate means differ in retained rows.",
                scope="covariate_balance",
            )
        )
    if variance_reduction.status is VarianceReductionStatus.NEGATIVE_REDUCTION:
        warnings.append(
            AnalysisWarning(
                code="cuped.degraded_precision",
                message="CUPED increased estimated treatment-effect variance on retained rows.",
                scope="variance_reduction",
            )
        )
    return tuple(warnings)


def _typed_equal(value: object, expected: object) -> bool:
    return type(value) is type(expected) and value == expected


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        converted = float(value)
    except OverflowError:
        return None
    return converted if math.isfinite(converted) else None


__all__ = ["CupedAnalysisService"]
