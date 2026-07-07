from __future__ import annotations

from packages.agents.nodes import planner_node
from packages.agents.state import build_initial_state


def test_planner_node_classifies_decision_questions_with_partial_update() -> None:
    state = {"question": "Should we approve this rollout?", "trace": [{"node": "existing"}]}

    updated = planner_node(state)

    assert updated["intent"] == "decision"
    assert updated["required_agents"] == ["decision"]
    assert "question" not in updated
    assert updated["trace"] == [
        {
            "node": "planner",
            "intent": "decision",
            "required_agents": ["decision"],
        }
    ]
    assert updated["errors"] == []


def test_planner_node_defaults_to_qa_for_general_questions() -> None:
    state = build_initial_state("What happened in this experiment?")

    updated = planner_node(state)

    assert updated["intent"] == "qa"
    assert updated["required_agents"] == ["retrieval"]
