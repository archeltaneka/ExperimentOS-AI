from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from packages.agents.business_impact_agent import BusinessImpactAgent
from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent
from packages.agents.nodes import (
    BusinessImpactAgentLike,
    ExperimentAnalysisAgentLike,
    RetrievalAgentLike,
    business_impact_node,
    experiment_analysis_node,
    planner_node,
    retrieval_node,
)
from packages.agents.retrieval_agent import RetrievalAgent
from packages.agents.state import AgentInputState, AgentState


def build_agent_workflow(
    *,
    retrieval_agent: RetrievalAgentLike | None = None,
    experiment_analysis_agent: ExperimentAnalysisAgentLike | None = None,
    business_impact_agent: BusinessImpactAgentLike | None = None,
):
    if retrieval_agent is None:
        retrieval_agent = RetrievalAgent()
    if experiment_analysis_agent is None:
        experiment_analysis_agent = ExperimentAnalysisAgent()
    if business_impact_agent is None:
        business_impact_agent = BusinessImpactAgent()
    builder = StateGraph(AgentState, input_schema=AgentInputState)
    builder.add_node("planner", planner_node)
    builder.add_node(
        "retrieval",
        partial(retrieval_node, retrieval_agent=retrieval_agent),
    )
    builder.add_node(
        "experiment_analysis",
        partial(
            experiment_analysis_node,
            experiment_analysis_agent=experiment_analysis_agent,
        ),
    )
    builder.add_node(
        "business_impact",
        partial(
            business_impact_node,
            business_impact_agent=business_impact_agent,
        ),
    )
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "retrieval")
    builder.add_edge("retrieval", "experiment_analysis")
    builder.add_edge("experiment_analysis", "business_impact")
    builder.add_edge("business_impact", END)
    return builder.compile()
