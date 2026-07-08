from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from pydantic import BaseModel

from packages.agents.tools.business import ABSOLUTE_LIFT_TOOL, RELATIVE_LIFT_TOOL
from packages.agents.tools.decision import DECISION_CONFIDENCE_TOOL, EVIDENCE_VALIDATION_TOOL
from packages.agents.tools.risk import RISK_SCORING_TOOL
from packages.agents.tools.schemas import ExecutedToolCall, ToolSpec

_TOOLS: dict[str, ToolSpec[Any, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def register_tool(spec: ToolSpec[Any, Any]) -> None:
    _TOOLS[spec.name] = spec


def get_tool(name: str) -> ToolSpec[Any, Any]:
    try:
        return _TOOLS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown tool: {name}") from exc


def list_tools() -> list[str]:
    return sorted(_TOOLS)


def execute_tool(
    name: str,
    payload: dict[str, object],
    *,
    node: str,
) -> ExecutedToolCall[BaseModel]:
    started_at = perf_counter()
    at = _utc_now_iso()
    try:
        spec = get_tool(name)
        validated_input = spec.input_model.model_validate(payload)
        output = spec.handler(validated_input)
        validated_output = spec.output_model.model_validate(output)
        return ExecutedToolCall(
            output=validated_output,
            record={
                "tool_name": name,
                "status": "completed",
                "node": node,
                "input_summary": validated_input.model_dump(),
                "output_summary": validated_output.model_dump(),
                "latency_ms": (perf_counter() - started_at) * 1000.0,
                "at": at,
            },
        )
    except Exception as exc:
        return ExecutedToolCall(
            output=None,
            record={
                "tool_name": name,
                "status": "failed",
                "node": node,
                "input_summary": dict(payload),
                "output_summary": {},
                "latency_ms": (perf_counter() - started_at) * 1000.0,
                "error": f"{type(exc).__name__}: {exc}",
                "at": at,
            },
        )


def _register_builtin_tools() -> None:
    for spec in (
        ABSOLUTE_LIFT_TOOL,
        RELATIVE_LIFT_TOOL,
        RISK_SCORING_TOOL,
        EVIDENCE_VALIDATION_TOOL,
        DECISION_CONFIDENCE_TOOL,
    ):
        register_tool(spec)


_register_builtin_tools()
