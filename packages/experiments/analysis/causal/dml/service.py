"""Deterministic orchestration for bounded partialling-out DML."""

from __future__ import annotations

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
from ..advanced.conformance import (
    configuration_fingerprint,
    execution_metadata,
    supplied_nuisance_fingerprints,
)
from ..diagnostics import EvidenceLimitation, EvidenceLimitationCode
from ..models import ObservationalAnalysisRequest
from ..propensity import OverlapStatus
from .adapter import SklearnLogisticTreatmentAdapter, SklearnRidgeOutcomeAdapter
from .crossfit import CrossFitError, CrossFittedNuisanceResult, cross_fit_nuisances
from .folds import FoldObservation, build_fold_plan
from .models import (
    DMLDiagnostic,
    DMLDiagnosticCategory,
    DMLDiagnosticStatus,
    DMLExecutionRequest,
    DMLFoldPlan,
)
from .numerics import (
    DMLComputation,
    DMLNumericalError,
    assess_dml_overlap,
    build_nuisance_diagnostics,
    estimate_partialling_out,
)
from .protocols import NuisanceRole, OutcomeNuisanceModel, TreatmentNuisanceModel
from .results import (
    DMLAbstentionReason,
    DMLCausalStatus,
    DMLFoldFitProvenance,
    DMLResult,
    DMLSensitivityCode,
    DMLSensitivityFlag,
    DMLStatus,
)
from .validation import (
    DMLValidationDisposition,
    DMLValidationResult,
    validate_dml_input,
)


