"""Explicit owned causal dispatch. Identification is never supplied by a caller."""

from datetime import datetime

from packages.observability.base import BaseObservabilityProvider

from ..causal.did.models import DifferenceInDifferencesResult
from ..causal.did.service import DifferenceInDifferencesService
from ..causal.dml.models import DMLExecutionRequest
from ..causal.dml.results import DMLResult
from ..causal.dml.service import DoubleMachineLearningEstimator
from ..causal.hte.models import HTEExecutionRequest
from ..causal.hte.results import HeterogeneousEffectResult
from ..causal.hte.service import HeterogeneousEffectEstimator
from ..causal.ipw.models import IPWExecutionRequest, TreatmentEffectResult
from ..causal.ipw.service import IPWTreatmentEffectEstimator
from ..causal.models import IdentificationResult, IdentificationStatus
from ..causal.propensity.models import (
    PropensityExecutionRequest,
    PropensityResult,
    PropensityStatus,
)
from ..causal.propensity.service import DeterministicLogisticPropensityEstimator
from ..causal.service import CausalIdentificationService
from ..validation import AnalysisTable
from .datasets import AnalysisDataResolver, resolve_dataset
from .requests import (
    DidWorkflowRequest,
    DMLWorkflowRequest,
    HTEWorkflowRequest,
    IPWWorkflowRequest,
    PropensityWorkflowRequest,
    WorkflowAnalysisRequest,
)


def dispatch_did(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> DifferenceInDifferencesResult:
    if not isinstance(request, DidWorkflowRequest):
        raise ValueError("method/request mismatch")
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    # Decode only the declared time column. Invalid strings remain invalid.
    table = dataset.table
    for time_column in (
        request.execution.binding.time_column,
        request.execution.binding.treatment_start_column,
    ):
        if time_column not in table.columns:
            continue
        position = table.columns.index(time_column)
        rows = []
        for row in table.rows:
            values = list(row)
            value = values[position]
            if isinstance(value, str):
                try:
                    values[position] = datetime.fromisoformat(value)
                except ValueError:
                    pass
            rows.append(tuple(values))
        table = AnalysisTable(columns=table.columns, rows=tuple(rows))
    return DifferenceInDifferencesService(observability_provider=provider).analyze(
        request.execution,
        table,
        provenance=dataset.provenance,
    )


def dispatch_propensity(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> PropensityResult | IdentificationResult:
    if not isinstance(request, PropensityWorkflowRequest):
        raise ValueError("method/request mismatch")
    identification = CausalIdentificationService().identify(request.execution.analysis_request)
    if identification.status is not IdentificationStatus.IDENTIFIED:
        return identification
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    return DeterministicLogisticPropensityEstimator(observability_provider=provider).fit_predict(
        request.execution,
        dataset.table,
        provenance=dataset.provenance,
    )


def dispatch_ipw(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> TreatmentEffectResult | PropensityResult | IdentificationResult:
    if not isinstance(request, IPWWorkflowRequest):
        raise ValueError("method/request mismatch")
    identification = CausalIdentificationService().identify(request.analysis_request)
    if identification.status is not IdentificationStatus.IDENTIFIED:
        return identification
    dataset = resolve_dataset(resolver, request.dataset, request.experiment_id)
    propensity = DeterministicLogisticPropensityEstimator(
        observability_provider=provider
    ).fit_predict(
        PropensityExecutionRequest(
            analysis_request=request.analysis_request,
            binding=request.propensity_binding,
            configuration=request.propensity_configuration,
        ),
        dataset.table,
        provenance=dataset.provenance,
    )
    if propensity.status is not PropensityStatus.COMPLETED:
        return propensity
    execution = IPWExecutionRequest(
        identification_result=identification,
        propensity_result=propensity,
        binding=request.binding,
        configuration=request.configuration,
    )
    return IPWTreatmentEffectEstimator(observability_provider=provider).analyze(
        execution,
        dataset.table,
        provenance=dataset.provenance,
    )


def dispatch_dml(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> DMLResult | IdentificationResult:
    if not isinstance(request, DMLWorkflowRequest):
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
    return DoubleMachineLearningEstimator(observability_provider=provider).analyze(
        execution,
        dataset.table,
        provenance=dataset.provenance,
    )


def dispatch_hte(
    request: WorkflowAnalysisRequest,
    resolver: AnalysisDataResolver,
    provider: BaseObservabilityProvider,
) -> HeterogeneousEffectResult | IdentificationResult:
    if not isinstance(request, HTEWorkflowRequest):
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
    return HeterogeneousEffectEstimator(observability_provider=provider).analyze(
        execution,
        dataset.table,
        provenance=dataset.provenance,
    )
