"""Statistical success is not product readiness or approval."""

import pytest

from packages.agents.service import AgentWorkflowService
from tests.test_agent_analysis_workflow import ForbiddenAgent
from tests.test_analysis_service import fixed_case


def test_positive_analysis_does_not_authorize_rollout():
    request, dataset = fixed_case()
    state = AgentWorkflowService(retrieval_agent=ForbiddenAgent()).run(
        "Should we launch?",
        experiment_id="experiment-a",
        analysis_request=request,
        analysis_datasets=(dataset,),
    )
    assert state["analysis_result"].status == "completed"
    assert state["decision"]["recommendation"] == "needs_more_data"
    assert "readiness" in state["decision"]["rationale"].lower()


def test_analysis_alone_leaves_decision_not_required():
    request, dataset = fixed_case()
    state = AgentWorkflowService(retrieval_agent=ForbiddenAgent()).run(
        "Analyze", analysis_request=request, analysis_datasets=(dataset,)
    )
    assert state["decision"]["decision_status"] == "not_required"


@pytest.mark.parametrize("status", ["pending", "approved", "rejected", "revision_requested"])
def test_structured_evidence_cannot_clear_existing_approval_requirement(status):
    from packages.agents.decision_agent import DecisionAgent
    from packages.agents.human_approval_agent import HumanApprovalAgent
    from packages.agents.state import create_initial_state
    from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
    from packages.experiments.analysis.orchestration.service import AnalysisService

    request, dataset = fixed_case()
    state = create_initial_state(
        "Should we launch?",
        analysis_request=request,
        human_approval_input={}
        if status == "pending"
        else {"status": status, "actor": "reviewer", "feedback": "Reviewed evidence"},
    )
    state["analysis_result"] = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(
        request
    )
    state["decision"]["approval_required"] = True
    state.update(DecisionAgent().run(state))
    update = HumanApprovalAgent().run(state)
    assert state["decision"]["approval_required"]
    assert update["human_approval"]["required"]
    assert update["human_approval"]["status"] == status


def test_business_executes_through_workflow_and_preserves_analysis():
    from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
    from tests.test_analysis_business_gating import business_case

    payload, dataset = business_case()
    state = AgentWorkflowService(retrieval_agent=ForbiddenAgent()).run(
        "Analyze",
        analysis_request=normalize_analysis_input(payload, experiment_id="experiment-a"),
        analysis_datasets=(dataset,),
    )
    assert state["analysis_result"].business_impact.net_monetary_impact.central == pytest.approx(
        9000
    )
    assert state["decision"]["decision_status"] == "not_required"
