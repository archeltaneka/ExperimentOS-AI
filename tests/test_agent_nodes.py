from __future__ import annotations

from packages.agents.nodes import planner_node
from packages.agents.state import create_initial_state


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
