from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.agents.state import create_initial_state


def build_sample_agent_state() -> dict[str, object]:
    state = create_initial_state("Should we roll out the payment recommendation experiment?")
    state["intent"] = "decision_support"
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-001-payment-recommendation",
            "quote": "Primary metric improved.",
            "section": "Results",
            "metadata": {"section": "Results"},
        },
        {
            "document_id": "doc-2",
            "experiment_id": "exp-001-payment-recommendation",
            "quote": "Annualized impact was material.",
            "section": "Recommendation",
            "metadata": {"section": "Recommendation"},
        },
    ]
    state["tool_calls"] = [
        {
            "tool_name": "calculate_absolute_lift",
            "status": "completed",
            "node": "business_impact",
            "input_summary": {"baseline_value": 0.67, "treatment_value": 0.73},
            "output_summary": {"absolute_lift": 0.06},
            "latency_ms": 1.2,
            "at": "2026-07-09T00:00:01Z",
        },
        {
            "tool_name": "score_experiment_risk",
            "status": "failed",
            "node": "risk_assessment",
            "input_summary": {"risk_factors": [{"severity": "medium"}]},
            "output_summary": {},
            "latency_ms": 0.8,
            "error": "ValueError: boom",
            "at": "2026-07-09T00:00:02Z",
        },
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "status": "completed",
        "summary": "Payment success improved in treatment.",
        "findings": ["Treatment outperformed control."],
        "experiment_id": "exp-001-payment-recommendation",
        "experiment_name": "Adaptive Payment Method Recommendation",
        "primary_metric": "payment_success_rate",
        "control": {"metric_name": "payment_success_rate", "variant": "control", "value": 0.67},
        "treatment": {
            "metric_name": "payment_success_rate",
            "variant": "treatment",
            "value": 0.73,
        },
        "treatment_control_comparison": {
            "metric_name": "payment_success_rate",
            "control_value": 0.67,
            "treatment_value": 0.73,
            "absolute_delta": 0.06,
            "relative_lift": 0.089552,
        },
        "observed_lift": {
            "metric_name": "payment_success_rate",
            "relative_lift": 0.089552,
        },
        "statistical_significance": {"p_value": 0.02, "is_significant": True},
        "guardrail_metrics": [],
        "evidence_citations": list(state["citations"]),
        "analysis_confidence": "high",
    }
    state["business_impact"] = {
        **state["business_impact"],
        "summary": "Treatment improved the primary business metric.",
        "impact_status": "estimated",
        "primary_business_metric": "payment_success_rate",
        "baseline_value": 0.67,
        "treatment_value": 0.73,
        "absolute_lift": 0.06,
        "relative_lift": 0.089552,
        "confidence_level": "high",
        "evidence_citations": list(state["citations"]),
    }
    state["risk_assessment"] = {
        **state["risk_assessment"],
        "risk_status": "assessed",
        "overall_risk_level": "medium",
        "risk_score": 2,
        "risk_factors": [
            {
                "code": "monitor_rollout",
                "title": "Monitor ramp",
                "severity": "medium",
                "category": "rollout",
                "detail": "Monitor telemetry during ramp.",
                "mitigation": "Ramp gradually.",
            }
        ],
        "mitigation_actions": ["Ramp gradually."],
        "evidence_citations": list(state["citations"]),
        "confidence_level": "high",
    }
    state["decision"] = {
        **state["decision"],
        "decision_status": "decided",
        "recommendation": "rollout",
        "confidence": "high",
        "rationale": "Positive lift outweighed manageable risk.",
        "supporting_evidence": ["Primary metric improved."],
        "blocking_issues": [],
        "recommended_next_actions": ["Roll out gradually."],
        "approval_required": True,
        "evidence_citations": list(state["citations"]),
    }
    state["human_approval"] = {
        **state["human_approval"],
        "status": "approved",
        "required": True,
        "feedback": "Approved.",
        "actor": "director@example.com",
        "timestamp": "2026-07-09T00:00:07Z",
    }
    state["executive_summary"] = {
        **state["executive_summary"],
        "summary_status": "generated",
        "headline": "Rollout is supported.",
        "recommendation": "rollout",
        "summary": "Rollout is supported.",
        "evidence_citations": list(state["citations"]),
    }
    state["metrics"] = {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {
            "embedding_time_ms": 10.0,
            "vector_search_time_ms": 8.0,
            "retrieved_chunks": 2,
            "average_similarity": 0.91,
        },
        "experiment_analysis": {"status": "completed", "latency_ms": 20.0},
        "business_impact": {"status": "estimated", "latency_ms": 12.0},
        "risk_assessment": {"status": "assessed", "latency_ms": 15.0},
        "decision": {"status": "decided", "latency_ms": 11.0},
        "human_approval": {"status": "approved", "latency_ms": 4.0},
        "executive_summary": {"status": "generated", "latency_ms": 9.0},
    }
    state["trace"] = [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "started", "at": "2026-07-09T00:00:01Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:02Z"},
        {"node": "experiment_analysis", "event": "started", "at": "2026-07-09T00:00:02Z"},
        {
            "node": "experiment_analysis",
            "event": "completed",
            "at": "2026-07-09T00:00:03Z",
        },
        {"node": "business_impact", "event": "started", "at": "2026-07-09T00:00:03Z"},
        {"node": "business_impact", "event": "completed", "at": "2026-07-09T00:00:04Z"},
        {"node": "risk_assessment", "event": "started", "at": "2026-07-09T00:00:04Z"},
        {"node": "risk_assessment", "event": "completed", "at": "2026-07-09T00:00:05Z"},
        {"node": "decision", "event": "started", "at": "2026-07-09T00:00:05Z"},
        {"node": "decision", "event": "completed", "at": "2026-07-09T00:00:06Z"},
        {"node": "human_approval", "event": "started", "at": "2026-07-09T00:00:06Z"},
        {"node": "human_approval", "event": "completed", "at": "2026-07-09T00:00:07Z"},
        {"node": "executive_summary", "event": "started", "at": "2026-07-09T00:00:07Z"},
        {
            "node": "executive_summary",
            "event": "completed",
            "at": "2026-07-09T00:00:08Z",
        },
    ]
    state["timestamps"] = {
        "created_at": "2026-07-09T00:00:00Z",
        "updated_at": "2026-07-09T00:00:08Z",
    }
    return state


