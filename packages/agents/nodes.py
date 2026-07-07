from __future__ import annotations

from packages.agents.state import AgentInputState, AgentIntent, AgentState, AgentStateUpdate


def planner_node(state: AgentInputState | AgentState) -> AgentStateUpdate:
    intent = classify_intent(state["question"])
    required_agents = required_agents_for_intent(intent)
    trace_entry = {
        "node": "planner",
        "intent": intent,
        "required_agents": required_agents,
    }
    return {
        "intent": intent,
        "required_agents": required_agents,
        "retrieved_chunks": [],
        "analysis": "",
        "business_impact": "",
        "risks": [],
        "decision": "",
        "executive_summary": "",
        "citations": [],
        "metrics": {},
        "errors": [],
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


def required_agents_for_intent(intent: AgentIntent) -> list[str]:
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
