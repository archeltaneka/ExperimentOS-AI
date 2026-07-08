from __future__ import annotations

from packages.agents.state import create_initial_state


def build_executive_summary_state():
    state = create_initial_state("Summarize the payment recommendation experiment for executives.")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "executive_summary",
    ]
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-001-payment-recommendation",
            "quote": "Treatment improved payment success rate with significant lift.",
            "section": "Results",
            "metadata": {"section": "Results"},
        }
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "summary": "Primary metric improved with strong supporting evidence.",
        "findings": [
            "Treatment beat control on payment success rate.",
            "Guardrail metrics remained acceptable.",
        ],
        "status": "completed",
        "experiment_id": "exp-001-payment-recommendation",
        "experiment_name": "Adaptive Payment Method Recommendation",
        "primary_metric": "payment_success_rate",
        "statistical_significance": {
            "p_value": 0.041,
            "is_significant": True,
        },
        "limitations": [],
        "evidence_citations": list(state["citations"]),
        "analysis_confidence": "high",
    }
    state["business_impact"] = {
        **state["business_impact"],
        "summary": "Estimated positive business impact from the observed lift.",
        "impact_status": "estimated",
        "primary_business_metric": "payment_success_rate",
        "baseline_value": 0.6760,
        "treatment_value": 0.7310,
        "absolute_lift": 0.0550,
        "relative_lift": 0.0814,
        "confidence_level": "high",
        "assumptions": ["Impact is based on observed primary metric lift."],
        "limitations": [],
        "evidence_citations": list(state["citations"]),
    }
    state["risk_assessment"] = {
        **state["risk_assessment"],
        "risk_status": "assessed",
        "overall_risk_level": "low",
        "risk_score": 0,
        "risk_factors": [],
        "guardrail_concerns": [],
        "data_quality_concerns": [],
        "statistical_concerns": [],
        "rollout_concerns": [],
        "user_or_business_concerns": [],
        "mitigation_actions": ["Monitor rollout metrics during the initial ramp."],
        "assumptions": ["Risk score is deterministic."],
        "limitations": [],
        "evidence_citations": list(state["citations"]),
        "confidence_level": "high",
    }
    state["decision"] = {
        **state["decision"],
        "decision_status": "decided",
        "recommendation": "rollout",
        "confidence": "high",
        "rationale": "Positive lift, grounded business impact, and low risk support rollout.",
        "supporting_evidence": [
            "Primary metric improved.",
            "Business impact estimate is positive.",
        ],
        "blocking_issues": [],
        "recommended_next_actions": [
            "Roll out gradually and monitor primary and guardrail metrics.",
        ],
        "approval_required": True,
        "evidence_citations": list(state["citations"]),
        "assumptions": ["Decision uses deterministic rules."],
        "limitations": [],
    }
    return state


def test_executive_summary_agent_generates_full_summary_for_positive_evidence() -> None:
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent

    update = ExecutiveSummaryAgent().run(build_executive_summary_state())

    assert update["executive_summary"]["summary_status"] == "generated"
    assert update["executive_summary"]["headline"] == (
        "Rollout is supported by the current evidence."
    )
    assert update["executive_summary"]["recommendation"] == "rollout"
    assert update["executive_summary"]["business_impact_summary"] == (
        "Estimated positive business impact from the observed lift."
    )
    assert update["executive_summary"]["risk_summary"] == (
        "Risk is currently assessed as low with no material blocking factors recorded."
    )
    assert update["executive_summary"]["decision_rationale"] == (
        "Positive lift, grounded business impact, and low risk support rollout."
    )
    assert update["executive_summary"]["confidence"] == "high"
    assert update["executive_summary"]["recommended_next_actions"] == [
        "Roll out gradually and monitor primary and guardrail metrics."
    ]


