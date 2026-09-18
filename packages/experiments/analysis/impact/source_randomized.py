"""Adapters for owned fixed-horizon randomized, CUPED, and Bayesian results."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel

from ..estimands import EstimandKind
from ..metrics import MetricType
from ..provenance import AssumptionAssessment, AssumptionStatus, Diagnostic, ProvenanceRecord
from ..randomized.bayesian.models import BayesianAnalysisResult, BayesianComputationStatus
from ..randomized.cuped.models import CupedAnalysisResult, CupedStatus
from ..randomized.models import (
    ComputationStatus,
    EvidenceCategory,
    RandomizedAnalysisResult,
    RandomizedTestType,
)
from ..requests import AnalysisRequest
from ..study_designs import RandomizedAnalysisMethod, RandomizedExperimentDesign
from ..uncertainty import ConfidenceInterval, CredibleInterval
from .source_common import (
    block,
    interval_contains,
    native_diagnostic_blocks,
    revalidate_exact,
    snapshot,
    unique_blocks,
    value_text,
)
from .source_models import (
    EffectInterval,
    EffectScaleName,
    SourceEffect,
    SourceRecord,
    TargetKind,
)


def adapt_randomized(source: RandomizedAnalysisResult) -> SourceEffect:
    validated = revalidate_exact(source, RandomizedAnalysisResult)
    if validated is None:
        return _invalid(source, "randomized", "randomized")
    request = validated.analysis_request
    diagnostics = tuple(validated.diagnostics)
    blocks = list(native_diagnostic_blocks(diagnostics))
    if request is None:
        blocks.append(
            block(
                "impact.source.request_missing",
                "A complete randomized analysis request is required for impact semantics.",
            )
        )
    if validated.status is not ComputationStatus.COMPLETED:
        blocks.append(_native_status_block(validated.status.value))

    point = validated.point_effect.absolute_effect.value if validated.point_effect else None
    interval = validated.test_result.confidence_interval if validated.test_result else None
    if request is not None and validated.point_effect is not None:
        if validated.point_effect.absolute_effect.unit != request.outcome.metric.unit:
            blocks.append(
                block("impact.source.effect_unit_mismatch", "Effect unit differs from metric unit.")
            )
    if validated.estimand.kind is EstimandKind.RELATIVE_LIFT:
        blocks.append(
            block(
                "impact.source.relative_uncertainty_missing",
                "Randomized inference reports an absolute interval, not a relative interval.",
            )
        )
    effect_scale = _randomized_scale(request.outcome.metric.metric_type) if request else None
    if request is not None and effect_scale is None:
        blocks.append(
            block("impact.source.metric_scale_unsupported", "Outcome metric scale is unsupported.")
        )
    blocks.extend(_randomized_safety_blocks(validated, request, point, interval))

    estimator = (
        f"randomized_{validated.test_result.test_type.value}"
        if validated.test_result is not None
        else "randomized"
    )
    return _finish(
        source_type="randomized",
        estimator=estimator,
        estimand=validated.estimand.kind.value,
        request_id=validated.request_id,
        native_status=validated.status.value,
        request=request,
        point=point,
        interval=interval,
        effect_scale=effect_scale,
        target_kind=_randomized_target(validated.estimand.kind),
        conditional=_randomized_conditional(
            validated.assumptions, validated.warnings, validated.evidence_category
        ),
        provenance=validated.provenance,
        diagnostics=diagnostics,
        warnings=validated.warnings,
        assumptions=validated.assumptions,
        blocks=blocks,
        metadata=snapshot("configuration", (validated.configuration,))
        + (
            snapshot("configuration", (validated.configuration_provenance,))
            if validated.configuration_provenance is not None
            else ()
        ),
    )


def adapt_cuped(source: CupedAnalysisResult) -> SourceEffect:
    validated = revalidate_exact(source, CupedAnalysisResult)
    if validated is None:
        return _invalid(source, "cuped", "cuped")
    adjusted = validated.adjusted_result
    diagnostics = tuple(validated.diagnostics) + (
        tuple(adjusted.diagnostics) if adjusted is not None else ()
    )
    blocks = list(native_diagnostic_blocks(diagnostics))
    eligible = {
        CupedStatus.COMPLETED,
        CupedStatus.NO_IMPROVEMENT,
        CupedStatus.DEGRADED_PRECISION,
    }
    if validated.status not in eligible:
        blocks.append(_native_status_block(validated.status.value))
    if adjusted is None or adjusted.status is not ComputationStatus.COMPLETED:
        blocks.append(
            block(
                "impact.source.adjusted_effect_missing", "CUPED adjusted inference is unavailable."
            )
        )

    point = (
        adjusted.point_effect.absolute_effect.value if adjusted and adjusted.point_effect else None
    )
    interval = (
        adjusted.test_result.confidence_interval if adjusted and adjusted.test_result else None
    )
    if adjusted is not None and adjusted.point_effect is not None:
        if (
            adjusted.point_effect.absolute_effect.unit
            != validated.analysis_request.outcome.metric.unit
        ):
            blocks.append(
                block("impact.source.effect_unit_mismatch", "Effect unit differs from metric unit.")
            )
    if validated.analysis_request.estimand.kind is EstimandKind.RELATIVE_LIFT:
        blocks.append(
            block(
                "impact.source.relative_uncertainty_missing",
                "CUPED inference reports an absolute interval, not a relative interval.",
            )
        )
    effect_scale = _randomized_scale(validated.analysis_request.outcome.metric.metric_type)
    if effect_scale is None:
        blocks.append(
            block("impact.source.metric_scale_unsupported", "Outcome metric scale is unsupported.")
        )
    if adjusted is not None:
        blocks.extend(
            _randomized_safety_blocks(
                adjusted,
                validated.analysis_request,
                point,
                interval,
            )
        )
    if any(item.status is AssumptionStatus.VIOLATED for item in validated.assumptions):
        blocks.append(
            block("impact.source.assumption_violated", "A declared CUPED assumption is violated.")
        )

    return _finish(
        source_type="cuped",
        estimator="cuped",
        estimand=validated.analysis_request.estimand.kind.value,
        request_id=validated.request_id,
        native_status=validated.status.value,
        request=validated.analysis_request,
        point=point,
        interval=interval,
        effect_scale=effect_scale,
        target_kind=_randomized_target(validated.analysis_request.estimand.kind),
        conditional=_randomized_conditional(
            tuple(validated.assumptions) + (tuple(adjusted.assumptions) if adjusted else ()),
            tuple(validated.warnings) + (tuple(adjusted.warnings) if adjusted else ()),
            adjusted.evidence_category if adjusted else None,
        ),
        provenance=validated.provenance,
        diagnostics=diagnostics,
        warnings=tuple(validated.warnings) + (tuple(adjusted.warnings) if adjusted else ()),
        assumptions=tuple(validated.assumptions)
        + (tuple(adjusted.assumptions) if adjusted else ()),
        blocks=blocks,
        metadata=snapshot(
            "cuped",
            tuple(
                item
                for item in (
                    validated.covariate,
                    validated.retention,
                    validated.coefficient,
                    validated.balance,
                    validated.variance_reduction,
                )
                if item is not None
            ),
        )
        + snapshot("configuration", (validated.full_sample_unadjusted_result.configuration,)),
    )


def adapt_bayesian(source: BayesianAnalysisResult) -> SourceEffect:
    validated = revalidate_exact(source, BayesianAnalysisResult)
    if validated is None:
        return _invalid(source, "bayesian_randomized", "bayesian_randomized")
    request = validated.analysis_request
    diagnostics = tuple(validated.diagnostics)
    blocks = list(native_diagnostic_blocks(diagnostics))
    if validated.status is not BayesianComputationStatus.COMPLETED:
        blocks.append(_native_status_block(validated.status.value))
    if request is None:
        blocks.append(
            block(
                "impact.source.request_missing",
                "A complete Bayesian analysis request is required for impact semantics.",
            )
        )
    point = validated.effect.posterior_mean if validated.effect else None
    interval = validated.effect.credible_interval if validated.effect else None
    effect_scale = _randomized_scale(request.outcome.metric.metric_type) if request else None
    if validated.estimand is not None and validated.estimand.kind is EstimandKind.RELATIVE_LIFT:
        blocks.append(
            block(
                "impact.source.relative_uncertainty_missing",
                "Bayesian inference reports an absolute interval, not a relative interval.",
            )
        )
    if request is not None and effect_scale is None:
        blocks.append(
            block("impact.source.metric_scale_unsupported", "Outcome metric scale is unsupported.")
        )
    if point is not None and interval is not None and not interval_contains(point, interval):
        blocks.append(
            block(
                "impact.source.interval_point_mismatch",
                "Bayesian credible interval does not contain its point summary.",
            )
        )
    if any(item.status is AssumptionStatus.VIOLATED for item in validated.assumptions):
        blocks.append(
            block(
                "impact.source.assumption_violated", "A declared Bayesian assumption is violated."
            )
        )
    if request is not None and isinstance(request.study_design, RandomizedExperimentDesign):
        if request.study_design.method is RandomizedAnalysisMethod.SEQUENTIAL_AB:
            blocks.append(
                block(
                    "impact.source.sequential_unsupported",
                    "Sequential monitoring results are not eligible impact sources.",
                )
            )
    return _finish(
        source_type="bayesian_randomized",
        estimator="bayesian_randomized",
        estimand=(validated.estimand.kind.value if validated.estimand else "unknown"),
        request_id=validated.request_id,
        native_status=validated.status.value,
        request=request,
        point=point,
        interval=interval,
        effect_scale=effect_scale,
        target_kind=(_randomized_target(validated.estimand.kind) if validated.estimand else None),
        conditional=_randomized_conditional(validated.assumptions, validated.warnings, None),
        provenance=validated.provenance,
        diagnostics=diagnostics,
        warnings=validated.warnings,
        assumptions=validated.assumptions,
        blocks=blocks,
        metadata=snapshot(
            "bayesian",
            tuple(
                item
                for item in (
                    validated.likelihood,
                    validated.treatment_prior,
                    validated.control_prior,
                    validated.configuration,
                    validated.configuration_provenance,
                )
                if item is not None
            ),
        ),
    )


def _finish(
    *,
    source_type: str,
    estimator: str,
    estimand: str,
    request_id: str,
    native_status: str,
    request: AnalysisRequest | None,
    point: float | None,
    interval: EffectInterval | None,
    effect_scale: EffectScaleName | None,
    target_kind: TargetKind | None,
    conditional: bool,
    provenance: tuple[ProvenanceRecord, ...],
    diagnostics: Iterable[BaseModel],
    warnings: Iterable[BaseModel],
    assumptions: Iterable[BaseModel],
    blocks: Iterable[Diagnostic],
    metadata: tuple[SourceRecord, ...] = (),
) -> SourceEffect:
    typed_blocks = unique_blocks(blocks)
    analysis_request = request
    observed_period = None
    if analysis_request is not None and isinstance(
        analysis_request.study_design, RandomizedExperimentDesign
    ):
        observed_period = analysis_request.study_design.experiment_period
    return SourceEffect(
        source_type=source_type,
        estimator=estimator,
        estimand=estimand,
        request_id=request_id,
        native_status=native_status,
        metric=analysis_request.outcome if analysis_request is not None else None,
        population=analysis_request.population if analysis_request is not None else None,
        analysis_unit=(analysis_request.unit_of_analysis if analysis_request is not None else None),
        observed_period=observed_period,
        point=None if typed_blocks else point,
        interval=None if typed_blocks else interval,
        effect_scale=effect_scale,
        target_kind=target_kind,
        conditional=conditional,
        provenance=provenance,
        blocking_diagnostics=typed_blocks,
        source_diagnostics=snapshot("source", diagnostics),
        source_warnings=snapshot("source", warnings),
        source_assumptions=snapshot("source", assumptions),
        source_metadata=metadata,
    )


def _invalid(source: object, source_type: str, estimator: str) -> SourceEffect:
    provenance = getattr(source, "provenance", ())
    if not isinstance(provenance, tuple) or not all(
        isinstance(item, ProvenanceRecord) for item in provenance
    ):
        provenance = ()
    diagnostics = getattr(source, "diagnostics", ())
    if not isinstance(diagnostics, tuple) or not all(
        isinstance(item, BaseModel) for item in diagnostics
    ):
        diagnostics = ()
    warnings = getattr(source, "warnings", ())
    if not isinstance(warnings, tuple) or not all(isinstance(item, BaseModel) for item in warnings):
        warnings = ()
    assumptions = getattr(source, "assumptions", ())
    if not isinstance(assumptions, tuple) or not all(
        isinstance(item, BaseModel) for item in assumptions
    ):
        assumptions = ()
    request = getattr(source, "analysis_request", None)
    metric = getattr(request, "outcome", None)
    population = getattr(request, "population", None)
    analysis_unit = getattr(request, "unit_of_analysis", None)
    design = getattr(request, "study_design", None)
    observed_period = (
        design.experiment_period if isinstance(design, RandomizedExperimentDesign) else None
    )
    estimand = getattr(source, "estimand", None)
    estimand_kind = getattr(estimand, "kind", None)
    request_id = getattr(source, "request_id", None)
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = None
    return SourceEffect(
        source_type=source_type,
        estimator=estimator,
        estimand=value_text(estimand_kind, "unknown"),
        request_id=request_id,
        native_status=value_text(getattr(source, "status", None), "invalid_contract"),
        metric=metric,
        population=population,
        analysis_unit=analysis_unit,
        observed_period=observed_period,
        provenance=provenance,
        blocking_diagnostics=(
            block(
                "impact.source.invalid_contract", "The owned source contract failed revalidation."
            ),
        ),
        source_diagnostics=snapshot("source", diagnostics),
        source_warnings=snapshot("source", warnings),
        source_assumptions=snapshot("source", assumptions),
    )


def _native_status_block(status: str) -> Diagnostic:
    return block(
        "impact.source.native_status",
        f"Source status {status!r} does not provide an eligible effect.",
    )


def _randomized_scale(metric_type: MetricType) -> EffectScaleName | None:
    if metric_type is MetricType.BINARY:
        return "absolute_binary"
    if metric_type in {MetricType.CONTINUOUS, MetricType.COUNT}:
        return "continuous"
    return None


def _randomized_target(kind: EstimandKind) -> TargetKind:
    if kind is EstimandKind.AVERAGE_TREATMENT_EFFECT_ON_TREATED:
        return "treated"
    if kind is EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT:
        return "conditioned"
    return "full"


def _randomized_safety_blocks(
    result: RandomizedAnalysisResult,
    request: AnalysisRequest | None,
    point: float | None,
    interval: ConfidenceInterval | CredibleInterval | None,
) -> tuple[Diagnostic, ...]:
    blocks: list[Diagnostic] = []
    if result.evidence_category in {
        EvidenceCategory.RANDOMIZED_DESIGN_WITH_VIOLATED_ASSUMPTIONS,
        EvidenceCategory.NO_RANDOMIZED_EVIDENCE,
    }:
        blocks.append(
            block(
                "impact.source.randomized_evidence_invalid",
                "Randomized evidence category does not support an effect claim.",
            )
        )
    if any(item.status is AssumptionStatus.VIOLATED for item in result.assumptions):
        blocks.append(
            block("impact.source.assumption_violated", "A randomized assumption is violated.")
        )
    if point is not None and interval is not None and not interval_contains(point, interval):
        blocks.append(
            block(
                "impact.source.interval_point_mismatch",
                "Source interval does not contain its point estimate.",
            )
        )
    if request is not None:
        design = request.study_design
        if not isinstance(design, RandomizedExperimentDesign):
            blocks.append(
                block("impact.source.randomized_design_required", "Randomized design is required.")
            )
        elif design.method is RandomizedAnalysisMethod.SEQUENTIAL_AB:
            blocks.append(
                block(
                    "impact.source.sequential_unsupported",
                    "Sequential monitoring results are not eligible impact sources.",
                )
            )
        metric_type = request.outcome.metric.metric_type
        test_type = result.test_result.test_type if result.test_result is not None else None
        if (
            metric_type is MetricType.BINARY
            and test_type is not RandomizedTestType.TWO_PROPORTION_Z
        ):
            blocks.append(
                block(
                    "impact.source.estimator_metric_mismatch",
                    "Binary outcome lacks binary inference.",
                )
            )
        if (
            metric_type in {MetricType.CONTINUOUS, MetricType.COUNT}
            and test_type is not RandomizedTestType.WELCH_T
        ):
            blocks.append(
                block(
                    "impact.source.estimator_metric_mismatch",
                    "Continuous/count outcome lacks compatible inference.",
                )
            )
    return tuple(blocks)


def _randomized_conditional(
    assumptions: Iterable[AssumptionAssessment],
    warnings: Iterable[BaseModel],
    evidence: EvidenceCategory | None,
) -> bool:
    return (
        evidence is EvidenceCategory.RANDOMIZED_DESIGN_WITH_LIMITED_ASSUMPTIONS
        or any(item.status is not AssumptionStatus.SUPPORTED for item in assumptions)
        or any(True for _item in warnings)
    )


__all__ = ["adapt_bayesian", "adapt_cuped", "adapt_randomized"]
