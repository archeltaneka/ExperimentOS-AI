from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from packages.agents.state import (
    AgentState,
    AgentStateUpdate,
    ErrorRecord,
    HumanApprovalRecord,
    create_error_entry,
    create_trace_entry,
)

HUMAN_APPROVAL_NODE = "human_approval"
_VALID_APPROVAL_STATUSES = {"approved", "rejected", "revision_requested"}


@dataclass
class HumanApprovalAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        trace = [create_trace_entry(node=HUMAN_APPROVAL_NODE, event="started")]
        approval, errors, details = _build_human_approval(state)
        return {
            "human_approval": approval,
            "errors": errors,
            "trace": [
                *trace,
                create_trace_entry(
                    node=HUMAN_APPROVAL_NODE,
                    event="completed",
                    details=details,
                ),
            ],
            "metrics": {
                **state["metrics"],
                "human_approval": {
                    "status": approval["status"],
                    "latency_ms": (perf_counter() - started_at) * 1000.0,
                    "approval_required": approval["required"],
                    "input_present": bool(state["human_approval_input"]),
                    "has_feedback": bool(approval["feedback"]),
                    "error_count": len(errors),
                },
            },
        }


def _build_human_approval(
    state: AgentState,
) -> tuple[HumanApprovalRecord, list[ErrorRecord], dict[str, object]]:
    decision = state.get("decision")
    input_present = bool(state["human_approval_input"])
    input_errors: list[ErrorRecord] = []
    if not isinstance(decision, dict) or "approval_required" not in decision:
        return (
            {
                "status": "not_requested",
                "required": False,
                "feedback": "",
                "actor": None,
                "timestamp": None,
            },
            [
                create_error_entry(
                    code="human_approval_missing_decision",
                    message="Human approval could not read decision.approval_required.",
                    node=HUMAN_APPROVAL_NODE,
                )
            ],
            {
                "status": "not_requested",
                "approval_required": False,
                "input_present": input_present,
            },
        )

    approval_required = bool(decision["approval_required"])
    approval_input = _normalize_input(state["human_approval_input"])
    if approval_input["error"] is not None:
        input_errors.append(approval_input["error"])

    if not approval_required:
        return (
            {
                "status": "skipped",
                "required": False,
                "feedback": "",
                "actor": None,
                "timestamp": None,
            },
            input_errors,
            {
                "status": "skipped",
                "approval_required": False,
                "input_present": input_present,
            },
        )

    status = approval_input["status"]
    if status not in _VALID_APPROVAL_STATUSES:
        return (
            {
                "status": "pending",
                "required": True,
                "feedback": approval_input["feedback"],
                "actor": approval_input["actor"],
                "timestamp": approval_input["timestamp"],
            },
            input_errors,
            {
                "status": "pending",
                "approval_required": True,
                "input_present": input_present,
            },
        )

    return (
        {
            "status": status,
            "required": True,
            "feedback": approval_input["feedback"],
            "actor": approval_input["actor"],
            "timestamp": approval_input["timestamp"],
        },
        input_errors,
        {
            "status": status,
            "approval_required": True,
            "input_present": input_present,
        },
    )


def _normalize_input(input_record: object) -> dict[str, object]:
    if not isinstance(input_record, dict):
        return {
            "status": "",
            "feedback": "",
            "actor": None,
            "timestamp": None,
            "error": _invalid_input_error(
                reason="input_not_mapping",
                raw_type=type(input_record).__name__,
            ),
        }

    status = str(input_record.get("status", "")).strip().lower()
    feedback = _normalize_optional_string(input_record.get("feedback"), default="")
    actor = _normalize_optional_string(input_record.get("actor"))
    timestamp = _normalize_optional_string(input_record.get("timestamp"))
    error: ErrorRecord | None = None
    if status and status not in _VALID_APPROVAL_STATUSES:
        error = _invalid_input_error(
            reason="unknown_status",
            raw_type=type(input_record).__name__,
            status=status,
        )
    return {
        "status": status,
        "feedback": feedback,
        "actor": actor,
        "timestamp": timestamp,
        "error": error,
    }


def _normalize_optional_string(value: object, *, default: str | None = None) -> str | None:
    if value is None:
        return default
    normalized = str(value).strip()
    if normalized:
        return normalized
    return default


def _invalid_input_error(
    *,
    reason: str,
    raw_type: str,
    status: str | None = None,
) -> ErrorRecord:
    details: dict[str, object] = {
        "reason": reason,
        "raw_type": raw_type,
    }
    if status is not None:
        details["status"] = status
    return create_error_entry(
        code="human_approval_invalid_input",
        message="Human approval input could not be normalized safely.",
        node=HUMAN_APPROVAL_NODE,
        details=details,
    )
