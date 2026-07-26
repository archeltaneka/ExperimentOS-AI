"""Deterministic cross-object analysis request consistency rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ..estimands import EstimandKind
from ..metrics import MetricType
from ..provenance import DiagnosticOutcome, DiagnosticSeverity
from ..study_designs import (
    CovariateDefinition,
    CovariateRole,
    CovariateTiming,
    ObservationalStudyDesign,
    QuasiExperimentalDesign,
    RandomizedAnalysisMethod,
    RandomizedExperimentDesign,
    TreatmentRelationship,
)
from .bindings import MetricDataBinding
from .context import ValidationContext
from .models import (
    DiagnosticDisposition,
    EligibilityDiagnostic,
    ValidationCategory,
)


def validate_request_consistency(
    context: ValidationContext,
) -> tuple[EligibilityDiagnostic, ...]:
    """Return blocking cross-object diagnostics in a fixed rule-family order."""
    diagnostics: list[EligibilityDiagnostic] = []
    diagnostics.extend(_metric_estimand_diagnostics(context))
    diagnostics.extend(_cate_diagnostics(context))
    diagnostics.extend(_method_prerequisite_diagnostics(context))
    diagnostics.extend(_binding_consistency_diagnostics(context))
    diagnostics.extend(_duplicate_covariate_diagnostics(context))
    diagnostics.extend(_role_conflict_diagnostics(context))
    diagnostics.extend(_covariate_timing_diagnostics(context))
    diagnostics.extend(_unit_and_clustering_diagnostics(context))
    return tuple(diagnostics)


def _binding_consistency_diagnostics(
    context: ValidationContext,
) -> Iterable[EligibilityDiagnostic]:
    """Validate bidirectional request-to-table role mappings without reading row values."""
    request = context.request
    binding = context.binding

    yield from _metric_shape_diagnostics(
        metric_id=request.outcome.metric.metric_id,
        metric_type=request.outcome.metric.metric_type,
        role="outcome",
        value_column=binding.outcome.value_column,
    )

    declared_covariates = {item.metric.metric_id: item for item in request.covariates}
    bound_covariates = {item.metric_id: item for item in binding.covariates}
    for metric_id in dict.fromkeys(item.metric_id for item in binding.covariates):
        if metric_id not in declared_covariates:
            yield _metric_binding_undeclared(metric_id, role="covariate")

    pre_binding_ids = tuple(item.metric_id for item in binding.pre_treatment_metrics)
    duplicate_pre_binding_ids = set(_duplicates(pre_binding_ids))
    for metric_id in _duplicates(pre_binding_ids):
        yield _blocking(
            code="request.metric_binding_duplicate",
            category=ValidationCategory.REQUEST,
            message="A physical metric binding may be declared only once per role.",
            context={"metric_id": metric_id, "role": "pre_treatment_metric"},
        )

    declared_pre_metrics = {item.metric.metric_id: item for item in request.pre_treatment_metrics}
    bound_pre_metrics: dict[str, MetricDataBinding] = {}
    for item in binding.pre_treatment_metrics:
        bound_pre_metrics.setdefault(item.metric_id, item)
    for metric_id in dict.fromkeys(item.metric.metric_id for item in request.pre_treatment_metrics):
        metric_binding = bound_pre_metrics.get(metric_id)
        if metric_binding is None:
            yield _metric_binding_missing(metric_id, role="pre_treatment_metric")
            continue
        if metric_id not in duplicate_pre_binding_ids:
            yield from _metric_shape_diagnostics(
                metric_id=metric_id,
                metric_type=declared_pre_metrics[metric_id].metric.metric_type,
                role="pre_treatment_metric",
                value_column=metric_binding.value_column,
            )
    for metric_id in dict.fromkeys(pre_binding_ids):
        if metric_id not in declared_pre_metrics:
            yield _metric_binding_undeclared(metric_id, role="pre_treatment_metric")

    cross_family_metric_ids = tuple(sorted(set(bound_covariates).intersection(bound_pre_metrics)))
    for metric_id in cross_family_metric_ids:
        yield _blocking(
            code="request.metric_binding_conflict",
            category=ValidationCategory.REQUEST,
            message="One metric identifier cannot be bound to contradictory analytical roles.",
            context={
                "first_role": "covariate",
                "metric_id": metric_id,
                "second_role": "pre_treatment_metric",
            },
        )

    protected_columns = {
        binding.treatment_column: "treatment",
        **{column: "outcome" for column in binding.outcome.columns},
        binding.observation_unit_column: "observation_unit",
    }
    protected_columns.update(
        {
            column: role
            for column, role in (
                (binding.randomization_unit_column, "randomization_unit"),
                (binding.clustering_unit_column, "clustering_unit"),
                (binding.timestamp_column, "timestamp"),
                (binding.treatment_timestamp_column, "treatment_timestamp"),
            )
            if column is not None
        }
    )
    physical_metric_columns = {item.column: item.metric_id for item in binding.covariates}
    for metric_id, metric_binding in bound_pre_metrics.items():
        if metric_id in duplicate_pre_binding_ids:
            continue
        for column in metric_binding.columns:
            protected_role = protected_columns.get(column)
            if protected_role is not None:
                yield _blocking(
                    code="request.metric_binding_role_conflict",
                    category=ValidationCategory.REQUEST,
                    message="A metric binding cannot reuse a protected physical role.",
                    context={
                        "column": column,
                        "metric_id": metric_id,
                        "protected_role": protected_role,
                    },
                )
                continue
            first_metric_id = physical_metric_columns.get(column)
            if first_metric_id is not None and first_metric_id != metric_id:
                yield _blocking(
                    code="request.metric_binding_conflict",
                    category=ValidationCategory.REQUEST,
                    message="Physical metric columns must map to one declared metric.",
                    context={
                        "column": column,
                        "first_metric_id": first_metric_id,
                        "second_metric_id": metric_id,
                    },
                )
                continue
            physical_metric_columns[column] = metric_id

    segment = request.segment
    if segment is not None:
        segment_attributes = {criterion.attribute for criterion in segment.criteria}
        ordinary_adjustment_roles = {
            CovariateRole.ADJUSTMENT,
            CovariateRole.CONFOUNDER,
            CovariateRole.CUPED,
            CovariateRole.PRECISION,
        }
        for metric_id, covariate_binding in bound_covariates.items():
            covariate = declared_covariates.get(metric_id)
            if (
                covariate is not None
                and covariate.role in ordinary_adjustment_roles
                and covariate_binding.column in segment_attributes
            ):
                yield _blocking(
                    code="request.segment_covariate_binding_conflict",
                    category=ValidationCategory.REQUEST,
                    message=(
                        "A physical segment attribute cannot also be an adjustment covariate."
                    ),
                    context={
                        "column": covariate_binding.column,
                        "metric_id": metric_id,
                    },
                )


def _metric_shape_diagnostics(
    *,
    metric_id: str,
    metric_type: MetricType,
    role: str,
    value_column: str | None,
) -> Iterable[EligibilityDiagnostic]:
    expected_shape = "numerator_denominator" if metric_type is MetricType.RATIO else "scalar"
    observed_shape = "scalar" if value_column is not None else "numerator_denominator"
    if expected_shape != observed_shape:
        yield _blocking(
            code="request.metric_binding_shape_incompatible",
            category=ValidationCategory.REQUEST,
            message="The declared metric type is incompatible with its physical input shape.",
            context={
                "expected_shape": expected_shape,
                "metric_id": metric_id,
                "observed_shape": observed_shape,
                "role": role,
            },
        )


def _metric_binding_missing(metric_id: str, *, role: str) -> EligibilityDiagnostic:
    return _blocking(
        code="request.metric_binding_missing",
        category=ValidationCategory.REQUEST,
        message="A declared metric requires a physical data binding.",
        context={"metric_id": metric_id, "role": role},
    )


def _metric_binding_undeclared(metric_id: str, *, role: str) -> EligibilityDiagnostic:
    return _blocking(
        code="request.metric_binding_undeclared",
        category=ValidationCategory.REQUEST,
        message="A physical metric binding must reference declared request metadata.",
        context={"metric_id": metric_id, "role": role},
    )


def _metric_estimand_diagnostics(
    context: ValidationContext,
) -> Iterable[EligibilityDiagnostic]:
    request = context.request
    if (
        request.estimand.kind is EstimandKind.DIFFERENCE_IN_PROPORTIONS
        and request.outcome.metric.metric_type not in {MetricType.BINARY, MetricType.PROPORTION}
    ):
        yield _blocking(
            code="request.metric_estimand_incompatible",
            category=ValidationCategory.REQUEST,
            message="Difference in proportions requires a binary or proportion outcome metric.",
            context={
                "estimand": request.estimand.kind.value,
                "metric_type": request.outcome.metric.metric_type.value,
            },
        )


def _cate_diagnostics(context: ValidationContext) -> Iterable[EligibilityDiagnostic]:
    request = context.request
    if (
        request.estimand.kind is EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT
        and request.segment != request.estimand.conditioning_segment
    ):
        conditioning_segment = request.estimand.conditioning_segment
        yield _blocking(
            code="request.cate_segment_mismatch",
            category=ValidationCategory.REQUEST,
            message="The requested segment must match the CATE conditioning segment.",
            context={
                "conditioning_segment_id": (
                    conditioning_segment.segment_id
                    if conditioning_segment is not None
                    else "unavailable"
                ),
                "request_segment_id": (
                    request.segment.segment_id if request.segment is not None else "unavailable"
                ),
            },
        )


def _method_prerequisite_diagnostics(
    context: ValidationContext,
) -> Iterable[EligibilityDiagnostic]:
    request = context.request
    design = request.study_design
    method = design.method
    is_hte = method.value == "heterogeneous_treatment_effect"
    is_cate = request.estimand.kind is EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT
    if is_hte != is_cate:
        yield _blocking(
            code="method.estimand_incompatible",
            category=ValidationCategory.METHOD,
            message="Heterogeneous treatment-effect methods and CATE estimands must be paired.",
            context={"estimand": request.estimand.kind.value, "method": method.value},
        )

    if (
        isinstance(design, RandomizedExperimentDesign)
        and method is RandomizedAnalysisMethod.CUPED
        and not request.pre_treatment_metrics
        and not any(covariate.role is CovariateRole.CUPED for covariate in request.covariates)
    ):
        yield _blocking(
            code="method.pre_treatment_input_required",
            category=ValidationCategory.METHOD,
            message="CUPED requires a declared pre-treatment metric or CUPED covariate.",
            context={"method": method.value},
        )

    if (
        isinstance(design, RandomizedExperimentDesign)
        and method is RandomizedAnalysisMethod.SEQUENTIAL_AB
        and context.binding.timestamp_column is None
    ):
        yield _blocking(
            code="method.timestamp_required",
            category=ValidationCategory.METHOD,
            message="Sequential analysis requires a timestamp column binding.",
            context={"method": method.value},
        )

    if isinstance(design, QuasiExperimentalDesign) and context.binding.timestamp_column is None:
        yield _blocking(
            code="method.timestamp_required",
            category=ValidationCategory.METHOD,
            message="Difference-in-Differences requires a timestamp column binding.",
            context={"method": method.value},
        )

    if isinstance(design, ObservationalStudyDesign) and not request.covariates:
        yield _blocking(
            code="method.covariate_required",
            category=ValidationCategory.METHOD,
            message="The requested observational method requires declared covariates.",
            context={"method": method.value},
        )


def _duplicate_covariate_diagnostics(
    context: ValidationContext,
) -> Iterable[EligibilityDiagnostic]:
    metric_ids = tuple(covariate.metric.metric_id for covariate in context.request.covariates)
    for metric_id in _duplicates(metric_ids):
        yield _blocking(
            code="request.duplicate_covariate",
            category=ValidationCategory.REQUEST,
            message="A covariate metric identifier may be declared only once.",
            context={"metric_id": metric_id},
        )
    pre_treatment_metric_ids = tuple(
        metric.metric.metric_id for metric in context.request.pre_treatment_metrics
    )
    for metric_id in _duplicates(pre_treatment_metric_ids):
        yield _blocking(
            code="request.duplicate_pre_treatment_metric",
            category=ValidationCategory.REQUEST,
            message="A pre-treatment metric identifier may be declared only once.",
            context={"metric_id": metric_id},
        )


def _role_conflict_diagnostics(
    context: ValidationContext,
) -> Iterable[EligibilityDiagnostic]:
    request = context.request
    conflicting_roles = {CovariateRole.TREATMENT_INDICATOR, CovariateRole.TREATMENT_PROXY}
    for covariate in context.request.covariates:
        reuses_outcome = covariate.metric.metric_id == request.outcome.metric.metric_id
        if reuses_outcome or covariate.role in conflicting_roles:
            yield _blocking(
                code="request.covariate_role_conflict",
                category=ValidationCategory.REQUEST,
                message="A covariate must not reuse another declared analytical role.",
                context={
                    "metric_id": covariate.metric.metric_id,
                    "role": covariate.role.value,
                },
            )

    if request.segment is None:
        return
    protected_columns = {
        context.binding.treatment_column,
        *context.binding.outcome.columns,
        context.binding.observation_unit_column,
    }
    protected_columns.update(
        column
        for column in (
            context.binding.randomization_unit_column,
            context.binding.clustering_unit_column,
        )
        if column is not None
    )
    segment_attributes = tuple(criterion.attribute for criterion in request.segment.criteria)
    for attribute in dict.fromkeys(
        value for value in segment_attributes if value in protected_columns
    ):
        yield _blocking(
            code="request.segment_role_conflict",
            category=ValidationCategory.REQUEST,
            message="A segment attribute must not reuse a protected analytical role.",
            context={"attribute": attribute},
        )


def _covariate_timing_diagnostics(
    context: ValidationContext,
) -> Iterable[EligibilityDiagnostic]:
    cutoff = _treatment_cutoff(context)
    for covariate in context.request.covariates:
        if covariate.timing is CovariateTiming.POST_TREATMENT:
            yield _covariate_blocking(
                "covariate.post_treatment_leakage",
                "Post-treatment covariates cannot be used for causal adjustment.",
                covariate,
            )
        elif covariate.timing is CovariateTiming.UNKNOWN:
            yield _covariate_blocking(
                "covariate.timing_unknown",
                "Covariate timing must be known before causal adjustment.",
                covariate,
            )
        elif (
            covariate.timing is CovariateTiming.PRE_TREATMENT
            and cutoff is not None
            and covariate.measurement_period.end > cutoff
        ):
            yield _covariate_blocking(
                "covariate.measurement_after_treatment",
                "A pre-treatment covariate measurement cannot extend after treatment starts.",
                covariate,
            )

        if covariate.treatment_relationship in {
            TreatmentRelationship.ASSIGNMENT_DERIVED,
            TreatmentRelationship.PROXY,
        }:
            yield _covariate_blocking(
                "covariate.treatment_relationship_conflict",
                "Treatment-derived or proxy covariates cannot be used for causal adjustment.",
                covariate,
            )
        elif covariate.treatment_relationship is TreatmentRelationship.UNKNOWN:
            yield _covariate_blocking(
                "covariate.relationship_unknown",
                "Covariate relationship to treatment must be known for causal adjustment.",
                covariate,
            )


def _unit_and_clustering_diagnostics(
    context: ValidationContext,
) -> Iterable[EligibilityDiagnostic]:
    request = context.request
    design = request.study_design
    if isinstance(design, RandomizedExperimentDesign):
        randomization_unit = design.randomization_unit.unit_id
        analysis_unit = request.unit_of_analysis.unit_id
        if randomization_unit != analysis_unit:
            if request.clustering.kind == "none":
                yield _blocking(
                    code="unit.cluster_required",
                    category=ValidationCategory.UNIT,
                    message=(
                        "Analysis below the randomization unit requires clustering by the "
                        "randomization unit."
                    ),
                    context={
                        "analysis_unit": analysis_unit,
                        "randomization_unit": randomization_unit,
                    },
                )
            elif request.clustering.unit.unit_id != randomization_unit:
                yield _blocking(
                    code="unit.cluster_mismatch",
                    category=ValidationCategory.UNIT,
                    message="The clustering unit must match the randomized assignment unit.",
                    context={
                        "clustering_unit": request.clustering.unit.unit_id,
                        "randomization_unit": randomization_unit,
                    },
                )
        if context.binding.randomization_unit_column is None:
            yield _blocking(
                code="unit.randomization_identifier_required",
                category=ValidationCategory.UNIT,
                message="Randomized designs require a randomization-unit column binding.",
                context={"randomization_unit": randomization_unit},
            )

        randomization_column = context.binding.randomization_unit_column
        if (
            design.randomization_unit == request.unit_of_analysis
            and randomization_column is not None
            and randomization_column != context.binding.observation_unit_column
        ):
            yield _binding_mismatch(
                first_role="randomization_unit",
                first_column=randomization_column,
                second_role="observation_unit",
                second_column=context.binding.observation_unit_column,
                unit_id=design.randomization_unit.unit_id,
            )

        if request.clustering.kind == "clustered":
            clustering_column = context.binding.clustering_unit_column
            if (
                design.randomization_unit == request.clustering.unit
                and randomization_column is not None
                and clustering_column is not None
                and randomization_column != clustering_column
            ):
                yield _binding_mismatch(
                    first_role="randomization_unit",
                    first_column=randomization_column,
                    second_role="clustering_unit",
                    second_column=clustering_column,
                    unit_id=design.randomization_unit.unit_id,
                )

    if request.clustering.kind == "clustered":
        clustering_column = context.binding.clustering_unit_column
        if clustering_column is None:
            yield _blocking(
                code="unit.cluster_identifier_required",
                category=ValidationCategory.UNIT,
                message="Clustered analysis requires a clustering-unit column binding.",
                context={"clustering_unit": request.clustering.unit.unit_id},
            )
        elif (
            request.clustering.unit == request.unit_of_analysis
            and clustering_column != context.binding.observation_unit_column
        ):
            yield _binding_mismatch(
                first_role="observation_unit",
                first_column=context.binding.observation_unit_column,
                second_role="clustering_unit",
                second_column=clustering_column,
                unit_id=request.unit_of_analysis.unit_id,
            )


def _treatment_cutoff(context: ValidationContext) -> datetime | None:
    design = context.request.study_design
    if isinstance(design, RandomizedExperimentDesign):
        return design.experiment_period.start
    if isinstance(design, QuasiExperimentalDesign):
        return design.post_treatment_period.start
    return None


def _covariate_blocking(
    code: str,
    message: str,
    covariate: CovariateDefinition,
) -> EligibilityDiagnostic:
    return _blocking(
        code=code,
        category=ValidationCategory.COVARIATE,
        message=message,
        context={"metric_id": covariate.metric.metric_id},
    )


def _binding_mismatch(
    *,
    first_role: str,
    first_column: str,
    second_role: str,
    second_column: str,
    unit_id: str,
) -> EligibilityDiagnostic:
    return _blocking(
        code="unit.binding_mismatch",
        category=ValidationCategory.UNIT,
        message="Equal logical analysis units must use the same physical column binding.",
        context={
            "first_column": first_column,
            "first_role": first_role,
            "second_column": second_column,
            "second_role": second_role,
            "unit_id": unit_id,
        },
    )


def _blocking(
    *,
    code: str,
    category: ValidationCategory,
    message: str,
    context: dict[str, bool | int | float | str],
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": code,
            "category": category,
            "severity": DiagnosticSeverity.ERROR,
            "outcome": DiagnosticOutcome.FAILED,
            "disposition": DiagnosticDisposition.BLOCKING,
            "message": message,
            "context": context,
        }
    )


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)
