from __future__ import annotations

import pytest

from packages.agents.service import AgentWorkflowInputError, AgentWorkflowService
from packages.agents.workflow import build_agent_workflow


class StubGraphRetrievalAgent:
    def run(self, state):
        return {
            "retrieved_chunks": [
                {
                    "document_id": "doc-1",
                    "experiment_id": "exp-1",
                    "content": "Chunk from retrieval.",
                    "score": 0.88,
                    "metadata": {"section": "Results"},
                }
            ],
            "citations": [
                {
                    "document_id": "doc-1",
                    "experiment_id": "exp-1",
                    "quote": "Chunk from retrieval.",
                    "section": "Results",
                    "metadata": {"section": "Results"},
                }
            ],
            "metrics": {"retrieval": {"retrieved_chunks": 1}},
            "trace": [
                {"node": "retrieval", "event": "started", "at": "2026-07-07T00:00:00Z"},
                {"node": "retrieval", "event": "completed", "at": "2026-07-07T00:00:01Z"},
            ],
            "errors": [],
        }


def test_build_agent_workflow_exposes_question_only_input_schema() -> None:
    graph = build_agent_workflow()

    schema = graph.get_input_schema().model_json_schema()

    assert schema["required"] == ["question"]
    assert set(schema["properties"]) == {"question"}


def test_build_agent_workflow_returns_invokable_graph() -> None:
    graph = build_agent_workflow()

    result = graph.invoke({"question": "Summarize the checkout UX experiment for executives."})

    assert result["question"] == "Summarize the checkout UX experiment for executives."
    assert result["request"]["question"] == "Summarize the checkout UX experiment for executives."
    assert result["intent"] == "executive_summary"
    assert result["required_agents"] == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "executive_summary",
    ]
    assert result["trace"][0]["node"] == "planner"
    assert result["trace"][0]["event"] == "planned"
    assert result["human_approval"]["status"] == "not_requested"
    assert result["run_metadata"]["workflow"] == "phase2_shared_state"


def test_agent_workflow_service_runs_graph_and_returns_state() -> None:
    service = AgentWorkflowService()

    result = service.run("What happened in the payment recommendation experiment?")

    assert result["question"] == "What happened in the payment recommendation experiment?"
    assert result["intent"] == "experiment_lookup"
    assert result["required_agents"] == ["retrieval"]
    assert result["experiment_analysis"]["summary"] == ""
    assert result["errors"] == []
    assert result["tool_calls"] == []


def test_agent_workflow_service_rejects_blank_question() -> None:
    service = AgentWorkflowService()

    with pytest.raises(AgentWorkflowInputError, match="question must not be empty"):
        service.run("   ")


def test_build_agent_workflow_accepts_injected_retrieval_agent() -> None:
    graph = build_agent_workflow(retrieval_agent=StubGraphRetrievalAgent())

    result = graph.invoke({"question": "What happened in the payment recommendation experiment?"})

    assert result["retrieved_chunks"][0]["content"] == "Chunk from retrieval."
    assert [entry["node"] for entry in result["trace"]] == ["planner", "retrieval", "retrieval"]


def test_agent_workflow_service_accepts_injected_retrieval_agent() -> None:
    service = AgentWorkflowService(retrieval_agent=StubGraphRetrievalAgent())

    result = service.run("What happened in the payment recommendation experiment?")

    assert result["citations"][0]["quote"] == "Chunk from retrieval."
    assert result["metrics"]["retrieval"]["retrieved_chunks"] == 1
