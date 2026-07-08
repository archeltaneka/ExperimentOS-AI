from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from packages.agents.nodes import RetrievalAgentLike, planner_node, retrieval_node
from packages.agents.retrieval_agent import RetrievalAgent
from packages.agents.state import AgentInputState, AgentState


def build_agent_workflow(
    *,
    retrieval_agent: RetrievalAgentLike | None = None,
):
    if retrieval_agent is None:
        retrieval_agent = RetrievalAgent()
    builder = StateGraph(AgentState, input_schema=AgentInputState)
    builder.add_node("planner", planner_node)
    builder.add_node(
        "retrieval",
        partial(retrieval_node, retrieval_agent=retrieval_agent),
    )
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "retrieval")
    builder.add_edge("retrieval", END)
    return builder.compile()
