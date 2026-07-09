from __future__ import annotations

from packages.agents.nodes import planner_node
from packages.agents.state import create_initial_state


class RecordingAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "retrieved_chunks": [],
            "citations": [],
            "metrics": {"retrieval": {"retrieved_chunks": 0}},
            "errors": [],
            "trace": [],
        }


class RecordingExperimentAnalysisAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "experiment_analysis": {
                **state["experiment_analysis"],
                "summary": "Primary metric improved in treatment.",
                "findings": ["Treatment beat control on the primary metric."],
                "status": "completed",
            },
            "experiment_metadata": {"primary_metric": "payment_success_rate"},
            "experiment_metrics": [
                {
                    "metric_name": "payment_success_rate",
                    "variant": "control",
                    "value": 0.6760,
                },
                {
                    "metric_name": "payment_success_rate",
                    "variant": "treatment",
                    "value": 0.7310,
                },
            ],
            "metrics": {"experiment_analysis": {"status": "completed"}},
            "errors": [],
            "trace": [],
        }


class RecordingBusinessImpactAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "business_impact": {
                **state["business_impact"],
                "summary": "Treatment increased the primary business metric.",
                "impact_status": "estimated",
                "primary_business_metric": "payment_success_rate",
                "baseline_value": 0.6760,
                "treatment_value": 0.7310,
                "absolute_lift": 0.055,
                "relative_lift": 0.081361,
                "confidence_level": "high",
                "evidence_citations": list(state["citations"]),
            },
            "metrics": {"business_impact": {"status": "estimated"}},
            "errors": [],
            "trace": [],
        }


class RecordingRiskAssessmentAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "risk_assessment": {
                **state["risk_assessment"],
                "risk_status": "assessed",
                "overall_risk_level": "low",
                "risk_score": 1,
                "risk_factors": [],
                "mitigation_actions": ["Monitor rollout metrics during the initial ramp."],
                "evidence_citations": list(state["citations"]),
                "confidence_level": "high",
            },
            "risks": [],
            "metrics": {"risk_assessment": {"status": "assessed"}},
            "errors": [],
            "trace": [],
        }


class RecordingDecisionAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "decision": {
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
                "recommended_next_actions": [
                    "Roll out gradually and monitor guardrails.",
                ],
                "approval_required": True,
                "evidence_citations": list(state["citations"]),
                "assumptions": ["Decision uses deterministic rules."],
                "limitations": [],
            },
            "metrics": {"decision": {"status": "decided"}},
            "errors": [],
            "trace": [],
        }


class RecordingExecutiveSummaryAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "executive_summary": {
                **state["executive_summary"],
                "summary_status": "generated",
                "headline": "Rollout is supported by the current evidence.",
                "recommendation": "rollout",
                "key_findings": [
                    "Primary metric improved.",
                    "Risk remained manageable.",
                ],
                "business_impact_summary": "Treatment increased the primary business metric.",
                "risk_summary": (
                    "Risk is currently assessed as low with no material blocking "
                    "factors recorded."
                ),
                "decision_rationale": "Positive lift, positive business impact, and low risk.",
                "recommended_next_actions": ["Roll out gradually and monitor guardrails."],
                "confidence": "high",
                "evidence_citations": list(state["citations"]),
                "limitations": [],
                "summary": "Rollout is supported by the current evidence.",
            },
            "metrics": {"executive_summary": {"status": "generated"}},
            "errors": [],
            "trace": [],
        }


class RecordingHumanApprovalAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        return {
            "human_approval": {
                **state["human_approval"],
                "status": "pending",
                "required": True,
                "feedback": "",
                "actor": None,
                "timestamp": None,
            },
            "metrics": {"human_approval": {"status": "pending"}},
            "errors": [],
            "trace": [],
        }


def test_planner_node_classifies_decision_questions_with_partial_update() -> None:
    state = {
        "question": "Should we roll out the payment recommendation experiment?",
        "trace": [{"node": "existing"}],
    }

    updated = planner_node(state)

    assert updated["intent"] == "decision_support"
    assert updated["required_agents"] == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    assert "question" not in updated
    assert (
        updated["request"]["question"]
        == "Should we roll out the payment recommendation experiment?"
    )
    assert updated["planner_notes"]
    assert updated["experiment_context"] == {
        "experiment_ids": [],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }
    assert updated["human_approval"]["status"] == "not_requested"
    assert updated["human_approval"]["required"] is False
    assert updated["human_approval"]["feedback"] == ""
    assert updated["human_approval"]["actor"] is None
    assert updated["human_approval"]["timestamp"] is None
    assert updated["human_approval_input"] == {}
    assert updated["tool_calls"] == []
    assert updated["trace"] == [
        {
            "node": "planner",
            "event": "planned",
            "details": {
                "intent": "decision_support",
                "required_agents": [
                    "retrieval",
                    "experiment_analysis",
                    "business_impact",
                    "risk_assessment",
                    "decision",
                    "human_approval",
                    "executive_summary",
                ],
                "experiment_hints": ["payment recommendation"],
            },
            "at": updated["trace"][0]["at"],
        }
    ]
    assert updated["errors"] == []


