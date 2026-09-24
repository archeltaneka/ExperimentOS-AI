"""Real graph and API serialization compared to independently invoked analyzers."""

import asyncio

import pytest

from apps.api.ask_service import AgentWorkflowAskService, AskRequest
from packages.evals.agent_analysis_cases import (
    build_analysis_case_service,
    load_analysis_workflow_cases,
    run_direct_reference,
)
from packages.evals.statistical.workflow.optional import effective_case


@pytest.mark.parametrize("case", load_analysis_workflow_cases(), ids=lambda case: case.case_id)
def test_local_analysis_fixture_end_to_end(case):
    case, _, _ = effective_case(case)
    response = asyncio.run(
        AgentWorkflowAskService(build_analysis_case_service(case)).answer(
            AskRequest.model_validate(case.ask_payload)
        )
    )
    assert response.analysis.method == case.expected_method
    assert response.analysis.status == case.expected_status
    if case.expected_method in {"randomized_fixed_horizon", "did"}:
        assert response.analysis.evidence == run_direct_reference(case)
    if case.presenter_candidate:
        assert case.presenter_candidate not in response.answer
        assert response.analysis.integrity_findings
    if case.case_id == "business":
        assert response.analysis.business_impact.net_monetary_impact.central == pytest.approx(9000)
