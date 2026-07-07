from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from packages.agents.nodes import planner_node
from packages.agents.state import AgentInputState, AgentState


def build_agent_workflow():
    builder = StateGraph(AgentState, input_schema=AgentInputState)
    builder.add_node("planner", planner_node)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", END)
    return builder.compile()
