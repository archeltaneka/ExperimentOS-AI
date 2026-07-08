from __future__ import annotations

from packages.agents.nodes import planner_node
from packages.agents.state import create_initial_state


class RecordingAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "retrieved_chunks": [],
            "citations": [],
            "metrics": {"retrieval": {"retrieved_chunks": 0}},
            "errors": [],
            "trace": [],
        }


def test_planner_node_classifies_decision_questions_with_partial_update() -> None:
    state = {
        "question": "Should we roll out the payment recommendation experiment?",
        "trace": [{"node": "existing"}],
    }

    updated = planner_node(state)

    assert updated["intent"] == "decision_support"
    assert updated["required_agents"] == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "executive_summary",
    ]
    assert "question" not in updated
    assert (
        updated["request"]["question"]
        == "Should we roll out the payment recommendation experiment?"
    )
    assert updated["planner_notes"]
    assert updated["experiment_context"] == {
        "experiment_ids": [],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }
    assert updated["human_approval"]["status"] == "not_requested"
    assert updated["tool_calls"] == []
    assert updated["trace"] == [
        {
            "node": "planner",
            "event": "planned",
            "details": {
                "intent": "decision_support",
                "required_agents": [
                    "retrieval",
                    "experiment_analysis",
                    "business_impact",
                    "risk_assessment",
                    "decision",
                    "executive_summary",
                ],
                "experiment_hints": ["payment recommendation"],
            },
            "at": updated["trace"][0]["at"],
        }
    ]
    assert updated["errors"] == []


def test_planner_node_uses_retrieval_for_experiment_lookup_questions() -> None:
    state = create_initial_state("What happened in the payment recommendation experiment?")

    updated = planner_node(state)

    assert updated["intent"] == "experiment_lookup"
    assert updated["required_agents"] == ["retrieval"]


def test_retrieval_node_skips_when_retrieval_is_not_required() -> None:
    from packages.agents.nodes import retrieval_node

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
    agent = RecordingAgent()

    update = retrieval_node(state, retrieval_agent=agent)

    assert agent.calls == 0
    assert "retrieved_chunks" not in update
    assert "citations" not in update
    assert state["retrieved_chunks"] == [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "content": "Existing retrieval chunk.",
            "score": 0.42,
            "metadata": {"section": "Existing"},
        }
    ]
    assert state["citations"] == [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "quote": "Existing retrieval chunk.",
            "section": "Existing",
            "metadata": {"section": "Existing"},
        }
    ]
    assert "errors" not in update
    assert update["trace"][0]["node"] == "retrieval"
    assert update["trace"][0]["event"] == "skipped"


def test_retrieval_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import retrieval_node

    state = create_initial_state("What happened in the payment recommendation experiment?")
    state["required_agents"] = ["retrieval"]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    agent = RecordingAgent()

    update = retrieval_node(state, retrieval_agent=agent)

    assert agent.calls == 1
    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {"retrieved_chunks": 0},
    }
    assert update["errors"] == []
