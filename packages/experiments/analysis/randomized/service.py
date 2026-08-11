"""Eligibility-gated orchestration for unadjusted randomized analysis."""

from __future__ import annotations

from collections.abc import Mapping

from ..base import AnalysisStatus, ContractModel, NonEmptyStr
from ..estimands import EstimandKind
from ..metrics import MetricType
from ..provenance import (
    AnalysisWarning,
    DiagnosticOutcome,
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceSourceType,
)
from ..requests import AnalysisRequest
from ..study_designs import RandomizedAnalysisMethod
from ..uncertainty import RequestedConfidenceLevel
from ..validation import (
    AnalysisDataBinding,
    AnalysisEligibilityService,
    AnalysisTable,
    MethodCapabilityRegistry,
    ValidationPolicy,
)
from ..validation.context import ValidationContext
from ..validation.data_rules import validate_data
from ..validation.models import EligibilityDiagnostic, EligibilityValidationResult
from .assumptions import randomized_assumptions
from .binary import analyze_binary_two_proportion_z
from .config import RandomizedAnalysisConfig
from .continuous import analyze_continuous_welch
from .models import (
    AlternativeHypothesis,
    ComputationStatus,
    Conclusion,
    EvidenceCategory,
    PracticalSignificance,
    RandomizedAbstentionReason,
    RandomizedAnalysisResult,
    RandomizedDiagnostic,
    RandomizedDiagnosticCategory,
    RandomizedDiagnosticStatus,
    RandomizedHypothesis,
)


class RandomizedAnalysisExecutionRequest(ContractModel):
    """Explicit request envelope for the v1 randomized analyzer."""

    request_id: NonEmptyStr
    analysis_request: AnalysisRequest
    alternative: AlternativeHypothesis


