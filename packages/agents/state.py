from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict
from typing_extensions import TypedDict

AgentIntent = Literal["qa", "analysis", "risk", "decision", "summary", "unknown"]


class AgentInputState(BaseModel):
    question: str

    model_config = ConfigDict(extra="forbid", frozen=True)


def append_str_list(current: list[str], update: list[str] | None) -> list[str]:
    if update is None:
        return current
    return [*current, *update]


def append_dict_list(
    current: list[dict[str, object]],
    update: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    if update is None:
        return current
    return [*current, *update]


class AgentState(TypedDict):
    question: str
    intent: AgentIntent
    required_agents: list[str]
    retrieved_chunks: list[dict[str, object]]
    analysis: str
    business_impact: str
    risks: list[str]
    decision: str
    executive_summary: str
    citations: list[dict[str, object]]
    metrics: dict[str, object]
    errors: Annotated[list[str], append_str_list]
    trace: Annotated[list[dict[str, object]], append_dict_list]


class AgentStateUpdate(TypedDict, total=False):
    intent: AgentIntent
    required_agents: list[str]
    retrieved_chunks: list[dict[str, object]]
    analysis: str
    business_impact: str
    risks: list[str]
    decision: str
    executive_summary: str
    citations: list[dict[str, object]]
    metrics: dict[str, object]
    errors: list[str]
    trace: list[dict[str, object]]


def build_initial_state(question: str) -> AgentState:
    return {
        "question": question,
        "intent": "unknown",
        "required_agents": [],
        "retrieved_chunks": [],
        "analysis": "",
        "business_impact": "",
        "risks": [],
        "decision": "",
        "executive_summary": "",
        "citations": [],
        "metrics": {},
        "errors": [],
        "trace": [],
    }