def test_extract_workflow_observation_reads_agent_metrics_from_state() -> None:
    from packages.agents.observability import extract_workflow_observation

    observation = extract_workflow_observation(build_sample_agent_state())

    assert observation.workflow_latency_ms == pytest.approx(8000.0)
    assert observation.trace_completeness == pytest.approx(1.0)
    assert observation.total_tool_calls == 2
    assert observation.total_tool_failures == 1
    assert observation.retrieval_metrics["retrieved_chunks"] == 2
    assert observation.decision_status == "decided"
    assert observation.approval_status == "approved"
    assert observation.final_recommendation == "rollout"
    assert observation.nodes["retrieval"].latency_ms == pytest.approx(18.0)
    assert observation.nodes["risk_assessment"].tool_failure_count == 1


def test_trace_completeness_uses_expected_phase2_workflow_nodes() -> None:
    from packages.agents.observability import calculate_trace_completeness

    state = build_sample_agent_state()
    state["trace"] = [entry for entry in state["trace"] if entry["node"] != "executive_summary"]

    completeness = calculate_trace_completeness(state)

    assert completeness == pytest.approx(7 / 8)


def test_agent_sample_metrics_calculate_routing_citation_and_recommendation_coverage() -> None:
    from packages.agents.observability import extract_workflow_observation
    from packages.evals.agent_dataset import AgentEvaluationCase
    from packages.evals.agent_metrics import calculate_agent_sample_metrics

    case = AgentEvaluationCase(
        id="payment-rollout",
        question="Should we roll out the payment recommendation experiment?",
        category="rollout_decision",
        expected_intent="decision_support",
        expected_required_agents=(
            "retrieval",
            "experiment_analysis",
            "business_impact",
            "risk_assessment",
            "decision",
            "human_approval",
            "executive_summary",
        ),
        expected_decision_status="decided",
        expected_recommendation="rollout",
        expected_summary_status="generated",
        expected_min_citations=2,
    )

    metrics = calculate_agent_sample_metrics(
        case=case,
        observation=extract_workflow_observation(build_sample_agent_state()),
    )

    assert metrics.planner_intent_accuracy == pytest.approx(1.0)
    assert metrics.routing_accuracy == pytest.approx(1.0)
    assert metrics.citation_coverage == pytest.approx(1.0)
    assert metrics.recommendation_coverage == pytest.approx(1.0)
    assert metrics.workflow_success is True
    assert metrics.passed is True


def test_agent_sample_metrics_detect_recommendation_miss() -> None:
    from packages.agents.observability import extract_workflow_observation
    from packages.evals.agent_dataset import AgentEvaluationCase
    from packages.evals.agent_metrics import calculate_agent_sample_metrics

    case = AgentEvaluationCase(
        id="payment-no-rollout",
        question="Should we roll out the payment recommendation experiment?",
        category="rollout_decision",
        expected_intent="decision_support",
        expected_required_agents=("retrieval", "decision"),
        expected_recommendation="do_not_rollout",
    )

    metrics = calculate_agent_sample_metrics(
        case=case,
        observation=extract_workflow_observation(build_sample_agent_state()),
    )

    assert metrics.recommendation_coverage == pytest.approx(0.0)
    assert metrics.passed is False
    assert "recommendation" in " ".join(metrics.failure_reasons).lower()


