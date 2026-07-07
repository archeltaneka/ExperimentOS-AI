from __future__ import annotations

from packages.agents.state import build_initial_state


def test_build_initial_state_sets_required_defaults() -> None:
    state = build_initial_state("Why did this experiment ship?")

    assert state["question"] == "Why did this experiment ship?"
    assert state["intent"] == "unknown"
    assert state["required_agents"] == []
    assert state["retrieved_chunks"] == []
    assert state["analysis"] == ""
    assert state["business_impact"] == ""
    assert state["risks"] == []
    assert state["decision"] == ""
    assert state["executive_summary"] == ""
    assert state["citations"] == []
    assert state["metrics"] == {}
    assert state["errors"] == []
    assert state["trace"] == []
