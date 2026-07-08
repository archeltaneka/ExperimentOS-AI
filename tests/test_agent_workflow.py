from __future__ import annotations

import pytest

from packages.agents.nodes import retrieval_node
from packages.agents.service import AgentWorkflowInputError, AgentWorkflowService
from packages.agents.state import create_initial_state
from packages.agents.workflow import build_agent_workflow


class StubGraphRetrievalAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
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
            "metrics": {
                **state["metrics"],
                "retrieval": {"retrieved_chunks": 1},
            },
            "trace": [
                {"node": "retrieval", "event": "started", "at": "2026-07-07T00:00:00Z"},
                {"node": "retrieval", "event": "completed", "at": "2026-07-07T00:00:01Z"},
            ],
            "errors": [],
        }


class StubGraphExperimentAnalysisAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "experiment_analysis": {
                **state["experiment_analysis"],
                "summary": "Primary metric improved in treatment.",
                "findings": ["Treatment beat control on the primary metric."],
                "status": "completed",
                "experiment_id": "exp-001-payment-recommendation",
                "experiment_name": "Adaptive Payment Method Recommendation",
                "primary_metric": "payment_success_rate",
                "evidence_citations": state["citations"],
                "analysis_confidence": "medium",
            },
            "metrics": {
                **state["metrics"],
                "experiment_analysis": {"status": "completed", "citation_count": len(state["citations"])},
            },
            "trace": [
                {
                    "node": "experiment_analysis",
                    "event": "started",
                    "at": "2026-07-08T00:00:02Z",
                },
                {
                    "node": "experiment_analysis",
                    "event": "completed",
                    "at": "2026-07-08T00:00:03Z",
                },
            ],
            "errors": [],
        }


def test_build_agent_workflow_exposes_question_only_input_schema() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
    )

    schema = graph.get_input_schema().model_json_schema()

    assert schema["required"] == ["question"]
    assert set(schema["properties"]) == {"question"}


def test_build_agent_workflow_returns_invokable_graph() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
    )

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
    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
        "experiment_analysis",
    ]
    assert [entry["event"] for entry in result["trace"]] == [
        "planned",
        "started",
        "completed",
        "started",
        "completed",
    ]
    assert result["human_approval"]["status"] == "not_requested"
    assert result["run_metadata"]["workflow"] == "phase2_shared_state"
    assert result["metrics"]["planner_rule_version"] == "deterministic_v1"
    assert result["metrics"]["retrieval"]["retrieved_chunks"] == 1
    assert result["metrics"]["experiment_analysis"]["status"] == "completed"
    assert result["experiment_analysis"]["status"] == "completed"


def test_agent_workflow_service_runs_graph_and_returns_state() -> None:
    service = AgentWorkflowService(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
    )

    result = service.run("What happened in the payment recommendation experiment?")

    assert result["question"] == "What happened in the payment recommendation experiment?"
    assert result["intent"] == "experiment_lookup"
    assert result["required_agents"] == ["retrieval"]
    assert result["experiment_analysis"]["summary"] == ""
    assert result["errors"] == []
    assert result["tool_calls"] == []
    assert result["metrics"]["planner_rule_version"] == "deterministic_v1"
    assert result["metrics"]["retrieval"]["retrieved_chunks"] == 1


def test_agent_workflow_service_rejects_blank_question() -> None:
    service = AgentWorkflowService()

    with pytest.raises(AgentWorkflowInputError, match="question must not be empty"):
        service.run("   ")


def test_build_agent_workflow_accepts_injected_retrieval_agent() -> None:
    retrieval_agent = StubGraphRetrievalAgent()
    experiment_analysis_agent = StubGraphExperimentAnalysisAgent()
    graph = build_agent_workflow(
        retrieval_agent=retrieval_agent,
        experiment_analysis_agent=experiment_analysis_agent,
    )

    result = graph.invoke({"question": "What happened in the payment recommendation experiment?"})

    assert result["retrieved_chunks"][0]["content"] == "Chunk from retrieval."
    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
    ]
    assert [entry["event"] for entry in result["trace"]] == [
        "planned",
        "started",
        "completed",
        "skipped",
    ]
    assert retrieval_agent.calls[0]["intent"] == "experiment_lookup"
    assert retrieval_agent.calls[0]["required_agents"] == ["retrieval"]
    assert retrieval_agent.calls[0]["experiment_context"] == {
        "experiment_ids": [],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }
    assert retrieval_agent.calls[0]["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "planner_required_agent_count": 1,
        "planner_experiment_hint_count": 1,
    }


def test_agent_workflow_service_accepts_injected_retrieval_agent() -> None:
    retrieval_agent = StubGraphRetrievalAgent()
    service = AgentWorkflowService(
        retrieval_agent=retrieval_agent,
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
    )

    result = service.run("What happened in the payment recommendation experiment?")

    assert result["citations"][0]["quote"] == "Chunk from retrieval."
    assert result["metrics"]["retrieval"]["retrieved_chunks"] == 1
    assert retrieval_agent.calls[0]["intent"] == "experiment_lookup"
    assert retrieval_agent.calls[0]["required_agents"] == ["retrieval"]
    assert retrieval_agent.calls[0]["experiment_context"] == {
        "experiment_ids": [],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }


def test_build_agent_workflow_skips_retrieval_when_not_required() -> None:
    retrieval_agent = StubGraphRetrievalAgent()
    graph = build_agent_workflow(
        retrieval_agent=retrieval_agent,
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
    )

    result = graph.invoke({"question": "Hello"})

    assert retrieval_agent.calls == []
    assert result["required_agents"] == []
    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "experiment_analysis",
    ]
    assert [entry["event"] for entry in result["trace"]] == ["planned", "skipped", "skipped"]
    assert result["errors"] == []
    assert result["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "planner_required_agent_count": 0,
        "planner_experiment_hint_count": 0,
    }


def test_retrieval_skip_update_does_not_overwrite_existing_outputs() -> None:
    state = create_initial_state("Hello")
    state["required_agents"] = []
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "content": "Existing retrieval chunk.",
            "score": 0.42,
            "metadata": {"section": "Existing"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "quote": "Existing retrieval chunk.",
            "section": "Existing",
            "metadata": {"section": "Existing"},
        }
    ]

    update = retrieval_node(state, retrieval_agent=StubGraphRetrievalAgent())

    assert "retrieved_chunks" not in update
    assert "citations" not in update
    assert "errors" not in update
    assert update["trace"][0]["event"] == "skipped"


def test_build_agent_workflow_runs_experiment_analysis_after_retrieval() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
    )

    result = graph.invoke({"question": "Summarize the checkout UX experiment for executives."})

    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
        "experiment_analysis",
    ]
    assert result["experiment_analysis"]["status"] == "completed"
    assert result["experiment_analysis"]["evidence_citations"] == result["citations"]
