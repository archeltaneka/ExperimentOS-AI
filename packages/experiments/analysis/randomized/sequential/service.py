"""Pre-registered cumulative-look sequential randomized analysis."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

import scipy.stats as _stats  # type: ignore[import-untyped]

from packages.observability.base import BaseObservabilityProvider, BufferedSpan
from packages.observability.noop import NoOpObservabilityProvider

from ...provenance import DiagnosticSeverity, ProvenanceRecord
from ...requests import AnalysisRequest
from ...study_designs import RandomizedAnalysisMethod, RandomizedExperimentDesign
from ...validation import AnalysisDataBinding, AnalysisTable, ValidationPolicy
from ..models import AlternativeHypothesis, ComputationStatus, RandomizedAnalysisResult
from ..service import RandomizedAnalysisExecutionRequest, RandomizedAnalysisService
from .assumptions import sequential_assumptions
from .boundaries import generate_sequential_boundaries
from .fingerprint import sequential_plan_fingerprint
from .models import (
    INFORMATION_TIME_TOLERANCE,
    PlanIntegrityStatus,
    SequentialAlphaSummary,
    SequentialAnalysisHistory,
    SequentialAnalysisPlan,
    SequentialDiagnostic,
    SequentialDiagnosticCategory,
    SequentialLookMetadata,
    SequentialLookResult,
    SequentialPlanAudit,
    SequentialStoppingStatus,
)


@dataclass(frozen=True)
class SequentialLookExecution:
    """Caller-owned cumulative data snapshot for one declared look."""

    look_index: int
    information_time: float
    plan_fingerprint: str
    analysis_request: AnalysisRequest
    table: AnalysisTable
    binding: AnalysisDataBinding
    executed_at: datetime | None = None


class SequentialAnalysisService:
    """Validate a complete supplied history and evaluate each valid registered look."""

    def __init__(
        self,
        *,
        validation_policy: ValidationPolicy | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self._policy = validation_policy or ValidationPolicy()
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        plan: SequentialAnalysisPlan,
        executions: tuple[SequentialLookExecution, ...],
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> SequentialAnalysisHistory:
        started_at = perf_counter()
        span = _start_span(self.observability_provider, look_count=len(executions))
        result = self._analyze(plan, executions, provenance=provenance)
        _finish_span(
            self.observability_provider,
            span,
            result=result,
            duration_ms=(perf_counter() - started_at) * 1000.0,
        )
        return result

    def _analyze(
        self,
        plan: SequentialAnalysisPlan,
        executions: tuple[SequentialLookExecution, ...],
        *,
        provenance: tuple[ProvenanceRecord, ...],
    ) -> SequentialAnalysisHistory:
        supplied_fingerprint = plan.plan_fingerprint
        actual_fingerprint = sequential_plan_fingerprint(plan)
        if supplied_fingerprint is None or supplied_fingerprint != actual_fingerprint:
            return _invalid_plan_mutation_history(plan, provenance=provenance)
        boundaries = generate_sequential_boundaries(plan)
        retained: list[SequentialLookResult] = []
        deviations: list[SequentialDiagnostic] = []
        seen_indexes: set[int] = set()
        previous_counts: tuple[int, int, int] | None = None
        previous_units: dict[tuple[str, str], tuple[tuple[str, str], tuple[str, str]]] | None = None
        previous_binding: AnalysisDataBinding | None = None
        previous_executed_at: datetime | None = None
        status = SequentialStoppingStatus.CONTINUE

        for execution in executions:
            expected_index = len(retained) + 1
            deviation = _validate_declared_look(
                plan,
                execution,
                expected_index=expected_index,
                seen_indexes=seen_indexes,
                efficacy_already_reached=status is SequentialStoppingStatus.EFFICACY,
                previous_binding=previous_binding,
                previous_executed_at=previous_executed_at,
            )
            if deviation is not None:
                deviations.append(deviation)
                status = SequentialStoppingStatus.INVALID
                break

            try:
                counts, units = _cumulative_snapshot(plan, execution)
            except (KeyError, TypeError, ValueError):
                deviations.append(
                    _deviation(
                        "SEQUENTIAL_ANALYSIS_BINDING_INVALID",
                        "The supplied table does not satisfy its declared analysis-role binding.",
                        category=SequentialDiagnosticCategory.CONFIGURATION,
                    )
                )
                status = SequentialStoppingStatus.INVALID
                break
            planned_counts = plan.planned_looks[
                execution.look_index - 1
            ].expected_cumulative_sample_counts
            if planned_counts is not None and counts != (
                planned_counts.total,
                planned_counts.treatment,
                planned_counts.control,
            ):
                deviations.append(
                    _deviation(
                        "SEQUENTIAL_PLANNED_SAMPLE_COUNT_MISMATCH",
                        "Cumulative sample counts differ from the registered look.",
                        category=SequentialDiagnosticCategory.SAMPLE,
                    )
                )
                status = SequentialStoppingStatus.INVALID
                break
            deviation = _validate_cumulative_history(
                counts,
                units,
                previous_counts=previous_counts,
                previous_units=previous_units,
            )
            if deviation is not None:
                deviations.append(deviation)
                status = SequentialStoppingStatus.INVALID
                break

            boundary = boundaries[execution.look_index - 1]
            randomized_result = _analyze_look(
                plan,
                execution,
                validation_policy=self._policy,
                provenance=provenance,
            )
            if randomized_result.status in {
                ComputationStatus.ABSTAINED,
                ComputationStatus.INVALID,
                ComputationStatus.UNSUPPORTED,
            }:
                look_status = SequentialStoppingStatus.ABSTAIN
                statistic = None
                crossed = False
                estimator_method = None
            else:
                if randomized_result.test_result is None or randomized_result.point_effect is None:
                    raise RuntimeError(
                        "numerical randomized result is missing inferential evidence"
                    )
                statistic = _signed_normal_score(
                    randomized_result.test_result.p_value,
                    randomized_result.point_effect.absolute_effect.value,
                )
                crossed = boundary.nominal_alpha > 0.0 and (
                    abs(statistic) >= boundary.critical_boundary
                )
                look_status = (
                    SequentialStoppingStatus.EFFICACY
                    if crossed
                    else SequentialStoppingStatus.CONTINUE
                )
                estimator_method = randomized_result.test_result.test_type

            total, treatment, control = counts
            plan_fingerprint = plan.plan_fingerprint
            if plan_fingerprint is None:
                raise RuntimeError("validated sequential plan is missing its fingerprint")
            look_result = SequentialLookResult(
                plan_id=plan.plan_id,
                plan_fingerprint=plan_fingerprint,
                look_index=execution.look_index,
                information_time=execution.information_time,
                cumulative_sample_count=total,
                treatment_count=treatment,
                control_count=control,
                estimator_method=estimator_method,
                look_level_analysis=randomized_result,
                standardized_statistic=statistic,
                sequential_boundary=boundary.critical_boundary,
                cumulative_alpha_spent=boundary.cumulative_alpha_spent,
                nominal_alpha=boundary.nominal_alpha,
                boundary_crossed=crossed,
                stopping_status=look_status,
                assumptions=sequential_assumptions() + randomized_result.assumptions,
                diagnostics=(),
                warnings=randomized_result.warnings,
                executed_at=execution.executed_at,
                duration_ms=None,
                provenance=provenance,
            )
            retained.append(look_result)
            seen_indexes.add(execution.look_index)
            previous_counts = counts
            previous_units = units
            previous_binding = execution.binding
            previous_executed_at = execution.executed_at
            status = look_status

        integrity = PlanIntegrityStatus.INVALID if deviations else PlanIntegrityStatus.VALID
        if deviations:
            status = SequentialStoppingStatus.INVALID
        latest_boundary = boundaries[len(retained) - 1] if retained else None
        cumulative_alpha = (
            latest_boundary.cumulative_alpha_spent if latest_boundary is not None else 0.0
        )
        metadata = tuple(_look_metadata(item) for item in retained)
        return SequentialAnalysisHistory(
            plan=_plan_audit(plan),
            boundaries=boundaries,
            looks=tuple(retained),
            current_look=retained[-1] if retained else None,
            current_status=status,
            plan_integrity=integrity,
            alpha_summary=SequentialAlphaSummary(
                method=plan.boundary_method,
                total_alpha=plan.total_alpha,
                cumulative_alpha_spent=cumulative_alpha,
                remaining_alpha=max(0.0, plan.total_alpha - cumulative_alpha),
                evaluated_look_count=len(retained),
            ),
            deviations=tuple(deviations),
            first_look=metadata[0] if metadata else None,
            latest_look=metadata[-1] if metadata else None,
            provenance=provenance,
        )


def _invalid_plan_mutation_history(
    plan: SequentialAnalysisPlan,
    *,
    provenance: tuple[ProvenanceRecord, ...],
) -> SequentialAnalysisHistory:
    deviation = _deviation(
        "SEQUENTIAL_PLAN_FINGERPRINT_CHANGED",
        "The supplied plan no longer matches its immutable registered fingerprint.",
        category=SequentialDiagnosticCategory.PLAN,
    )
    return SequentialAnalysisHistory(
        plan=_plan_audit(plan),
        boundaries=(),
        looks=(),
        current_look=None,
        current_status=SequentialStoppingStatus.INVALID,
        plan_integrity=PlanIntegrityStatus.INVALID,
        alpha_summary=SequentialAlphaSummary(
            method=plan.boundary_method,
            total_alpha=plan.total_alpha,
            cumulative_alpha_spent=0.0,
            remaining_alpha=plan.total_alpha,
            evaluated_look_count=0,
        ),
        deviations=(deviation,),
        first_look=None,
        latest_look=None,
        provenance=provenance,
    )


def _plan_audit(plan: SequentialAnalysisPlan) -> SequentialPlanAudit:
    fingerprint = plan.plan_fingerprint
    if fingerprint is None:
        fingerprint = sequential_plan_fingerprint(plan)
    return SequentialPlanAudit(
        schema_version=plan.schema_version,
        plan_version=plan.plan_version,
        method_version=plan.method_version,
        plan_id=plan.plan_id,
        experiment_id=plan.experiment_id,
        analysis_request=plan.analysis_request,
        total_alpha=plan.total_alpha,
        sidedness=plan.sidedness,
        boundary_method=plan.boundary_method,
        planned_looks=plan.planned_looks,
        registration_marker=plan.registration_marker,
        registered_at=plan.registered_at,
        provenance=plan.provenance,
        plan_fingerprint=fingerprint,
    )


def _start_span(
    provider: BaseObservabilityProvider,
    *,
    look_count: int,
) -> BufferedSpan | None:
    before_failures = _provider_failure_count(provider)
    try:
        parent = provider.current_span()
        inputs: dict[str, object] = {"look_count": look_count}
        metadata: dict[str, object] = {
            "inference_family": "frequentist",
            "method": "sequential",
            "analysis_started": True,
        }
        tags = ("analysis", "sequential")
        if parent is not None and parent.provider is provider:
            return provider.start_span(
                "sequential_analysis",
                inputs=inputs,
                metadata=metadata,
                tags=tags,
                parent=parent,
            )
        return provider.start_root_span(
            "sequential_analysis",
            inputs=inputs,
            metadata=metadata,
            tags=tags,
        )
    except Exception:
        _increment_provider_failure(provider, before_failures)
        return None


def _finish_span(
    provider: BaseObservabilityProvider,
    span: BufferedSpan | None,
    *,
    result: SequentialAnalysisHistory,
    duration_ms: float,
) -> None:
    if span is None:
        return
    current = result.current_look
    diagnostic_codes = tuple(item.code for item in result.deviations)
    metadata: dict[str, object] = {
        "inference_family": "frequentist",
        "method": "sequential",
        "estimand": result.plan.analysis_request.estimand.kind.value,
        "boundary_family": result.plan.boundary_method.value,
        "look_index": current.look_index if current is not None else 0,
        "information_time_bucket": (
            "final" if current is not None and current.information_time == 1.0 else "interim"
        ),
        "status": result.current_status.value,
        "abstention_state": result.current_status
        in {SequentialStoppingStatus.ABSTAIN, SequentialStoppingStatus.INVALID},
        "boundary_crossed": current.boundary_crossed if current is not None else False,
        "plan_integrity": result.plan_integrity.value,
        "plan_integrity_status": result.plan_integrity.value,
        "stopping_state": result.current_status.value,
        "diagnostic_codes": diagnostic_codes,
        "diagnostic_count": len(diagnostic_codes),
        "duration_ms": duration_ms,
        "analysis_completed": True,
    }
    _run_observability_operation(provider, lambda: span.add_metadata(metadata))
    _run_observability_operation(
        provider,
        lambda: span.finish(
            outputs={"status": result.current_status.value, "analysis_completed": True}
        ),
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
        current = provider.failure_count
    except Exception:
        current = None
    try:
        if before_failures is None or current is None or current == before_failures:
            provider.increment_failure()
    except Exception:
        return


def _validate_declared_look(
    plan: SequentialAnalysisPlan,
    execution: SequentialLookExecution,
    *,
    expected_index: int,
    seen_indexes: set[int],
    efficacy_already_reached: bool,
    previous_binding: AnalysisDataBinding | None,
    previous_executed_at: datetime | None,
) -> SequentialDiagnostic | None:
    if execution.look_index < 1 or execution.look_index > len(plan.planned_looks):
        return _deviation("SEQUENTIAL_UNPLANNED_LOOK", "The supplied look is not in the plan.")
    if execution.look_index in seen_indexes or execution.look_index < expected_index:
        return _deviation("SEQUENTIAL_DUPLICATE_LOOK", "A planned look was evaluated twice.")
    if execution.look_index > expected_index:
        return _deviation("SEQUENTIAL_SKIPPED_LOOK", "A required planned look was skipped.")
    if efficacy_already_reached:
        return _deviation(
            "SEQUENTIAL_LOOK_AFTER_EFFICACY",
            "No later look may create another decision after efficacy stopping eligibility.",
        )
    planned = plan.planned_looks[execution.look_index - 1]
    if not math.isclose(
        execution.information_time,
        planned.information_time,
        rel_tol=0.0,
        abs_tol=INFORMATION_TIME_TOLERANCE,
    ):
        return _deviation(
            "SEQUENTIAL_INFORMATION_TIME_MISMATCH",
            "The look information time differs from the registered schedule.",
        )
    if execution.plan_fingerprint != plan.plan_fingerprint:
        return _deviation(
            "SEQUENTIAL_PLAN_FINGERPRINT_CHANGED",
            "The execution fingerprint differs from the registered plan.",
        )
    if execution.executed_at is not None and execution.executed_at.utcoffset() is None:
        return _deviation(
            "SEQUENTIAL_EXECUTION_TIME_INVALID",
            "Look execution timestamps must be timezone-aware.",
        )
    if plan.registered_at is not None and execution.executed_at is not None:
        if execution.executed_at < plan.registered_at:
            return _deviation(
                "SEQUENTIAL_PLAN_NOT_PREREGISTERED",
                "The look execution time precedes the explicit registration time.",
            )
    if (
        previous_executed_at is not None
        and execution.executed_at is not None
        and execution.executed_at < previous_executed_at
    ):
        return _deviation(
            "SEQUENTIAL_EXECUTION_TIME_DECREASED",
            "Look execution times must be chronological.",
        )
    if previous_binding is not None and execution.binding != previous_binding:
        return _deviation(
            "SEQUENTIAL_ANALYSIS_BINDING_CHANGED",
            "Physical analysis-role bindings changed between cumulative looks.",
            category=SequentialDiagnosticCategory.CONFIGURATION,
        )
    request = execution.analysis_request
    registered = plan.analysis_request
    if request.outcome.metric.metric_type is not registered.outcome.metric.metric_type:
        return _deviation("SEQUENTIAL_METRIC_TYPE_CHANGED", "The primary metric type changed.")
    if request.outcome != registered.outcome:
        return _deviation("SEQUENTIAL_OUTCOME_CHANGED", "The primary outcome changed.")
    if request.treatment != registered.treatment:
        return _deviation("SEQUENTIAL_TREATMENT_CHANGED", "The treatment definition changed.")
    if request.control != registered.control:
        return _deviation("SEQUENTIAL_CONTROL_CHANGED", "The control definition changed.")
    if request.estimand != registered.estimand:
        return _deviation("SEQUENTIAL_ESTIMAND_CHANGED", "The estimand changed.")
    request_design = request.study_design
    registered_design = registered.study_design
    if not isinstance(request_design, RandomizedExperimentDesign) or not isinstance(
        registered_design,
        RandomizedExperimentDesign,
    ):
        return _deviation(
            "SEQUENTIAL_ESTIMATOR_CONFIGURATION_CHANGED",
            "The registered randomized design type changed.",
        )
    if request.unit_of_analysis != registered.unit_of_analysis or (
        request_design.randomization_unit != registered_design.randomization_unit
    ):
        return _deviation("SEQUENTIAL_ANALYSIS_UNIT_CHANGED", "Analysis-unit semantics changed.")
    if request.study_design.method is not RandomizedAnalysisMethod.SEQUENTIAL_AB:
        return _deviation(
            "SEQUENTIAL_ESTIMATOR_CONFIGURATION_CHANGED",
            "The registered sequential estimator configuration changed.",
        )
    if request != registered:
        return _deviation(
            "SEQUENTIAL_ESTIMATOR_CONFIGURATION_CHANGED",
            "The execution analysis configuration differs from the registered plan.",
            category=SequentialDiagnosticCategory.CONFIGURATION,
        )
    return None


def _cumulative_snapshot(
    plan: SequentialAnalysisPlan,
    execution: SequentialLookExecution,
) -> tuple[
    tuple[int, int, int],
    dict[tuple[str, str], tuple[tuple[str, str], tuple[str, str]]],
]:
    binding = execution.binding
    table = execution.table
    treatment_index = table.columns.index(binding.treatment_column)
    unit_index = table.columns.index(binding.observation_unit_column)
    outcome_column = binding.outcome.value_column
    if outcome_column is None:
        raise ValueError("sequential v1 requires a scalar outcome binding")
    outcome_index = table.columns.index(outcome_column)
    treatment_value = plan.analysis_request.treatment.assignment_value
    control_value = plan.analysis_request.control.assignment_value
    treatment = 0
    control = 0
    units: dict[tuple[str, str], tuple[tuple[str, str], tuple[str, str]]] = {}
    for row in table.rows:
        assignment = row[treatment_index]
        unit = row[unit_index]
        outcome = row[outcome_index]
        unit_key = (type(unit).__name__, repr(unit))
        assignment_key = (type(assignment).__name__, repr(assignment))
        outcome_key = (type(outcome).__name__, repr(outcome))
        if type(assignment) is type(treatment_value) and assignment == treatment_value:
            treatment += 1
            units[unit_key] = (assignment_key, outcome_key)
        elif type(assignment) is type(control_value) and assignment == control_value:
            control += 1
            units[unit_key] = (assignment_key, outcome_key)
    return (treatment + control, treatment, control), units


def _validate_cumulative_history(
    counts: tuple[int, int, int],
    units: dict[tuple[str, str], tuple[tuple[str, str], tuple[str, str]]],
    *,
    previous_counts: tuple[int, int, int] | None,
    previous_units: dict[tuple[str, str], tuple[tuple[str, str], tuple[str, str]]] | None,
) -> SequentialDiagnostic | None:
    if previous_counts is None or previous_units is None:
        return None
    total, treatment, control = counts
    previous_total, previous_treatment, previous_control = previous_counts
    if total < previous_total:
        return _deviation(
            "SEQUENTIAL_SAMPLE_COUNT_DECREASED",
            "The cumulative eligible sample count decreased.",
            category=SequentialDiagnosticCategory.SAMPLE,
        )
    if treatment < previous_treatment:
        return _deviation(
            "SEQUENTIAL_TREATMENT_COUNT_DECREASED",
            "The cumulative treatment count decreased.",
            category=SequentialDiagnosticCategory.SAMPLE,
        )
    if control < previous_control:
        return _deviation(
            "SEQUENTIAL_CONTROL_COUNT_DECREASED",
            "The cumulative control count decreased.",
            category=SequentialDiagnosticCategory.SAMPLE,
        )
    missing_units = set(previous_units).difference(units)
    if missing_units:
        return _deviation(
            "SEQUENTIAL_CUMULATIVE_UNITS_MISSING",
            "Previously observed units are missing from the cumulative look.",
            category=SequentialDiagnosticCategory.SAMPLE,
        )
    if any(units[key][0] != values[0] for key, values in previous_units.items()):
        return _deviation(
            "SEQUENTIAL_TREATMENT_ASSIGNMENT_CHANGED",
            "A previously observed unit switched treatment assignment.",
            category=SequentialDiagnosticCategory.SAMPLE,
        )
    if any(units[key][1] != values[1] for key, values in previous_units.items()):
        return _deviation(
            "SEQUENTIAL_CUMULATIVE_OUTCOME_CHANGED",
            "A previously observed unit's outcome changed in cumulative data.",
            category=SequentialDiagnosticCategory.SAMPLE,
        )
    return None


def _analyze_look(
    plan: SequentialAnalysisPlan,
    execution: SequentialLookExecution,
    *,
    validation_policy: ValidationPolicy,
    provenance: tuple[ProvenanceRecord, ...],
) -> RandomizedAnalysisResult:
    request = plan.analysis_request
    fixed_request = request.model_copy(
        update={
            "study_design": request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.FIXED_HORIZON_AB}
            )
        }
    )
    return RandomizedAnalysisService(validation_policy=validation_policy).analyze(
        RandomizedAnalysisExecutionRequest(
            request_id=f"sequential-look-{execution.look_index}",
            analysis_request=fixed_request,
            alternative=AlternativeHypothesis.TWO_SIDED,
        ),
        execution.table,
        execution.binding,
        provenance=provenance,
    )


def _signed_normal_score(p_value: float, effect: float) -> float:
    if effect == 0.0:
        return 0.0
    half_p = max(p_value / 2.0, math.nextafter(0.0, 1.0))
    magnitude = float(_stats.norm.isf(half_p))
    if not math.isfinite(magnitude):
        raise ValueError("sequential monitoring score must be finite")
    return math.copysign(magnitude, effect)


def _deviation(
    code: str,
    message: str,
    *,
    category: SequentialDiagnosticCategory = SequentialDiagnosticCategory.LOOK,
) -> SequentialDiagnostic:
    return SequentialDiagnostic(
        code=code,
        category=category,
        severity=DiagnosticSeverity.FATAL,
        message=message,
    )


def _look_metadata(result: SequentialLookResult) -> SequentialLookMetadata:
    return SequentialLookMetadata(
        look_index=result.look_index,
        information_time=result.information_time,
        cumulative_sample_count=result.cumulative_sample_count,
        treatment_count=result.treatment_count,
        control_count=result.control_count,
        executed_at=result.executed_at,
    )


__all__ = ["SequentialAnalysisService", "SequentialLookExecution"]
