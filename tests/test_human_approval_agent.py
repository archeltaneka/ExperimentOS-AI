from __future__ import annotations

from packages.agents.human_approval_agent import HumanApprovalAgent
from packages.agents.state import AgentState, create_initial_state


def build_human_approval_state() -> AgentState:
    state = create_initial_state("Should we roll out the payment recommendation experiment?")
    state["decision"] = {
        **state["decision"],
        "decision_status": "decided",
        "recommendation": "rollout",
        "confidence": "high",
        "rationale": "Positive lift, positive business impact, and low risk.",
        "supporting_evidence": [
            "Primary metric improved.",
            "Business impact estimate is positive.",
        ],
        "blocking_issues": [],
        "recommended_next_actions": ["Roll out gradually and monitor guardrails."],
        "approval_required": True,
        "evidence_citations": [],
        "assumptions": ["Decision uses deterministic rules."],
        "limitations": [],
    }
    return state


def test_human_approval_agent_skips_when_approval_not_required() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = False

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "skipped"
    assert update["human_approval"]["required"] is False


def test_human_approval_agent_marks_pending_when_required_but_missing_input() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {}

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "pending"
    assert update["human_approval"]["required"] is True


def test_human_approval_agent_records_approved() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {
        "status": "approved",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"] == {
        "status": "approved",
        "required": True,
        "feedback": "",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }


def test_human_approval_agent_records_rejected_with_feedback() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {
        "status": "rejected",
        "feedback": "Do not proceed until JP telemetry is fixed.",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "rejected"
    assert update["human_approval"]["feedback"] == (
        "Do not proceed until JP telemetry is fixed."
    )


def test_human_approval_agent_records_revision_requested() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {
        "status": "revision_requested",
        "feedback": "Clarify the guardrail monitoring plan before approval.",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "revision_requested"
    assert update["human_approval"]["feedback"] == (
        "Clarify the guardrail monitoring plan before approval."
    )


def test_human_approval_agent_appends_error_for_unknown_status() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {
        "status": "escalated",
        "feedback": "Needs another pass.",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "pending"
    assert update["human_approval"]["required"] is True
    assert update["errors"][0]["code"] == "human_approval_invalid_input"
    assert update["errors"][0]["node"] == "human_approval"


def test_human_approval_agent_appends_error_for_malformed_raw_input() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = "approve now"  # type: ignore[assignment]

    update = HumanApprovalAgent().run(state)  # type: ignore[arg-type]

    assert update["human_approval"]["status"] == "pending"
    assert update["human_approval"]["required"] is True
    assert update["errors"][0]["code"] == "human_approval_invalid_input"
    assert update["errors"][0]["node"] == "human_approval"


def test_human_approval_agent_returns_error_when_decision_is_missing() -> None:
    state = build_human_approval_state()
    del state["decision"]

    update = HumanApprovalAgent().run(state)  # type: ignore[arg-type]

    assert update["human_approval"] == {
        "status": "not_requested",
        "required": False,
        "feedback": "",
        "actor": None,
        "timestamp": None,
    }
    assert update["errors"][0]["code"] == "human_approval_missing_decision"
    assert update["trace"][0]["event"] == "started"
    assert update["trace"][1]["event"] == "completed"


def test_human_approval_agent_returns_error_when_approval_required_is_string() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = "true"  # type: ignore[assignment]

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"] == {
        "status": "not_requested",
        "required": False,
        "feedback": "",
        "actor": None,
        "timestamp": None,
    }
    assert update["errors"][0]["code"] == "human_approval_missing_decision"
    assert update["errors"][0]["node"] == "human_approval"


def test_human_approval_agent_returns_error_when_approval_required_is_none() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = None  # type: ignore[assignment]

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"] == {
        "status": "not_requested",
        "required": False,
        "feedback": "",
        "actor": None,
        "timestamp": None,
    }
    assert update["errors"][0]["code"] == "human_approval_missing_decision"
    assert update["errors"][0]["node"] == "human_approval"


def test_human_approval_agent_records_trace_and_metrics() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {
        "status": "approved",
        "feedback": "Looks good to proceed.",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}

    update = HumanApprovalAgent().run(state)

    assert update["trace"][0]["node"] == "human_approval"
    assert update["trace"][0]["event"] == "started"
    assert update["trace"][1]["node"] == "human_approval"
    assert update["trace"][1]["event"] == "completed"
    assert update["trace"][1]["details"] == {
        "status": "approved",
        "approval_required": True,
        "input_present": True,
    }
    assert update["metrics"]["planner_rule_version"] == "deterministic_v1"
    assert update["metrics"]["human_approval"]["status"] == "approved"
    assert update["metrics"]["human_approval"]["approval_required"] is True
    assert update["metrics"]["human_approval"]["input_present"] is True
    assert update["metrics"]["human_approval"]["has_feedback"] is True
    assert update["metrics"]["human_approval"]["error_count"] == 0
    assert isinstance(update["metrics"]["human_approval"]["latency_ms"], float)
