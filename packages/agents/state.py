"""Shared LangGraph state contract for the internal Phase 2 agent workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, TypeAdapter
from typing_extensions import TypedDict

AgentIntent = Literal["qa", "analysis", "risk", "decision", "summary", "unknown"]
RequiredAgent = Literal[
    "planner",
    "retrieval",
    "analysis",
    "business_impact",
    "risk",
    "decision",
    "summary",
    "human_approval",
]
HumanApprovalStatus = Literal["not_requested", "pending", "approved", "rejected"]
ToolCallStatus = Literal["pending", "completed", "failed"]


class AgentInputState(BaseModel):
    question: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentRequest(TypedDict):
    question: str
    normalized_question: str


class ExperimentContext(TypedDict):
    experiment_ids: list[str]
    filters: dict[str, object]


class RetrievedChunk(TypedDict, total=False):
    chunk_id: str
    document_id: str
    experiment_id: str
    content: str
    score: float
    metadata: dict[str, object]


class Citation(TypedDict, total=False):
    chunk_id: str
    document_id: str
    experiment_id: str
    quote: str
    section: str
    metadata: dict[str, object]


class ExperimentAnalysis(TypedDict):
    summary: str
    findings: list[str]


class BusinessImpact(TypedDict):
    summary: str
    impacts: list[str]


class RiskRecord(TypedDict, total=False):
    title: str
    severity: str
    detail: str
    mitigation: str


class DecisionRecord(TypedDict):
    recommendation: str
    rationale: str


class ExecutiveSummary(TypedDict):
    summary: str


class HumanApprovalRecord(TypedDict):
    status: HumanApprovalStatus
    reviewer: str | None
    reviewed_at: str | None
    notes: str


class ToolCallRecord(TypedDict, total=False):
    tool_name: str
    status: ToolCallStatus
    arguments: dict[str, object]
    result: dict[str, object]
    error: str
    at: str


class ErrorRecord(TypedDict, total=False):
    code: str
    message: str
    node: str
    details: dict[str, object]
    at: str


class TraceEntry(TypedDict, total=False):
    node: str
    event: str
    details: dict[str, object]
    at: str


class StateTimestamps(TypedDict):
    created_at: str
    updated_at: str


class RunMetadata(TypedDict):
    run_id: str
    workflow: str
    state_version: int


def append_str_list(current: list[str], update: list[str] | None) -> list[str]:
    if update is None:
        return current
    return [*current, *update]


def append_dict_list[T](
    current: list[T],
    update: list[T] | None,
) -> list[T]:
    if update is None:
        return current
    return [*current, *update]


class AgentState(TypedDict):
    question: str
    request: AgentRequest
    intent: AgentIntent
    required_agents: list[RequiredAgent]
    experiment_context: ExperimentContext
    retrieved_chunks: list[RetrievedChunk]
    citations: list[Citation]
    experiment_analysis: ExperimentAnalysis
    business_impact: BusinessImpact
    risks: list[RiskRecord]
    decision: DecisionRecord
    executive_summary: ExecutiveSummary
    human_approval: HumanApprovalRecord
    tool_calls: Annotated[list[ToolCallRecord], append_dict_list]
    metrics: dict[str, object]
    errors: Annotated[list[ErrorRecord], append_dict_list]
    trace: Annotated[list[TraceEntry], append_dict_list]
    timestamps: StateTimestamps
    run_metadata: RunMetadata


class AgentStateUpdate(TypedDict, total=False):
    request: AgentRequest
    intent: AgentIntent
    required_agents: list[RequiredAgent]
    experiment_context: ExperimentContext
    retrieved_chunks: list[RetrievedChunk]
    citations: list[Citation]
    experiment_analysis: ExperimentAnalysis
    business_impact: BusinessImpact
    risks: list[RiskRecord]
    decision: DecisionRecord
    executive_summary: ExecutiveSummary
    human_approval: HumanApprovalRecord
    tool_calls: list[ToolCallRecord]
    metrics: dict[str, object]
    errors: list[ErrorRecord]
    trace: list[TraceEntry]
    timestamps: StateTimestamps
    run_metadata: RunMetadata


AGENT_STATE_ADAPTER = TypeAdapter(AgentState)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _updated_timestamps(timestamps: StateTimestamps) -> StateTimestamps:
    return {
        "created_at": timestamps["created_at"],
        "updated_at": _utc_now_iso(),
    }


def create_trace_entry(
    *,
    node: str,
    event: str,
    details: dict[str, object] | None = None,
    at: str | None = None,
) -> TraceEntry:
    entry: TraceEntry = {
        "node": node,
        "event": event,
        "at": at or _utc_now_iso(),
    }
    if details:
        entry["details"] = details
    return entry


def create_error_entry(
    *,
    code: str,
    message: str,
    node: str | None = None,
    details: dict[str, object] | None = None,
    at: str | None = None,
) -> ErrorRecord:
    entry: ErrorRecord = {
        "code": code,
        "message": message,
        "at": at or _utc_now_iso(),
    }
    if node is not None:
        entry["node"] = node
    if details:
        entry["details"] = details
    return entry


def create_initial_state(question: str) -> AgentState:
    normalized_question = question.strip()
    now = _utc_now_iso()
    return {
        "question": question,
        "request": {
            "question": question,
            "normalized_question": normalized_question,
        },
        "intent": "unknown",
        "required_agents": [],
        "experiment_context": {
            "experiment_ids": [],
            "filters": {},
        },
        "retrieved_chunks": [],
        "citations": [],
        "experiment_analysis": {
            "summary": "",
            "findings": [],
        },
        "business_impact": {
            "summary": "",
            "impacts": [],
        },
        "risks": [],
        "decision": {
            "recommendation": "",
            "rationale": "",
        },
        "executive_summary": {
            "summary": "",
        },
        "human_approval": {
            "status": "not_requested",
            "reviewer": None,
            "reviewed_at": None,
            "notes": "",
        },
        "tool_calls": [],
        "metrics": {},
        "errors": [],
        "trace": [],
        "timestamps": {
            "created_at": now,
            "updated_at": now,
        },
        "run_metadata": {
            "run_id": str(uuid4()),
            "workflow": "phase2_shared_state",
            "state_version": 2,
        },
    }


def build_initial_state(question: str) -> AgentState:
    return create_initial_state(question)


def append_trace(
    state: AgentState,
    *,
    node: str,
    event: str,
    details: dict[str, object] | None = None,
) -> AgentState:
    updated = {
        **state,
        "trace": [
            *state["trace"],
            create_trace_entry(node=node, event=event, details=details),
        ],
        "timestamps": _updated_timestamps(state["timestamps"]),
    }
    return validate_state_shape(updated)


def append_error(
    state: AgentState,
    *,
    code: str,
    message: str,
    node: str | None = None,
    details: dict[str, object] | None = None,
) -> AgentState:
    updated = {
        **state,
        "errors": [
            *state["errors"],
            create_error_entry(
                code=code,
                message=message,
                node=node,
                details=details,
            ),
        ],
        "timestamps": _updated_timestamps(state["timestamps"]),
    }
    return validate_state_shape(updated)


def record_metric(state: AgentState, name: str, value: object) -> AgentState:
    updated = {
        **state,
        "metrics": {
            **state["metrics"],
            name: value,
        },
        "timestamps": _updated_timestamps(state["timestamps"]),
    }
    return validate_state_shape(updated)


def validate_state_shape(state: object) -> AgentState:
    return AGENT_STATE_ADAPTER.validate_python(state)
