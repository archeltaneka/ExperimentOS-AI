from __future__ import annotations

from packages.agents.state import create_initial_state


def build_business_impact_state():
    state = create_initial_state("What is the business impact of the payment recommendation?")
    state["required_agents"] = ["retrieval", "experiment_analysis", "business_impact"]
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-001-payment-recommendation",
            "quote": "Control recorded 0.6760 while treatment recorded 0.7310.",
            "section": "Results",
            "metadata": {"section": "Results"},
        }
    ]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-001-payment-recommendation",
            "content": "Control recorded 0.6760 while treatment recorded 0.7310.",
            "score": 0.94,
            "metadata": {"section": "Results"},
        }
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "summary": "Primary metric improved in treatment.",
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
        "limitations": [
            "Sample ratio mismatch from late allocation rule change in mobile web."
        ],
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
            "revenue_per_user",
        ],
        "business_decision": "Roll out to AU, SG, and GB; hold JP pending wallet tracking fix.",
    }
    state["experiment_metrics"] = [
        {
            "metric_name": "payment_success_rate",
            "variant": "control",
            "value": 0.6760,
            "unit": "rate",
            "numerator": 46,
            "denominator": 68,
        },
        {
            "metric_name": "payment_success_rate",
            "variant": "treatment",
            "value": 0.7310,
            "unit": "rate",
            "numerator": 57,
            "denominator": 78,
        },
    ]
    return state


def test_business_impact_agent_calculates_estimate_from_baseline_and_treatment() -> None:
    from packages.agents.business_impact_agent import BusinessImpactAgent

    state = build_business_impact_state()

    update = BusinessImpactAgent().run(state)

    assert update["business_impact"]["impact_status"] == "estimated"
    assert update["business_impact"]["primary_business_metric"] == "payment_success_rate"
    assert update["business_impact"]["baseline_value"] == 0.6760
    assert update["business_impact"]["treatment_value"] == 0.7310
    assert update["business_impact"]["absolute_lift"] == 0.055
    assert update["business_impact"]["relative_lift"] == 0.081361
    assert update["business_impact"]["confidence_level"] == "high"
    assert update["business_impact"]["evidence_citations"] == state["citations"]
    assert [entry["event"] for entry in update["trace"]] == ["started", "completed"]
    assert update["metrics"]["business_impact"]["status"] == "estimated"


def test_business_impact_agent_returns_partial_estimate_when_only_observed_lift_exists() -> None:
    from packages.agents.business_impact_agent import BusinessImpactAgent

    state = build_business_impact_state()
    state["experiment_analysis"]["control"] = {}
    state["experiment_analysis"]["treatment"] = {}
    state["experiment_analysis"]["treatment_control_comparison"] = {}
    state["experiment_metrics"] = []

    update = BusinessImpactAgent().run(state)

    assert update["business_impact"]["impact_status"] == "partial_estimate"
    assert update["business_impact"]["baseline_value"] is None
    assert update["business_impact"]["treatment_value"] is None
    assert update["business_impact"]["absolute_lift"] is None
    assert update["business_impact"]["relative_lift"] == 0.0814
    assert "observed lift" in " ".join(update["business_impact"]["assumptions"]).lower()


def test_business_impact_agent_carries_annualized_impact_from_source_evidence() -> None:
    from packages.agents.business_impact_agent import BusinessImpactAgent

    state = build_business_impact_state()
    state["citations"] = [
        {
            "document_id": "doc-annualized",
            "experiment_id": "exp-001-payment-recommendation",
            "quote": "Estimated annualized impact is USD 1250000 for high-intent wallet users.",
            "section": "Business Impact",
            "metadata": {
                "section": "Business Impact",
                "estimated_annualized_impact": {
                    "amount": 1250000,
                    "currency": "USD",
                    "period": "annual",
                },
                "affected_segment": "high-intent wallet users",
            },
        }
    ]
    state["experiment_analysis"]["evidence_citations"] = list(state["citations"])

    update = BusinessImpactAgent().run(state)

    assert update["business_impact"]["estimated_annualized_impact"] == {
        "amount": 1250000,
        "currency": "USD",
        "period": "annual",
    }
    assert update["business_impact"]["affected_segment"] == "high-intent wallet users"
    assert update["metrics"]["business_impact"]["has_annualized_impact"] is True


def test_business_impact_agent_returns_insufficient_data_without_analysis_inputs() -> None:
    from packages.agents.business_impact_agent import BusinessImpactAgent

    state = create_initial_state("What is the business impact?")
    state["required_agents"] = ["business_impact"]

    update = BusinessImpactAgent().run(state)

    assert update["business_impact"]["impact_status"] == "insufficient_data"
    assert update["business_impact"]["primary_business_metric"] == ""
    assert update["business_impact"]["relative_lift"] is None
    assert update["metrics"]["business_impact"]["status"] == "insufficient_data"


def test_business_impact_agent_handles_zero_baseline_without_dividing() -> None:
    from packages.agents.business_impact_agent import BusinessImpactAgent

    state = build_business_impact_state()
    state["experiment_analysis"]["control"]["value"] = 0.0
    state["experiment_analysis"]["treatment"]["value"] = 0.2
    state["experiment_analysis"]["treatment_control_comparison"] = {
        "metric_name": "payment_success_rate",
        "control_value": 0.0,
        "treatment_value": 0.2,
        "absolute_delta": 0.2,
        "unit": "rate",
    }

    update = BusinessImpactAgent().run(state)

    assert update["business_impact"]["impact_status"] == "estimated"
    assert update["business_impact"]["absolute_lift"] == 0.2
    assert update["business_impact"]["relative_lift"] is None
    assert "baseline" in " ".join(update["business_impact"]["limitations"]).lower()


def test_business_impact_agent_preserves_citations_and_records_metrics() -> None:
    from packages.agents.business_impact_agent import BusinessImpactAgent

    state = build_business_impact_state()

    update = BusinessImpactAgent().run(state)

    assert update["business_impact"]["evidence_citations"] == state["citations"]
    assert update["metrics"]["business_impact"]["citation_count"] == 1
    assert update["metrics"]["business_impact"]["latency_ms"] >= 0.0
