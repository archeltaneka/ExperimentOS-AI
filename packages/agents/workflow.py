from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from packages.agents.business_impact_agent import BusinessImpactAgent
from packages.agents.decision_agent import DecisionAgent
from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent
from packages.agents.nodes import (
    BusinessImpactAgentLike,
    DecisionAgentLike,
    ExperimentAnalysisAgentLike,
    RetrievalAgentLike,
    RiskAssessmentAgentLike,
    business_impact_node,
    decision_node,
    experiment_analysis_node,
    planner_node,
    retrieval_node,
    risk_assessment_node,
)
from packages.agents.retrieval_agent import RetrievalAgent
from packages.agents.risk_assessment_agent import RiskAssessmentAgent
from packages.agents.state import AgentInputState, AgentState


def build_agent_workflow(
    *,
    retrieval_agent: RetrievalAgentLike | None = None,
    experiment_analysis_agent: ExperimentAnalysisAgentLike | None = None,
    business_impact_agent: BusinessImpactAgentLike | None = None,
    risk_assessment_agent: RiskAssessmentAgentLike | None = None,
    decision_agent: DecisionAgentLike | None = None,
):
    if retrieval_agent is None:
        retrieval_agent = RetrievalAgent()
    if experiment_analysis_agent is None:
        experiment_analysis_agent = ExperimentAnalysisAgent()
    if business_impact_agent is None:
        business_impact_agent = BusinessImpactAgent()
    if risk_assessment_agent is None:
        risk_assessment_agent = RiskAssessmentAgent()
    if decision_agent is None:
        decision_agent = DecisionAgent()
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
    builder.add_node(
        "risk_assessment",
        partial(
            risk_assessment_node,
            risk_assessment_agent=risk_assessment_agent,
        ),
    )
    builder.add_node(
        "decision",
        partial(
            decision_node,
            decision_agent=decision_agent,
        ),
    )
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "retrieval")
    builder.add_edge("retrieval", "experiment_analysis")
    builder.add_edge("experiment_analysis", "business_impact")
    builder.add_edge("business_impact", "risk_assessment")
    builder.add_edge("risk_assessment", "decision")
    builder.add_edge("decision", END)
    return builder.compile()
