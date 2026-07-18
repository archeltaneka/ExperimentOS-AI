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
    diagnostics.extend(_duplicate_covariate_diagnostics(context))
    diagnostics.extend(_role_conflict_diagnostics(context))
    diagnostics.extend(_covariate_timing_diagnostics(context))
    diagnostics.extend(_unit_and_clustering_diagnostics(context))
    return tuple(diagnostics)


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

    if request.clustering.kind == "clustered" and context.binding.clustering_unit_column is None:
        yield _blocking(
            code="unit.cluster_identifier_required",
            category=ValidationCategory.UNIT,
            message="Clustered analysis requires a clustering-unit column binding.",
            context={"clustering_unit": request.clustering.unit.unit_id},
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
