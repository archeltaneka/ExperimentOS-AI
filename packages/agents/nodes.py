from __future__ import annotations

from packages.agents.state import (
    AgentInputState,
    AgentIntent,
    AgentState,
    AgentStateUpdate,
    RequiredAgent,
    create_initial_state,
    create_trace_entry,
)


def planner_node(state: AgentInputState | AgentState) -> AgentStateUpdate:
    question = state["question"]
    intent = classify_intent(question)
    required_agents = required_agents_for_intent(intent)
    defaults = create_initial_state(question)
    trace_entry = create_trace_entry(
        node="planner",
        event="classified",
        details={
            "intent": intent,
            "required_agents": required_agents,
        },
    )
    return {
        **{
            key: value
            for key, value in defaults.items()
            if key != "question"
        },
        "intent": intent,
        "required_agents": required_agents,
        "trace": [trace_entry],
    }


def classify_intent(question: str) -> AgentIntent:
    normalized = question.lower()
    if any(token in normalized for token in ("risk", "risks", "concern", "downside", "failure")):
        return "risk"
    if any(token in normalized for token in ("decide", "decision", "approve", "ship", "rollout")):
        return "decision"
    if any(token in normalized for token in ("summary", "summarize", "tl;dr")):
        return "summary"
    if any(token in normalized for token in ("analyze", "analysis", "why", "impact")):
        return "analysis"
    return "qa"


def required_agents_for_intent(intent: AgentIntent) -> list[RequiredAgent]:
    if intent == "qa":
        return ["retrieval"]
    if intent == "analysis":
        return ["analysis"]
    if intent == "risk":
        return ["risk"]
    if intent == "decision":
        return ["decision"]
    if intent == "summary":
        return ["summary"]
    return []
