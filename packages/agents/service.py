from __future__ import annotations

from packages.agents.business_impact_agent import BusinessImpactAgent
from packages.agents.decision_agent import DecisionAgent
from packages.agents.executive_summary_agent import ExecutiveSummaryAgent
from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent
from packages.agents.human_approval_agent import HumanApprovalAgent
from packages.agents.nodes import (
    BusinessImpactAgentLike,
    DecisionAgentLike,
    ExecutiveSummaryAgentLike,
    ExperimentAnalysisAgentLike,
    HumanApprovalAgentLike,
    RetrievalAgentLike,
    RiskAssessmentAgentLike,
)
from packages.agents.retrieval_agent import RetrievalAgent
from packages.agents.risk_assessment_agent import RiskAssessmentAgent
from packages.agents.state import AgentState
from packages.agents.workflow import build_agent_workflow


class AgentWorkflowInputError(ValueError):
    pass


class AgentWorkflowService:
    def __init__(
        self,
        retrieval_agent: RetrievalAgentLike | None = None,
        experiment_analysis_agent: ExperimentAnalysisAgentLike | None = None,
        business_impact_agent: BusinessImpactAgentLike | None = None,
        risk_assessment_agent: RiskAssessmentAgentLike | None = None,
        decision_agent: DecisionAgentLike | None = None,
        human_approval_agent: HumanApprovalAgentLike | None = None,
        executive_summary_agent: ExecutiveSummaryAgentLike | None = None,
    ) -> None:
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
        if human_approval_agent is None:
            human_approval_agent = HumanApprovalAgent()
        if executive_summary_agent is None:
            executive_summary_agent = ExecutiveSummaryAgent()
        self.workflow = build_agent_workflow(
            retrieval_agent=retrieval_agent,
            experiment_analysis_agent=experiment_analysis_agent,
            business_impact_agent=business_impact_agent,
            risk_assessment_agent=risk_assessment_agent,
            decision_agent=decision_agent,
            human_approval_agent=human_approval_agent,
            executive_summary_agent=executive_summary_agent,
        )

    def run(self, question: str) -> AgentState:
        normalized_question = question.strip()
        if not normalized_question:
            raise AgentWorkflowInputError("question must not be empty")
        return self.workflow.invoke({"question": normalized_question})
