"""Lazy calls to existing optional owned adapters, never estimator fallback."""

from packages.observability.base import BaseObservabilityProvider

from ..causal.advanced.models import AdvancedCausalResult
from ..causal.dml.models import DMLExecutionRequest
from ..causal.dowhy.models import DoWhyAnalysisResult, DoWhyExecutionRequest
from ..causal.hte.models import HTEExecutionRequest
from ..causal.hte.results import HeterogeneousEffectResult
from ..causal.models import IdentificationResult, IdentificationStatus
from ..causal.service import CausalIdentificationService
from .datasets import AnalysisDataResolver, resolve_dataset
from .requests import (
    DoWhyWorkflowRequest,
    EconMLDMLWorkflowRequest,
    EconMLHTEWorkflowRequest,
    WorkflowAnalysisRequest,
)


def dispatch_econml_dml(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> AdvancedCausalResult | IdentificationResult:
    from ..causal.econml import EconMLDMLAdapter

    if not isinstance(request, EconMLDMLWorkflowRequest):
        raise ValueError("method/request mismatch")
    identification = CausalIdentificationService().identify(request.analysis_request)
    if identification.status is not IdentificationStatus.IDENTIFIED:
        return identification
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    execution = DMLExecutionRequest(
        identification_result=identification,
        binding=request.binding,
        configuration=request.configuration,
    )
    return EconMLDMLAdapter(
        configuration=request.adapter_configuration, observability_provider=provider
    ).analyze(
        execution,
        dataset.table,
        provenance=dataset.provenance,
    )


def dispatch_econml_hte(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> HeterogeneousEffectResult | IdentificationResult:
    from ..causal.econml import EconMLHTEAdapter

    if not isinstance(request, EconMLHTEWorkflowRequest):
        raise ValueError("method/request mismatch")
    identification = CausalIdentificationService().identify(request.analysis_request)
    if identification.status is not IdentificationStatus.IDENTIFIED:
        return identification
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    execution = HTEExecutionRequest(
        identification_result=identification,
        binding=request.binding,
        configuration=request.configuration,
        modifier=request.modifier,
    )
    return EconMLHTEAdapter(
        configuration=request.adapter_configuration, observability_provider=provider
    ).analyze(
        execution,
        dataset.table,
        provenance=dataset.provenance,
    )


def dispatch_dowhy(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> DoWhyAnalysisResult | IdentificationResult:
    from ..causal.dowhy.adapter import DoWhyAdapter

    if not isinstance(request, DoWhyWorkflowRequest):
        raise ValueError("method/request mismatch")
    identification = CausalIdentificationService().identify(request.analysis_request)
    if identification.status is not IdentificationStatus.IDENTIFIED:
        return identification
    dataset = (
        resolve_dataset(resolver, request.dataset, request.experiment_id)
        if request.dataset is not None
        else None
    )
    execution = DoWhyExecutionRequest(
        identification_result=identification,
        binding=request.binding,
        configuration=request.configuration,
    )
    return DoWhyAdapter(observability_provider=provider).analyze(
        execution,
        dataset.table if dataset else None,
        provenance=dataset.provenance if dataset else identification.provenance,
    )
