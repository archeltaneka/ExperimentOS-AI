"""Optional API analysis contracts and safe failure responses."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from apps.api.ask_service import AgentWorkflowAskService, AskRequest, AskResponse
from apps.api.main import app, get_ask_service
from packages.agents.service import AgentWorkflowService
from tests.test_agent_analysis_workflow import ForbiddenAgent
from tests.test_analysis_service import fixed_case


def ask_payload():
    request, dataset = fixed_case()
    params = request.model_dump(
        mode="json", exclude={"schema_version", "request_id", "experiment_id", "method", "business"}
    )
    return {
        "question": "Analyze",
        "experiment_id": "experiment-a",
        "analysis": {
            "method": request.method,
            "request_id": request.request_id,
            "parameters": params,
        },
        "analysis_datasets": [dataset.model_dump(mode="json")],
    }


def test_api_preserves_typed_analysis_and_excludes_rows():
    response = asyncio.run(
        AgentWorkflowAskService(AgentWorkflowService(retrieval_agent=ForbiddenAgent())).answer(
            AskRequest.model_validate(ask_payload())
        )
    )
    assert response.analysis.status == "completed"
    assert response.analysis.evidence.point_effect.absolute_effect.value == 10
    assert AskResponse.model_validate_json(response.model_dump_json()) == response
    assert "treatment-0" not in response.model_dump_json()
    assert "analysis_datasets" not in response.model_dump_json()


@pytest.mark.parametrize(
    "analysis",
    [{"method": "unsupported"}, {"method": ["did", "dml"]}, {"method": "cuped", "parameters": {}}],
)
def test_invalid_analysis_returns_structured_abstention_not_infrastructure_error(analysis):
    payload = ask_payload()
    payload["analysis"] = analysis
    response = asyncio.run(
        AgentWorkflowAskService(AgentWorkflowService(retrieval_agent=ForbiddenAgent())).answer(
            AskRequest.model_validate(payload)
        )
    )
    assert response.analysis.status in {"invalid", "abstained"}
    assert response.analysis.evidence is None
    assert response.analysis.abstention


def test_http_dataset_validation_does_not_echo_rows():
    payload = ask_payload()
    payload["analysis_datasets"][0]["rows"] = [[{"secret": "RAW_ROW_SENTINEL"}]]
    app.dependency_overrides[get_ask_service] = lambda: AgentWorkflowAskService(
        AgentWorkflowService(retrieval_agent=ForbiddenAgent())
    )
    try:
        response = TestClient(app).post("/ask", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "RAW_ROW_SENTINEL" not in response.text
    assert '"input":' not in response.text


def test_concurrent_requests_with_same_dataset_and_request_ids_are_isolated():
    from copy import deepcopy

    first = ask_payload()
    second = deepcopy(first)
    for row in second["analysis_datasets"][0]["rows"]:
        if row[1] == "treatment":
            row[2] += 3
    service = AgentWorkflowAskService(AgentWorkflowService(retrieval_agent=ForbiddenAgent()))

    async def run():
        return await asyncio.gather(
            service.answer(AskRequest.model_validate(first)),
            service.answer(AskRequest.model_validate(second)),
        )

    a, b = asyncio.run(run())
    assert a.analysis.evidence.point_effect.absolute_effect.value == 10
    assert b.analysis.evidence.point_effect.absolute_effect.value == 13
    assert a.analysis.analysis_id != b.analysis.analysis_id


def test_dataset_owned_by_another_experiment_abstains():
    payload = ask_payload()
    payload["analysis_datasets"][0]["experiment_id"] = "other-experiment"
    result = asyncio.run(
        AgentWorkflowAskService(AgentWorkflowService(retrieval_agent=ForbiddenAgent())).answer(
            AskRequest.model_validate(payload)
        )
    )
    assert result.analysis.status == "abstained"
    assert result.analysis.abstention.code == "analysis.dataset_ownership"


def test_analysis_infrastructure_failure_does_not_expose_exception_payload():
    from apps.api.ask_service import AgentWorkflowExecutionError

    class BrokenWorkflow:
        def run(self, *args, **kwargs):
            raise RuntimeError("RAW_ROW_SENTINEL")

    with pytest.raises(AgentWorkflowExecutionError, match="infrastructure unavailable") as captured:
        asyncio.run(
            AgentWorkflowAskService(BrokenWorkflow()).answer(
                AskRequest.model_validate(ask_payload())
            )
        )
    assert "RAW_ROW_SENTINEL" not in str(captured.value)