def test_executive_summary_agent_returns_partial_summary_when_inputs_are_incomplete() -> None:
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent

    state = build_executive_summary_state()
    state["business_impact"]["impact_status"] = "partial_estimate"
    state["business_impact"]["limitations"] = [
        "Baseline and treatment values were unavailable, so only observed lift could be reported."
    ]
    state["risk_assessment"]["risk_status"] = "partial_assessment"
    state["risk_assessment"]["limitations"] = ["Risk evidence is incomplete."]

    update = ExecutiveSummaryAgent().run(state)

    assert update["executive_summary"]["summary_status"] == "partial_summary"
    assert "incomplete" in " ".join(update["executive_summary"]["limitations"]).lower()
    assert update["executive_summary"]["recommendation"] == "rollout"


def test_executive_summary_agent_preserves_needs_more_data_decision_tone() -> None:
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent

    state = build_executive_summary_state()
    state["decision"]["decision_status"] = "needs_more_data"
    state["decision"]["recommendation"] = "continue_experiment"
    state["decision"]["confidence"] = "low"
    state["decision"]["rationale"] = (
        "Evidence is directionally positive but incomplete, so rollout is not ready."
    )
    state["decision"]["blocking_issues"] = [
        "Statistical significance is missing for the primary metric."
    ]

    update = ExecutiveSummaryAgent().run(state)

    assert update["executive_summary"]["summary_status"] == "partial_summary"
    assert update["executive_summary"]["headline"] == (
        "Rollout is not ready; more evidence is required."
    )
    assert update["executive_summary"]["recommendation"] == "continue_experiment"
    assert "not ready" in update["executive_summary"]["summary"].lower()


def test_executive_summary_agent_summarizes_do_not_rollout_decision() -> None:
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent

    state = build_executive_summary_state()
    state["decision"]["recommendation"] = "do_not_rollout"
    state["decision"]["rationale"] = (
        "The primary metric moved in the wrong direction, so rollout is not supported."
    )
    state["risk_assessment"]["overall_risk_level"] = "high"
    state["risk_assessment"]["risk_score"] = 3
    state["risk_assessment"]["risk_factors"] = [
        {
            "code": "negative_or_unclear_lift",
            "title": "Primary metric moved in the wrong direction",
            "severity": "high",
            "category": "user_or_business",
            "detail": "Observed lift is negative.",
            "mitigation": "Do not expand rollout.",
        }
    ]

    update = ExecutiveSummaryAgent().run(state)

    assert update["executive_summary"]["summary_status"] == "generated"
    assert update["executive_summary"]["headline"] == (
        "Do not roll out based on the current evidence."
    )
    assert update["executive_summary"]["recommendation"] == "do_not_rollout"
    assert update["executive_summary"]["risk_summary"] == (
        "Risk is currently assessed as high with 1 material factor recorded."
    )


def test_executive_summary_agent_returns_insufficient_data_safely() -> None:
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent

    state = create_initial_state("Summarize this for executives.")
    state["required_agents"] = ["executive_summary"]

    update = ExecutiveSummaryAgent().run(state)

    assert update["executive_summary"]["summary_status"] == "insufficient_data"
    assert update["executive_summary"]["headline"] == (
        "Insufficient evidence to prepare an executive summary."
    )
    assert update["executive_summary"]["recommendation"] == "needs_more_data"
    assert update["executive_summary"]["key_findings"] == []
    assert update["executive_summary"]["limitations"]


def test_executive_summary_agent_preserves_citations_trace_and_metrics() -> None:
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent

    state = build_executive_summary_state()
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}

    update = ExecutiveSummaryAgent().run(state)

    assert update["executive_summary"]["evidence_citations"] == state["citations"]
    assert update["metrics"]["planner_rule_version"] == "deterministic_v1"
    assert update["metrics"]["executive_summary"]["status"] == "generated"
    assert update["metrics"]["executive_summary"]["citation_count"] == 1
    assert update["metrics"]["executive_summary"]["latency_ms"] >= 0.0
    assert [entry["event"] for entry in update["trace"]] == ["started", "completed"]
