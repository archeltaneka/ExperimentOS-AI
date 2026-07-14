from __future__ import annotations

import pytest

from packages.agents.nodes import retrieval_node
from packages.agents.service import AgentWorkflowInputError, AgentWorkflowService
from packages.agents.state import create_initial_state
from packages.agents.workflow import build_agent_workflow


class StubGraphRetrievalAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "retrieved_chunks": [
                {
                    "document_id": "doc-1",
                    "experiment_id": "exp-1",
                    "content": "Chunk from retrieval.",
                    "score": 0.88,
                    "metadata": {"section": "Results"},
                }
            ],
            "citations": [
                {
                    "document_id": "doc-1",
                    "experiment_id": "exp-1",
                    "quote": "Chunk from retrieval.",
                    "section": "Results",
                    "metadata": {"section": "Results"},
                }
            ],
            "metrics": {
                **state["metrics"],
                "retrieval": {"retrieved_chunks": 1},
            },
            "trace": [
                {"node": "retrieval", "event": "started", "at": "2026-07-07T00:00:00Z"},
                {"node": "retrieval", "event": "completed", "at": "2026-07-07T00:00:01Z"},
            ],
            "errors": [],
        }


class StubGraphExperimentAnalysisAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "experiment_analysis": {
                **state["experiment_analysis"],
                "summary": "Primary metric improved in treatment.",
                "findings": ["Treatment beat control on the primary metric."],
                "status": "completed",
                "experiment_id": "exp-001-payment-recommendation",
                "experiment_name": "Adaptive Payment Method Recommendation",
                "primary_metric": "payment_success_rate",
                "evidence_citations": state["citations"],
                "analysis_confidence": "medium",
            },
            "experiment_metadata": {
                "primary_metric": "payment_success_rate",
                "business_decision": (
                    "Roll out to AU, SG, and GB; hold JP pending wallet tracking fix."
                ),
            },
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
            "metrics": {
                **state["metrics"],
                "experiment_analysis": {
                    "status": "completed",
                    "citation_count": len(state["citations"]),
                },
            },
            "trace": [
                {
                    "node": "experiment_analysis",
                    "event": "started",
                    "at": "2026-07-08T00:00:02Z",
                },
                {
                    "node": "experiment_analysis",
                    "event": "completed",
                    "at": "2026-07-08T00:00:03Z",
                },
            ],
            "errors": [],
        }


class StubGraphBusinessImpactAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "business_impact": {
                **state["business_impact"],
                "summary": "Treatment improved the primary business metric.",
                "impact_status": "estimated",
                "primary_business_metric": "payment_success_rate",
                "baseline_value": 0.6760,
                "treatment_value": 0.7310,
                "absolute_lift": 0.055,
                "relative_lift": 0.081361,
                "confidence_level": "medium",
                "evidence_citations": list(state["citations"]),
            },
            "metrics": {
                **state["metrics"],
                "business_impact": {
                    "status": "estimated",
                    "citation_count": len(state["citations"]),
                },
            },
            "trace": [
                {
                    "node": "business_impact",
                    "event": "started",
                    "at": "2026-07-08T00:00:04Z",
                },
                {
                    "node": "business_impact",
                    "event": "completed",
                    "at": "2026-07-08T00:00:05Z",
                },
            ],
            "errors": [],
        }


class StubGraphRiskAssessmentAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "risk_assessment": {
                **state["risk_assessment"],
                "risk_status": "assessed",
                "overall_risk_level": "medium",
                "risk_score": 4,
                "risk_factors": [
                    {
                        "code": "monitor_rollout",
                        "title": "Rollout should be monitored during ramp",
                        "severity": "medium",
                        "category": "rollout",
                        "detail": "Initial rollout still depends on monitoring.",
                        "mitigation": "Ramp gradually and watch primary and guardrail metrics.",
                    }
                ],
                "mitigation_actions": ["Ramp gradually and watch primary and guardrail metrics."],
                "evidence_citations": list(state["citations"]),
                "confidence_level": "medium",
            },
            "risks": [
                {
                    "title": "Rollout should be monitored during ramp",
                    "severity": "medium",
                    "detail": "Initial rollout still depends on monitoring.",
                    "mitigation": "Ramp gradually and watch primary and guardrail metrics.",
                }
            ],
            "metrics": {
                **state["metrics"],
                "risk_assessment": {
                    "status": "assessed",
                    "risk_factor_count": 1,
                    "citation_count": len(state["citations"]),
                },
            },
            "trace": [
                {
                    "node": "risk_assessment",
                    "event": "started",
                    "at": "2026-07-08T00:00:06Z",
                },
                {
                    "node": "risk_assessment",
                    "event": "completed",
                    "at": "2026-07-08T00:00:07Z",
                },
            ],
            "errors": [],
        }


class StubGraphDecisionAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "decision": {
                **state["decision"],
                "decision_status": "decided",
                "recommendation": "rollout",
                "confidence": "medium",
                "rationale": "Positive evidence outweighed manageable rollout risk.",
                "supporting_evidence": [
                    "Primary metric improved.",
                    "Business impact estimate is positive.",
                ],
                "blocking_issues": [],
                "recommended_next_actions": [
                    "Ramp gradually and monitor primary and guardrail metrics.",
                ],
                "approval_required": True,
                "evidence_citations": list(state["citations"]),
                "assumptions": ["Decision uses deterministic rules."],
                "limitations": [],
            },
            "metrics": {
                **state["metrics"],
                "decision": {
                    "status": "decided",
                    "recommendation": "rollout",
                    "citation_count": len(state["citations"]),
                },
            },
            "trace": [
                {"node": "decision", "event": "started", "at": "2026-07-08T00:00:08Z"},
                {"node": "decision", "event": "completed", "at": "2026-07-08T00:00:09Z"},
            ],
            "errors": [],
        }


class StubGraphHumanApprovalAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "human_approval": {
                **state["human_approval"],
                "status": "approved",
                "required": True,
                "feedback": "Approved for monitored rollout.",
                "actor": "director@example.com",
                "timestamp": "2026-07-08T00:00:10Z",
            },
            "metrics": {
                **state["metrics"],
                "human_approval": {
                    "status": "approved",
                    "approval_required": True,
                    "input_present": True,
                },
            },
            "trace": [
                {
                    "node": "human_approval",
                    "event": "started",
                    "at": "2026-07-08T00:00:10Z",
                },
                {
                    "node": "human_approval",
                    "event": "completed",
                    "at": "2026-07-08T00:00:11Z",
                },
            ],
            "errors": [],
        }


class StubGraphExecutiveSummaryAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, state):
        self.calls.append(state)
        return {
            "executive_summary": {
                **state["executive_summary"],
                "summary_status": "generated",
                "headline": "Rollout is supported by the current evidence.",
                "recommendation": str(state["decision"]["recommendation"]),
                "key_findings": [
                    "Primary metric improved.",
                    "Business impact estimate is positive.",
                ],
                "business_impact_summary": str(state["business_impact"]["summary"]),
                "risk_summary": (
                    "Risk is currently assessed as medium with 1 material factor recorded."
                ),
                "decision_rationale": str(state["decision"]["rationale"]),
                "recommended_next_actions": list(state["decision"]["recommended_next_actions"]),
                "confidence": str(state["decision"]["confidence"]),
                "evidence_citations": list(state["citations"]),
                "limitations": [],
                "summary": "Rollout is supported by the current evidence.",
            },
            "metrics": {
                **state["metrics"],
                "executive_summary": {
                    "status": "generated",
                    "citation_count": len(state["citations"]),
                },
            },
            "trace": [
                {
                    "node": "executive_summary",
                    "event": "started",
                    "at": "2026-07-08T00:00:10Z",
                },
                {
                    "node": "executive_summary",
                    "event": "completed",
                    "at": "2026-07-08T00:00:11Z",
                },
            ],
            "errors": [],
        }


