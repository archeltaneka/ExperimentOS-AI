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


def planner_node(state: AgentInputState | AgentState) -> AgentStateUpdate:
    question = state["question"]
    defaults = create_initial_state(question)
    plan = plan_question(question)
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
        "experiment_context": plan.experiment_context,
        "metrics": plan.metrics,
        "trace": [trace_entry],
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
    return retrieval_agent.run(state)
