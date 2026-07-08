from __future__ import annotations

import json

from packages.agents.state import (
    append_error,
    append_trace,
    build_initial_state,
    create_initial_state,
    record_metric,
    validate_state_shape,
)


def test_create_initial_state_sets_shared_contract_defaults() -> None:
    state = create_initial_state("Why did this experiment ship?")

    assert state["question"] == "Why did this experiment ship?"
    assert state["request"]["question"] == "Why did this experiment ship?"
    assert state["request"]["normalized_question"] == "Why did this experiment ship?"
    assert state["intent"] == "unknown"
    assert state["required_agents"] == []
    assert state["planner_notes"] == ""
    assert state["experiment_context"] == {
        "experiment_ids": [],
        "filters": {},
    }
    assert state["retrieved_chunks"] == []
    assert state["citations"] == []
    assert state["experiment_analysis"] == {
        "summary": "",
        "findings": [],
        "status": "not_applicable",
        "experiment_id": "",
        "experiment_name": "",
        "hypothesis": "",
        "primary_metric": "",
        "control": {},
        "treatment": {},
        "treatment_control_comparison": {},
        "observed_lift": {},
        "statistical_significance": {},
        "confidence_level": {},
        "guardrail_metrics": [],
        "limitations": [],
        "evidence_citations": [],
        "analysis_confidence": "low",
    }
    assert state["business_impact"] == {
        "summary": "",
        "impact_status": "not_required",
        "primary_business_metric": "",
        "baseline_value": None,
        "treatment_value": None,
        "absolute_lift": None,
        "relative_lift": None,
        "estimated_annualized_impact": None,
        "affected_segment": "",
        "operational_savings": None,
        "confidence_level": "low",
        "assumptions": [],
        "limitations": [],
        "evidence_citations": [],
    }
    assert state["risk_assessment"] == {
        "risk_status": "not_required",
        "overall_risk_level": "unknown",
        "risk_score": None,
        "risk_factors": [],
        "guardrail_concerns": [],
        "data_quality_concerns": [],
        "statistical_concerns": [],
        "rollout_concerns": [],
        "user_or_business_concerns": [],
        "mitigation_actions": [],
        "assumptions": [],
        "limitations": [],
        "evidence_citations": [],
        "confidence_level": "low",
    }
    assert state["experiment_metadata"] == {}
    assert state["experiment_metrics"] == []
    assert state["risks"] == []
    assert state["decision"] == {
        "decision_status": "not_required",
        "recommendation": "unknown",
        "confidence": "unknown",
        "rationale": "",
        "supporting_evidence": [],
        "blocking_issues": [],
        "recommended_next_actions": [],
        "approval_required": False,
        "evidence_citations": [],
        "assumptions": [],
        "limitations": [],
    }
    assert state["executive_summary"] == {
        "summary": "",
    }
    assert state["human_approval"] == {
        "status": "not_requested",
        "reviewer": None,
        "reviewed_at": None,
        "notes": "",
    }
    assert state["tool_calls"] == []
    assert state["metrics"] == {}
    assert state["errors"] == []
    assert state["trace"] == []
    assert state["run_metadata"]["state_version"] == 7
    assert state["run_metadata"]["workflow"] == "phase2_shared_state"
    assert state["timestamps"]["created_at"]
    assert state["timestamps"]["updated_at"]


def test_create_initial_state_sets_structured_experiment_analysis_defaults() -> None:
    state = create_initial_state("Analyze the payment recommendation experiment.")

    assert state["experiment_analysis"] == {
        "summary": "",
        "findings": [],
        "status": "not_applicable",
        "experiment_id": "",
        "experiment_name": "",
        "hypothesis": "",
        "primary_metric": "",
        "control": {},
        "treatment": {},
        "treatment_control_comparison": {},
        "observed_lift": {},
        "statistical_significance": {},
        "confidence_level": {},
        "guardrail_metrics": [],
        "limitations": [],
        "evidence_citations": [],
        "analysis_confidence": "low",
    }


def test_build_initial_state_remains_a_compatibility_alias() -> None:
    state = build_initial_state("Should we ship?")

    assert state["question"] == "Should we ship?"
    assert state["request"]["normalized_question"] == "Should we ship?"
    assert state["run_metadata"]["workflow"] == "phase2_shared_state"
    assert state["timestamps"]["created_at"]


def test_append_trace_adds_new_entry_and_updates_timestamp() -> None:
    state = create_initial_state("What happened?")

    updated = append_trace(
        state,
        node="planner",
        event="classified",
        details={"intent": "qa"},
    )

    assert len(updated["trace"]) == 1
    assert updated["trace"][0]["node"] == "planner"
    assert updated["trace"][0]["event"] == "classified"
    assert updated["trace"][0]["details"] == {"intent": "qa"}
    assert updated["timestamps"]["updated_at"] >= state["timestamps"]["updated_at"]


def test_append_error_adds_structured_error_and_updates_timestamp() -> None:
    state = create_initial_state("What failed?")

    updated = append_error(
        state,
        code="planner_failure",
        message="planner failed",
        node="planner",
        details={"reason": "timeout"},
    )

    assert updated["errors"] == [
        {
            "code": "planner_failure",
            "message": "planner failed",
            "node": "planner",
            "details": {"reason": "timeout"},
            "at": updated["errors"][0]["at"],
        }
    ]
    assert updated["timestamps"]["updated_at"] >= state["timestamps"]["updated_at"]


def test_record_metric_sets_named_metric_and_updates_timestamp() -> None:
    state = create_initial_state("How long did this take?")

    updated = record_metric(state, "planner_latency_ms", 12.5)

    assert updated["metrics"] == {"planner_latency_ms": 12.5}
    assert updated["timestamps"]["updated_at"] >= state["timestamps"]["updated_at"]


def test_state_is_json_serializable_and_validatable() -> None:
    state = create_initial_state("Summarize this experiment.")
    state = append_trace(state, node="planner", event="completed")
    state = append_error(state, code="none", message="no-op")
    state = record_metric(state, "planner_latency_ms", 1)

    payload = json.loads(json.dumps(state))
    validated = validate_state_shape(payload)

    assert payload["question"] == "Summarize this experiment."
    assert validated["question"] == "Summarize this experiment."
