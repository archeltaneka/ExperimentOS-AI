from __future__ import annotations

from packages.agents.planner import plan_question


def test_plan_question_classifies_decision_support_requests() -> None:
    plan = plan_question("Should we roll out the payment recommendation experiment?")

    assert plan.intent == "decision_support"
    assert plan.required_agents == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "executive_summary",
    ]
    assert plan.experiment_context["filters"] == {
        "experiment_hints": ["payment recommendation"],
    }


def test_plan_question_classifies_experiment_lookup_requests() -> None:
    plan = plan_question("What happened in the payment recommendation experiment?")

    assert plan.intent == "experiment_lookup"
    assert plan.required_agents == ["retrieval"]


def test_plan_question_classifies_risk_requests() -> None:
    plan = plan_question("What are the risks of launching the hotel image quality experiment?")

    assert plan.intent == "risk_assessment"
    assert plan.required_agents == [
        "retrieval",
        "experiment_analysis",
        "risk_assessment",
    ]


def test_plan_question_classifies_business_impact_requests() -> None:
    plan = plan_question("What is the business impact of the loyalty experiment?")

    assert plan.intent == "business_impact"
    assert plan.required_agents == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
    ]


def test_plan_question_classifies_executive_summary_requests() -> None:
    plan = plan_question("Summarize the checkout UX experiment for executives.")

    assert plan.intent == "executive_summary"
    assert plan.required_agents == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "executive_summary",
    ]


def test_plan_question_handles_unknown_requests_safely() -> None:
    plan = plan_question("Tell me a joke about penguins.")

    assert plan.intent == "unknown"
    assert plan.required_agents == []
    assert plan.experiment_context == {
        "experiment_ids": [],
        "filters": {},
    }


def test_plan_question_extracts_experiment_hints() -> None:
    plan = plan_question("Compare the CRM and premium subscription experiments.")

    assert plan.experiment_context["filters"] == {
        "experiment_hints": ["crm", "premium subscription"],
    }
