from __future__ import annotations

from packages.agents.state import create_initial_state


def build_decision_state():
    state = create_initial_state("Should we roll out the payment recommendation experiment?")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
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
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-001-payment-recommendation",
            "content": "Treatment improved payment success rate with significant lift.",
            "score": 0.94,
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
        "hypothesis": "Payment ranking will improve successful checkout completion.",
        "primary_metric": "payment_success_rate",
        "control": {
            "metric_name": "payment_success_rate",
            "variant": "control",
            "value": 0.6760,
            "unit": "rate",
        },
        "treatment": {
            "metric_name": "payment_success_rate",
            "variant": "treatment",
            "value": 0.7310,
            "unit": "rate",
        },
        "treatment_control_comparison": {
            "metric_name": "payment_success_rate",
            "control_value": 0.6760,
            "treatment_value": 0.7310,
            "absolute_delta": 0.0550,
            "relative_lift": 0.0814,
            "unit": "rate",
            "p_value": 0.041,
        },
        "observed_lift": {
            "metric_name": "payment_success_rate",
            "relative_lift": 0.0814,
            "unit": "rate",
            "p_value": 0.041,
        },
        "statistical_significance": {
            "p_value": 0.041,
            "is_significant": True,
        },
        "guardrail_metrics": [
            {
                "metric_name": "payment_retry_rate",
                "control_value": 0.1180,
                "treatment_value": 0.0830,
                "absolute_delta": -0.0350,
                "relative_lift": -0.2966,
                "unit": "rate",
                "p_value": 0.083,
            }
        ],
        "limitations": [],
        "evidence_citations": list(state["citations"]),
        "analysis_confidence": "high",
    }
    state["business_impact"] = {
        **state["business_impact"],
        "summary": "Estimated positive business impact.",
        "impact_status": "estimated",
        "primary_business_metric": "payment_success_rate",
        "baseline_value": 0.6760,
        "treatment_value": 0.7310,
        "absolute_lift": 0.0550,
        "relative_lift": 0.0814,
        "estimated_annualized_impact": {
            "amount": 1250000,
            "currency": "USD",
            "period": "annual",
        },
        "affected_segment": "high-intent wallet users",
        "operational_savings": None,
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
    return state


def test_decision_agent_recommends_rollout_for_positive_low_risk_evidence() -> None:
    from packages.agents.decision_agent import DecisionAgent

    update = DecisionAgent().run(build_decision_state())

    assert update["decision"]["decision_status"] == "decided"
    assert update["decision"]["recommendation"] == "rollout"
    assert update["decision"]["confidence"] == "high"
    assert update["decision"]["approval_required"] is True
    assert update["decision"]["evidence_citations"]
    assert update["metrics"]["decision"]["status"] == "decided"
    assert update["metrics"]["decision"]["recommendation"] == "rollout"
    assert [entry["event"] for entry in update["trace"]] == ["started", "completed"]


def test_decision_agent_records_evidence_validation_and_confidence_tool_calls() -> None:
    from packages.agents.decision_agent import DecisionAgent

    state = build_decision_state()

    update = DecisionAgent().run(state)

    assert [call["tool_name"] for call in update["tool_calls"]] == [
        "validate_required_evidence",
        "score_decision_confidence",
    ]
    assert update["decision"]["confidence"] == "high"


def test_decision_agent_uses_evidence_validation_to_block_incomplete_state() -> None:
    from packages.agents.decision_agent import DecisionAgent

    state = build_decision_state()
    state["experiment_analysis"]["statistical_significance"] = {}
    state["citations"] = []

    update = DecisionAgent().run(state)

    assert update["decision"]["decision_status"] in {"needs_more_data", "insufficient_data"}
    assert update["tool_calls"][0]["tool_name"] == "validate_required_evidence"
    assert "citations" in update["decision"]["blocking_issues"][0] or update["decision"][
        "blocking_issues"
    ]


def test_decision_agent_requests_more_data_when_evidence_is_incomplete() -> None:
    from packages.agents.decision_agent import DecisionAgent

    state = build_decision_state()
    state["experiment_analysis"]["statistical_significance"] = {}
    state["experiment_analysis"]["observed_lift"].pop("p_value")
    state["experiment_analysis"]["treatment_control_comparison"].pop("p_value")
    state["business_impact"]["impact_status"] = "partial_estimate"
    state["risk_assessment"]["risk_status"] = "partial_assessment"
    state["risk_assessment"]["overall_risk_level"] = "medium"
    state["risk_assessment"]["statistical_concerns"] = [
        "No stored statistical significance signal was available.",
    ]

    update = DecisionAgent().run(state)

    assert update["decision"]["decision_status"] == "needs_more_data"
    assert update["decision"]["recommendation"] == "continue_experiment"
    assert update["decision"]["confidence"] == "low"
    assert update["decision"]["blocking_issues"]


def test_decision_agent_recommends_do_not_rollout_for_negative_lift() -> None:
    from packages.agents.decision_agent import DecisionAgent

    state = build_decision_state()
    state["experiment_analysis"]["treatment"]["value"] = 0.6410
    state["experiment_analysis"]["treatment_control_comparison"] = {
        "metric_name": "payment_success_rate",
        "control_value": 0.6760,
        "treatment_value": 0.6410,
        "absolute_delta": -0.0350,
        "relative_lift": -0.0518,
        "unit": "rate",
        "p_value": 0.041,
    }
    state["experiment_analysis"]["observed_lift"] = {
        "metric_name": "payment_success_rate",
        "relative_lift": -0.0518,
        "unit": "rate",
        "p_value": 0.041,
    }
    state["business_impact"]["treatment_value"] = 0.6410
    state["business_impact"]["absolute_lift"] = -0.0350
    state["business_impact"]["relative_lift"] = -0.0518
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

    update = DecisionAgent().run(state)

    assert update["decision"]["decision_status"] == "decided"
    assert update["decision"]["recommendation"] == "do_not_rollout"
    assert update["decision"]["confidence"] == "medium"


def test_decision_agent_recommends_rollback_for_harmful_guardrail_deterioration() -> None:
    from packages.agents.decision_agent import DecisionAgent

    state = build_decision_state()
    state["experiment_analysis"]["guardrail_metrics"] = [
        {
            "metric_name": "refund_rate",
            "control_value": 0.0120,
            "treatment_value": 0.0280,
            "absolute_delta": 0.0160,
            "relative_lift": 1.3333,
            "unit": "rate",
            "p_value": 0.031,
        }
    ]
    state["risk_assessment"]["overall_risk_level"] = "high"
    state["risk_assessment"]["risk_score"] = 4
    state["risk_assessment"]["guardrail_concerns"] = [
        "Guardrail metric refund_rate moved in a riskier direction.",
    ]
    state["risk_assessment"]["risk_factors"] = [
        {
            "code": "guardrail_metric_deterioration",
            "title": "refund_rate deteriorated",
            "severity": "high",
            "category": "guardrail",
            "detail": "Guardrail metric refund_rate moved in a riskier direction.",
            "mitigation": "Stop rollout and investigate the regression.",
        }
    ]

    update = DecisionAgent().run(state)

    assert update["decision"]["decision_status"] == "decided"
    assert update["decision"]["recommendation"] == "rollback"
    assert any(
        "guardrail" in issue.lower() or "refund_rate" in issue.lower()
        for issue in update["decision"]["blocking_issues"]
    )


def test_decision_agent_preserves_citations_trace_metrics_and_blocking_errors() -> None:
    from packages.agents.decision_agent import DecisionAgent

    state = build_decision_state()
    state["errors"] = [
        {
            "code": "retrieval_failed",
            "message": "Retrieval failed: vector search timed out",
            "node": "retrieval",
            "at": "2026-07-08T00:00:00Z",
        }
    ]

    update = DecisionAgent().run(state)

    assert update["decision"]["decision_status"] == "blocked"
    assert update["decision"]["recommendation"] == "needs_more_data"
    assert update["decision"]["evidence_citations"] == state["citations"]
    assert update["decision"]["blocking_issues"] == [
        "retrieval_failed: Retrieval failed: vector search timed out"
    ]
    assert update["metrics"]["decision"]["blocking_issue_count"] == 1
    assert update["metrics"]["decision"]["latency_ms"] >= 0.0