def test_agent_sample_metrics_detect_approval_status_miss() -> None:
    from packages.agents.observability import extract_workflow_observation
    from packages.evals.agent_dataset import AgentEvaluationCase
    from packages.evals.agent_metrics import calculate_agent_sample_metrics

    case = AgentEvaluationCase(
        id="payment-approval-rejected",
        question="Should we roll out the payment recommendation experiment?",
        category="approval_workflow",
        expected_intent="decision_support",
        expected_required_agents=("retrieval", "decision", "human_approval"),
        expected_recommendation="rollout",
        expected_approval_status="rejected",
    )

    metrics = calculate_agent_sample_metrics(
        case=case,
        observation=extract_workflow_observation(build_sample_agent_state()),
    )

    assert metrics.passed is False
    assert "approval status mismatch" in " ".join(metrics.failure_reasons).lower()


def test_load_agent_evaluation_dataset_validates_records(tmp_path: Path) -> None:
    from packages.evals.agent_dataset import load_agent_evaluation_dataset

    dataset_path = tmp_path / "agent_dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "lookup-payment",
                    "question": "What happened in the payment recommendation experiment?",
                    "category": "lookup",
                    "expected_intent": "experiment_lookup",
                    "expected_required_agents": ["retrieval"],
                    "expected_min_citations": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    dataset = load_agent_evaluation_dataset(dataset_path)

    assert len(dataset) == 1
    assert dataset[0].id == "lookup-payment"
    assert dataset[0].category == "lookup"
    assert dataset[0].expected_required_agents == ("retrieval",)
    assert dataset[0].expected_approval_status is None
    assert dataset[0].expected_failure_mode is None
    assert dataset[0].notes is None


def test_load_agent_evaluation_dataset_supports_optional_metadata_fields(tmp_path: Path) -> None:
    from packages.evals.agent_dataset import load_agent_evaluation_dataset

    dataset_path = tmp_path / "agent_dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "premium-needs-more-data",
                    "question": "Should we roll out the premium subscription experiment?",
                    "category": "insufficient_evidence",
                    "expected_intent": "decision_support",
                    "expected_required_agents": [
                        "retrieval",
                        "experiment_analysis",
                        "business_impact",
                        "risk_assessment",
                        "decision",
                        "human_approval",
                        "executive_summary",
                    ],
                    "expected_decision_status": "needs_more_data",
                    "expected_recommendation": "needs_more_data",
                    "expected_summary_status": "generated",
                    "expected_approval_status": "revision_requested",
                    "expected_min_citations": 1,
                    "expected_failure_mode": "insufficient_business_evidence",
                    "notes": "Do not invent revenue, ROI, or statistical significance.",
                }
            ]
        ),
        encoding="utf-8",
    )

    dataset = load_agent_evaluation_dataset(dataset_path)

    assert len(dataset) == 1
    assert dataset[0].category == "insufficient_evidence"
    assert dataset[0].expected_approval_status == "revision_requested"
    assert dataset[0].expected_failure_mode == "insufficient_business_evidence"
    assert dataset[0].notes == "Do not invent revenue, ROI, or statistical significance."


def test_load_agent_evaluation_dataset_rejects_invalid_optional_metadata(tmp_path: Path) -> None:
    from packages.evals.agent_dataset import load_agent_evaluation_dataset

    dataset_path = tmp_path / "agent_dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "payment-invalid-approval-status",
                    "question": "Should we roll out the payment recommendation experiment?",
                    "category": "rollout_decision",
                    "expected_intent": "decision_support",
                    "expected_required_agents": ["retrieval", "decision"],
                    "expected_approval_status": "ship_it",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_approval_status"):
        load_agent_evaluation_dataset(dataset_path)