def test_build_agent_workflow_exposes_question_only_input_schema() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    schema = graph.get_input_schema().model_json_schema()

    assert schema["required"] == ["question"]
    assert set(schema["properties"]) == {"question"}


def test_build_agent_workflow_returns_invokable_graph() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = graph.invoke({"question": "Summarize the checkout UX experiment for executives."})

    assert result["question"] == "Summarize the checkout UX experiment for executives."
    assert result["request"]["question"] == "Summarize the checkout UX experiment for executives."
    assert result["intent"] == "executive_summary"
    assert result["required_agents"] == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
        "experiment_analysis",
        "business_impact",
        "business_impact",
        "risk_assessment",
        "risk_assessment",
        "decision",
        "decision",
        "human_approval",
        "human_approval",
        "executive_summary",
        "executive_summary",
    ]
    assert [entry["event"] for entry in result["trace"]] == [
        "planned",
        "started",
        "completed",
        "started",
        "completed",
        "started",
        "completed",
        "started",
        "completed",
        "started",
        "completed",
        "started",
        "completed",
        "started",
        "completed",
    ]
    assert result["human_approval"]["status"] == "approved"
    assert result["run_metadata"]["workflow"] == "phase2_shared_state"
    assert result["metrics"]["planner_rule_version"] == "deterministic_v1"
    assert result["metrics"]["retrieval"]["retrieved_chunks"] == 1
    assert result["metrics"]["experiment_analysis"]["status"] == "completed"
    assert result["metrics"]["business_impact"]["status"] == "estimated"
    assert result["metrics"]["risk_assessment"]["status"] == "assessed"
    assert result["metrics"]["decision"]["status"] == "decided"
    assert result["metrics"]["human_approval"]["status"] == "approved"
    assert result["metrics"]["executive_summary"]["status"] == "generated"
    assert result["experiment_analysis"]["status"] == "completed"
    assert result["business_impact"]["impact_status"] == "estimated"
    assert result["risk_assessment"]["risk_status"] == "assessed"
    assert result["decision"]["decision_status"] == "decided"
    assert result["executive_summary"]["summary_status"] == "generated"


