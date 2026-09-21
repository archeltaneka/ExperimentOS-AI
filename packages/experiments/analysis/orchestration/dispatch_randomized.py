"""Thin calls into existing randomized services; statistical formulas stay there."""

from packages.observability.base import BaseObservabilityProvider

from ..randomized.bayesian.models import BayesianAnalysisResult
from ..randomized.bayesian.service import BayesianAnalysisService
from ..randomized.cuped.models import CupedAnalysisResult
from ..randomized.cuped.service import CupedAnalysisService
from ..randomized.models import RandomizedAnalysisResult
from ..randomized.sequential.models import SequentialAnalysisHistory
from ..randomized.sequential.service import SequentialAnalysisService, SequentialLookExecution
from ..randomized.service import RandomizedAnalysisService
from .datasets import AnalysisDataResolver, resolve_dataset
from .requests import (
    BayesianWorkflowRequest,
    CupedWorkflowRequest,
    FixedHorizonWorkflowRequest,
    SequentialWorkflowRequest,
    WorkflowAnalysisRequest,
)


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


def dispatch_cuped(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> CupedAnalysisResult:
    if not isinstance(request, CupedWorkflowRequest):
        raise ValueError("method/request mismatch")
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    return CupedAnalysisService(observability_provider=provider).analyze(
        request.execution,
        dataset.table,
        request.binding,
        provenance=dataset.provenance,
    )


def dispatch_bayesian(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> BayesianAnalysisResult:
    if not isinstance(request, BayesianWorkflowRequest):
        raise ValueError("method/request mismatch")
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    return BayesianAnalysisService(observability_provider=provider).analyze(
        request.execution,
        dataset.table,
        request.binding,
        provenance=dataset.provenance,
    )


def dispatch_sequential(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> SequentialAnalysisHistory:
    if not isinstance(request, SequentialWorkflowRequest):
        raise ValueError("method/request mismatch")
    executions = []
    provenance = request.plan.provenance
    for look in request.looks:
        dataset = resolve_dataset(resolver, look.dataset, request.experiment_id)
        provenance = (*provenance, *dataset.provenance)
        executions.append(
            SequentialLookExecution(
                look_index=look.look_index,
                information_time=look.information_time,
                plan_fingerprint=look.plan_fingerprint,
                analysis_request=look.analysis_request,
                table=dataset.table,
                binding=look.binding,
                executed_at=look.executed_at,
            )
        )
    return SequentialAnalysisService(observability_provider=provider).analyze(
        request.plan,
        tuple(executions),
        provenance=provenance,
    )
