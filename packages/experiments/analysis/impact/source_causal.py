"""Adapters for owned causal effect results and HTE subgroup selections."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel

from ..causal.advanced.models import AdvancedCausalResult
from ..causal.advanced.quality import evaluate_advanced_quality
from ..causal.assumptions import CausalAssumption, CausalAssumptionStatus
from ..causal.designs import CausalOutcome, TimeSemantics, UnitSemantics
from ..causal.did.models import DidStatus, DifferenceInDifferencesResult
from ..causal.dml.results import DMLResult, DMLStatus
from ..causal.estimands import CausalEstimand, EffectScale, TargetPopulationKind
from ..causal.hte.assignment import subgroup_rule
from ..causal.hte.quality import evaluate_hte_quality
from ..causal.hte.results import (
    HeterogeneousEffectResult,
    HTEStatus,
    HTESubgroupStatus,
    SubgroupEffectResult,
)
from ..causal.ipw.models import IPWBalanceStatus, IPWStatus, TreatmentEffectResult
from ..causal.models import (
    IdentificationResult,
    IdentificationStatus,
    ObservationalAnalysisRequest,
)
from ..causal.propensity.models import OverlapStatus
from ..causal.service import CausalIdentificationService
from ..metrics import MetricType
from ..populations import PopulationDefinition
from ..provenance import Diagnostic, ProvenanceRecord
from ..uncertainty import ConfidenceInterval
from .source_common import (
    block,
    interval_contains,
    native_diagnostic_blocks,
    revalidate_exact,
    snapshot,
    unique_blocks,
    value_text,
)
from .source_models import EffectScaleName, SourceEffect, SourceRecord, TargetKind


def adapt_ipw(source: TreatmentEffectResult) -> SourceEffect:
    result = revalidate_exact(source, TreatmentEffectResult)
    if result is None:
        return _invalid(source, "ipw")
    blocks = list(native_diagnostic_blocks(result.diagnostics))
    blocks.extend(_causal_assumption_blocks(result.assumptions))
    identification, identification_blocks = _reidentify(
        result.analysis_request,
        result.estimand,
        result.outcome,
        result.target_population.population if result.target_population else None,
    )
    blocks.extend(identification_blocks)
    if result.status is not IPWStatus.COMPLETED:
        blocks.append(_native_status_block(result.status.value))
    if result.overlap.status in {OverlapStatus.SEVERE, OverlapStatus.UNAVAILABLE}:
        blocks.append(block("impact.source.overlap_blocking", "IPW overlap is not usable."))
    if result.balance_status in {IPWBalanceStatus.SEVERE, IPWBalanceStatus.UNAVAILABLE}:
        blocks.append(
            block(
                "impact.source.balance_blocking",
                "IPW residual balance is not usable.",
            )
        )
    return _causal_effect(
        source_type="ipw",
        estimator="ipw",
        request_id=result.request_id,
        status=result.status.value,
        estimand=result.estimand,
        outcome=result.outcome,
        units=(result.analysis_request.identification.units),
        time=result.analysis_request.identification.time,
        point=result.point_estimate,
        interval=(result.test_result.confidence_interval if result.test_result else None),
        population=(result.target_population.population if result.target_population else None),
        provenance=result.provenance,
        fingerprint=(result.score_model.fingerprint_sha256 if result.score_model else None),
        diagnostics=snapshot("source", result.diagnostics)
        + snapshot("identification", identification.diagnostics),
        warnings=snapshot("source", result.warnings)
        + snapshot("sensitivity", result.sensitivity_flags),
        assumptions=snapshot("source", result.assumptions),
        limitations=snapshot("source", result.evidence_limitations)
        + snapshot("identification", identification.evidence_limitations),
        blocks=blocks,
        metadata=snapshot("configuration", (result.configuration, result.score_model))
        if result.score_model is not None
        else snapshot("configuration", (result.configuration,)),
    )


def adapt_did(source: DifferenceInDifferencesResult) -> SourceEffect:
    result = revalidate_exact(source, DifferenceInDifferencesResult)
    if result is None:
        return _invalid(source, "did")
    blocks = list(native_diagnostic_blocks(result.diagnostics))
    blocks.extend(_causal_assumption_blocks(result.assumptions))
    identification, identification_blocks = _reidentify(
        result.analysis_request,
        result.estimand,
        result.outcome,
        result.population,
    )
    blocks.extend(identification_blocks)
    if result.status is not DidStatus.COMPLETED:
        blocks.append(_native_status_block(result.status.value))
    return _causal_effect(
        source_type="did",
        estimator="did",
        request_id=result.request_id,
        status=result.status.value,
        estimand=result.estimand,
        outcome=result.outcome,
        units=result.units,
        time=result.time,
        point=(result.cell_means.did_estimate if result.cell_means else None),
        interval=(result.test_result.confidence_interval if result.test_result else None),
        population=result.population,
        provenance=result.provenance,
        fingerprint=None,
        diagnostics=snapshot("source", result.diagnostics)
        + snapshot("identification", identification.diagnostics),
        warnings=snapshot("source", result.warnings),
        assumptions=snapshot("source", result.assumptions),
        limitations=snapshot("source", result.evidence_limitations)
        + snapshot("identification", identification.evidence_limitations),
        blocks=blocks,
        metadata=snapshot(
            "did",
            (result.configuration, result.pretrend, result.sample_counts),
        ),
    )


def adapt_dml(source: DMLResult) -> SourceEffect:
    result = revalidate_exact(source, DMLResult)
    if result is None:
        return _invalid(source, "dml")
    blocks = list(native_diagnostic_blocks(result.diagnostics))
    blocks.extend(_causal_assumption_blocks(result.assumptions))
    identification, identification_blocks = _reidentify(
        result.analysis_request,
        result.estimand,
        result.outcome,
        result.target_population.population if result.target_population else None,
    )
    blocks.extend(identification_blocks)
    if result.status is not DMLStatus.COMPLETED:
        blocks.append(_native_status_block(result.status.value))
    if result.overlap is None or result.overlap.status in {
        OverlapStatus.SEVERE,
        OverlapStatus.UNAVAILABLE,
    }:
        blocks.append(block("impact.source.overlap_blocking", "DML overlap is not usable."))
    return _causal_effect(
        source_type="dml",
        estimator="dml",
        request_id=result.request_id,
        status=result.status.value,
        estimand=result.estimand,
        outcome=result.outcome,
        units=result.analysis_request.identification.units,
        time=result.analysis_request.identification.time,
        point=result.point_estimate,
        interval=(result.test_result.confidence_interval if result.test_result else None),
        population=(result.target_population.population if result.target_population else None),
        provenance=result.provenance,
        fingerprint=result.configuration_fingerprint_sha256,
        diagnostics=snapshot("source", result.diagnostics)
        + snapshot("identification", identification.diagnostics),
        warnings=snapshot("source", result.warnings)
        + snapshot("sensitivity", result.sensitivity_flags),
        assumptions=snapshot("source", result.assumptions),
        limitations=snapshot("source", result.evidence_limitations)
        + snapshot("identification", identification.evidence_limitations),
        blocks=blocks,
        metadata=snapshot(
            "dml",
            tuple(
                item
                for item in (
                    result.configuration,
                    result.sample_counts,
                    result.nuisance_diagnostics,
                    result.outcome_residual_diagnostics,
                    result.treatment_residual_diagnostics,
                    result.influence_diagnostics,
                    result.overlap,
                    *result.fold_fits,
                )
                if item is not None
            ),
        ),
    )


def adapt_advanced(source: AdvancedCausalResult) -> SourceEffect:
    result = revalidate_exact(source, AdvancedCausalResult)
    if result is None:
        return _invalid(source, "econml_dml")
    identification = result.execution_request.identification_result
    blocks: list[Diagnostic] = list(native_diagnostic_blocks(result.diagnostics))
    blocks.extend(_causal_assumption_blocks(identification.assumptions))
    if result.status is not DMLStatus.COMPLETED:
        blocks.append(_native_status_block(result.status.value))
    blocks.extend(evaluate_advanced_quality(result).blocking_findings)
    estimator = (
        f"econml_{result.adapter_provenance.estimator_class}"
        if result.adapter_provenance is not None
        else "econml_dml"
    )
    return _causal_effect(
        source_type="advanced_causal",
        estimator=estimator,
        request_id=identification.request_id,
        status=result.status.value,
        estimand=identification.estimand,
        outcome=identification.outcome,
        units=identification.units,
        time=identification.time,
        point=result.point_estimate,
        interval=(result.inference.confidence_interval if result.inference else None),
        population=(
            identification.estimand.target_population.population
            if identification.estimand is not None
            else identification.population
        ),
        provenance=result.provenance,
        fingerprint=result.configuration_fingerprint_sha256,
        diagnostics=snapshot("source", result.diagnostics)
        + snapshot("identification", identification.diagnostics),
        warnings=snapshot("identification", identification.warnings),
        assumptions=snapshot("identification", identification.assumptions),
        limitations=snapshot("source", result.evidence_limitations)
        + snapshot("identification", identification.evidence_limitations),
        blocks=blocks,
        metadata=snapshot(
            "advanced",
            tuple(
                item
                for item in (
                    result.configuration,
                    result.adapter_provenance,
                    result.sample_counts,
                    result.overlap,
                    result.nuisance_diagnostics,
                    *result.fold_fits,
                )
                if item is not None
            ),
        ),
    )


def adapt_hte(source: HeterogeneousEffectResult, subgroup_id: str | None) -> SourceEffect:
    result = revalidate_exact(source, HeterogeneousEffectResult)
    if result is None:
        return _invalid(source, "hte")
    identification = result.execution_request.identification_result
    all_diagnostics = snapshot("parent", result.diagnostics) + snapshot(
        "identification", identification.diagnostics
    )
    identification_warnings = snapshot("identification", identification.warnings)
    blocks: list[Diagnostic] = []
    if result.status is not HTEStatus.COMPLETED:
        blocks.append(_native_status_block(result.status.value))
    if identification.status is not IdentificationStatus.IDENTIFIED:
        blocks.append(
            block(
                "impact.source.identification_invalid",
                "HTE requires an identified parent request.",
            )
        )
    if result.modifier != result.execution_request.modifier:
        blocks.append(
            block(
                "impact.source.subgroup_definition_mismatch",
                "HTE result modifier does not match its execution request.",
            )
        )
    blocks.extend(_causal_assumption_blocks(result.assumptions))
    if result.adapter_provenance is not None:
        blocks.extend(
            finding
            for finding in evaluate_advanced_quality(result).blocking_findings
            if not finding.code.startswith("hte.quality.")
        )
    if subgroup_id is None:
        blocks.append(
            block(
                "impact.source.subgroup_required",
                "One owned HTE subgroup must be selected explicitly.",
            )
        )
        return _hte_effect(
            result,
            None,
            identification,
            all_diagnostics,
            blocks,
            warnings=identification_warnings,
        )

    selected = next(
        (item for item in result.subgroup_results if item.subgroup_id == subgroup_id), None
    )
    definition = next(
        (item for item in result.modifier.subgroups if item.subgroup_id == subgroup_id), None
    )
    if selected is None or definition is None:
        blocks.append(
            block(
                "impact.source.subgroup_unknown", "Selected subgroup is not owned by this result."
            )
        )
        return _hte_effect(
            result,
            None,
            identification,
            all_diagnostics,
            blocks,
            warnings=identification_warnings,
            subgroup_id=subgroup_id,
        )

    scoped_native = tuple(
        item
        for item in result.diagnostics
        if item.subgroup_id is None or item.subgroup_id == subgroup_id
    ) + tuple(selected.diagnostics)
    blocks.extend(native_diagnostic_blocks(scoped_native))
    if selected.status is not HTESubgroupStatus.COMPLETED:
        blocks.append(block("impact.source.subgroup_status", "Selected subgroup did not complete."))
    if selected.rule != subgroup_rule(result.execution_request, definition):
        blocks.append(
            block(
                "impact.source.subgroup_rule_mismatch",
                "Selected subgroup rule does not match its structured definition.",
            )
        )
    if selected.overlap is None or selected.overlap.status in {
        OverlapStatus.SEVERE,
        OverlapStatus.UNAVAILABLE,
    }:
        blocks.append(
            block(
                "impact.source.subgroup_overlap_missing",
                "Selected subgroup requires usable overlap evidence.",
            )
        )
    quality = evaluate_hte_quality(result)
    for finding in quality.blocking_findings:
        if finding.subgroup_id is None or finding.subgroup_id == subgroup_id:
            blocks.append(block(finding.code, finding.message))
    advisory = tuple(
        finding
        for finding in quality.advisory_findings
        if finding.subgroup_id is None or finding.subgroup_id == subgroup_id
    )
    return _hte_effect(
        result,
        selected,
        identification,
        all_diagnostics + snapshot("selected_subgroup", selected.diagnostics),
        blocks,
        warnings=identification_warnings + snapshot("quality", advisory),
        subgroup_id=subgroup_id,
    )


def _hte_effect(
    result: HeterogeneousEffectResult,
    selected: SubgroupEffectResult | None,
    identification: IdentificationResult,
    diagnostics: tuple[SourceRecord, ...],
    blocks: Iterable[Diagnostic],
    *,
    warnings: tuple[SourceRecord, ...] = (),
    subgroup_id: str | None = None,
) -> SourceEffect:
    estimand = getattr(identification, "estimand", None)
    outcome = getattr(identification, "outcome", None)
    units = getattr(identification, "units", None)
    time = getattr(identification, "time", None)
    typed_blocks = list(blocks)
    effect_scale = _effect_scale(estimand, outcome)
    if effect_scale is None:
        typed_blocks.append(
            block("impact.source.metric_scale_unsupported", "Causal effect scale is unsupported.")
        )
    final_blocks = unique_blocks(typed_blocks)
    point = getattr(selected, "estimate", None)
    interval = getattr(selected, "confidence_interval", None)
    if point is not None and interval is not None and not interval_contains(point, interval):
        final_blocks = unique_blocks(
            (
                *final_blocks,
                block(
                    "impact.source.interval_point_mismatch",
                    "Selected subgroup interval does not contain its point estimate.",
                ),
            )
        )
    method = (
        "econml_hte"
        if result.adapter_provenance is not None
        else "hte_doubly_robust"
        if result.method == "doubly_robust_subgroup_effects"
        else "hte_dml"
    )
    population = estimand.target_population.population if estimand is not None else None
    return SourceEffect(
        source_type="heterogeneous_effect",
        estimator=method,
        estimand=(estimand.estimand_type.value if estimand is not None else "cate"),
        request_id=result.request_id,
        native_status=result.status.value,
        metric=(outcome.metric if outcome is not None else None),
        population=population,
        analysis_unit=(units.analysis_unit if units is not None else None),
        observed_period=(time.post_period if time is not None else None),
        point=None if final_blocks else point,
        interval=None if final_blocks else interval,
        effect_scale=effect_scale,
        target_kind="conditioned",
        subgroup_id=subgroup_id,
        subgroup_rule=(getattr(selected, "rule", None) if selected is not None else None),
        conditional=True,
        provenance=result.provenance,
        fingerprint=result.configuration_fingerprint_sha256,
        blocking_diagnostics=final_blocks,
        source_diagnostics=diagnostics,
        source_warnings=warnings,
        source_assumptions=snapshot("source", result.assumptions),
        evidence_limitations=snapshot("identification", identification.evidence_limitations),
        source_metadata=snapshot(
            "hte",
            (
                result.execution_request.configuration,
                result.modifier,
                result.global_heterogeneity,
                result.multiplicity,
                *(() if result.adapter_provenance is None else (result.adapter_provenance,)),
            ),
        ),
    )


def _causal_effect(
    *,
    source_type: str,
    estimator: str,
    request_id: str,
    status: str,
    estimand: CausalEstimand | None,
    outcome: CausalOutcome | None,
    units: UnitSemantics | None,
    time: TimeSemantics | None,
    point: float | None,
    interval: ConfidenceInterval | None,
    population: PopulationDefinition | None,
    provenance: tuple[ProvenanceRecord, ...],
    fingerprint: str | None,
    diagnostics: tuple[SourceRecord, ...],
    warnings: tuple[SourceRecord, ...],
    assumptions: tuple[SourceRecord, ...],
    limitations: tuple[SourceRecord, ...],
    blocks: Iterable[Diagnostic],
    metadata: tuple[SourceRecord, ...] = (),
) -> SourceEffect:
    typed_blocks = list(blocks)
    if estimand is None or outcome is None:
        typed_blocks.append(
            block(
                "impact.source.identification_missing",
                "Complete estimand and outcome are required.",
            )
        )
    effect_scale = _effect_scale(estimand, outcome)
    if effect_scale is None:
        typed_blocks.append(
            block("impact.source.metric_scale_unsupported", "Causal effect scale is unsupported.")
        )
    if point is None or interval is None:
        typed_blocks.append(
            block(
                "impact.source.uncertainty_missing",
                "Point estimate and compatible interval are required.",
            )
        )
    elif not interval_contains(point, interval):
        typed_blocks.append(
            block(
                "impact.source.interval_point_mismatch",
                "Source interval does not contain its point estimate.",
            )
        )
    final_blocks = unique_blocks(typed_blocks)
    return SourceEffect(
        source_type=source_type,
        estimator=estimator,
        estimand=(estimand.estimand_type.value if estimand is not None else "unknown"),
        request_id=request_id,
        native_status=status,
        metric=(outcome.metric if outcome is not None else None),
        population=population,
        analysis_unit=(units.analysis_unit if units is not None else None),
        observed_period=(time.post_period if time is not None else None),
        point=None if final_blocks else point,
        interval=None if final_blocks else interval,
        effect_scale=effect_scale,
        target_kind=_target_kind(estimand),
        conditional=True,
        provenance=provenance,
        fingerprint=fingerprint,
        blocking_diagnostics=final_blocks,
        source_diagnostics=diagnostics,
        source_warnings=warnings,
        source_assumptions=assumptions,
        evidence_limitations=limitations,
        source_metadata=metadata,
    )


def _effect_scale(
    estimand: CausalEstimand | None, outcome: CausalOutcome | None
) -> EffectScaleName | None:
    if estimand is None or outcome is None:
        return None
    metric_type = outcome.metric.metric.metric_type
    if estimand.effect_scale is EffectScale.RISK_DIFFERENCE:
        return (
            "absolute_binary" if metric_type in {MetricType.BINARY, MetricType.PROPORTION} else None
        )
    if estimand.effect_scale is EffectScale.RISK_RATIO:
        # Owned native estimators currently report difference-scale points and
        # intervals.  A risk-ratio declaration cannot relabel those values.
        return None
    if estimand.effect_scale is EffectScale.MEAN_DIFFERENCE:
        return "absolute_binary" if metric_type is MetricType.BINARY else "continuous"
    return None


def _target_kind(estimand: CausalEstimand | None) -> TargetKind | None:
    if estimand is None:
        return None
    if estimand.target_population.kind is TargetPopulationKind.FULL:
        return "full"
    if estimand.target_population.kind is TargetPopulationKind.TREATED:
        return "treated"
    return "conditioned"


def _invalid(source: object, estimator: str) -> SourceEffect:
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
    return SourceEffect(
        source_type=estimator,
        estimator=estimator,
        estimand="unknown",
        request_id=getattr(source, "request_id", None),
        native_status=value_text(getattr(source, "status", None), "invalid_contract"),
        provenance=provenance,
        blocking_diagnostics=(
            block(
                "impact.source.invalid_contract", "The owned source contract failed revalidation."
            ),
        ),
        source_diagnostics=snapshot("source", diagnostics),
    )


def _native_status_block(status: str) -> Diagnostic:
    return block(
        "impact.source.native_status",
        f"Source status {status!r} does not provide an eligible effect.",
    )


def _reidentify(
    request: ObservationalAnalysisRequest,
    estimand: CausalEstimand | None,
    outcome: CausalOutcome | None,
    population: PopulationDefinition | None,
) -> tuple[IdentificationResult, tuple[Diagnostic, ...]]:
    identified = CausalIdentificationService().identify(request)
    blocks: list[Diagnostic] = []
    if identified.status is not IdentificationStatus.IDENTIFIED:
        blocks.append(
            block(
                "impact.source.identification_invalid",
                "Source declarations do not pass causal identification.",
            )
        )
    identified_population = (
        identified.estimand.target_population.population
        if identified.estimand is not None
        else None
    )
    if (
        estimand != identified.estimand
        or outcome != identified.outcome
        or population != identified_population
    ):
        blocks.append(
            block(
                "impact.source.identification_echo_mismatch",
                "Source effect identity does not match its identified declarations.",
            )
        )
    return identified, tuple(blocks)


def _causal_assumption_blocks(
    assumptions: Iterable[CausalAssumption],
) -> tuple[Diagnostic, ...]:
    if any(item.status is CausalAssumptionStatus.VIOLATED for item in assumptions):
        return (
            block(
                "impact.source.assumption_violated",
                "A required causal assumption is violated.",
            ),
        )
    return ()


__all__ = ["adapt_advanced", "adapt_did", "adapt_dml", "adapt_hte", "adapt_ipw"]
