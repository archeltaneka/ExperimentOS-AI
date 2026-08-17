"""Eligibility-gated orchestration for conjugate Bayesian A/B analysis."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import nullcontext
from time import perf_counter

from pydantic import ValidationError

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ...base import AnalysisStatus
from ...metrics import MetricType
from ...provenance import (
    AnalysisWarning,
    DiagnosticOutcome,
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceSourceType,
)
from ...requests import AnalysisRequest
from ...study_designs import RandomizedAnalysisMethod
from ...uncertainty import RequestedCredibleLevel
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
from .assumptions import bayesian_assumptions
from .binary import calculate_beta_binomial_posteriors
from .continuous import calculate_normal_inverse_gamma_posteriors
from .models import (
    BayesianAbstentionReason,
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisResult,
    BayesianArmPosterior,
    BayesianComputationConfig,
    BayesianComputationStatus,
    BayesianDiagnostic,
    BayesianDiagnosticCategory,
    BayesianDiagnosticStatus,
    BernoulliBinomialLikelihood,
    BetaPrior,
    NormalInverseGammaPrior,
    NormalUnknownMeanVarianceLikelihood,
    PosteriorEffectSummary,
)
from .numerics import BayesianNumericalError

_BAYESIAN_COMPATIBLE_BLOCKERS = frozenset({"outcome.zero_variance"})


class BayesianAnalysisService:
    """Validate and dispatch one explicit conjugate Bayesian A/B request."""

    def __init__(
        self,
        *,
        validation_policy: ValidationPolicy | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self._policy = validation_policy or ValidationPolicy(
            minimum_total=2,
            minimum_per_arm=1,
            weak_total=100,
            weak_per_arm=30,
        )
        self._capability_registry = MethodCapabilityRegistry.with_implemented_methods(
            (RandomizedAnalysisMethod.BAYESIAN_AB,)
        )
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: BayesianAnalysisExecutionRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> BayesianAnalysisResult:
        """Return a Bayesian result after shared and model-specific validation."""
        started_at = perf_counter()
        span = _start_span(
            self.observability_provider,
            execution=execution,
            table=table,
        )
        eligibility_provider = (
            self.observability_provider if span is not None else NoOpObservabilityProvider()
        )
        activation = span.activate() if span is not None else nullcontext()
        try:
            with activation:
                result = self._analyze(
                    execution,
                    table,
                    binding,
                    provenance=provenance,
                    eligibility_provider=eligibility_provider,
                )
        except Exception as error:
            _finish_failure(
                self.observability_provider,
                span,
                error=error,
                duration_ms=(perf_counter() - started_at) * 1000.0,
            )
            raise
        _finish_success(
            self.observability_provider,
            span,
            result=result,
            duration_ms=(perf_counter() - started_at) * 1000.0,
        )
        return result

    def _analyze(
        self,
        execution: BayesianAnalysisExecutionRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        *,
        provenance: tuple[ProvenanceRecord, ...],
        eligibility_provider: BaseObservabilityProvider,
    ) -> BayesianAnalysisResult:
        config = BayesianComputationConfig()
        request = execution.analysis_request
        result_provenance = _analysis_provenance(execution, provenance)
        eligibility = AnalysisEligibilityService(
            policy=self._policy,
            capability_registry=self._capability_registry,
            configuration_provenance="bayesian-analysis-service-v1",
            observability_provider=eligibility_provider,
        ).validate(request, table, binding)
        diagnostics = tuple(_translate_diagnostic(item) for item in eligibility.diagnostics)
        warnings = _translate_warnings(eligibility)

        mismatch = _likelihood_mismatch(execution)
        if mismatch is not None:
            return _non_numerical_result(
                execution=execution,
                status=BayesianComputationStatus.UNSUPPORTED,
                code="likelihood_outcome_mismatch",
                message=mismatch,
                diagnostics=diagnostics
                + (
                    _diagnostic(
                        code="declaration.likelihood_outcome_mismatch",
                        category=BayesianDiagnosticCategory.DECLARATION,
                        status=BayesianDiagnosticStatus.FAILED,
                        severity=DiagnosticSeverity.ERROR,
                        message=mismatch,
                    ),
                ),
                warnings=warnings,
                provenance=result_provenance,
                config=config,
            )

        blocking_codes = {item.code for item in eligibility.blocking_diagnostics}
        unhandled_blockers = blocking_codes - _BAYESIAN_COMPATIBLE_BLOCKERS
        if unhandled_blockers or eligibility.status is AnalysisStatus.NEEDS_MORE_DATA:
            primary = eligibility.abstention_reason
            code = f"eligibility.{primary.code}" if primary is not None else "eligibility.blocked"
            message = (
                primary.message
                if primary is not None
                else "Shared randomized-analysis eligibility did not support computation."
            )
            return _non_numerical_result(
                execution=execution,
                status=BayesianComputationStatus.ABSTAINED,
                code=code,
                message=message,
                diagnostics=diagnostics,
                warnings=warnings,
                provenance=result_provenance,
                config=config,
            )

        data = validate_data(
            ValidationContext(request=request, table=table, binding=binding, policy=self._policy)
        )
        if data.valid_row_indexes != data.population_row_indexes:
            return _non_numerical_result(
                execution=execution,
                status=BayesianComputationStatus.ABSTAINED,
                code="incomplete_outcome_data",
                message="Bayesian v1 does not drop missing or invalid outcome observations.",
                diagnostics=diagnostics,
                warnings=warnings,
                provenance=result_provenance,
                config=config,
            )
        treatment_values, control_values = _extract_arm_values(
            request,
            table,
            binding,
            row_indexes=data.valid_row_indexes,
        )
        if not treatment_values or not control_values:
            return _non_numerical_result(
                execution=execution,
                status=BayesianComputationStatus.ABSTAINED,
                code="empty_arm",
                message="Each Bayesian analysis arm requires at least one valid observation.",
                diagnostics=diagnostics,
                warnings=warnings,
                provenance=result_provenance,
                config=config,
            )
        if isinstance(execution.likelihood, NormalUnknownMeanVarianceLikelihood) and (
            len(treatment_values) < 2 or len(control_values) < 2
        ):
            return _non_numerical_result(
                execution=execution,
                status=BayesianComputationStatus.ABSTAINED,
                code="continuous_arm_inadequate",
                message=(
                    "The unknown-variance continuous model requires at least two valid "
                    "observations in each arm."
                ),
                diagnostics=diagnostics,
                warnings=warnings,
                provenance=result_provenance,
                config=config,
            )

        uncertainty = request.uncertainty
        assert isinstance(uncertainty, RequestedCredibleLevel)
        treatment: BayesianArmPosterior
        control: BayesianArmPosterior
        effect: PosteriorEffectSummary
        try:
            if isinstance(execution.likelihood, BernoulliBinomialLikelihood):
                assert isinstance(execution.treatment_prior, BetaPrior)
                assert isinstance(execution.control_prior, BetaPrior)
                treatment, control, effect = calculate_beta_binomial_posteriors(
                    treatment_arm_id=request.treatment.treatment_id,
                    treatment_values=treatment_values,
                    treatment_prior=execution.treatment_prior,
                    control_arm_id=request.control.control_id,
                    control_values=control_values,
                    control_prior=execution.control_prior,
                    credible_level=uncertainty.level,
                    metric_direction=request.outcome.direction,
                    rope=execution.rope,
                    config=config,
                )
            else:
                assert isinstance(execution.treatment_prior, NormalInverseGammaPrior)
                assert isinstance(execution.control_prior, NormalInverseGammaPrior)
                treatment, control, effect = calculate_normal_inverse_gamma_posteriors(
                    treatment_arm_id=request.treatment.treatment_id,
                    treatment_values=treatment_values,
                    treatment_prior=execution.treatment_prior,
                    control_arm_id=request.control.control_id,
                    control_values=control_values,
                    control_prior=execution.control_prior,
                    credible_level=uncertainty.level,
                    metric_direction=request.outcome.direction,
                    rope=execution.rope,
                    config=config,
                )
        except BayesianNumericalError:
            return _non_numerical_result(
                execution=execution,
                status=BayesianComputationStatus.INVALID,
                code="posterior_computation_invalid",
                message="The posterior calculation did not produce finite valid quantities.",
                diagnostics=diagnostics
                + (
                    _diagnostic(
                        code="computation.posterior_invalid",
                        category=BayesianDiagnosticCategory.COMPUTATION,
                        status=BayesianDiagnosticStatus.FAILED,
                        severity=DiagnosticSeverity.ERROR,
                        message="Posterior computation failed finite-safety validation.",
                    ),
                ),
                warnings=warnings,
                provenance=result_provenance,
                config=config,
            )

        diagnostics += (
            _diagnostic(
                code="declaration.priors_valid",
                category=BayesianDiagnosticCategory.DECLARATION,
                status=BayesianDiagnosticStatus.PASSED,
                message="Both explicit conjugate priors passed validation.",
            ),
            _diagnostic(
                code="computation.analytic_arm_updates",
                category=BayesianDiagnosticCategory.COMPUTATION,
                status=BayesianDiagnosticStatus.PASSED,
                message="Arm posterior parameters were updated analytically.",
            ),
            _diagnostic(
                code="computation.deterministic_quadrature",
                category=BayesianDiagnosticCategory.COMPUTATION,
                status=BayesianDiagnosticStatus.PASSED,
                message="Effect probabilities and credible bounds used deterministic quadrature.",
                context={"maximum_absolute_error": effect.quadrature.maximum_absolute_error},
            ),
        )
        prior_diagnostics, prior_warnings = _prior_information_context(
            execution,
            treatment_n=treatment.n,
            control_n=control.n,
        )
        diagnostics += prior_diagnostics
        warnings += prior_warnings
        return BayesianAnalysisResult(
            request_id=execution.request_id,
            analysis_request=request,
            metric=request.outcome.metric,
            estimand=request.estimand,
            treatment_arm_id=request.treatment.treatment_id,
            control_arm_id=request.control.control_id,
            status=BayesianComputationStatus.COMPLETED,
            likelihood=execution.likelihood,
            treatment_prior=execution.treatment_prior,
            control_prior=execution.control_prior,
            treatment_posterior=treatment,
            control_posterior=control,
            effect=effect,
            assumptions=bayesian_assumptions(execution.likelihood),
            diagnostics=diagnostics,
            warnings=warnings,
            provenance=result_provenance,
            configuration=config,
        )

    def analyze_payload(
        self,
        payload: Mapping[str, object],
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> BayesianAnalysisResult:
        """Validate an untrusted execution payload and return typed declaration failures."""
        try:
            execution = BayesianAnalysisExecutionRequest.model_validate(payload)
        except ValidationError as error:
            started_at = perf_counter()
            result = _invalid_payload_result(payload, error=error, provenance=provenance)
            span = _start_invalid_payload_span(
                self.observability_provider,
                result=result,
                table=table,
            )
            _finish_success(
                self.observability_provider,
                span,
                result=result,
                duration_ms=(perf_counter() - started_at) * 1000.0,
                prior_validity="invalid",
            )
            return result
        return self.analyze(execution, table, binding, provenance=provenance)


def _start_span(
    provider: BaseObservabilityProvider,
    *,
    execution: BayesianAnalysisExecutionRequest,
    table: AnalysisTable,
) -> BufferedSpan | None:
    before_failures = _provider_failure_count(provider)
    metadata: dict[str, object] = {
        "inference_family": "bayesian",
        "likelihood_family": execution.likelihood.likelihood_family,
        "outcome_type": execution.analysis_request.outcome.metric.metric_type.value,
        "computation_mode": "deterministic_quadrature",
        "analysis_started": True,
    }
    try:
        parent = provider.current_span()
        if parent is not None and parent.provider is provider:
            return provider.start_span(
                "bayesian_randomized_analysis",
                inputs={"total_row_count": len(table.rows)},
                metadata=metadata,
                tags=("analysis", "randomized", "bayesian"),
                parent=parent,
            )
        return provider.start_root_span(
            "bayesian_randomized_analysis",
            inputs={"total_row_count": len(table.rows)},
            metadata=metadata,
            tags=("analysis", "randomized", "bayesian"),
        )
    except Exception:
        _increment_provider_failure(provider, before_failures)
        return None


def _start_invalid_payload_span(
    provider: BaseObservabilityProvider,
    *,
    result: BayesianAnalysisResult,
    table: AnalysisTable,
) -> BufferedSpan | None:
    before_failures = _provider_failure_count(provider)
    likelihood_family = (
        "unsupported" if result.status is BayesianComputationStatus.UNSUPPORTED else "invalid"
    )
    metadata: dict[str, object] = {
        "inference_family": "bayesian",
        "likelihood_family": likelihood_family,
        "outcome_type": result.metric.metric_type.value if result.metric is not None else "unknown",
        "computation_mode": "deterministic_quadrature",
        "analysis_started": True,
    }
    try:
        return provider.start_root_span(
            "bayesian_randomized_analysis",
            inputs={"total_row_count": len(table.rows)},
            metadata=metadata,
            tags=("analysis", "randomized", "bayesian"),
        )
    except Exception:
        _increment_provider_failure(provider, before_failures)
        return None


def _finish_success(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: BayesianAnalysisResult,
    duration_ms: float,
    prior_validity: str = "valid",
) -> None:
    if span is None:
        return
    treatment_count = result.treatment_posterior.n if result.treatment_posterior else 0
    control_count = result.control_posterior.n if result.control_posterior else 0
    diagnostic_codes = tuple(item.code for item in result.diagnostics)
    metadata: dict[str, object] = {
        "status": result.status.value,
        "prior_validity": prior_validity,
        "rope_requested": bool(
            result.analysis_request is not None
            and result.effect is not None
            and result.effect.rope_probability is not None
        ),
        "probability_of_superiority_available": bool(
            result.effect is not None and result.effect.probability_of_superiority is not None
        ),
        "diagnostic_codes": diagnostic_codes,
        "diagnostic_count": len(diagnostic_codes),
        "warning_count": len(result.warnings),
        "treatment_count": treatment_count,
        "control_count": control_count,
        "duration_ms": duration_ms,
        "analysis_completed": True,
    }
    _run_observability_operation(provider, lambda: span.add_metadata(metadata))
    _run_observability_operation(
        provider,
        lambda: span.finish(outputs={"status": result.status.value, "analysis_completed": True}),
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
    _run_observability_operation(
        provider,
        lambda: span.add_metadata(
            {"status": "failed", "duration_ms": duration_ms, "analysis_completed": False}
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.record_error(
            "Bayesian randomized analysis failed.",
            details={"type": error.__class__.__name__},
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.finish(outputs={"status": "failed", "analysis_completed": False}),
    )


def _run_observability_operation(
    provider: BaseObservabilityProvider,
    operation: Callable[[], object],
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


def _likelihood_mismatch(execution: BayesianAnalysisExecutionRequest) -> str | None:
    metric_type = execution.analysis_request.outcome.metric.metric_type
    if isinstance(execution.likelihood, BernoulliBinomialLikelihood):
        if metric_type is not MetricType.BINARY:
            return "Bernoulli/Binomial likelihood requires a declared binary outcome."
    elif metric_type is not MetricType.CONTINUOUS:
        return "Normal unknown-variance likelihood requires a declared continuous outcome."
    return None


def _extract_arm_values(
    request: AnalysisRequest,
    table: AnalysisTable,
    binding: AnalysisDataBinding,
    *,
    row_indexes: tuple[int, ...],
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    treatment_index = table.columns.index(binding.treatment_column)
    outcome_column = binding.outcome.value_column
    if outcome_column is None:
        raise RuntimeError("validated Bayesian outcome binding has no value column")
    outcome_index = table.columns.index(outcome_column)
    treatment_values: list[object] = []
    control_values: list[object] = []
    for row_index in row_indexes:
        row = table.rows[row_index]
        assignment = row[treatment_index]
        if type(assignment) is type(request.treatment.assignment_value) and (
            assignment == request.treatment.assignment_value
        ):
            treatment_values.append(row[outcome_index])
        elif type(assignment) is type(request.control.assignment_value) and (
            assignment == request.control.assignment_value
        ):
            control_values.append(row[outcome_index])
    return (tuple(treatment_values), tuple(control_values))


def _analysis_provenance(
    execution: BayesianAnalysisExecutionRequest,
    provenance: tuple[ProvenanceRecord, ...],
) -> tuple[ProvenanceRecord, ...]:
    return provenance + (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.ANALYSIS_REQUEST,
            source_id=execution.request_id,
            source_version=(
                f"method=bayesian_ab;likelihood={execution.likelihood.likelihood_family}"
            ),
        ),
    )


def _translate_diagnostic(diagnostic: EligibilityDiagnostic) -> BayesianDiagnostic:
    status = {
        DiagnosticOutcome.PASSED: BayesianDiagnosticStatus.PASSED,
        DiagnosticOutcome.FAILED: BayesianDiagnosticStatus.FAILED,
        DiagnosticOutcome.UNAVAILABLE: BayesianDiagnosticStatus.UNAVAILABLE,
    }[diagnostic.outcome]
    context = {entry.key: entry.value for entry in diagnostic.context}
    return _diagnostic(
        code=f"eligibility.{diagnostic.code}",
        category=BayesianDiagnosticCategory.INPUT,
        status=status,
        severity=diagnostic.severity,
        message=diagnostic.message,
        context=context,
        recommended_action=diagnostic.recommended_action,
    )


def _translate_warnings(
    eligibility: EligibilityValidationResult,
) -> tuple[AnalysisWarning, ...]:
    return tuple(
        AnalysisWarning(
            code=f"eligibility.{item.code}",
            message=item.message,
            scope="eligibility",
        )
        for item in eligibility.warnings
    )


def _non_numerical_result(
    *,
    execution: BayesianAnalysisExecutionRequest,
    status: BayesianComputationStatus,
    code: str,
    message: str,
    diagnostics: tuple[BayesianDiagnostic, ...],
    warnings: tuple[AnalysisWarning, ...],
    provenance: tuple[ProvenanceRecord, ...],
    config: BayesianComputationConfig,
) -> BayesianAnalysisResult:
    request = execution.analysis_request
    return BayesianAnalysisResult(
        request_id=execution.request_id,
        analysis_request=request,
        metric=request.outcome.metric,
        estimand=request.estimand,
        treatment_arm_id=request.treatment.treatment_id,
        control_arm_id=request.control.control_id,
        status=status,
        likelihood=execution.likelihood,
        treatment_prior=execution.treatment_prior,
        control_prior=execution.control_prior,
        assumptions=bayesian_assumptions(execution.likelihood),
        diagnostics=diagnostics,
        warnings=warnings,
        provenance=provenance,
        configuration=config,
        abstention_reason=BayesianAbstentionReason(code=code, message=message),
    )


def _invalid_payload_result(
    payload: Mapping[str, object],
    *,
    error: ValidationError,
    provenance: tuple[ProvenanceRecord, ...],
) -> BayesianAnalysisResult:
    locations = tuple(tuple(item["loc"]) for item in error.errors(include_input=False))
    is_likelihood = any(location and location[0] == "likelihood" for location in locations)
    is_prior = any(
        location and location[0] in {"treatment_prior", "control_prior"} for location in locations
    )
    is_rope = any(location and location[0] == "rope" for location in locations)
    if is_likelihood:
        status = BayesianComputationStatus.UNSUPPORTED
        code = "unsupported_likelihood"
        diagnostic_code = "declaration.unsupported_likelihood"
        message = "The declared likelihood family is not supported by Bayesian A/B v1."
    elif is_prior:
        status = BayesianComputationStatus.INVALID
        code = "invalid_prior"
        diagnostic_code = "declaration.invalid_prior"
        message = "At least one explicit prior failed validation."
    elif is_rope:
        status = BayesianComputationStatus.INVALID
        code = "invalid_rope"
        diagnostic_code = "declaration.invalid_rope"
        message = "The explicit practical-equivalence region failed validation."
    else:
        status = BayesianComputationStatus.INVALID
        code = "invalid_declaration"
        diagnostic_code = "declaration.invalid"
        message = "The Bayesian execution declaration failed validation."

    raw_request = payload.get("analysis_request")
    try:
        request = AnalysisRequest.model_validate(raw_request)
    except ValidationError:
        request = None
    raw_request_id = payload.get("request_id")
    request_id = (
        raw_request_id.strip()
        if isinstance(raw_request_id, str) and raw_request_id.strip()
        else "invalid-bayesian-request"
    )
    config = BayesianComputationConfig()
    return BayesianAnalysisResult(
        request_id=request_id,
        analysis_request=request,
        metric=request.outcome.metric if request is not None else None,
        estimand=request.estimand if request is not None else None,
        treatment_arm_id=request.treatment.treatment_id if request is not None else None,
        control_arm_id=request.control.control_id if request is not None else None,
        status=status,
        assumptions=(),
        diagnostics=(
            _diagnostic(
                code=diagnostic_code,
                category=BayesianDiagnosticCategory.DECLARATION,
                status=BayesianDiagnosticStatus.FAILED,
                severity=DiagnosticSeverity.ERROR,
                message=message,
            ),
        ),
        warnings=(),
        provenance=provenance,
        configuration=config,
        abstention_reason=BayesianAbstentionReason(code=code, message=message),
    )


def _diagnostic(
    *,
    code: str,
    category: BayesianDiagnosticCategory,
    status: BayesianDiagnosticStatus,
    message: str,
    severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
    context: Mapping[str, object] | None = None,
    recommended_action: str | None = None,
) -> BayesianDiagnostic:
    return BayesianDiagnostic.model_validate(
        {
            "code": code,
            "category": category,
            "severity": severity,
            "status": status,
            "message": message,
            "context": context or {},
            "recommended_action": recommended_action,
        }
    )


def _prior_information_context(
    execution: BayesianAnalysisExecutionRequest,
    *,
    treatment_n: int,
    control_n: int,
) -> tuple[tuple[BayesianDiagnostic, ...], tuple[AnalysisWarning, ...]]:
    diagnostics: list[BayesianDiagnostic] = []
    warnings: list[AnalysisWarning] = []
    for arm, prior, observed_n in (
        ("treatment", execution.treatment_prior, treatment_n),
        ("control", execution.control_prior, control_n),
    ):
        if isinstance(prior, BetaPrior):
            assert prior.effective_sample_size is not None
            information = prior.effective_sample_size
            heuristic = "beta_effective_sample_size_gt_observed_n"
            information_key = "prior_effective_sample_size"
        else:
            information = prior.kappa_0
            heuristic = "normal_prior_kappa_gt_observed_n"
            information_key = "prior_kappa"
        dominated = information > observed_n
        diagnostics.append(
            _diagnostic(
                code=f"prior.{arm}_information_context",
                category=BayesianDiagnosticCategory.RESULT,
                status=BayesianDiagnosticStatus.PASSED,
                severity=(DiagnosticSeverity.WARNING if dominated else DiagnosticSeverity.INFO),
                message=(
                    "A documented model-specific prior/data information heuristic was evaluated; "
                    "it is not a universal measure of prior strength."
                ),
                context={
                    "heuristic": heuristic,
                    information_key: information,
                    "observed_n": observed_n,
                    "prior_dominated": dominated,
                },
            )
        )
        if dominated:
            warnings.append(
                AnalysisWarning(
                    code=f"prior.{arm}_dominance",
                    message=(
                        "The declared prior exceeds observed arm information under the documented "
                        "model-specific heuristic; inspect prior sensitivity before interpretation."
                    ),
                    scope="bayesian_prior",
                )
            )
    return (tuple(diagnostics), tuple(warnings))


__all__ = ["BayesianAnalysisService"]
