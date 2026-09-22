"""Business prerequisite gates and public projections; no arithmetic lives here."""

from typing import Literal

from ..base import ContractModel
from ..impact import inputs as inputs
from ..impact.results import BusinessImpactResult, CostBreakdown, Derivation, DerivedQuantity
from ..impact.service import BusinessImpactService
from ..impact.sources import adapt_source
from ..provenance import AnalysisWarning, Diagnostic, ProvenanceRecord
from ..results import AbstentionReason
from ..uncertainty import ConfidenceInterval, CredibleInterval
from .requests import BusinessInputRefusal, refusal_diagnostic, refusal_reason


class BusinessInputsEvidence(ContractModel):
    request_id: str
    output: Literal["outcome", "gross", "net"]
    population: inputs.PopulationInput
    exposure: inputs.ExposureInput
    horizon: inputs.TimeHorizon
    binding: inputs.EffectBinding
    baseline: inputs.BaselineRate | None
    exposure_conversion: inputs.ExposureConversion | None
    conversion: inputs.MonetaryConversion | None
    costs: inputs.CostDeclaration | None
    persistence: inputs.PersistenceAssumption | None
    repetition: inputs.PopulationRepetition | None
    subgroup_id: str | None


class BusinessImpactEvidence(ContractModel):
    status: Literal["completed", "inconclusive", "abstained", "failed"]
    inputs: BusinessInputsEvidence | None = None
    source_fingerprint: str | None = None
    source_point: float | None = None
    source_interval: ConfidenceInterval | CredibleInterval | None = None
    horizon_kind: Literal["observed", "extrapolated"] | None = None
    population_multiplier: float | None = None
    exposed_population: DerivedQuantity | None = None
    gross_incremental_outcome: DerivedQuantity | None = None
    gross_monetary_impact: DerivedQuantity | None = None
    declared_costs: DerivedQuantity | None = None
    cost_breakdown: tuple[CostBreakdown, ...] = ()
    net_monetary_impact: DerivedQuantity | None = None
    derivations: tuple[Derivation, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    warnings: tuple[AnalysisWarning, ...] = ()
    provenance: tuple[ProvenanceRecord, ...] = ()
    abstention: AbstentionReason | None = None


def business_refusal(code: str, diagnostics: tuple[Diagnostic, ...] = ()) -> BusinessImpactEvidence:
    return BusinessImpactEvidence(
        status="abstained",
        abstention=refusal_reason(code),
        diagnostics=diagnostics or (refusal_diagnostic(code),),
    )


def business_preconditions(
    native: object, request: inputs.BusinessImpactRequest | BusinessInputRefusal | None, status: str
) -> BusinessImpactEvidence | None:
    if status not in {"completed", "inconclusive"}:
        return business_refusal("analysis.business.upstream_ineligible")
    if request is None:
        return business_refusal("analysis.business.inputs_missing")
    if isinstance(request, BusinessInputRefusal):
        return BusinessImpactEvidence(
            status="abstained", diagnostics=request.diagnostics, abstention=request.abstention
        )
    source = adapt_source(native, subgroup_id=request.subgroup_id)
    if not source.calculable:
        return business_refusal("analysis.business.source_ineligible", source.blocking_diagnostics)
    return None


def project_business(result: BusinessImpactResult) -> BusinessImpactEvidence:
    special = {
        "inputs",
        "source_fingerprint",
        "source_point",
        "source_interval",
        "provenance",
        "abstention",
    }
    values = {
        field: getattr(result, field)
        for field in BusinessImpactEvidence.model_fields
        if field not in special
    }
    request = result.inputs
    values["inputs"] = (
        BusinessInputsEvidence.model_validate(
            {field: getattr(request, field) for field in BusinessInputsEvidence.model_fields}
        )
        if request
        else None
    )
    provenance = result.source.provenance
    if request:
        provenance = (
            *provenance,
            *(p for item in inputs.input_evidence(request) for p in item.provenance),
        )
    values.update(
        source_fingerprint=result.source.fingerprint,
        source_point=result.source.point,
        source_interval=result.source.interval,
        abstention=result.abstention_reason,
        provenance=provenance,
    )
    return BusinessImpactEvidence.model_validate(values)


def analyze_business(
    native: object, request: inputs.BusinessImpactRequest | BusinessInputRefusal | None, status: str
) -> BusinessImpactEvidence:
    refused = business_preconditions(native, request, status)
    if refused is not None:
        return refused
    assert isinstance(request, inputs.BusinessImpactRequest)
    try:
        return project_business(BusinessImpactService().analyze(native, request))
    except Exception:
        return BusinessImpactEvidence(
            status="failed", diagnostics=(refusal_diagnostic("analysis.business.failure"),)
        )
