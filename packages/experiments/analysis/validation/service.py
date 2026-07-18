"""Fixed-order orchestration for pre-estimator analysis eligibility validation."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from ..base import AnalysisStatus
from ..provenance import DiagnosticOutcome, DiagnosticSeverity
from ..requests import AnalysisRequest
from ..results import AbstentionReason, EligibilityStatus
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
_CAPABILITY_DIAGNOSTIC_CODES = frozenset(
    {"method.contract_unsupported", "method.implementation_unavailable"}
)


def aggregate_status(
    diagnostics: tuple[EligibilityDiagnostic, ...],
) -> EligibilityStatus:
    """Apply the explicit blocking, needs-data, warning, eligible precedence."""
    dispositions = {item.disposition for item in diagnostics}
    if DiagnosticDisposition.BLOCKING in dispositions:
        return AnalysisStatus.INELIGIBLE
    if DiagnosticDisposition.NEEDS_MORE_DATA in dispositions:
        return AnalysisStatus.NEEDS_MORE_DATA
    if DiagnosticDisposition.WARNING in dispositions:
        return AnalysisStatus.ELIGIBLE_WITH_WARNINGS
    return AnalysisStatus.ELIGIBLE


class AnalysisEligibilityService:
    """Compose request, data, and design validation without invoking an estimator."""

    def __init__(
        self,
        *,
        policy: ValidationPolicy | None = None,
        capability_registry: MethodCapabilityRegistry | None = None,
        configuration_provenance: str = "explicit defaults",
    ) -> None:
        self._policy = policy if policy is not None else ValidationPolicy()
        self._capability_registry = (
            capability_registry
            if capability_registry is not None
            else MethodCapabilityRegistry.default()
        )
        self._configuration_provenance = configuration_provenance

    def validate(
        self,
        request: AnalysisRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
    ) -> EligibilityValidationResult:
        """Validate one immutable request/table/binding bundle in a fixed order."""
        context = ValidationContext(
            request=request,
            table=table,
            binding=binding,
            policy=self._policy,
        )
        request_diagnostics = _validate_request_and_capability(
            context,
            self._capability_registry,
        )
        data_result = validate_data(context)
        dependency_diagnostics: tuple[EligibilityDiagnostic, ...]
        if _schema_is_unreadable(data_result):
            dependency_diagnostics = (_dependent_rules_unavailable(),)
            design_result = _empty_design_result(context)
        else:
            dependency_diagnostics = ()
            design_result = validate_design(context, data_result)

        diagnostics = (
            request_diagnostics
            + data_result.diagnostics
            + dependency_diagnostics
            + design_result.diagnostics
        )
        data_eligible = not any(
            diagnostic.code not in _CAPABILITY_DIAGNOSTIC_CODES
            and diagnostic.disposition
            in {DiagnosticDisposition.BLOCKING, DiagnosticDisposition.NEEDS_MORE_DATA}
            for diagnostic in diagnostics
        )
        method_support = self._capability_registry.assess(
            request,
            data_eligible=data_eligible,
        )
        status = aggregate_status(diagnostics)
        return EligibilityValidationResult(
            status=status,
            requested_method=context.method,
            experiment_design=context.design_type,
            diagnostics=diagnostics,
            blocking_diagnostics=tuple(
                item for item in diagnostics if item.disposition is DiagnosticDisposition.BLOCKING
            ),
            warnings=tuple(
                item for item in diagnostics if item.disposition is DiagnosticDisposition.WARNING
            ),
            dataset_summary=data_result.dataset_summary,
            treatment_summary=data_result.treatment_summary,
            outcome_summary=data_result.outcome_summary,
            missingness_summary=data_result.missingness_summary,
            unit_integrity_summary=design_result.unit_integrity_summary,
            time_summary=design_result.time_summary,
            segment_summary=design_result.segment_summary,
            method_support=method_support,
            abstention_reason=_abstention_reason(status, diagnostics),
            policy_version=self._policy.policy_version,
            configuration_provenance=self._configuration_provenance,
        )

    def validate_payload(
        self,
        payload: Mapping[str, object],
        table: AnalysisTable,
        binding: AnalysisDataBinding,
    ) -> EligibilityValidationResult:
        """Validate a request payload, translating only Pydantic contract errors."""
        try:
            request = AnalysisRequest.model_validate(payload)
        except ValidationError as error:
            return self._invalid_payload_result(error, payload, table)
        return self.validate(request, table, binding)

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
            abstention_reason=AbstentionReason(
                code=diagnostic.code,
                message=diagnostic.message,
                missing_or_invalid_information=(diagnostic.code,),
            ),
            policy_version=self._policy.policy_version,
            configuration_provenance=self._configuration_provenance,
        )


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


def _abstention_reason(
    status: EligibilityStatus,
    diagnostics: tuple[EligibilityDiagnostic, ...],
) -> AbstentionReason | None:
    if status is AnalysisStatus.INELIGIBLE:
        primary_disposition = DiagnosticDisposition.BLOCKING
    elif status is AnalysisStatus.NEEDS_MORE_DATA:
        primary_disposition = DiagnosticDisposition.NEEDS_MORE_DATA
    else:
        return None

    primary = next(item for item in diagnostics if item.disposition is primary_disposition)
    required_codes = tuple(
        dict.fromkeys(
            item.code
            for item in diagnostics
            if item.disposition
            in {DiagnosticDisposition.BLOCKING, DiagnosticDisposition.NEEDS_MORE_DATA}
        )
    )
    return AbstentionReason(
        code=primary.code,
        message=primary.message,
        missing_or_invalid_information=required_codes,
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
