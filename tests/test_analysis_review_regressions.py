"""Independent regressions for whole-branch review findings."""

import asyncio

import pytest

from apps.api.ask_service import AgentWorkflowAskService, AskRequest
from packages.agents.service import AgentWorkflowService
from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.registry import default_registry
from packages.experiments.analysis.orchestration.service import AnalysisService
from packages.observability.noop import NoOpObservabilityProvider
from tests.test_agent_analysis_workflow import ForbiddenAgent
from tests.test_analysis_dispatch_causal import causal_case
from tests.test_api_analysis import ask_payload


@pytest.mark.parametrize("method", ["did", "propensity_diagnostics", "ipw_ate", "dml", "hte"])
def test_safe_native_context_and_diagnostics_survive_projection(method):
    request, dataset = causal_case(method)
    resolver = RequestDatasetResolver((dataset,))
    native = (
        default_registry().resolve(method).handler(request, resolver, NoOpObservabilityProvider())
    )
    result = AnalysisService(resolver=resolver).analyze(request)
    evidence = result.evidence
    declaration = (
        native.analysis_request.identification
        if hasattr(native, "analysis_request")
        else native.execution_request.identification_result.identification_request
    )
    assert evidence.context.outcome == declaration.outcome
    assert evidence.context.units == declaration.units
    if method == "propensity_diagnostics":
        assert evidence.weights.ess == native.weights.ess
        assert evidence.model_provenance == native.model_provenance
        assert evidence.model_fit.status == native.model_fit.status
        assert evidence.model_fit.sklearn_version == native.model_fit.sklearn_version
    if method == "ipw_ate":
        assert evidence.score_model == native.score_model
    if method in {"dml", "hte"}:
        assert evidence.fold_fits == native.fold_fits
        assert evidence.fold_plan.summaries == native.fold_plan.summaries
    text = result.model_dump_json()
    for forbidden in ('"scores":', '"assignments":', '"observation_id":'):
        assert forbidden not in text


def test_orphan_datasets_abstain_in_api_and_direct_workflow():
    payload = ask_payload()
    payload.pop("analysis")
    request = AskRequest.model_validate(payload)
    workflow = AgentWorkflowService(retrieval_agent=ForbiddenAgent())
    response = asyncio.run(AgentWorkflowAskService(workflow).answer(request))
    assert response.analysis.status == "abstained"
    assert response.analysis.abstention.code == "analysis.method_ambiguous"
    state = workflow.run(
        "Analyze", experiment_id=request.experiment_id, analysis_datasets=request.analysis_datasets
    )
    assert state["analysis_result"].status == "abstained"
