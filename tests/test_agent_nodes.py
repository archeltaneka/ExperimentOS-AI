from __future__ import annotations

from packages.agents.nodes import planner_node
from packages.agents.state import create_initial_state


def test_planner_node_classifies_decision_questions_with_partial_update() -> None:
    state = {"question": "Should we approve this rollout?", "trace": [{"node": "existing"}]}

    updated = planner_node(state)

    assert updated["intent"] == "decision"
    assert updated["required_agents"] == ["decision"]
    assert "question" not in updated
    assert updated["request"]["question"] == "Should we approve this rollout?"
    assert updated["experiment_context"] == {
        "experiment_ids": [],
        "filters": {},
    }
    assert updated["human_approval"]["status"] == "not_requested"
    assert updated["tool_calls"] == []
    assert updated["trace"] == [
        {
            "node": "planner",
            "event": "classified",
            "details": {
                "intent": "decision",
                "required_agents": ["decision"],
            },
            "at": updated["trace"][0]["at"],
        }
    ]
    assert updated["errors"] == []


def test_planner_node_defaults_to_qa_for_general_questions() -> None:
    state = create_initial_state("What happened in this experiment?")

    updated = planner_node(state)

    assert updated["intent"] == "qa"
    assert updated["required_agents"] == ["retrieval"]
