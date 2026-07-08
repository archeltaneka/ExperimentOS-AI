from __future__ import annotations

from packages.agents.state import create_initial_state


def build_risk_assessment_state():
    state = create_initial_state("What are the rollout risks for the payment recommendation?")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
    ]
    state["experiment_context"] = {
        "experiment_ids": ["exp-001-payment-recommendation"],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }
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
        "confidence_level": {"confidence_level": 0.95},
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
    state["experiment_metadata"] = {
        "experiment_id": "exp-001-payment-recommendation",
        "name": "Adaptive Payment Method Recommendation",
        "area": "payment recommendation",
        "primary_metric": "payment_success_rate",
        "secondary_metrics": [
            "checkout_completion_rate",
            "payment_retry_rate",
        ],
        "business_decision": "Roll out to AU, SG, and GB.",
        "imperfections": [],
    }
    state["experiment_metrics"] = [
        {
            "metric_name": "payment_success_rate",
            "variant": "control",
            "value": 0.6760,
            "unit": "rate",
        },
        {
            "metric_name": "payment_success_rate",
            "variant": "treatment",
            "value": 0.7310,
            "unit": "rate",
            "p_value": 0.041,
            "lift_vs_control": 0.0814,
        },
    ]
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
    return state


def test_risk_assessment_agent_returns_low_risk_for_strong_positive_evidence() -> None:
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent

    state = build_risk_assessment_state()

    update = RiskAssessmentAgent().run(state)

    assert update["risk_assessment"]["risk_status"] == "assessed"
    assert update["risk_assessment"]["overall_risk_level"] == "low"
    assert update["risk_assessment"]["risk_score"] == 0
    assert update["risk_assessment"]["risk_factors"] == []
    assert update["risk_assessment"]["evidence_citations"] == state["citations"]
    assert update["risk_assessment"]["confidence_level"] == "high"
    assert update["risks"] == []
    assert [entry["event"] for entry in update["trace"]] == ["started", "completed"]
    assert update["metrics"]["risk_assessment"]["status"] == "assessed"


def test_risk_assessment_agent_flags_missing_statistical_support() -> None:
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent

    state = build_risk_assessment_state()
    state["experiment_analysis"]["statistical_significance"] = {}
    state["experiment_analysis"]["observed_lift"].pop("p_value")
    state["experiment_analysis"]["treatment_control_comparison"].pop("p_value")
    state["experiment_analysis"]["analysis_confidence"] = "medium"

    update = RiskAssessmentAgent().run(state)

    assert update["risk_assessment"]["risk_status"] == "assessed"
    assert update["risk_assessment"]["overall_risk_level"] == "medium"
    assert update["risk_assessment"]["risk_score"] == 2
    assert any(
        factor["code"] == "missing_statistical_significance"
        for factor in update["risk_assessment"]["risk_factors"]
    )
    assert update["risk_assessment"]["statistical_concerns"]


def test_risk_assessment_agent_returns_high_risk_for_negative_lift() -> None:
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent

    state = build_risk_assessment_state()
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

    update = RiskAssessmentAgent().run(state)

    assert update["risk_assessment"]["overall_risk_level"] == "high"
    assert update["risk_assessment"]["risk_score"] == 3
    assert any(
        factor["code"] == "negative_or_unclear_lift"
        for factor in update["risk_assessment"]["risk_factors"]
    )


def test_risk_assessment_agent_returns_partial_assessment_when_business_impact_missing() -> None:
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent

    state = build_risk_assessment_state()
    state["business_impact"] = {
        **state["business_impact"],
        "impact_status": "insufficient_data",
        "baseline_value": None,
        "treatment_value": None,
        "absolute_lift": None,
        "relative_lift": None,
        "estimated_annualized_impact": None,
        "confidence_level": "low",
        "limitations": ["Business impact estimate could not be grounded."],
    }

    update = RiskAssessmentAgent().run(state)

    assert update["risk_assessment"]["risk_status"] == "partial_assessment"
    assert update["risk_assessment"]["overall_risk_level"] == "medium"
    assert any(
        factor["code"] == "business_impact_insufficient"
        for factor in update["risk_assessment"]["risk_factors"]
    )
    assert update["risk_assessment"]["user_or_business_concerns"]


def test_risk_assessment_agent_returns_insufficient_data_safely() -> None:
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent

    state = create_initial_state("What are the rollout risks?")
    state["required_agents"] = ["risk_assessment"]

    update = RiskAssessmentAgent().run(state)

    assert update["risk_assessment"]["risk_status"] == "insufficient_data"
    assert update["risk_assessment"]["overall_risk_level"] == "unknown"
    assert update["risk_assessment"]["risk_score"] is None
    assert update["metrics"]["risk_assessment"]["status"] == "insufficient_data"
    assert update["risk_assessment"]["limitations"]


def test_risk_assessment_agent_preserves_citations_trace_and_metrics() -> None:
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent

    state = build_risk_assessment_state()
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}

    update = RiskAssessmentAgent().run(state)

    assert update["risk_assessment"]["evidence_citations"] == state["citations"]
    assert update["metrics"]["planner_rule_version"] == "deterministic_v1"
    assert update["metrics"]["risk_assessment"]["citation_count"] == 1
    assert update["metrics"]["risk_assessment"]["latency_ms"] >= 0.0
    assert [entry["node"] for entry in update["trace"]] == [
        "risk_assessment",
        "risk_assessment",
    ]