class RandomizedAnalysisService:
    """Validate, extract, and dispatch one supported randomized analysis."""

    def __init__(self, *, validation_policy: ValidationPolicy | None = None) -> None:
        self._policy = validation_policy or ValidationPolicy()
        self._eligibility = AnalysisEligibilityService(
            policy=self._policy,
            capability_registry=MethodCapabilityRegistry.with_implemented_methods(
                (RandomizedAnalysisMethod.FIXED_HORIZON_AB,)
            ),
            configuration_provenance="randomized-analysis-service-v1",
        )

    def analyze(
        self,
        execution: RandomizedAnalysisExecutionRequest,
        table: AnalysisTable,
        binding: AnalysisDataBinding,
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> RandomizedAnalysisResult:
        """Return an estimate only after the existing eligibility service approves it."""
        request = execution.analysis_request
        config = _configuration(request)
        result_provenance = _analysis_provenance(execution, provenance)
        eligibility = self._eligibility.validate(request, table, binding)

        if not isinstance(request.uncertainty, RequestedConfidenceLevel):
            return _unsupported_result(
                execution,
                config,
                result_provenance,
                eligibility=eligibility,
                code="unsupported_uncertainty",
                message="V1 supports frequentist confidence intervals only.",
            )

        if execution.alternative is not AlternativeHypothesis.TWO_SIDED:
            return _unsupported_result(
                execution,
                config,
                result_provenance,
                eligibility=eligibility,
                code="unsupported_alternative_hypothesis",
                message="Only a declared two-sided alternative hypothesis is supported.",
            )

        if eligibility.status not in {
            AnalysisStatus.ELIGIBLE,
            AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
        }:
            return _eligibility_abstention(
                execution, eligibility, config, result_provenance
            )

        unsupported = _unsupported_request_reason(request, binding)
        if unsupported is not None:
            code, message = unsupported
            return _unsupported_result(
                execution,
                config,
                result_provenance,
                eligibility=eligibility,
                code=code,
                message=message,
            )

        data = validate_data(
            ValidationContext(request=request, table=table, binding=binding, policy=self._policy)
        )
        if data.valid_row_indexes != data.population_row_indexes:
            return _analysis_abstention(
                execution,
                eligibility,
                config,
                result_provenance,
                code="incomplete_outcome_data",
                message=(
                    "V1 does not drop population rows with missing or invalid outcome values."
                ),
            )

        treatment_values, control_values = _extract_arm_values(
            request,
            table,
            binding,
            row_indexes=data.valid_row_indexes,
        )
        common: dict[str, object] = {
            "request_id": execution.request_id,
            "metric": request.outcome.metric,
            "estimand": request.estimand,
            "treatment_arm_id": request.treatment.treatment_id,
            "treatment_values": treatment_values,
            "control_arm_id": request.control.control_id,
            "control_values": control_values,
            "provenance": result_provenance,
            "configuration": config,
            "alternative": execution.alternative,
        }
        if request.outcome.metric.metric_type is MetricType.CONTINUOUS:
            result = analyze_continuous_welch(**common)  # type: ignore[arg-type]
        else:
            result = analyze_binary_two_proportion_z(**common)  # type: ignore[arg-type]
        return _attach_request(result, request, eligibility)


def _configuration(request: AnalysisRequest) -> RandomizedAnalysisConfig:
    uncertainty = request.uncertainty
    if not isinstance(uncertainty, RequestedConfidenceLevel):
        return RandomizedAnalysisConfig()
    return RandomizedAnalysisConfig(
        alpha=1.0 - uncertainty.level,
        confidence_level=uncertainty.level,
    )


def _analysis_provenance(
    execution: RandomizedAnalysisExecutionRequest,
    provenance: tuple[ProvenanceRecord, ...],
) -> tuple[ProvenanceRecord, ...]:
    request_record = ProvenanceRecord(
        source_type=ProvenanceSourceType.ANALYSIS_REQUEST,
        source_id=execution.request_id,
        source_version=f"alternative={execution.alternative.value}",
    )
    return provenance + (request_record,)


def _unsupported_request_reason(
    request: AnalysisRequest,
    binding: AnalysisDataBinding,
) -> tuple[str, str] | None:
    metric_type = request.outcome.metric.metric_type
    supported_estimands = {
        MetricType.CONTINUOUS: {
            EstimandKind.AVERAGE_TREATMENT_EFFECT,
            EstimandKind.DIFFERENCE_IN_MEANS,
            EstimandKind.INTENTION_TO_TREAT,
        },
        MetricType.BINARY: {
            EstimandKind.AVERAGE_TREATMENT_EFFECT,
            EstimandKind.DIFFERENCE_IN_PROPORTIONS,
            EstimandKind.INTENTION_TO_TREAT,
        },
    }
    if metric_type not in supported_estimands:
        return ("unsupported_outcome_type", "V1 supports continuous and binary outcomes only.")
    if request.estimand.kind not in supported_estimands[metric_type]:
        return ("incompatible_estimand", "The declared estimand is incompatible with the outcome.")
    if binding.outcome.value_column is None:
        return ("unsupported_outcome_binding", "V1 requires one explicit outcome value column.")
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
        raise RuntimeError("validated v1 outcome binding has no value column")
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
    return tuple(treatment_values), tuple(control_values)


def _attach_request(
    result: RandomizedAnalysisResult,
    request: AnalysisRequest,
    eligibility: EligibilityValidationResult,
) -> RandomizedAnalysisResult:
    payload = result.model_dump(mode="python")
    payload["analysis_request"] = request
    payload["diagnostics"] = result.diagnostics + tuple(
        _translate_diagnostic(item) for item in eligibility.diagnostics
    )
    payload["warnings"] = result.warnings + _translate_warnings(eligibility)
    return RandomizedAnalysisResult.model_validate(payload)


def _eligibility_abstention(
    execution: RandomizedAnalysisExecutionRequest,
    eligibility: EligibilityValidationResult,
    config: RandomizedAnalysisConfig,
    provenance: tuple[ProvenanceRecord, ...],
) -> RandomizedAnalysisResult:
    primary = eligibility.abstention_reason
    if primary is None:
        raise RuntimeError("non-eligible validation result omitted its abstention reason")
    code = f"eligibility.{primary.code}"
    return RandomizedAnalysisResult(
        request_id=execution.request_id,
        analysis_request=execution.analysis_request,
        metric=execution.analysis_request.outcome.metric,
        estimand=execution.analysis_request.estimand,
        hypothesis=RandomizedHypothesis(alternative=execution.alternative),
        status=ComputationStatus.ABSTAINED,
        conclusion=Conclusion.INCONCLUSIVE,
        practical_significance=PracticalSignificance.NOT_ASSESSED,
        evidence_category=EvidenceCategory.NO_RANDOMIZED_EVIDENCE,
        assumptions=randomized_assumptions(),
        diagnostics=tuple(_translate_diagnostic(item) for item in eligibility.diagnostics),
        warnings=(),
        provenance=provenance,
        configuration=config,
        abstention_reason=RandomizedAbstentionReason(
            code=code,
            message=primary.message,
            missing_or_invalid_information=tuple(
                f"eligibility.{item}" for item in primary.missing_or_invalid_information
            ),
        ),
    )


def _translate_diagnostic(diagnostic: EligibilityDiagnostic) -> RandomizedDiagnostic:
    status = {
        DiagnosticOutcome.PASSED: RandomizedDiagnosticStatus.PASSED,
        DiagnosticOutcome.FAILED: RandomizedDiagnosticStatus.FAILED,
        DiagnosticOutcome.UNAVAILABLE: RandomizedDiagnosticStatus.UNAVAILABLE,
    }[diagnostic.outcome]
    context: Mapping[str, object] = {entry.key: entry.value for entry in diagnostic.context}
    return RandomizedDiagnostic.model_validate(
        {
            "code": f"eligibility.{diagnostic.code}",
            "category": RandomizedDiagnosticCategory.INPUT,
            "severity": diagnostic.severity,
            "status": status,
            "message": diagnostic.message,
            "context": context,
            "recommended_action": diagnostic.recommended_action,
        }
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


def _analysis_abstention(
    execution: RandomizedAnalysisExecutionRequest,
    eligibility: EligibilityValidationResult,
    config: RandomizedAnalysisConfig,
    provenance: tuple[ProvenanceRecord, ...],
    *,
    code: str,
    message: str,
) -> RandomizedAnalysisResult:
    return RandomizedAnalysisResult(
        request_id=execution.request_id,
        analysis_request=execution.analysis_request,
        metric=execution.analysis_request.outcome.metric,
        estimand=execution.analysis_request.estimand,
        hypothesis=RandomizedHypothesis(alternative=execution.alternative),
        status=ComputationStatus.ABSTAINED,
        conclusion=Conclusion.INCONCLUSIVE,
        practical_significance=PracticalSignificance.NOT_ASSESSED,
        evidence_category=EvidenceCategory.RANDOMIZED_DESIGN_WITH_LIMITED_ASSUMPTIONS,
        assumptions=randomized_assumptions(),
        diagnostics=(
            RandomizedDiagnostic(
                code=code,
                category=RandomizedDiagnosticCategory.INPUT,
                severity=DiagnosticSeverity.ERROR,
                status=RandomizedDiagnosticStatus.FAILED,
                message=message,
            ),
        )
        + tuple(_translate_diagnostic(item) for item in eligibility.diagnostics),
        warnings=_translate_warnings(eligibility),
        provenance=provenance,
        configuration=config,
        abstention_reason=RandomizedAbstentionReason(
            code=code,
            message=message,
            missing_or_invalid_information=(code,),
        ),
    )


def _unsupported_result(
    execution: RandomizedAnalysisExecutionRequest,
    config: RandomizedAnalysisConfig,
    provenance: tuple[ProvenanceRecord, ...],
    *,
    eligibility: EligibilityValidationResult,
    code: str,
    message: str,
) -> RandomizedAnalysisResult:
    return RandomizedAnalysisResult(
        request_id=execution.request_id,
        analysis_request=execution.analysis_request,
        metric=execution.analysis_request.outcome.metric,
        estimand=execution.analysis_request.estimand,
        hypothesis=RandomizedHypothesis(alternative=execution.alternative),
        status=ComputationStatus.UNSUPPORTED,
        conclusion=Conclusion.UNSUPPORTED,
        practical_significance=PracticalSignificance.NOT_ASSESSED,
        evidence_category=EvidenceCategory.NO_RANDOMIZED_EVIDENCE,
        assumptions=randomized_assumptions(),
        diagnostics=(
            RandomizedDiagnostic(
                code=code,
                category=RandomizedDiagnosticCategory.CONFIGURATION,
                severity=DiagnosticSeverity.ERROR,
                status=RandomizedDiagnosticStatus.FAILED,
                message=message,
            ),
        )
        + tuple(_translate_diagnostic(item) for item in eligibility.diagnostics),
        warnings=_translate_warnings(eligibility),
        provenance=provenance,
        configuration=config,
        abstention_reason=RandomizedAbstentionReason(
            code=code,
            message=message,
            missing_or_invalid_information=(code,),
        ),
    )


__all__ = ["RandomizedAnalysisExecutionRequest", "RandomizedAnalysisService"]
