"""Fixed-order orchestration for pre-estimator analysis eligibility validation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter

from pydantic import ValidationError

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ..base import AnalysisStatus
from ..provenance import DiagnosticOutcome, DiagnosticSeverity
from ..requests import AnalysisRequest
from .bindings import AnalysisDataBinding
from .capabilities import MethodCapability, MethodCapabilityRegistry
from .context import ValidationContext
from .data_rules import DataRuleResult, validate_data
from .design_rules import DesignRuleResult, validate_design
from .models import (
    DatasetSummary,
    DiagnosticDisposition,
    EligibilityDiagnostic,
    EligibilityValidationResult,
    MethodContractStatus,
    MethodImplementationStatus,
    MethodSupportAssessment,
    OutcomeSummary,
    SegmentEligibilitySummary,
    TreatmentSummary,
    UnitIntegritySummary,
    ValidationCategory,
    data_is_eligible,
    derive_abstention_reason,
)
from .models import (
    aggregate_status as aggregate_status,
)
from .policy import ValidationPolicy
from .request_rules import validate_request_consistency
from .table import AnalysisTable

_UNREADABLE_SCHEMA_CODES = frozenset(
    {
        "schema.duplicate_column",
        "schema.empty_dataset",
        "schema.required_column_missing",
    }
)


class AnalysisEligibilityService:
    """Compose request, data, and design validation without invoking an estimator."""

    def __init__(
        self,
        *,
        policy: ValidationPolicy | None = None,
        capability_registry: MethodCapabilityRegistry | None = None,
        configuration_provenance: str = "explicit defaults",
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self._policy = policy if policy is not None else ValidationPolicy()
        self._capability_registry = (
            capability_registry
            if capability_registry is not None
            else MethodCapabilityRegistry.default()
        )
        self._configuration_provenance = configuration_provenance
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def validate(
        self,
        request: AnalysisRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
    ) -> EligibilityValidationResult:
        """Validate one immutable request/table/binding bundle in a fixed order."""
        started_at = perf_counter()
        span = _start_validation_span(
            self.observability_provider,
            table,
            method=request.study_design.method.value,
            design=request.study_design.design_type,
        )
        return self._validate_started(request, table, binding, started_at, span)

    def _validate_started(
        self,
        request: AnalysisRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        started_at: float,
        span: BufferedSpan | None,
    ) -> EligibilityValidationResult:
        failure_stage = "context"
        try:
            context = ValidationContext(
                request=request,
                table=table,
                binding=binding,
                policy=self._policy,
            )
            failure_stage = "request_and_capability"
            request_diagnostics = _validate_request_and_capability(
                context,
                self._capability_registry,
            )
            failure_stage = "data"
            data_result = validate_data(context)
            dependency_diagnostics: tuple[EligibilityDiagnostic, ...]
            failure_stage = "design"
            if _schema_is_unreadable(data_result):
                dependency_diagnostics = (_dependent_rules_unavailable(),)
                design_result = _empty_design_result(context)
            else:
                dependency_diagnostics = ()
                design_result = validate_design(context, data_result)

            failure_stage = "aggregation"
            diagnostics = (
                request_diagnostics
                + data_result.diagnostics
                + dependency_diagnostics
                + design_result.diagnostics
            )
            data_eligible = data_is_eligible(diagnostics)
            method_support = self._capability_registry.assess(
                request,
                data_eligible=data_eligible,
            )
            status = aggregate_status(diagnostics)
            result = EligibilityValidationResult(
                status=status,
                requested_method=context.method,
                experiment_design=context.design_type,
                diagnostics=diagnostics,
                blocking_diagnostics=tuple(
                    item
                    for item in diagnostics
                    if item.disposition is DiagnosticDisposition.BLOCKING
                ),
                warnings=tuple(
                    item
                    for item in diagnostics
                    if item.disposition is DiagnosticDisposition.WARNING
                ),
                dataset_summary=data_result.dataset_summary,
                treatment_summary=data_result.treatment_summary,
                outcome_summary=data_result.outcome_summary,
                missingness_summary=data_result.missingness_summary,
                unit_integrity_summary=design_result.unit_integrity_summary,
                time_summary=design_result.time_summary,
                segment_summary=design_result.segment_summary,
                method_support=method_support,
                abstention_reason=derive_abstention_reason(status, diagnostics),
                policy_version=self._policy.policy_version,
                configuration_provenance=self._configuration_provenance,
            )
        except Exception as error:
            _finish_validation_failure(
                self.observability_provider,
                span,
                error=error,
                failure_stage=failure_stage,
                duration_ms=(perf_counter() - started_at) * 1000.0,
            )
            raise

        _finish_validation_success(
            self.observability_provider,
            span,
            result=result,
            duration_ms=(perf_counter() - started_at) * 1000.0,
        )
        return result

    def validate_payload(
        self,
        payload: Mapping[str, object],
        table: AnalysisTable,
        binding: AnalysisDataBinding,
    ) -> EligibilityValidationResult:
        """Validate a request payload, translating only Pydantic contract errors."""
        started_at = perf_counter()
        method, design = _payload_observability_identity(payload, self._capability_registry)
        span = _start_validation_span(
            self.observability_provider,
            table,
            method=method,
            design=design,
        )
        try:
            request = AnalysisRequest.model_validate(payload)
        except ValidationError as error:
            try:
                result = self._invalid_payload_result(error, payload, table)
            except Exception as unexpected:
                _finish_validation_failure(
                    self.observability_provider,
                    span,
                    error=unexpected,
                    failure_stage="payload_translation",
                    duration_ms=(perf_counter() - started_at) * 1000.0,
                )
                raise
            _finish_validation_success(
                self.observability_provider,
                span,
                result=result,
                duration_ms=(perf_counter() - started_at) * 1000.0,
            )
            return result
        except Exception as unexpected:
            _finish_validation_failure(
                self.observability_provider,
                span,
                error=unexpected,
                failure_stage="payload_parsing",
                duration_ms=(perf_counter() - started_at) * 1000.0,
            )
            raise
        return self._validate_started(request, table, binding, started_at, span)

    def _invalid_payload_result(
        self,
        error: ValidationError,
        payload: Mapping[str, object],
        table: AnalysisTable,
    ) -> EligibilityValidationResult:
        diagnostic = _contract_invalid_diagnostic(error)
        capability = _capability_from_payload(payload, self._capability_registry)
        method_support = MethodSupportAssessment(
            requested_method=capability.method if capability is not None else None,
            contract_status=(
                capability.contract_status
                if capability is not None
                else MethodContractStatus.UNSUPPORTED
            ),
            implementation_status=(
                capability.implementation_status
                if capability is not None
                else MethodImplementationStatus.UNAVAILABLE
            ),
            data_eligible=False,
            executable=False,
        )
        return EligibilityValidationResult(
            status=AnalysisStatus.INELIGIBLE,
            requested_method=capability.method if capability is not None else None,
            experiment_design=capability.design_type if capability is not None else None,
            diagnostics=(diagnostic,),
            blocking_diagnostics=(diagnostic,),
            warnings=(),
            dataset_summary=DatasetSummary(
                input_row_count=len(table.rows),
                population_row_count=0,
                column_count=len(table.columns),
            ),
            treatment_summary=_empty_treatment_summary(),
            outcome_summary=_empty_outcome_summary(),
            missingness_summary=(),
            unit_integrity_summary=_empty_unit_summary(),
            time_summary=None,
            segment_summary=None,
            method_support=method_support,
            abstention_reason=derive_abstention_reason(AnalysisStatus.INELIGIBLE, (diagnostic,)),
            policy_version=self._policy.policy_version,
            configuration_provenance=self._configuration_provenance,
        )


def _start_validation_span(
    provider: BaseObservabilityProvider,
    table: AnalysisTable,
    *,
    method: str,
    design: str,
) -> BufferedSpan | None:
    inputs: dict[str, object] = {
        "row_count": len(table.rows),
        "column_count": len(table.columns),
    }
    metadata = {
        "method": method,
        "design": design,
        "validation_started": True,
    }
    before_failures = _provider_failure_count(provider)
    try:
        parent = provider.current_span()
        if parent is not None and parent.provider is provider:
            return provider.start_span(
                "analysis_validation",
                inputs=inputs,
                metadata=metadata,
                parent=parent,
            )
        return provider.start_root_span(
            "analysis_validation",
            inputs=inputs,
            metadata=metadata,
        )
    except Exception:
        _increment_provider_failure(provider, before_failures)
        return None


def _finish_validation_success(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: EligibilityValidationResult,
    duration_ms: float,
) -> None:
    if span is None:
        return
    _run_observability_operation(
        provider,
        lambda: span.add_metadata(
            {
                "status": result.status.value,
                "blocking_diagnostic_count": len(result.blocking_diagnostics),
                "warning_diagnostic_count": len(result.warnings),
                "duration_ms": duration_ms,
                "needs_more_data": result.status is AnalysisStatus.NEEDS_MORE_DATA,
                "method_unavailable": (
                    result.method_support.implementation_status
                    is MethodImplementationStatus.UNAVAILABLE
                ),
                "validator_failure": False,
                "validation_completed": True,
            }
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.finish(
            outputs={
                "status": result.status.value,
                "validation_completed": True,
            }
        ),
    )


def _finish_validation_failure(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    error: Exception,
    failure_stage: str,
    duration_ms: float,
) -> None:
    if span is None:
        return
    _run_observability_operation(
        provider,
        lambda: span.add_metadata(
            {
                "duration_ms": duration_ms,
                "validator_failure": True,
                "validator_failure_stage": failure_stage,
                "validation_completed": False,
            }
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.record_error(
            "Analysis validation failed.",
            details={
                "type": error.__class__.__name__,
                "stage": failure_stage,
            },
        ),
    )
    _run_observability_operation(
        provider,
        lambda: span.finish(outputs={"validation_completed": False}),
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


def _validate_request_and_capability(
    context: ValidationContext,
    registry: MethodCapabilityRegistry,
) -> tuple[EligibilityDiagnostic, ...]:
    diagnostics = list(validate_request_consistency(context))
    capability = registry.for_request(context.request)
    if capability.contract_status is MethodContractStatus.UNSUPPORTED:
        diagnostics.append(
            _blocking_unavailable(
                code="method.contract_unsupported",
                message="The requested analysis method is not supported by the contracts.",
                context={"method": capability.method},
            )
        )
    elif capability.implementation_status is MethodImplementationStatus.UNAVAILABLE:
        diagnostics.append(
            _blocking_unavailable(
                code="method.implementation_unavailable",
                message="No estimator implementation is available for the requested method.",
                context={"method": capability.method},
            )
        )
    return tuple(diagnostics)


def _schema_is_unreadable(result: DataRuleResult) -> bool:
    return any(item.code in _UNREADABLE_SCHEMA_CODES for item in result.diagnostics)


def _dependent_rules_unavailable() -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": "schema.dependent_rules_unavailable",
            "category": ValidationCategory.SCHEMA,
            "severity": DiagnosticSeverity.INFO,
            "outcome": DiagnosticOutcome.UNAVAILABLE,
            "disposition": DiagnosticDisposition.INFORMATIONAL,
            "message": "Data-dependent design rules are unavailable until schema errors are fixed.",
            "context": {"rule_family": "design"},
        }
    )


def _empty_design_result(context: ValidationContext) -> DesignRuleResult:
    segment = context.request.segment
    segment_summary = (
        SegmentEligibilitySummary(
            segment_id=segment.segment_id,
            selected_count=0,
            treatment_count=0,
            control_count=0,
            treatment_valid_outcome_count=0,
            control_valid_outcome_count=0,
        )
        if segment is not None
        else None
    )
    return DesignRuleResult(
        diagnostics=(),
        unit_integrity_summary=_empty_unit_summary(),
        time_summary=None,
        segment_summary=segment_summary,
    )


def _contract_invalid_diagnostic(error: ValidationError) -> EligibilityDiagnostic:
    errors = error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    )
    details = tuple(
        sorted(
            (
                ".".join(str(part) for part in item.get("loc", ())) or "$",
                str(item.get("type", "unknown")),
            )
            for item in errors
        )
    )
    return EligibilityDiagnostic.model_validate(
        {
            "code": "request.contract_invalid",
            "category": ValidationCategory.REQUEST,
            "severity": DiagnosticSeverity.ERROR,
            "outcome": DiagnosticOutcome.FAILED,
            "disposition": DiagnosticDisposition.BLOCKING,
            "message": "The analysis request payload does not satisfy its contract.",
            "context": {
                "error_count": len(details),
                "error_locations": "|".join(location for location, _ in details),
                "error_types": "|".join(error_type for _, error_type in details),
            },
        }
    )


def _capability_from_payload(
    payload: Mapping[str, object],
    registry: MethodCapabilityRegistry,
) -> MethodCapability | None:
    design = payload.get("study_design")
    if not isinstance(design, Mapping):
        return None
    design_type = design.get("design_type")
    method = design.get("method")
    if not isinstance(design_type, str) or not isinstance(method, str):
        return None
    return next(
        (
            capability
            for capability in registry.entries
            if capability.design_type == design_type and capability.method == method
        ),
        None,
    )


def _payload_observability_identity(
    payload: Mapping[str, object],
    registry: MethodCapabilityRegistry,
) -> tuple[str, str]:
    """Return only registry-owned low-cardinality identity for an untrusted payload."""
    capability = _capability_from_payload(payload, registry)
    if capability is None:
        return ("unknown", "unknown")
    return (capability.method, capability.design_type)


def _blocking_unavailable(
    *,
    code: str,
    message: str,
    context: dict[str, str],
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": code,
            "category": ValidationCategory.METHOD,
            "severity": DiagnosticSeverity.ERROR,
            "outcome": DiagnosticOutcome.UNAVAILABLE,
            "disposition": DiagnosticDisposition.BLOCKING,
            "message": message,
            "context": context,
        }
    )


def _empty_treatment_summary() -> TreatmentSummary:
    return TreatmentSummary(
        treatment_count=0,
        control_count=0,
        missing_count=0,
        unknown_count=0,
    )


def _empty_outcome_summary() -> OutcomeSummary:
    return OutcomeSummary(
        valid_count=0,
        missing_count=0,
        invalid_type_count=0,
        non_finite_count=0,
        invalid_value_count=0,
        treatment_valid_count=0,
        control_valid_count=0,
        has_variation=None,
    )


def _empty_unit_summary() -> UnitIntegritySummary:
    return UnitIntegritySummary(
        observation_unit_count=0,
        missing_identifier_count=0,
        duplicate_identifier_count=0,
        repeated_observation_count=0,
        assignment_conflict_count=0,
        cluster_count=None,
    )
