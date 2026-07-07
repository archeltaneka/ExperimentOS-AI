from __future__ import annotations

import pytest

from packages.agents.service import AgentWorkflowInputError, AgentWorkflowService
from packages.agents.workflow import build_agent_workflow


def test_build_agent_workflow_exposes_question_only_input_schema() -> None:
    graph = build_agent_workflow()

    schema = graph.get_input_schema().model_json_schema()

    assert schema["required"] == ["question"]
    assert set(schema["properties"]) == {"question"}


def test_build_agent_workflow_returns_invokable_graph() -> None:
    graph = build_agent_workflow()

    result = graph.invoke({"question": "Summarize the experiment."})

    assert result["question"] == "Summarize the experiment."
    assert result["request"]["question"] == "Summarize the experiment."
    assert result["intent"] == "summary"
    assert result["required_agents"] == ["summary"]
    assert result["trace"][0]["node"] == "planner"
    assert result["trace"][0]["event"] == "classified"
    assert result["human_approval"]["status"] == "not_requested"
    assert result["run_metadata"]["workflow"] == "phase2_shared_state"


def test_agent_workflow_service_runs_graph_and_returns_state() -> None:
    service = AgentWorkflowService()

    result = service.run("Why did the metrics move?")

    assert result["question"] == "Why did the metrics move?"
    assert result["intent"] == "analysis"
    assert result["required_agents"] == ["analysis"]
    assert result["errors"] == []
    assert result["experiment_analysis"]["summary"] == ""
    assert result["tool_calls"] == []


def test_agent_workflow_service_rejects_blank_question() -> None:
    service = AgentWorkflowService()

    with pytest.raises(AgentWorkflowInputError, match="question must not be empty"):
        service.run("   ")