class DoubleMachineLearningEstimator:
    """Cross-fit both nuisances and solve one ATE-style orthogonal score."""

    def __init__(
        self,
        *,
        outcome_adapter: OutcomeNuisanceModel | None = None,
        treatment_adapter: TreatmentNuisanceModel | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self._outcome_adapter = outcome_adapter
        self._treatment_adapter = treatment_adapter
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: DMLExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> DMLResult:
        """Return a complete owned result or a structured refusal."""
        started = perf_counter()
        span = _start_span(
            self.observability_provider,
            row_count=len(table.rows),
            fold_count=execution.configuration.fold_count,
        )
        try:
            result = self._analyze(execution, table, provenance=provenance)
            try:
                fingerprint = configuration_fingerprint(
                    execution,
                    "repository_dml",
                    nuisance_fingerprints=supplied_nuisance_fingerprints(
                        self._outcome_adapter, self._treatment_adapter
                    ),
                )
            except (ValueError, TypeError, AttributeError):
                # Preserve an existing normalized refusal for a malformed request.
                # Missing provenance remains a blocking conformance finding.
                fingerprint = None
            result = result.model_copy(update={"configuration_fingerprint_sha256": fingerprint})
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
        execution: DMLExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> DMLResult:
        validated = validate_dml_input(execution, table)
        result_provenance = _analysis_provenance(execution, provenance)
        if validated.disposition is not DMLValidationDisposition.VALID:
            return _noncompleted(execution, validated, result_provenance)

        try:
            plan = build_fold_plan(
                tuple(
                    FoldObservation(observation_id=row.observation_id, treated=row.treated)
                    for row in validated.rows
                ),
                execution.configuration,
            )
        except ValueError:
            return _failure_result(
                execution,
                validated,
                result_provenance,
                code="dml.fold.invalid_plan",
                category=DMLDiagnosticCategory.FOLD,
                message="The retained analysis population cannot satisfy the fold policy.",
            )

        feature_names = tuple(item.variable_id for item in execution.binding.covariates)
        outcome_adapter = self._outcome_adapter or SklearnRidgeOutcomeAdapter(
            feature_order=feature_names,
            seed=execution.configuration.random_seed,
        )
        treatment_adapter = self._treatment_adapter or SklearnLogisticTreatmentAdapter(
            feature_order=feature_names,
            seed=execution.configuration.random_seed,
        )
        try:
            crossfit = cross_fit_nuisances(
                validated.rows,
                plan,
                feature_names=feature_names,
                outcome_adapter=outcome_adapter,
                treatment_adapter=treatment_adapter,
            )
        except Exception as error:
            normalized = error if isinstance(error, CrossFitError) else None
            return _failure_result(
                execution,
                validated,
                result_provenance,
                code=normalized.code if normalized else "dml.nuisance.invalid_adapter",
                category=DMLDiagnosticCategory.NUISANCE,
                message="A required nuisance adapter failed the owned cross-fitting contract.",
                plan=plan,
                fold_index=normalized.fold_index if normalized else None,
                nuisance_role=normalized.role if normalized else None,
            )

        outcomes = tuple(row.outcome for row in validated.rows)
        treatment_bool = tuple(row.treated for row in validated.rows)
        treatment = tuple(float(value) for value in treatment_bool)
        try:
            nuisance = build_nuisance_diagnostics(
                outcome=outcomes,
                outcome_prediction=crossfit.outcome_predictions,
                treatment=treatment_bool,
                treatment_prediction=crossfit.treatment_predictions,
                config=execution.configuration,
            )
            overlap = assess_dml_overlap(
                scores=crossfit.treatment_predictions,
                treated=treatment_bool,
                config=execution.configuration,
            )
        except DMLNumericalError as error:
            return _failure_result(
                execution,
                validated,
                result_provenance,
                code=error.code,
                category=DMLDiagnosticCategory.NUISANCE,
                message=str(error),
                plan=plan,
                crossfit=crossfit,
            )
        if overlap.status is OverlapStatus.SEVERE:
            return _failure_result(
                execution,
                validated,
                result_provenance,
                code="dml.overlap.severe",
                category=DMLDiagnosticCategory.OVERLAP,
                message="Cross-fitted treatment scores fail the configured overlap safety policy.",
                plan=plan,
                crossfit=crossfit,
                nuisance=nuisance,
                overlap=overlap,
            )
        try:
            computation = estimate_partialling_out(
                outcome=outcomes,
                treatment=treatment,
                outcome_prediction=crossfit.outcome_predictions,
                treatment_prediction=crossfit.treatment_predictions,
                config=execution.configuration,
            )
        except DMLNumericalError as error:
            return _failure_result(
                execution,
                validated,
                result_provenance,
                code=error.code,
                category=(
                    DMLDiagnosticCategory.RESIDUAL
                    if "residual" in error.code
                    else DMLDiagnosticCategory.INFERENCE
                ),
                message=str(error),
                plan=plan,
                crossfit=crossfit,
                nuisance=nuisance,
                overlap=overlap,
            )
        return _completed(
            execution,
            validated,
            result_provenance,
            plan,
            crossfit,
            nuisance,
            overlap,
            computation,
        )


def _completed(
    execution: DMLExecutionRequest,
    validated: DMLValidationResult,
    provenance: ProvenanceRecords,
    plan: DMLFoldPlan,
    crossfit: CrossFittedNuisanceResult,
    nuisance: object,
    overlap: object,
    computation: DMLComputation,
) -> DMLResult:
    from .models import DMLNuisanceDiagnostics, DMLOverlapDiagnostic

    assert isinstance(nuisance, DMLNuisanceDiagnostics)
    assert isinstance(overlap, DMLOverlapDiagnostic)
    identification = execution.identification_result
    estimand = identification.estimand
    assert estimand is not None
    diagnostics = (
        _diagnostic(
            "dml.crossfit.complete",
            DMLDiagnosticCategory.FOLD,
            "Every retained observation received exactly one out-of-fold nuisance prediction.",
            severity=DiagnosticSeverity.INFO,
            status=DMLDiagnosticStatus.PASSED,
        ),
    )
    return DMLResult.model_validate(
        {
            **_common(execution, validated, provenance),
            "status": DMLStatus.COMPLETED,
            "causal_status": DMLCausalStatus.CONDITIONAL_ON_DECLARED_ASSUMPTIONS,
            "point_estimate": computation.point_estimate,
            "test_result": computation.inference,
            "fold_plan": plan,
            "fold_fits": _fold_fits(crossfit),
            "nuisance_diagnostics": nuisance,
            "outcome_residual_diagnostics": computation.outcome_residual_diagnostics,
            "treatment_residual_diagnostics": computation.treatment_residual_diagnostics,
            "influence_diagnostics": computation.influence_diagnostics,
            "overlap": overlap,
            "sensitivity_flags": _sensitivity(overlap.status),
            "diagnostics": diagnostics,
            "warnings": _warnings(diagnostics),
        }
    )


def _noncompleted(
    execution: DMLExecutionRequest,
    validated: DMLValidationResult,
    provenance: ProvenanceRecords,
) -> DMLResult:
    status = {
        DMLValidationDisposition.ABSTAINED: DMLStatus.ABSTAINED,
        DMLValidationDisposition.INVALID: DMLStatus.INVALID,
        DMLValidationDisposition.UNSUPPORTED: DMLStatus.UNSUPPORTED,
    }[validated.disposition]
    causal_status = {
        DMLStatus.ABSTAINED: DMLCausalStatus.ABSTAINED,
        DMLStatus.INVALID: DMLCausalStatus.INVALID,
        DMLStatus.UNSUPPORTED: DMLCausalStatus.UNSUPPORTED,
    }[status]
    primary = validated.diagnostics[0]
    return DMLResult.model_validate(
        {
            **_common(execution, validated, provenance),
            "status": status,
            "causal_status": causal_status,
            "sensitivity_flags": (),
            "diagnostics": validated.diagnostics,
            "warnings": _warnings(validated.diagnostics),
            "abstention_reason": DMLAbstentionReason(
                code=primary.code,
                message=primary.message,
            ),
        }
    )


def _failure_result(
    execution: DMLExecutionRequest,
    validated: DMLValidationResult,
    provenance: ProvenanceRecords,
    *,
    code: str,
    category: DMLDiagnosticCategory,
    message: str,
    plan: DMLFoldPlan | None = None,
    crossfit: CrossFittedNuisanceResult | None = None,
    nuisance: object | None = None,
    overlap: object | None = None,
    fold_index: int | None = None,
    nuisance_role: NuisanceRole | None = None,
) -> DMLResult:
    from .models import DMLNuisanceDiagnostics, DMLOverlapDiagnostic

    diagnostic = _diagnostic(code, category, message)
    return DMLResult.model_validate(
        {
            **_common(execution, validated, provenance),
            "status": DMLStatus.ABSTAINED,
            "causal_status": DMLCausalStatus.ABSTAINED,
            "fold_plan": plan,
            "fold_fits": _fold_fits(crossfit) if crossfit else (),
            "nuisance_diagnostics": (
                nuisance if isinstance(nuisance, DMLNuisanceDiagnostics) else None
            ),
            "overlap": overlap if isinstance(overlap, DMLOverlapDiagnostic) else None,
            "sensitivity_flags": (),
            "diagnostics": (diagnostic,),
            "warnings": _warnings((diagnostic,)),
            "abstention_reason": DMLAbstentionReason(
                code=code,
                message=message,
                fold_index=fold_index,
                nuisance_role=nuisance_role,
            ),
        }
    )


def _common(
    execution: DMLExecutionRequest,
    validated: DMLValidationResult,
    provenance: ProvenanceRecords,
) -> dict[str, object]:
    identification = execution.identification_result
    estimand = identification.estimand
    return {
        "request_id": execution.request_id,
        "analysis_request": ObservationalAnalysisRequest(
            request_id=execution.request_id,
            identification=identification.identification_request,
        ),
        "binding": execution.binding,
        "configuration": execution.configuration,
        "estimand": estimand,
        "treatment": identification.treatment,
        "outcome": identification.outcome,
        "covariates": tuple(item.variable_id for item in execution.binding.covariates),
        "target_population": estimand.target_population if estimand else None,
        "effect_scale": estimand.effect_scale if estimand else None,
        "adjustment_set": identification.adjustment_set,
        "sample_counts": validated.sample_counts,
        "assumptions": identification.assumptions,
        "evidence_limitations": _limitations(identification.evidence_limitations, provenance),
        "provenance": provenance,
    }


def _fold_fits(crossfit: CrossFittedNuisanceResult) -> tuple[DMLFoldFitProvenance, ...]:
    return tuple(
        DMLFoldFitProvenance(
            fold_index=record.fold_index,
            train_count=record.train_count,
            score_count=record.score_count,
            outcome_adapter=record.outcome_metadata,
            treatment_adapter=record.treatment_metadata,
            outcome_fit=record.outcome_fit,
            treatment_fit=record.treatment_fit,
        )
        for record in crossfit.fold_records
    )


def _limitations(
    upstream: tuple[EvidenceLimitation, ...],
    provenance: ProvenanceRecords,
) -> tuple[EvidenceLimitation, ...]:
    retained = tuple(
        item for item in upstream if item.code is not EvidenceLimitationCode.OVERLAP_NOT_EVALUATED
    )
    additions = (
        EvidenceLimitation(
            code=EvidenceLimitationCode.NUISANCE_MODEL_MISSPECIFICATION,
            description="Cross-fitted nuisance models may remain misspecified.",
            provenance=provenance,
        ),
        EvidenceLimitation(
            code=EvidenceLimitationCode.PARTIALLY_LINEAR_MODEL_RESTRICTION,
            description="The effect is identified only under the supported partially linear form.",
            provenance=provenance,
        ),
    )
    return tuple(sorted((*retained, *additions), key=lambda item: item.code.value))


def _sensitivity(overlap: OverlapStatus) -> tuple[DMLSensitivityFlag, ...]:
    flags = [
        DMLSensitivityFlag(
            code=DMLSensitivityCode.IDENTIFICATION_ASSUMPTIONS_UNVERIFIED,
            severity=DiagnosticSeverity.WARNING,
            message="Exchangeability and absence of unmeasured confounding remain unverified.",
        )
    ]
    if overlap is OverlapStatus.WEAK:
        flags.append(
            DMLSensitivityFlag(
                code=DMLSensitivityCode.WEAK_OVERLAP,
                severity=DiagnosticSeverity.WARNING,
                message="Cross-fitted treatment scores indicate weak overlap.",
            )
        )
    return tuple(flags)


def _diagnostic(
    code: str,
    category: DMLDiagnosticCategory,
    message: str,
    *,
    severity: DiagnosticSeverity = DiagnosticSeverity.FATAL,
    status: DMLDiagnosticStatus = DMLDiagnosticStatus.FAILED,
) -> DMLDiagnostic:
    return DMLDiagnostic(
        code=code,
        category=category,
        severity=severity,
        status=status,
        message=message,
    )


def _warnings(diagnostics: tuple[DMLDiagnostic, ...]) -> tuple[AnalysisWarning, ...]:
    return tuple(
        AnalysisWarning(code=item.code, message=item.message, scope="double_machine_learning")
        for item in diagnostics
        if item.severity is not DiagnosticSeverity.INFO
    )


def _analysis_provenance(
    execution: DMLExecutionRequest,
    provenance: ProvenanceRecords,
) -> ProvenanceRecords:
    return (
        *provenance,
        ProvenanceRecord(
            source_type=ProvenanceSourceType.CONFIGURATION,
            source_id=f"dml-config:{execution.configuration.analysis_version}",
            source_version=execution.configuration.analysis_version,
        ),
        ProvenanceRecord(
            source_type=ProvenanceSourceType.DERIVED,
            source_id="dml-partialling-out-orthogonal-score",
            source_version="1",
        ),
    )


def _start_span(
    provider: BaseObservabilityProvider,
    *,
    row_count: int,
    fold_count: int,
) -> BufferedSpan | None:
    before = _failure_count(provider)
    try:
        return provider.start_root_span(
            "double_machine_learning",
            inputs={"row_count": row_count},
            metadata={"method": "dml", "fold_count": fold_count},
            tags=("statistics", "causal", "dml"),
        )
    except Exception:
        _increment_failure(provider, before)
        return None


def _finish_result(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: DMLResult,
    duration_ms: float,
) -> None:
    if span is None:
        return
    metadata: dict[str, object] = {
        **execution_metadata(result, "repository_dml"),
        "method": "dml",
        "status": result.status.value,
        "estimand": (
            result.estimand.estimand_type.value if result.estimand is not None else "unavailable"
        ),
        "fold_count": result.configuration.fold_count,
        "cross_fitting_status": "complete" if result.fold_fits else "not_complete",
        "overlap_status": result.overlap.status.value if result.overlap else "unavailable",
        "outcome_nuisance_family": (
            result.fold_fits[0].outcome_adapter.model_family if result.fold_fits else "unavailable"
        ),
        "treatment_nuisance_family": (
            result.fold_fits[0].treatment_adapter.model_family
            if result.fold_fits
            else "unavailable"
        ),
        "diagnostic_codes": tuple(item.code for item in result.diagnostics),
        "retained_count": result.sample_counts.retained_count,
        "duration_ms": duration_ms,
    }
    _observe(provider, lambda: span.add_metadata(metadata))
    _observe(
        provider,
        lambda: span.finish(
            outputs={
                "status": result.status.value,
                "dml_completed": result.status is DMLStatus.COMPLETED,
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
            "Double Machine Learning analysis failed.",
            details={"type": error.__class__.__name__},
        ),
    )
    _observe(provider, lambda: span.finish(outputs={"status": "failed", "dml_completed": False}))


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
        if before is not None and provider.failure_count == before:
            provider.increment_failure()
    except Exception:
        return


__all__ = ["DoubleMachineLearningEstimator"]
