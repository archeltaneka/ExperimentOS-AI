"""Thin calls into existing randomized services; statistical formulas stay there."""

from packages.observability.base import BaseObservabilityProvider

from ..randomized.models import RandomizedAnalysisResult
from ..randomized.service import RandomizedAnalysisService
from .datasets import AnalysisDataResolver, resolve_dataset
from .requests import FixedHorizonWorkflowRequest, WorkflowAnalysisRequest


def dispatch_fixed_horizon(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> RandomizedAnalysisResult:
    if not isinstance(request, FixedHorizonWorkflowRequest):
        raise ValueError("method/request mismatch")
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    return RandomizedAnalysisService(observability_provider=provider).analyze(
        request.execution,
        dataset.table,
        request.binding,
        provenance=dataset.provenance,
    )
