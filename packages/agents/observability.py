from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from packages.agents.state import AgentState

PHASE2_WORKFLOW_NODES = (
    "planner",
    "retrieval",
    "experiment_analysis",
    "business_impact",
    "risk_assessment",
    "decision",
    "human_approval",
    "executive_summary",
)

NodeExecutionStatus = Literal[
    "planned",
    "started",
    "completed",
    "failed",
    "skipped",
    "missing",
]


@dataclass(frozen=True)
class AgentNodeObservation:
    node: str
    execution_status: NodeExecutionStatus
    result_status: str
    latency_ms: float
    error_count: int
    tool_call_count: int
    tool_failure_count: int


@dataclass(frozen=True)
class WorkflowObservation:
    run_id: str
    question: str
    intent: str
    required_agents: tuple[str, ...]
    workflow_latency_ms: float
    workflow_success: bool
    trace_completeness: float
    citation_count: int
    total_tool_calls: int
    total_tool_failures: int
    decision_status: str
    approval_status: str
    summary_status: str
    final_recommendation: str
    retrieval_metrics: dict[str, object]
    nodes: dict[str, AgentNodeObservation]
    errors: tuple[str, ...]


def calculate_trace_completeness(state: AgentState) -> float:
    seen = {
        str(entry.get("node", ""))
        for entry in state["trace"]
        if str(entry.get("node", "")) in PHASE2_WORKFLOW_NODES
    }
    return len(seen) / len(PHASE2_WORKFLOW_NODES)


def extract_workflow_observation(state: AgentState) -> WorkflowObservation:
    trace_by_node: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in state["trace"]:
        node = str(entry.get("node", ""))
        if node in PHASE2_WORKFLOW_NODES:
            trace_by_node[node].append(dict(entry))

    tool_calls_by_node: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in state["tool_calls"]:
        tool_calls_by_node[str(record.get("node", ""))].append(dict(record))

    errors_by_node: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in state["errors"]:
        errors_by_node[str(record.get("node", ""))].append(dict(record))

    nodes = {
        node: AgentNodeObservation(
            node=node,
            execution_status=_execution_status(trace_by_node.get(node, [])),
            result_status=_result_status(node, state),
            latency_ms=_latency_ms(node, state, trace_by_node.get(node, [])),
            error_count=len(errors_by_node.get(node, [])),
            tool_call_count=len(tool_calls_by_node.get(node, [])),
            tool_failure_count=sum(
                1 for record in tool_calls_by_node.get(node, []) if record.get("status") == "failed"
            ),
        )
        for node in PHASE2_WORKFLOW_NODES
    }

    errors = tuple(
        f"{record.get('code', 'unknown')}: {record.get('message', '')}".strip()
        for record in state["errors"]
    )
    total_tool_calls = len(state["tool_calls"])
    total_tool_failures = sum(
        1 for record in state["tool_calls"] if record.get("status") == "failed"
    )
    workflow_success = not state["errors"] and all(
        observation.execution_status != "failed" for observation in nodes.values()
    )

    retrieval_metrics = _retrieval_metrics(state)
    return WorkflowObservation(
        run_id=str(state["run_metadata"]["run_id"]),
        question=state["question"],
        intent=state["intent"],
        required_agents=tuple(state["required_agents"]),
        workflow_latency_ms=_workflow_latency_ms(state, nodes),
        workflow_success=workflow_success,
        trace_completeness=calculate_trace_completeness(state),
        citation_count=len(_unique_citations(state)),
        total_tool_calls=total_tool_calls,
        total_tool_failures=total_tool_failures,
        decision_status=str(state["decision"]["decision_status"]),
        approval_status=str(state["human_approval"]["status"]),
        summary_status=str(state["executive_summary"]["summary_status"]),
        final_recommendation=str(
            state["executive_summary"]["recommendation"] or state["decision"]["recommendation"]
        ),
        retrieval_metrics=retrieval_metrics,
        nodes=nodes,
        errors=errors,
    )


