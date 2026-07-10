from __future__ import annotations

from typing import Protocol

from packages.agents.planner import plan_question
from packages.agents.state import (
    AgentInputState,
    AgentState,
    AgentStateUpdate,
    RequiredAgent,
    create_initial_state,
    create_trace_entry,
)


class RetrievalAgentLike(Protocol):
    def run(self, state: AgentState) -> AgentStateUpdate:
        pass


class ExperimentAnalysisAgentLike(Protocol):
    def run(self, state: AgentState) -> AgentStateUpdate:
        pass


class BusinessImpactAgentLike(Protocol):
    def run(self, state: AgentState) -> AgentStateUpdate:
        pass


class RiskAssessmentAgentLike(Protocol):
    def run(self, state: AgentState) -> AgentStateUpdate:
        pass


class DecisionAgentLike(Protocol):
    def run(self, state: AgentState) -> AgentStateUpdate:
        pass


class HumanApprovalAgentLike(Protocol):
    def run(self, state: AgentState) -> AgentStateUpdate:
        pass


class ExecutiveSummaryAgentLike(Protocol):
    def run(self, state: AgentState) -> AgentStateUpdate:
        pass


def planner_node(state: AgentInputState | AgentState) -> AgentStateUpdate:
    if isinstance(state, dict):
        question = state["question"]
        request = state.get("request", {})
        human_approval_input = state.get("human_approval_input", {})
        preserved_run_metadata = state.get("run_metadata")
        preserved_timestamps = state.get("timestamps")
    else:
        question = state.question
        request = dict(getattr(state, "request", {}))
        human_approval_input = dict(getattr(state, "human_approval_input", {}))
        preserved_run_metadata = None
        preserved_timestamps = None
    defaults = create_initial_state(
        question,
        experiment_id=request.get("experiment_id"),
        top_k=request.get("top_k", 5),
        human_approval_input=human_approval_input,
    )
    plan = plan_question(question)
    preserved_experiment_ids = list(defaults["experiment_context"]["experiment_ids"])
    planned_filters = dict(plan.experiment_context["filters"])
    trace_entry = create_trace_entry(
        node="planner",
        event="planned",
        details={
            "intent": plan.intent,
            "required_agents": plan.required_agents,
            "experiment_hints": plan.experiment_hints,
        },
    )
    return {
        **{
            key: value
            for key, value in defaults.items()
            if key != "question"
        },
        "intent": plan.intent,
        "required_agents": plan.required_agents,
        "planner_notes": plan.planner_notes,
        "experiment_context": {
            "experiment_ids": preserved_experiment_ids,
            "filters": {
                **planned_filters,
                **defaults["experiment_context"]["filters"],
            },
        },
        "metrics": plan.metrics,
        "trace": [trace_entry],
        "run_metadata": (
            dict(preserved_run_metadata)
            if isinstance(preserved_run_metadata, dict)
            else defaults["run_metadata"]
        ),
        "timestamps": (
            dict(preserved_timestamps)
            if isinstance(preserved_timestamps, dict)
            else defaults["timestamps"]
        ),
    }


def retrieval_node(
    state: AgentState,
    *,
    retrieval_agent: RetrievalAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "retrieval" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="retrieval",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = retrieval_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update


def experiment_analysis_node(
    state: AgentState,
    *,
    experiment_analysis_agent: ExperimentAnalysisAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "experiment_analysis" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="experiment_analysis",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = experiment_analysis_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update


def business_impact_node(
    state: AgentState,
    *,
    business_impact_agent: BusinessImpactAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "business_impact" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="business_impact",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = business_impact_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update


def risk_assessment_node(
    state: AgentState,
    *,
    risk_assessment_agent: RiskAssessmentAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "risk_assessment" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="risk_assessment",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = risk_assessment_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update


def decision_node(
    state: AgentState,
    *,
    decision_agent: DecisionAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "decision" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="decision",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = decision_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update


def executive_summary_node(
    state: AgentState,
    *,
    executive_summary_agent: ExecutiveSummaryAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "executive_summary" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="executive_summary",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = executive_summary_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update


def human_approval_node(
    state: AgentState,
    *,
    human_approval_agent: HumanApprovalAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "human_approval" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="human_approval",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = human_approval_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update
