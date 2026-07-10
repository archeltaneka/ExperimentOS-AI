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
from packages.agents.observability import PHASE2_WORKFLOW_NODES, extract_workflow_observation
from packages.agents.retrieval_agent import RetrievalAgent
from packages.agents.risk_assessment_agent import RiskAssessmentAgent
from packages.agents.state import AgentState, create_initial_state
from packages.agents.workflow import build_agent_workflow
from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider


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
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.observability_provider = observability_provider or NoOpObservabilityProvider()
        if retrieval_agent is None:
            retrieval_agent = RetrievalAgent(
                observability_provider=self.observability_provider,
            )
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

    def run(
        self,
        question: str,
        experiment_id: str | None = None,
        top_k: int = 5,
        human_approval_input: dict[str, object] | None = None,
    ) -> AgentState:
        normalized_question = question.strip()
        if not normalized_question:
            raise AgentWorkflowInputError("question must not be empty")
        initial_state = create_initial_state(
            normalized_question,
            experiment_id=experiment_id,
            top_k=top_k,
            human_approval_input=human_approval_input,
        )
        metadata = {
            "surface": "agent_workflow",
            "workflow": initial_state["run_metadata"]["workflow"],
            "experimentos_trace_id": initial_state["run_metadata"]["run_id"],
            "top_k": top_k,
            "experiment_id": experiment_id or "",
        }
        parent_span = self.observability_provider.current_span()
        if parent_span is None:
            span = self.observability_provider.start_root_span(
                "workflow",
                trace_id=initial_state["run_metadata"]["run_id"],
                inputs={
                    "question": normalized_question,
                    "experiment_id": experiment_id or "",
                    "top_k": top_k,
                },
                metadata=metadata,
                tags=("agent_workflow",),
            )
        else:
            span = self.observability_provider.start_span(
                "workflow",
                inputs={
                    "question": normalized_question,
                    "experiment_id": experiment_id or "",
                    "top_k": top_k,
                },
                metadata=metadata,
                tags=("agent_workflow",),
            )
        with span.activate():
            try:
                config = self.observability_provider.build_langgraph_config(
                    metadata={
                        "workflow": initial_state["run_metadata"]["workflow"],
                        "experimentos_trace_id": initial_state["run_metadata"]["run_id"],
                    },
                    tags=("agent_workflow",),
                )
                state = self.workflow.invoke(initial_state, config=config)
                state["run_metadata"] = {
                    **state["run_metadata"],
                    "run_id": initial_state["run_metadata"]["run_id"],
                }
            except Exception as exc:
                span.record_error(exc, details={"surface": "agent_workflow"})
                span.finish(outputs={"status": "failed"})
                raise
            observation = extract_workflow_observation(state)
            span.add_metadata(
                {
                    "intent": observation.intent,
                    "required_agents": list(observation.required_agents),
                    "trace_completeness": observation.trace_completeness,
                    "workflow_success": observation.workflow_success,
                    "citation_count": observation.citation_count,
                    "decision_status": observation.decision_status,
                    "approval_status": observation.approval_status,
                    "summary_status": observation.summary_status,
                }
            )
            for node_name in PHASE2_WORKFLOW_NODES:
                node_observation = observation.nodes[node_name]
                child = span.start_child(
                    node_name,
                    metadata={
                        "execution_status": node_observation.execution_status,
                        "result_status": node_observation.result_status,
                        "latency_ms": node_observation.latency_ms,
                        "error_count": node_observation.error_count,
                        "tool_call_count": node_observation.tool_call_count,
                        "tool_failure_count": node_observation.tool_failure_count,
                        "required": node_name in observation.required_agents,
                    },
                )
                outputs = {
                    "status": node_observation.result_status,
                    "execution_status": node_observation.execution_status,
                }
                if node_name == "retrieval":
                    outputs.update(dict(observation.retrieval_metrics))
                child.finish(outputs=outputs)
            span.finish(
                outputs={
                    "status": "completed",
                    "workflow_success": observation.workflow_success,
                    "trace_completeness": observation.trace_completeness,
                    "citation_count": observation.citation_count,
                }
            )
            return state