def test_render_agent_evaluation_report_includes_summary_tables() -> None:
    from packages.agents.observability import extract_workflow_observation
    from packages.evals.agent_dataset import AgentEvaluationCase
    from packages.evals.agent_evaluator import AgentEvaluationRun, AgentEvaluationSampleResult
    from packages.evals.agent_metrics import AgentEvaluationSummary, calculate_agent_sample_metrics
    from packages.evals.agent_report import render_agent_evaluation_report

    case = AgentEvaluationCase(
        id="payment-rollout",
        question="Should we roll out the payment recommendation experiment?",
        category="rollout_decision",
        expected_intent="decision_support",
        expected_required_agents=(
            "retrieval",
            "experiment_analysis",
            "business_impact",
            "risk_assessment",
            "decision",
            "human_approval",
            "executive_summary",
        ),
        expected_decision_status="decided",
        expected_recommendation="rollout",
        expected_summary_status="generated",
        expected_min_citations=2,
    )
    observation = extract_workflow_observation(build_sample_agent_state())
    sample_metrics = calculate_agent_sample_metrics(case=case, observation=observation)
    sample = AgentEvaluationSampleResult(
        case=case,
        state=build_sample_agent_state(),
        observation=observation,
        metrics=sample_metrics,
        error=None,
    )
    run_result = AgentEvaluationRun(
        samples=[sample],
        summary=AgentEvaluationSummary.from_samples([sample]),
    )

    markdown = render_agent_evaluation_report(run_result)

    assert "# Agent Workflow Evaluation Report" in markdown
    assert "Pass count" in markdown
    assert "Per-Agent Latency" in markdown
    assert "planner intent accuracy" in markdown.lower()
    assert "payment-rollout" in markdown


def test_agent_evaluator_runs_small_fake_dataset() -> None:
    from packages.evals.agent_dataset import (
        DEFAULT_AGENT_DATASET_PATH,
        load_agent_evaluation_dataset,
    )
    from packages.evals.agent_evaluator import (
        AgentWorkflowEvaluator,
        build_default_agent_workflow_service,
    )

    assert DEFAULT_AGENT_DATASET_PATH == Path("data/eval/agent_dataset.json")
    assert DEFAULT_AGENT_DATASET_PATH.is_file()

    cases = load_agent_evaluation_dataset(DEFAULT_AGENT_DATASET_PATH)
    evaluator = AgentWorkflowEvaluator(
        workflow_service=build_default_agent_workflow_service(),
        cases=cases,
    )

    run_result = evaluator.evaluate()

    assert len(run_result.samples) >= 8
    assert run_result.summary.sample_count >= 8
    assert run_result.summary.pass_count == run_result.summary.sample_count
    assert run_result.summary.planner_intent_accuracy == pytest.approx(1.0)
    assert run_result.summary.routing_accuracy == pytest.approx(1.0)
    assert run_result.summary.citation_coverage >= 1.0
    assert {
        "lookup",
        "rollout_decision",
        "business_impact",
        "risk_guardrail",
        "approval_workflow",
        "insufficient_evidence",
    }.issubset({case.category for case in cases})


def test_agent_cli_parser_accepts_dataset_and_output() -> None:
    from packages.evals.run_agent import parse_args

    args = parse_args(
        [
            "--dataset",
            "data/eval/agent_dataset.json",
            "--output",
            "reports/agent_evaluation.md",
        ]
    )

    assert args.dataset == Path("data/eval/agent_dataset.json")
    assert args.output == Path("reports/agent_evaluation.md")


def test_agent_e2e_evaluator_runs_default_and_fallback_cases() -> None:
    from packages.evals.agent_e2e import AgentE2EEvaluator, build_default_agent_e2e_cases

    evaluator = AgentE2EEvaluator(cases=build_default_agent_e2e_cases())

    run_result = evaluator.evaluate()

    assert run_result.summary.sample_count >= 10
    assert run_result.summary.pass_count == run_result.summary.sample_count
    assert run_result.summary.default_agent_workflow_coverage == pytest.approx(1.0)
    assert run_result.summary.legacy_fallback_coverage == pytest.approx(1.0)
    assert run_result.summary.intent_accuracy == pytest.approx(1.0)
    assert run_result.summary.routing_accuracy == pytest.approx(1.0)
    assert run_result.summary.citation_coverage == pytest.approx(1.0)
    assert run_result.summary.decision_coverage == pytest.approx(1.0)
    assert run_result.summary.executive_summary_coverage == pytest.approx(1.0)
    assert run_result.summary.approval_status_coverage == pytest.approx(1.0)


def test_render_agent_e2e_report_includes_phase2_metrics() -> None:
    from packages.evals.agent_e2e import AgentE2EEvaluator, build_default_agent_e2e_cases
    from packages.evals.agent_e2e_report import render_agent_e2e_report

    run_result = AgentE2EEvaluator(cases=build_default_agent_e2e_cases()).evaluate()

    markdown = render_agent_e2e_report(run_result)

    assert "# Agent Workflow E2E Evaluation Report" in markdown
    assert "Intent accuracy" in markdown
    assert "Required agent routing accuracy" in markdown
    assert "Decision coverage" in markdown
    assert "Executive summary coverage" in markdown
    assert "Approval status coverage" in markdown
    assert "Phase 3 Next Steps" in markdown


def test_agent_e2e_cli_parser_accepts_output() -> None:
    from packages.evals.run_agent_e2e import parse_args

    args = parse_args(["--output", "reports/agent_e2e_evaluation.md"])

    assert args.output == Path("reports/agent_e2e_evaluation.md")
