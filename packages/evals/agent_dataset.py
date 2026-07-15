from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_AGENT_DATASET_PATH = Path("data/eval/agent_dataset.json")
_VALID_CATEGORIES = {
    "approval_workflow",
    "business_impact",
    "insufficient_evidence",
    "lookup",
    "risk_guardrail",
    "rollout_decision",
}
_VALID_INTENTS = {
    "business_impact",
    "decision_support",
    "executive_summary",
    "experiment_lookup",
    "risk_assessment",
}
_VALID_REQUIRED_AGENTS = {
    "business_impact",
    "decision",
    "executive_summary",
    "experiment_analysis",
    "human_approval",
    "retrieval",
    "risk_assessment",
}
_VALID_DECISION_STATUSES = {None, "decided", "needs_more_data"}
_VALID_SUMMARY_STATUSES = {None, "generated", "partial_summary"}
_VALID_FAILURE_MODES = {None, "insufficient_business_evidence"}
_VALID_APPROVAL_STATUSES = {
    "not_requested",
    "skipped",
    "pending",
    "approved",
    "rejected",
    "revision_requested",
}


@dataclass(frozen=True)
class AgentEvaluationCase:
    id: str
    question: str
    category: str
    expected_intent: str
    expected_required_agents: tuple[str, ...]
    expected_decision_status: str | None = None
    expected_recommendation: str | None = None
    expected_summary_status: str | None = None
    expected_approval_status: str | None = None
    expected_min_citations: int | None = None
    expected_failure_mode: str | None = None
    notes: str | None = None


def load_agent_evaluation_dataset(
    path: Path = DEFAULT_AGENT_DATASET_PATH,
) -> list[AgentEvaluationCase]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"unable to read agent evaluation dataset: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent evaluation dataset is not valid JSON: {path}") from exc

    if not isinstance(raw, list):
        raise ValueError("agent evaluation dataset must be a JSON list")

    cases = [_case_from_mapping(item, index=index) for index, item in enumerate(raw)]
    case_ids = [case.id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("agent evaluation dataset contains duplicate case ids")
    return cases


def _case_from_mapping(item: Any, *, index: int) -> AgentEvaluationCase:
    if not isinstance(item, dict):
        raise ValueError(f"agent evaluation dataset item {index} must be an object")

    required = {"id", "question", "category", "expected_intent", "expected_required_agents"}
    missing = sorted(required - set(item))
    if missing:
        raise ValueError(f"agent evaluation dataset item {index} is missing: {', '.join(missing)}")

    expected_min_citations = item.get("expected_min_citations")
    if expected_min_citations is not None and (
        not isinstance(expected_min_citations, int) or expected_min_citations < 0
    ):
        raise ValueError(
            f"agent evaluation dataset item {index} field 'expected_min_citations' "
            "must be a non-negative integer"
        )

    expected_approval_status = _optional_string(item, "expected_approval_status", index=index)
    if (
        expected_approval_status is not None
        and expected_approval_status not in _VALID_APPROVAL_STATUSES
    ):
        raise ValueError(
            f"agent evaluation dataset item {index} field 'expected_approval_status' "
            "must be a known approval status"
        )

    case = AgentEvaluationCase(
        id=_required_string(item, "id", index=index),
        question=_required_string(item, "question", index=index),
        category=_required_string(item, "category", index=index),
        expected_intent=_required_string(item, "expected_intent", index=index),
        expected_required_agents=_required_string_tuple(
            item,
            "expected_required_agents",
            index=index,
        ),
        expected_decision_status=_optional_string(
            item,
            "expected_decision_status",
            index=index,
        ),
        expected_recommendation=_optional_string(
            item,
            "expected_recommendation",
            index=index,
        ),
        expected_summary_status=_optional_string(
            item,
            "expected_summary_status",
            index=index,
        ),
        expected_approval_status=expected_approval_status,
        expected_min_citations=expected_min_citations,
        expected_failure_mode=_optional_string(
            item,
            "expected_failure_mode",
            index=index,
        ),
        notes=_optional_string(item, "notes", index=index),
    )
    _require_known(case.category, field="category", allowed=_VALID_CATEGORIES, index=index)
    _require_known(
        case.expected_intent,
        field="expected_intent",
        allowed=_VALID_INTENTS,
        index=index,
    )
    for required_agent in case.expected_required_agents:
        _require_known(
            required_agent,
            field="expected_required_agents",
            allowed=_VALID_REQUIRED_AGENTS,
            index=index,
        )
    _require_known(
        case.expected_decision_status,
        field="expected_decision_status",
        allowed=_VALID_DECISION_STATUSES,
        index=index,
    )
    _require_known(
        case.expected_summary_status,
        field="expected_summary_status",
        allowed=_VALID_SUMMARY_STATUSES,
        index=index,
    )
    _require_known(
        case.expected_failure_mode,
        field="expected_failure_mode",
        allowed=_VALID_FAILURE_MODES,
        index=index,
    )
    return case


def _require_known(
    value: str | None,
    *,
    field: str,
    allowed: set[str | None],
    index: int,
) -> None:
    if value not in allowed:
        rendered = ", ".join(sorted(item for item in allowed if item is not None))
        raise ValueError(
            f"agent evaluation dataset item {index} field {field!r} must be one of: {rendered}"
        )


def _required_string(item: dict[str, Any], key: str, *, index: int) -> str:
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"agent evaluation dataset item {index} field {key!r} must be a string")
    return value.strip()


def _required_string_tuple(item: dict[str, Any], key: str, *, index: int) -> tuple[str, ...]:
    value = item[key]
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"agent evaluation dataset item {index} field {key!r} must be a non-empty list"
        )
    entries: list[str] = []
    for offset, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(
                f"agent evaluation dataset item {index} field {key!r} entry {offset} "
                "must be a string"
            )
        entries.append(entry.strip())
    return tuple(entries)


def _optional_string(item: dict[str, Any], key: str, *, index: int) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"agent evaluation dataset item {index} field {key!r} must be a string when present"
        )
    return value.strip()