def test_planner_node_uses_retrieval_for_experiment_lookup_questions() -> None:
    state = create_initial_state("What happened in the payment recommendation experiment?")

    updated = planner_node(state)

    assert updated["intent"] == "experiment_lookup"
    assert updated["required_agents"] == ["retrieval"]


def test_planner_node_preserves_preseeded_experiment_context() -> None:
    state = create_initial_state(
        "What happened in the payment recommendation experiment?",
        experiment_id="00000000-0000-0000-0000-000000000123",
        top_k=2,
    )

    update = planner_node(state)

    assert update["request"]["experiment_id"] == "00000000-0000-0000-0000-000000000123"
    assert update["request"]["top_k"] == 2
    assert update["experiment_context"]["experiment_ids"] == [
        "00000000-0000-0000-0000-000000000123"
    ]


def test_retrieval_node_skips_when_retrieval_is_not_required() -> None:
    from packages.agents.nodes import retrieval_node

    state = create_initial_state("Hello")
    state["required_agents"] = []
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "content": "Existing retrieval chunk.",
            "score": 0.42,
            "metadata": {"section": "Existing"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "quote": "Existing retrieval chunk.",
            "section": "Existing",
            "metadata": {"section": "Existing"},
        }
    ]
    agent = RecordingAgent()

    update = retrieval_node(state, retrieval_agent=agent)

    assert agent.calls == 0
    assert "retrieved_chunks" not in update
    assert "citations" not in update
    assert state["retrieved_chunks"] == [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "content": "Existing retrieval chunk.",
            "score": 0.42,
            "metadata": {"section": "Existing"},
        }
    ]
    assert state["citations"] == [
        {
            "document_id": "doc-existing",
            "experiment_id": "exp-existing",
            "quote": "Existing retrieval chunk.",
            "section": "Existing",
            "metadata": {"section": "Existing"},
        }
    ]
    assert "errors" not in update
    assert update["trace"][0]["node"] == "retrieval"
    assert update["trace"][0]["event"] == "skipped"


def test_retrieval_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import retrieval_node

    state = create_initial_state("What happened in the payment recommendation experiment?")
    state["required_agents"] = ["retrieval"]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    agent = RecordingAgent()

    update = retrieval_node(state, retrieval_agent=agent)

    assert agent.calls == 1
    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {"retrieved_chunks": 0},
    }
    assert update["errors"] == []


def test_experiment_analysis_node_skips_when_not_required() -> None:
    from packages.agents.nodes import experiment_analysis_node

    state = create_initial_state("Hello")
    state["required_agents"] = ["retrieval"]
    agent = RecordingExperimentAnalysisAgent()

    update = experiment_analysis_node(state, experiment_analysis_agent=agent)

    assert agent.calls == 0
    assert "experiment_analysis" not in update
    assert "errors" not in update
    assert update["trace"][0]["node"] == "experiment_analysis"
    assert update["trace"][0]["event"] == "skipped"


def test_experiment_analysis_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import experiment_analysis_node

    state = create_initial_state("Should we ship it?")
    state["required_agents"] = ["retrieval", "experiment_analysis"]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    agent = RecordingExperimentAnalysisAgent()

    update = experiment_analysis_node(state, experiment_analysis_agent=agent)

    assert agent.calls == 1
    assert update["experiment_analysis"]["status"] == "completed"
    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "experiment_analysis": {"status": "completed"},
    }
    assert update["errors"] == []


def test_business_impact_node_skips_when_not_required() -> None:
    from packages.agents.nodes import business_impact_node

    state = create_initial_state("Hello")
    state["required_agents"] = ["retrieval", "experiment_analysis"]
    agent = RecordingBusinessImpactAgent()

    update = business_impact_node(state, business_impact_agent=agent)

    assert agent.calls == 0
    assert "business_impact" not in update
    assert "errors" not in update
    assert update["trace"][0]["node"] == "business_impact"
    assert update["trace"][0]["event"] == "skipped"


