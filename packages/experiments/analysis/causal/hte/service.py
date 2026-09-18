"""Deterministic DML-backed heterogeneous-effect orchestration."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import TypedDict

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ...provenance import (
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceRecords,
    ProvenanceSourceType,
)
from ...uncertainty import ConfidenceInterval
from ...validation.table import AnalysisTable
from ..advanced.conformance import (
    configuration_fingerprint,
    execution_metadata,
    supplied_nuisance_fingerprints,
)
from ..assumptions import CausalAssumption
from ..dml.adapter import SklearnLogisticTreatmentAdapter, SklearnRidgeOutcomeAdapter
from ..dml.crossfit import CrossFitError, CrossFittedNuisanceResult, cross_fit_nuisances
from ..dml.folds import FoldObservation, build_fold_plan
from ..dml.models import DMLFoldPlan, DMLNuisanceDiagnostics, DMLOverlapDiagnostic
from ..dml.numerics import DMLNumericalError, assess_dml_overlap, build_nuisance_diagnostics
from ..dml.protocols import OutcomeNuisanceModel, TreatmentNuisanceModel
from ..dml.results import DMLFoldFitProvenance
from ..estimands import CausalEstimand, TreatmentContrast
from ..propensity import OverlapStatus
from .assignment import subgroup_rule
from .models import (
    CategoricalSubgroup,
    ContinuousBinSubgroup,
    EffectModifierDefinition,
    HTEExecutionRequest,
    HTEPreSpecificationStatus,
)
from .numerics import (
    HTEGroupComputation,
    HTENumericalError,
    estimate_grouped_orthogonal_effects,
    estimate_orthogonal_group,
    holm_adjust,
)
from .results import (
    GlobalHeterogeneityEvidence,
    HeterogeneousEffectResult,
    HTEDiagnostic,
    HTEDiagnosticStatus,
    HTEEvidenceStatus,
    HTEStatus,
    HTESubgroupStatus,
    InteractionEffectResult,
    MultiplicityContext,
    SubgroupEffectResult,
    SubgroupSampleCounts,
)
from .validation import (
    HTEValidationDisposition,
    HTEValidationResult,
    ValidatedSubgroupCounts,
    validate_hte_input,
)


class _CommonResultArguments(TypedDict):
    request_id: str
    execution_request: HTEExecutionRequest
    analysis_semantics: HTEPreSpecificationStatus
    estimand: CausalEstimand | None
    treatment: TreatmentContrast | None
    modifier: EffectModifierDefinition
    assumptions: tuple[CausalAssumption, ...]
    provenance: ProvenanceRecords
    assignment_fingerprint_sha256: str | None
    raw_count: int
    retained_count: int
    unassigned_count: int


class _SubgroupResultArguments(TypedDict):
    subgroup_id: str
    label: str
    rule: str
    sample_counts: SubgroupSampleCounts
    overlap: DMLOverlapDiagnostic | None


class HeterogeneousEffectEstimator:
    """Estimate registered discrete subgroup ATEs from one cross-fit."""

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
        execution: HTEExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> HeterogeneousEffectResult:
        started = perf_counter()
        span = _start_span(self.observability_provider, len(table.rows))
        try:
            result = self._analyze(execution, table, provenance=provenance)
            try:
                fingerprint = configuration_fingerprint(
                    execution,
                    "repository_hte",
                    nuisance_fingerprints=supplied_nuisance_fingerprints(
                        self._outcome_adapter, self._treatment_adapter
                    ),
                )
            except (ValueError, TypeError, AttributeError):
                # Match the adapter boundary: malformed requests cannot make
                # provenance construction replace an owned refusal with an error.
                fingerprint = None
            result = result.model_copy(update={"configuration_fingerprint_sha256": fingerprint})
        except Exception as error:
            _finish_failure(
                self.observability_provider,
                span,
                error,
                (perf_counter() - started) * 1000.0,
            )
            raise
        _finish_result(
            self.observability_provider,
            span,
            result,
            (perf_counter() - started) * 1000.0,
        )
        return result

    def _analyze(
        self,
        execution: HTEExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> HeterogeneousEffectResult:
        validated = validate_hte_input(execution, table)
        owned_provenance = _analysis_provenance(execution, provenance)
        if validated.disposition is not HTEValidationDisposition.VALID:
            primary = validated.diagnostics[0]
            status = {
                HTEValidationDisposition.ABSTAINED: HTEStatus.ABSTAINED,
                HTEValidationDisposition.INVALID: HTEStatus.INVALID,
                HTEValidationDisposition.UNSUPPORTED: HTEStatus.UNSUPPORTED,
            }[validated.disposition]
            return _empty_result(
                execution,
                validated,
                owned_provenance,
                len(table.rows),
                status,
                primary.code,
                primary.message,
            )
        try:
            plan = build_fold_plan(
                tuple(
                    FoldObservation(observation_id=row.observation_id, treated=row.treated)
                    for row in validated.rows
                ),
                execution.configuration.dml,
            )
            outcome_adapter = self._outcome_adapter or SklearnRidgeOutcomeAdapter(
                feature_order=validated.feature_names, seed=execution.configuration.dml.random_seed
            )
            treatment_adapter = self._treatment_adapter or SklearnLogisticTreatmentAdapter(
                feature_order=validated.feature_names, seed=execution.configuration.dml.random_seed
            )
            crossfit = cross_fit_nuisances(
                tuple(row.as_dml_row() for row in validated.rows),
                plan,
                feature_names=validated.feature_names,
                outcome_adapter=outcome_adapter,
                treatment_adapter=treatment_adapter,
            )
            outcomes = tuple(row.outcome for row in validated.rows)
            treated = tuple(row.treated for row in validated.rows)
            nuisance = build_nuisance_diagnostics(
                outcome=outcomes,
                outcome_prediction=crossfit.outcome_predictions,
                treatment=treated,
                treatment_prediction=crossfit.treatment_predictions,
                config=execution.configuration.dml,
            )
            global_overlap = assess_dml_overlap(
                scores=crossfit.treatment_predictions,
                treated=treated,
                config=execution.configuration.dml,
            )
        except (ValueError, CrossFitError, DMLNumericalError) as error:
            return _empty_result(
                execution,
                validated,
                owned_provenance,
                len(table.rows),
                HTEStatus.ABSTAINED,
                getattr(error, "code", "hte.crossfit.failure"),
                "The deterministic nuisance cross-fit could not be completed.",
            )
        if global_overlap.status in {OverlapStatus.SEVERE, OverlapStatus.UNAVAILABLE}:
            subgroup_refusals = {
                counts.subgroup_id: (
                    _sparse_reason(execution, counts) or "hte.overlap.global_severe"
                )
                for counts in validated.subgroup_counts
            }
            return _empty_result(
                execution,
                validated,
                owned_provenance,
                len(table.rows),
                HTEStatus.ABSTAINED,
                "hte.overlap.global_severe",
                "Global cross-fitted treatment scores fail overlap policy.",
                plan=plan,
                crossfit=crossfit,
                nuisance=nuisance,
                global_overlap=global_overlap,
                subgroup_refusals=subgroup_refusals,
            )
        return _estimate_subgroups(
            execution,
            validated,
            owned_provenance,
            len(table.rows),
            plan,
            crossfit,
            nuisance,
            global_overlap,
        )


def _estimate_subgroups(
    execution: HTEExecutionRequest,
    validated: HTEValidationResult,
    provenance: ProvenanceRecords,
    raw_count: int,
    plan: DMLFoldPlan,
    crossfit: CrossFittedNuisanceResult,
    nuisance: DMLNuisanceDiagnostics,
    global_overlap: DMLOverlapDiagnostic,
) -> HeterogeneousEffectResult:
    counts_by_id = {item.subgroup_id: item for item in validated.subgroup_counts}
    supported: list[str] = []
    overlap_by_id: dict[str, DMLOverlapDiagnostic] = {}
    refused: dict[str, tuple[str, HTEDiagnostic]] = {}
    for subgroup_id in validated.subgroup_ids:
        counts = counts_by_id[subgroup_id]
        sparse = _sparse_reason(execution, counts)
        if sparse:
            refused[subgroup_id] = (
                sparse,
                _diagnostic(
                    sparse, "The subgroup does not satisfy configured sample minima.", subgroup_id
                ),
            )
            continue
        indices = tuple(
            index for index, row in enumerate(validated.rows) if row.subgroup_id == subgroup_id
        )
        try:
            overlap = assess_dml_overlap(
                scores=tuple(crossfit.treatment_predictions[index] for index in indices),
                treated=tuple(validated.rows[index].treated for index in indices),
                config=execution.configuration.dml,
            )
        except DMLNumericalError:
            overlap = None
        if overlap is None or overlap.status in {OverlapStatus.SEVERE, OverlapStatus.UNAVAILABLE}:
            code = "hte.subgroup.overlap_severe"
            refused[subgroup_id] = (
                code,
                _diagnostic(
                    code, "Subgroup-specific overlap fails configured policy.", subgroup_id
                ),
            )
            continue
        supported.append(subgroup_id)
        overlap_by_id[subgroup_id] = overlap

    computation = None
    single_group: HTEGroupComputation | None = None
    numerical_diagnostic = None
    if len(supported) >= 2:
        selected = tuple(
            index
            for subgroup_id in supported
            for index, row in enumerate(validated.rows)
            if row.subgroup_id == subgroup_id
        )
        try:
            computation = estimate_grouped_orthogonal_effects(
                outcomes=tuple(validated.rows[index].outcome for index in selected),
                treatments=tuple(float(validated.rows[index].treated) for index in selected),
                outcome_predictions=tuple(
                    crossfit.outcome_predictions[index] for index in selected
                ),
                treatment_predictions=tuple(
                    crossfit.treatment_predictions[index] for index in selected
                ),
                subgroup_ids=tuple(validated.rows[index].subgroup_id for index in selected),
                confidence_level=execution.configuration.dml.confidence_level,
                residual_tolerance=execution.configuration.dml.treatment_residual_tolerance,
            )
        except HTENumericalError as error:
            numerical_diagnostic = _diagnostic(error.code, str(error))
    elif len(supported) == 1:
        selected = tuple(
            index for index, row in enumerate(validated.rows) if row.subgroup_id == supported[0]
        )
        try:
            single_group = estimate_orthogonal_group(
                outcomes=tuple(validated.rows[index].outcome for index in selected),
                treatments=tuple(float(validated.rows[index].treated) for index in selected),
                outcome_predictions=tuple(
                    crossfit.outcome_predictions[index] for index in selected
                ),
                treatment_predictions=tuple(
                    crossfit.treatment_predictions[index] for index in selected
                ),
                subgroup_id=supported[0],
                confidence_level=execution.configuration.dml.confidence_level,
                residual_tolerance=execution.configuration.dml.treatment_residual_tolerance,
            )
        except HTENumericalError as error:
            numerical_diagnostic = _diagnostic(error.code, str(error))
    if computation is None and single_group is None:
        code = (
            numerical_diagnostic.code
            if numerical_diagnostic
            else "hte.heterogeneity.insufficient_groups"
        )
        message = (
            numerical_diagnostic.message
            if numerical_diagnostic
            else "At least two supported subgroups are required for direct heterogeneity evidence."
        )
        for subgroup_id in supported:
            refused[subgroup_id] = (code, _diagnostic(code, message, subgroup_id))
        group_map: dict[str, tuple[HTEGroupComputation, float]] = {}
        interactions: tuple[InteractionEffectResult, ...] = ()
        global_evidence = GlobalHeterogeneityEvidence(
            status=HTEEvidenceStatus.UNAVAILABLE, unavailable_reason=message
        )
    elif single_group is not None:
        group_map = {single_group.subgroup_id: (single_group, single_group.p_value)}
        interactions = ()
        global_evidence = GlobalHeterogeneityEvidence(
            status=HTEEvidenceStatus.UNAVAILABLE,
            unavailable_reason="Fewer than two subgroups have supportable estimates.",
        )
    else:
        assert computation is not None
        adjusted_groups = holm_adjust(tuple(item.p_value for item in computation.groups))
        adjusted_interactions = holm_adjust(tuple(item.p_value for item in computation.contrasts))
        group_map = {
            item.subgroup_id: (item, adjusted_groups[index])
            for index, item in enumerate(computation.groups)
        }
        interactions = tuple(
            InteractionEffectResult(
                reference_subgroup_id=item.reference_subgroup_id,
                comparison_subgroup_id=item.comparison_subgroup_id,
                estimate=item.estimate,
                standard_error=item.standard_error,
                confidence_interval=ConfidenceInterval(
                    lower=item.confidence_interval_lower,
                    upper=item.confidence_interval_upper,
                    confidence_level=execution.configuration.dml.confidence_level,
                ),
                p_value=item.p_value,
                adjusted_p_value=adjusted_interactions[index],
            )
            for index, item in enumerate(computation.contrasts)
        )
        global_evidence = GlobalHeterogeneityEvidence(
            status=HTEEvidenceStatus.AVAILABLE,
            statistic=computation.global_heterogeneity.statistic,
            degrees_of_freedom=computation.global_heterogeneity.degrees_of_freedom,
            p_value=computation.global_heterogeneity.p_value,
            detected=computation.global_heterogeneity.detected,
        )
    subgroup_results = tuple(
        _subgroup_result(
            execution,
            subgroup,
            counts_by_id[subgroup.subgroup_id],
            group_map.get(subgroup.subgroup_id),
            overlap_by_id.get(subgroup.subgroup_id),
            refused.get(subgroup.subgroup_id),
        )
        for subgroup in execution.modifier.subgroups
    )
    diagnostics = tuple(value[1] for value in refused.values())
    status = HTEStatus.COMPLETED if computation is not None and not refused else HTEStatus.ABSTAINED
    return HeterogeneousEffectResult(
        **_common(execution, validated, provenance, raw_count),
        status=status,
        subgroup_results=subgroup_results,
        interactions=interactions,
        global_heterogeneity=global_evidence,
        multiplicity=MultiplicityContext(
            subgroup_effect_tests=(
                len(computation.groups) if computation else (1 if single_group else 0)
            ),
            interaction_tests=len(interactions),
            global_tests=1 if computation else 0,
            corrected_families=(
                ("subgroup_effects", "reference_interactions")
                if interactions
                else (("subgroup_effects",) if computation or single_group else ())
            ),
        ),
        global_overlap=global_overlap,
        fold_plan=plan,
        fold_fits=_fold_fits(crossfit),
        nuisance_diagnostics=nuisance,
        diagnostics=diagnostics,
        abstention_reason=diagnostics[0].code if diagnostics else None,
    )


def _subgroup_result(
    execution: HTEExecutionRequest,
    subgroup: CategoricalSubgroup | ContinuousBinSubgroup,
    counts: ValidatedSubgroupCounts,
    computation: tuple[HTEGroupComputation, float] | None,
    overlap: DMLOverlapDiagnostic | None,
    refusal: tuple[str, HTEDiagnostic] | None,
) -> SubgroupEffectResult:
    common: _SubgroupResultArguments = {
        "subgroup_id": subgroup.subgroup_id,
        "label": subgroup.label,
        "rule": subgroup_rule(execution, subgroup),
        "sample_counts": counts.as_public_counts(),
        "overlap": overlap,
    }
    if computation is None:
        code, diagnostic = refusal or (
            "hte.subgroup.unavailable",
            _diagnostic("hte.subgroup.unavailable", "Subgroup estimate is unavailable."),
        )
        return SubgroupEffectResult(
            **common,
            status=HTESubgroupStatus.ABSTAINED,
            diagnostics=(diagnostic,),
            abstention_reason=code,
        )
    value, adjusted = computation
    return SubgroupEffectResult(
        **common,
        status=HTESubgroupStatus.COMPLETED,
        estimate=value.estimate,
        standard_error=value.standard_error,
        confidence_interval=ConfidenceInterval(
            lower=value.confidence_interval_lower,
            upper=value.confidence_interval_upper,
            confidence_level=execution.configuration.dml.confidence_level,
        ),
        p_value=value.p_value,
        adjusted_p_value=adjusted,
        uncertainty_method="orthogonal_score_influence_hc1",
    )


def _sparse_reason(execution: HTEExecutionRequest, counts: ValidatedSubgroupCounts) -> str | None:
    config = execution.configuration
    if counts.retained_count < config.minimum_subgroup_retained:
        return "hte.subgroup.sparse_total"
    if counts.treated_count < config.minimum_subgroup_treated:
        return "hte.subgroup.sparse_treated"
    if counts.control_count < config.minimum_subgroup_control:
        return "hte.subgroup.sparse_control"
    return None


def _empty_result(
    execution: HTEExecutionRequest,
    validated: HTEValidationResult,
    provenance: ProvenanceRecords,
    raw_count: int,
    status: HTEStatus,
    code: str,
    message: str,
    *,
    plan: DMLFoldPlan | None = None,
    crossfit: CrossFittedNuisanceResult | None = None,
    nuisance: DMLNuisanceDiagnostics | None = None,
    global_overlap: DMLOverlapDiagnostic | None = None,
    subgroup_refusals: dict[str, str] | None = None,
) -> HeterogeneousEffectResult:
    diagnostic = _diagnostic(code, message)
    counts_by_id = {item.subgroup_id: item for item in validated.subgroup_counts}
    subgroup_results = tuple(
        SubgroupEffectResult(
            subgroup_id=subgroup.subgroup_id,
            label=subgroup.label,
            rule=subgroup_rule(execution, subgroup),
            sample_counts=counts_by_id[subgroup.subgroup_id].as_public_counts(),
            status=HTESubgroupStatus.ABSTAINED,
            diagnostics=(
                _diagnostic(
                    (subgroup_refusals or {}).get(subgroup.subgroup_id, code),
                    (
                        "The subgroup does not satisfy configured sample minima."
                        if (subgroup_refusals or {})
                        .get(subgroup.subgroup_id, code)
                        .startswith("hte.subgroup.sparse")
                        else message
                    ),
                    subgroup.subgroup_id,
                ),
            ),
            abstention_reason=(subgroup_refusals or {}).get(subgroup.subgroup_id, code),
        )
        for subgroup in execution.modifier.subgroups
    )
    return HeterogeneousEffectResult(
        **_common(execution, validated, provenance, raw_count),
        status=status,
        subgroup_results=subgroup_results,
        interactions=(),
        global_heterogeneity=GlobalHeterogeneityEvidence(
            status=HTEEvidenceStatus.UNAVAILABLE, unavailable_reason=message
        ),
        multiplicity=MultiplicityContext(
            subgroup_effect_tests=0, interaction_tests=0, global_tests=0, corrected_families=()
        ),
        global_overlap=global_overlap,
        fold_plan=plan,
        fold_fits=_fold_fits(crossfit) if crossfit else (),
        nuisance_diagnostics=nuisance,
        diagnostics=(diagnostic,),
        abstention_reason=code,
    )


def _common(
    execution: HTEExecutionRequest,
    validated: HTEValidationResult,
    provenance: ProvenanceRecords,
    raw_count: int,
) -> _CommonResultArguments:
    identification = execution.identification_result
    return {
        "request_id": execution.request_id,
        "execution_request": execution,
        "analysis_semantics": execution.modifier.pre_specification,
        "estimand": identification.estimand,
        "treatment": identification.treatment,
        "modifier": execution.modifier,
        "assumptions": identification.assumptions,
        "provenance": provenance,
        "assignment_fingerprint_sha256": validated.assignment_fingerprint_sha256,
        "raw_count": raw_count,
        "retained_count": len(validated.rows),
        "unassigned_count": validated.unassigned_count,
    }


def _fold_fits(crossfit: CrossFittedNuisanceResult) -> tuple[DMLFoldFitProvenance, ...]:
    return tuple(
        DMLFoldFitProvenance(
            fold_index=item.fold_index,
            train_count=item.train_count,
            score_count=item.score_count,
            outcome_adapter=item.outcome_metadata,
            treatment_adapter=item.treatment_metadata,
            outcome_fit=item.outcome_fit,
            treatment_fit=item.treatment_fit,
        )
        for item in crossfit.fold_records
    )


def _diagnostic(code: str, message: str, subgroup_id: str | None = None) -> HTEDiagnostic:
    return HTEDiagnostic(
        code=code,
        severity=DiagnosticSeverity.FATAL,
        status=HTEDiagnosticStatus.FAILED,
        message=message,
        subgroup_id=subgroup_id,
    )


def _analysis_provenance(
    execution: HTEExecutionRequest, provenance: ProvenanceRecords
) -> ProvenanceRecords:
    registration_id = execution.modifier.registration_id or "unregistered"
    return (
        *provenance,
        ProvenanceRecord(
            source_type=ProvenanceSourceType.CONFIGURATION,
            source_id=f"hte-config:{execution.configuration.analysis_version}",
            source_version=execution.configuration.analysis_version,
        ),
        ProvenanceRecord(
            source_type=ProvenanceSourceType.ANALYSIS_REQUEST,
            source_id=f"hte-modifier-registration:{registration_id}",
            source_version="1",
        ),
        ProvenanceRecord(
            source_type=ProvenanceSourceType.DERIVED,
            source_id="hte-orthogonal-subgroup-interactions",
            source_version="1",
        ),
    )


def _start_span(provider: BaseObservabilityProvider, row_count: int) -> BufferedSpan | None:
    before = _failure_count(provider)
    try:
        return provider.start_root_span(
            "heterogeneous_treatment_effects",
            inputs={"row_count": row_count},
            metadata={"method": "dml_orthogonal_subgroup_interactions"},
            tags=("statistics", "causal", "hte"),
        )
    except Exception:
        _increment_failure(provider, before)
        return None


def _finish_result(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    result: HeterogeneousEffectResult,
    duration_ms: float,
) -> None:
    if span is None:
        return
    metadata: dict[str, object] = {
        **execution_metadata(result, "repository_hte"),
        "method": result.method,
        "estimand": result.estimand.estimand_type.value if result.estimand else "unavailable",
        "modifier_type": result.modifier.modifier_type.value,
        "subgroup_count": len(result.subgroup_results),
        "global_heterogeneity_status": result.global_heterogeneity.status.value,
        "multiplicity_method": result.multiplicity.correction_method.value,
        "pre_specification_status": result.analysis_semantics.value,
        "abstained_group_count": sum(
            item.status is HTESubgroupStatus.ABSTAINED for item in result.subgroup_results
        ),
        "overlap_failure_count": sum("overlap" in item.code for item in result.diagnostics),
        "status": result.status.value,
        "diagnostic_codes": tuple(item.code for item in result.diagnostics),
        "retained_count": result.retained_count,
        "duration_ms": duration_ms,
    }
    _observe(provider, lambda: span.add_metadata(metadata))
    _observe(
        provider,
        lambda: span.finish(
            outputs={
                "status": result.status.value,
                "hte_completed": result.status is HTEStatus.COMPLETED,
            }
        ),
    )


def _finish_failure(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    error: Exception,
    duration_ms: float,
) -> None:
    if span is None:
        return
    _observe(provider, lambda: span.add_metadata({"status": "failed", "duration_ms": duration_ms}))
    _observe(
        provider,
        lambda: span.record_error(
            "Heterogeneous-effect analysis failed.",
            details={"type": error.__class__.__name__},
        ),
    )
    _observe(provider, lambda: span.finish(outputs={"status": "failed", "hte_completed": False}))


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


__all__ = ["HeterogeneousEffectEstimator"]