def _execution_status(trace_entries: list[dict[str, object]]) -> NodeExecutionStatus:
    if not trace_entries:
        return "missing"
    event = str(trace_entries[-1].get("event", "missing"))
    if event in {"planned", "started", "completed", "failed", "skipped"}:
        return event
    return "missing"


def _result_status(node: str, state: AgentState) -> str:
    if node == "planner":
        return str(state["intent"])
    if node == "retrieval":
        retrieval = _retrieval_metrics(state)
        if retrieval:
            return "completed"
        return "not_required" if "retrieval" not in state["required_agents"] else "unknown"
    if node == "experiment_analysis":
        return str(state["experiment_analysis"]["status"])
    if node == "business_impact":
        return str(state["business_impact"]["impact_status"])
    if node == "risk_assessment":
        return str(state["risk_assessment"]["risk_status"])
    if node == "decision":
        return str(state["decision"]["decision_status"])
    if node == "human_approval":
        return str(state["human_approval"]["status"])
    return str(state["executive_summary"]["summary_status"])


def _latency_ms(
    node: str,
    state: AgentState,
    trace_entries: list[dict[str, object]],
) -> float:
    if node == "retrieval":
        retrieval = _retrieval_metrics(state)
        embedding = _float_value(retrieval.get("embedding_time_ms"))
        vector = _float_value(retrieval.get("vector_search_time_ms"))
        if embedding is not None or vector is not None:
            return (embedding or 0.0) + (vector or 0.0)

    metrics = state["metrics"].get(node)
    if isinstance(metrics, dict):
        latency = _float_value(metrics.get("latency_ms"))
        if latency is not None:
            return latency

    started_at = next(
        (
            _parse_iso8601(str(entry.get("at", "")))
            for entry in trace_entries
            if entry.get("event") == "started"
        ),
        None,
    )
    completed_at = next(
        (
            _parse_iso8601(str(entry.get("at", "")))
            for entry in reversed(trace_entries)
            if entry.get("event") in {"completed", "failed", "skipped", "planned"}
        ),
        None,
    )
    if started_at is not None and completed_at is not None:
        return max((completed_at - started_at).total_seconds() * 1000.0, 0.0)
    return 0.0


def _workflow_latency_ms(
    state: AgentState,
    nodes: dict[str, AgentNodeObservation],
) -> float:
    created_at = _parse_iso8601(state["timestamps"]["created_at"])
    updated_at = _parse_iso8601(state["timestamps"]["updated_at"])
    if created_at is not None and updated_at is not None:
        elapsed = max((updated_at - created_at).total_seconds() * 1000.0, 0.0)
        if elapsed > 0.0:
            return elapsed
    trace_times = [
        parsed
        for parsed in (_parse_iso8601(str(entry.get("at", ""))) for entry in state["trace"])
        if parsed is not None
    ]
    if trace_times:
        trace_elapsed = max((max(trace_times) - min(trace_times)).total_seconds() * 1000.0, 0.0)
        if trace_elapsed > 0.0:
            return trace_elapsed
    return sum(node.latency_ms for node in nodes.values())


def _retrieval_metrics(state: AgentState) -> dict[str, object]:
    retrieval = state["metrics"].get("retrieval", {})
    return dict(retrieval) if isinstance(retrieval, dict) else {}


def _unique_citations(state: AgentState) -> set[tuple[str, str, str, str]]:
    citations = [
        *state["citations"],
        *state["experiment_analysis"]["evidence_citations"],
        *state["business_impact"]["evidence_citations"],
        *state["risk_assessment"]["evidence_citations"],
        *state["decision"]["evidence_citations"],
        *state["executive_summary"]["evidence_citations"],
    ]
    return {
        (
            str(citation.get("document_id", "")),
            str(citation.get("experiment_id", "")),
            str(citation.get("section", "")),
            str(citation.get("quote", "")),
        )
        for citation in citations
    }


def _float_value(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_iso8601(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