def test_business_impact_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import business_impact_node

    state = create_initial_state("What is the business impact?")
    state["required_agents"] = ["retrieval", "experiment_analysis", "business_impact"]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    agent = RecordingBusinessImpactAgent()

    update = business_impact_node(state, business_impact_agent=agent)

    assert agent.calls == 1
    assert update["business_impact"]["impact_status"] == "estimated"
    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "business_impact": {"status": "estimated"},
    }
    assert update["errors"] == []


def test_risk_assessment_node_skips_when_not_required() -> None:
    from packages.agents.nodes import risk_assessment_node

    state = create_initial_state("Hello")
    state["required_agents"] = ["retrieval", "experiment_analysis", "business_impact"]
    agent = RecordingRiskAssessmentAgent()

    update = risk_assessment_node(state, risk_assessment_agent=agent)

    assert agent.calls == 0
    assert "risk_assessment" not in update
    assert "errors" not in update
    assert update["trace"][0]["node"] == "risk_assessment"
    assert update["trace"][0]["event"] == "skipped"


def test_risk_assessment_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import risk_assessment_node

    state = create_initial_state("What are the rollout risks?")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
    ]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    agent = RecordingRiskAssessmentAgent()

    update = risk_assessment_node(state, risk_assessment_agent=agent)

    assert agent.calls == 1
    assert update["risk_assessment"]["risk_status"] == "assessed"
    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "risk_assessment": {"status": "assessed"},
    }
    assert update["errors"] == []


def test_decision_node_skips_when_not_required() -> None:
    from packages.agents.nodes import decision_node

    state = create_initial_state("Hello")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
    ]
    agent = RecordingDecisionAgent()

    update = decision_node(state, decision_agent=agent)

    assert agent.calls == 0
    assert "decision" not in update
    assert "errors" not in update
    assert update["trace"][0]["node"] == "decision"
    assert update["trace"][0]["event"] == "skipped"


def test_decision_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import decision_node

    state = create_initial_state("Should we roll out the payment recommendation experiment?")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
    ]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-1",
            "quote": "Treatment improved the primary metric.",
            "section": "Results",
            "metadata": {"section": "Results"},
        }
    ]
    agent = RecordingDecisionAgent()

    update = decision_node(state, decision_agent=agent)

    assert agent.calls == 1
    assert update["decision"]["decision_status"] == "decided"
    assert update["decision"]["recommendation"] == "rollout"
    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "decision": {"status": "decided"},
    }
    assert update["errors"] == []


def test_executive_summary_node_skips_when_not_required() -> None:
    from packages.agents.nodes import executive_summary_node

    state = create_initial_state("Hello")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
    ]
    agent = RecordingExecutiveSummaryAgent()

    update = executive_summary_node(state, executive_summary_agent=agent)

    assert agent.calls == 0
    assert "executive_summary" not in update
    assert "errors" not in update
    assert update["trace"][0]["node"] == "executive_summary"
    assert update["trace"][0]["event"] == "skipped"


def test_executive_summary_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import executive_summary_node

    state = create_initial_state("Summarize this for executives.")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "executive_summary",
    ]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-1",
            "quote": "Treatment improved the primary metric.",
            "section": "Results",
            "metadata": {"section": "Results"},
        }
    ]
    agent = RecordingExecutiveSummaryAgent()

    update = executive_summary_node(state, executive_summary_agent=agent)

    assert agent.calls == 1
    assert update["executive_summary"]["summary_status"] == "generated"
    assert update["executive_summary"]["recommendation"] == "rollout"
    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "executive_summary": {"status": "generated"},
    }
    assert update["errors"] == []


def test_human_approval_node_skips_when_not_required() -> None:
    from packages.agents.nodes import human_approval_node

    state = create_initial_state("Hello")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
    ]
    agent = RecordingHumanApprovalAgent()

    update = human_approval_node(state, human_approval_agent=agent)

    assert agent.calls == 0
    assert "human_approval" not in update
    assert "errors" not in update
    assert update["trace"][0]["node"] == "human_approval"
    assert update["trace"][0]["event"] == "skipped"


def test_human_approval_node_delegates_to_injected_agent_when_required() -> None:
    from packages.agents.nodes import human_approval_node

    state = create_initial_state("Summarize for executives.")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    agent = RecordingHumanApprovalAgent()

    update = human_approval_node(state, human_approval_agent=agent)

    assert agent.calls == 1
    assert update["human_approval"]["status"] == "pending"


def test_human_approval_node_merges_metrics_from_state() -> None:
    from packages.agents.nodes import human_approval_node

    state = create_initial_state("Summarize for executives.")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    state["metrics"] = {"planner_rule_version": "deterministic_v1"}
    agent = RecordingHumanApprovalAgent()

    update = human_approval_node(state, human_approval_agent=agent)

    assert update["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "human_approval": {"status": "pending"},
    }
