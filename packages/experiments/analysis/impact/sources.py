"""Public fail-closed adapter from owned analysis results to impact evidence."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel

from ..base import ContractModel
from ..business_impact import BusinessImpactProjection
from ..causal.advanced.models import AdvancedCausalResult
from ..causal.did.models import DifferenceInDifferencesResult
from ..causal.dml.results import DMLResult
from ..causal.dowhy.models import DoWhyAnalysisResult
from ..causal.hte.results import HeterogeneousEffectResult
from ..causal.ipw.models import TreatmentEffectResult
from ..causal.models import IdentificationResult
from ..causal.propensity.models import PropensityResult
from ..estimates import (
    AssociationalEstimate,
    DescriptiveStatistic,
    ObservationalEstimate,
    QuasiExperimentalEstimate,
    RandomizedExperimentEstimate,
)
from ..provenance import ProvenanceRecord
from ..randomized.bayesian.models import BayesianAnalysisResult
from ..randomized.cuped.models import CupedAnalysisResult
from ..randomized.models import RandomizedAnalysisResult
from ..randomized.sequential.models import SequentialAnalysisHistory, SequentialLookResult
from ..results import (
    AbstainedAnalysisResult,
    CompletedAnalysisResult,
    EligibilityAssessment,
    FailedAnalysisResult,
    InconclusiveAnalysisResult,
)
from .source_causal import adapt_advanced, adapt_did, adapt_dml, adapt_hte, adapt_ipw
from .source_common import block, revalidate_exact, snapshot, value_text
from .source_models import SourceEffect
from .source_randomized import adapt_bayesian, adapt_cuped, adapt_randomized


def adapt_source(source: object, subgroup_id: str | None = None) -> SourceEffect:
    """Adapt an exact owned result, returning an auditable refusal for every failure."""
    try:
        return _adapt_source(source, subgroup_id)
    except (AttributeError, TypeError, ValueError):
        return _malformed_refusal(source)


def _adapt_source(source: object, subgroup_id: str | None = None) -> SourceEffect:
    if type(source) is RandomizedAnalysisResult:
        return adapt_randomized(source)
    if type(source) is CupedAnalysisResult:
        return adapt_cuped(source)
    if type(source) is BayesianAnalysisResult:
        return adapt_bayesian(source)
    if type(source) is TreatmentEffectResult:
        return adapt_ipw(source)
    if type(source) is DifferenceInDifferencesResult:
        return adapt_did(source)
    if type(source) is DMLResult:
        return adapt_dml(source)
    if type(source) is AdvancedCausalResult:
        return adapt_advanced(source)
    if type(source) is HeterogeneousEffectResult:
        return adapt_hte(source, subgroup_id)
    if type(source) in {SequentialLookResult, SequentialAnalysisHistory}:
        return _refuse_owned(
            source,
            expected=cast(type[ContractModel], type(source)),
            source_type="sequential_randomized",
            estimator="sequential",
            code="impact.source.sequential_unsupported",
            message="Sequential monitoring results are not eligible impact sources.",
        )
    if type(source) is DoWhyAnalysisResult:
        return _refuse_owned(
            source,
            expected=DoWhyAnalysisResult,
            source_type="dowhy",
            estimator="dowhy",
            code="impact.source.uncertainty_missing",
            message="DoWhy point evidence has no owned effect interval.",
        )
    if type(source) is IdentificationResult:
        return _refuse_owned(
            source,
            expected=IdentificationResult,
            source_type="causal_identification",
            estimator="identification",
            code="impact.source.non_effect",
            message="Causal identification is not an effect estimate.",
        )
    if type(source) is PropensityResult:
        return _refuse_owned(
            source,
            expected=PropensityResult,
            source_type="propensity",
            estimator="propensity",
            code="impact.source.non_effect",
            message="Propensity diagnostics are not an effect estimate.",
        )
    if type(source) in {
        EligibilityAssessment,
        CompletedAnalysisResult,
        InconclusiveAnalysisResult,
        AbstainedAnalysisResult,
        FailedAnalysisResult,
    }:
        return _refuse_owned(
            source,
            expected=cast(type[ContractModel], type(source)),
            source_type=value_text(getattr(source, "outcome_type", None), "analysis_outcome"),
            estimator="legacy_analysis_outcome",
            code="impact.source.unsupported_owned_result",
            message="Generic analysis outcomes are not schema-bound impact effect sources.",
        )
    if type(source) in {
        AssociationalEstimate,
        RandomizedExperimentEstimate,
        QuasiExperimentalEstimate,
        ObservationalEstimate,
        DescriptiveStatistic,
    }:
        return _refuse_finding(source)
    if type(source) is BusinessImpactProjection:
        return _refuse_owned(
            source,
            expected=BusinessImpactProjection,
            source_type="legacy_business_impact_projection",
            estimator="legacy_projection",
            code="impact.source.unsupported_owned_result",
            message="Legacy projections are not causal effect sources for new scenarios.",
        )
    return SourceEffect(
        source_type="unsupported",
        estimator="unknown",
        estimand="unknown",
        native_status="unsupported_type",
        blocking_diagnostics=(
            block(
                "impact.source.unsupported_type",
                "Object is not an exact supported ExperimentOS-owned result type.",
            ),
        ),
    )


def _malformed_refusal(source: object) -> SourceEffect:
    request_id = getattr(source, "request_id", None)
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = None
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
        source_type="invalid_owned_source",
        estimator=type(source).__name__,
        estimand="unknown",
        request_id=request_id,
        native_status="invalid_contract",
        provenance=provenance,
        blocking_diagnostics=(
            block(
                "impact.source.invalid_contract",
                "The owned source contract could not be safely adapted.",
            ),
        ),
        source_diagnostics=snapshot("source", diagnostics),
    )


def _refuse_finding(source: object) -> SourceEffect:
    expected = cast(type[ContractModel], type(source))
    validated = revalidate_exact(source, expected)
    if validated is None:
        return _malformed_refusal(source)
    details = getattr(validated, "estimate", validated)
    diagnostics = getattr(details, "diagnostics", ())
    warnings = getattr(details, "warnings", ())
    assumptions = getattr(details, "assumptions", ())
    provenance = getattr(details, "provenance", ())
    estimand = getattr(details, "estimand", None)
    status = getattr(details, "status", None)
    conclusion = getattr(validated, "conclusion_type", None)
    return SourceEffect(
        source_type=value_text(getattr(validated, "finding_type", None), "legacy_finding"),
        estimator=value_text(conclusion, "descriptive"),
        estimand=value_text(getattr(estimand, "kind", None), "none"),
        native_status=value_text(status, "unsupported"),
        provenance=provenance,
        blocking_diagnostics=(
            block(
                "impact.source.unsupported_owned_result",
                "Legacy findings are not schema-bound impact effect sources.",
            ),
        ),
        source_diagnostics=snapshot("source", diagnostics),
        source_warnings=snapshot("source", warnings),
        source_assumptions=snapshot("source", assumptions),
        source_metadata=snapshot("source", (validated,)),
    )


def _refuse_owned(
    source: object,
    *,
    expected: type[ContractModel],
    source_type: str,
    estimator: str,
    code: str,
    message: str,
) -> SourceEffect:
    validated = revalidate_exact(source, expected)
    if validated is None:
        code = "impact.source.invalid_contract"
        message = "The owned source contract failed revalidation."
    candidate: object = source if validated is None else validated
    diagnostics = getattr(candidate, "diagnostics", ())
    if not isinstance(diagnostics, tuple) or not all(
        isinstance(item, BaseModel) for item in diagnostics
    ):
        diagnostics = ()
    warnings = getattr(candidate, "warnings", ())
    if not isinstance(warnings, tuple) or not all(isinstance(item, BaseModel) for item in warnings):
        warnings = ()
    assumptions = getattr(candidate, "assumptions", ())
    if not isinstance(assumptions, tuple) or not all(
        isinstance(item, BaseModel) for item in assumptions
    ):
        assumptions = ()
    limitations = getattr(candidate, "evidence_limitations", ())
    if not isinstance(limitations, tuple) or not all(
        isinstance(item, BaseModel) for item in limitations
    ):
        limitations = ()
    provenance = getattr(candidate, "provenance", ())
    if not isinstance(provenance, tuple) or not all(
        isinstance(item, ProvenanceRecord) for item in provenance
    ):
        provenance = ()
    request_id = getattr(candidate, "request_id", None)
    if request_id is None:
        execution = getattr(candidate, "execution_request", None)
        request_id = getattr(execution, "request_id", None)
    status = getattr(candidate, "status", None)
    if status is None:
        status = getattr(candidate, "stopping_status", None)
    if status is None:
        status = getattr(candidate, "current_status", None)
    metadata: list[BaseModel] = []
    for field in (
        "configuration",
        "adapter_provenance",
        "identification",
        "estimate",
        "alpha_summary",
        "plan_integrity",
    ):
        item = getattr(candidate, field, None)
        if isinstance(item, BaseModel):
            metadata.append(item)
    refutations = getattr(candidate, "refutations", ())
    if isinstance(refutations, tuple):
        metadata.extend(item for item in refutations if isinstance(item, BaseModel))
    findings = getattr(candidate, "findings", ())
    if isinstance(findings, tuple):
        metadata.extend(item for item in findings if isinstance(item, BaseModel))
    for field in ("reason", "failures", "source_estimate"):
        item = getattr(candidate, field, None)
        if isinstance(item, BaseModel):
            metadata.append(item)
        elif isinstance(item, tuple):
            metadata.extend(value for value in item if isinstance(value, BaseModel))
    return SourceEffect(
        source_type=source_type,
        estimator=estimator,
        estimand="unknown",
        request_id=request_id,
        native_status=value_text(status, "refused"),
        provenance=provenance,
        blocking_diagnostics=(block(code, message),),
        source_diagnostics=snapshot("source", diagnostics),
        source_warnings=snapshot("source", warnings),
        source_assumptions=snapshot("source", assumptions),
        evidence_limitations=snapshot("source", limitations),
        source_metadata=snapshot("source", metadata),
    )


__all__ = ["adapt_source"]
