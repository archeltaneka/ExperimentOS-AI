"""Real graph integration with local data and no retrieval or live LLM."""

import pytest

from packages.agents.nodes import planner_node
from packages.agents.service import AgentWorkflowService
from packages.agents.state import create_initial_state, validate_state_shape
from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService
from tests.test_analysis_dispatch_causal import causal_case
from tests.test_analysis_service import fixed_case


class ForbiddenAgent:
    def run(self, state):
        pytest.fail("structured analysis must not use retrieval or legacy aggregate analysis")


def test_optional_state_fields_survive_planner_and_validation():
    request, _ = fixed_case()
    state = create_initial_state("Analyze", analysis_request=request)
    assert validate_state_shape(state)["analysis_request"] == request
    update = planner_node(state)
    assert update["analysis_request"] == request
    assert update["required_agents"] == ["experiment_analysis", "executive_summary"]
    assert create_initial_state("Tell me about checkout").get("analysis_request") is None


@pytest.mark.parametrize("method", ["randomized_fixed_horizon", "did"])
def test_real_workflow_preserves_service_evidence(method):
    request, dataset = fixed_case() if method == "randomized_fixed_horizon" else causal_case(method)
    expected = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    workflow = AgentWorkflowService(
        retrieval_agent=ForbiddenAgent(), experiment_analysis_agent=ForbiddenAgent()
    )
    state = workflow.run(
        "Analyze supplied data",
        experiment_id="experiment-a",
        analysis_request=request,
        analysis_datasets=(dataset,),
    )
    assert state["analysis_result"].evidence == expected.evidence
    assert state["analysis_request"] == request
    assert not state["experiment_analysis"]["statistical_significance"]
    assert not state["errors"]


def test_unsupported_request_never_falls_back_to_legacy_agent():
    request = normalize_analysis_input({"method": "try_everything"}, experiment_id="experiment-a")
    state = AgentWorkflowService(
        retrieval_agent=ForbiddenAgent(), experiment_analysis_agent=ForbiddenAgent()
    ).run("Analyze", analysis_request=request, experiment_id="experiment-a")
    assert state["analysis_result"].status == "abstained"
    assert state["analysis_result"].method == "try_everything"
    assert not state["experiment_metrics"]