def test_agent_workflow_service_runs_graph_and_returns_state() -> None:
    service = AgentWorkflowService(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = service.run("What happened in the payment recommendation experiment?")

    assert result["question"] == "What happened in the payment recommendation experiment?"
    assert result["intent"] == "experiment_lookup"
    assert result["required_agents"] == ["retrieval"]
    assert result["experiment_analysis"]["summary"] == ""
    assert result["business_impact"]["impact_status"] == "not_required"
    assert result["risk_assessment"]["risk_status"] == "not_required"
    assert result["decision"]["decision_status"] == "not_required"
    assert result["executive_summary"]["summary_status"] == "not_required"
    assert result["errors"] == []
    assert result["tool_calls"] == []
    assert result["metrics"]["planner_rule_version"] == "deterministic_v1"
    assert result["metrics"]["retrieval"]["retrieved_chunks"] == 1


def test_agent_workflow_service_passes_experiment_id_and_top_k() -> None:
    service = AgentWorkflowService(retrieval_agent=StubGraphRetrievalAgent())

    result = service.run(
        "What happened in the payment recommendation experiment?",
        experiment_id="00000000-0000-0000-0000-000000000123",
        top_k=2,
    )

    assert result["request"]["experiment_id"] == "00000000-0000-0000-0000-000000000123"
    assert result["request"]["top_k"] == 2


def test_agent_workflow_service_rejects_blank_question() -> None:
    service = AgentWorkflowService()

    with pytest.raises(AgentWorkflowInputError, match="question must not be empty"):
        service.run("   ")


def test_build_agent_workflow_accepts_injected_retrieval_agent() -> None:
    retrieval_agent = StubGraphRetrievalAgent()
    experiment_analysis_agent = StubGraphExperimentAnalysisAgent()
    graph = build_agent_workflow(
        retrieval_agent=retrieval_agent,
        experiment_analysis_agent=experiment_analysis_agent,
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = graph.invoke({"question": "What happened in the payment recommendation experiment?"})

    assert result["retrieved_chunks"][0]["content"] == "Chunk from retrieval."
    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    assert [entry["event"] for entry in result["trace"]] == [
        "planned",
        "started",
        "completed",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert retrieval_agent.calls[0]["intent"] == "experiment_lookup"
    assert retrieval_agent.calls[0]["required_agents"] == ["retrieval"]
    assert retrieval_agent.calls[0]["experiment_context"] == {
        "experiment_ids": [],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }
    assert retrieval_agent.calls[0]["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "planner_required_agent_count": 1,
        "planner_experiment_hint_count": 1,
    }


def test_agent_workflow_service_accepts_injected_retrieval_agent() -> None:
    retrieval_agent = StubGraphRetrievalAgent()
    service = AgentWorkflowService(
        retrieval_agent=retrieval_agent,
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = service.run("What happened in the payment recommendation experiment?")

    assert result["citations"][0]["quote"] == "Chunk from retrieval."
    assert result["metrics"]["retrieval"]["retrieved_chunks"] == 1
    assert retrieval_agent.calls[0]["intent"] == "experiment_lookup"
    assert retrieval_agent.calls[0]["required_agents"] == ["retrieval"]
    assert retrieval_agent.calls[0]["experiment_context"] == {
        "experiment_ids": [],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }


def test_build_agent_workflow_skips_retrieval_when_not_required() -> None:
    retrieval_agent = StubGraphRetrievalAgent()
    graph = build_agent_workflow(
        retrieval_agent=retrieval_agent,
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = graph.invoke({"question": "Hello"})

    assert retrieval_agent.calls == []
    assert result["required_agents"] == []
    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    assert [entry["event"] for entry in result["trace"]] == [
        "planned",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert result["errors"] == []
    assert result["metrics"] == {
        "planner_rule_version": "deterministic_v1",
        "planner_required_agent_count": 0,
        "planner_experiment_hint_count": 0,
    }


def test_retrieval_skip_update_does_not_overwrite_existing_outputs() -> None:
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

    update = retrieval_node(state, retrieval_agent=StubGraphRetrievalAgent())

    assert "retrieved_chunks" not in update
    assert "citations" not in update
    assert "errors" not in update
    assert update["trace"][0]["event"] == "skipped"


def test_build_agent_workflow_runs_experiment_analysis_after_retrieval() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = graph.invoke({"question": "Summarize the checkout UX experiment for executives."})

    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
        "experiment_analysis",
        "business_impact",
        "business_impact",
        "risk_assessment",
        "risk_assessment",
        "decision",
        "decision",
        "human_approval",
        "human_approval",
        "executive_summary",
        "executive_summary",
    ]
    assert result["experiment_analysis"]["status"] == "completed"
    assert result["experiment_analysis"]["evidence_citations"] == result["citations"]
    assert result["business_impact"]["evidence_citations"] == result["citations"]
    assert result["risk_assessment"]["evidence_citations"] == result["citations"]
    assert result["decision"]["decision_status"] == "decided"
    assert result["human_approval"]["status"] == "approved"
    assert result["executive_summary"]["summary_status"] == "generated"
    assert result["executive_summary"]["evidence_citations"] == result["citations"]


def test_build_agent_workflow_runs_human_approval_before_executive_summary() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = graph.invoke({"question": "Summarize the checkout UX experiment for executives."})

    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
        "experiment_analysis",
        "business_impact",
        "business_impact",
        "risk_assessment",
        "risk_assessment",
        "decision",
        "decision",
        "human_approval",
        "human_approval",
        "executive_summary",
        "executive_summary",
    ]
