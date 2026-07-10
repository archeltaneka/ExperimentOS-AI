from __future__ import annotations

import json
from pathlib import Path

from packages.agents.state import create_initial_state
from packages.evals.agent_dataset import AgentEvaluationCase
from packages.evals.agent_evaluator import AgentEvaluationRun, AgentEvaluationSampleResult
from packages.evals.agent_metrics import AgentEvaluationSummary, AgentSampleMetrics
from packages.evals.dataset import EvaluationQuestion
from packages.evals.evaluator import EvaluationRun, EvaluationSampleResult
from packages.evals.metrics import EvaluationSummary, SampleMetrics


def _make_case(**overrides):
    from packages.evals.factuality.models import CitationRecord, EvidenceRecord, FactualityCase

    defaults = {
        "case_id": "case-1",
        "dataset_identifier": "tests",
        "question": "Should we roll out the experiment?",
        "category": "rollout_decision",
        "surface": "agent_workflow",
        "answer": "Roll out because payment_success_rate improved from 0.67 to 0.73.",
        "citations": (
            CitationRecord(
                source_id="doc-1",
                source_type="document",
                text="payment_success_rate improved from 0.67 to 0.73.",
                metadata={"section": "Results"},
            ),
        ),
        "evidence": (
            EvidenceRecord(
                source_id="doc-1",
                source_type="document",
                text="payment_success_rate improved from 0.67 to 0.73.",
                metadata={"section": "Results"},
            ),
        ),
        "experiment_analysis": {
            "summary": "payment_success_rate improved from 0.67 to 0.73.",
            "primary_metric": "payment_success_rate",
            "observed_lift": {"relative_lift": 0.0896, "p_value": 0.02},
            "treatment_control_comparison": {
                "control_value": 0.67,
                "treatment_value": 0.73,
                "absolute_delta": 0.06,
                "relative_lift": 0.0896,
                "p_value": 0.02,
            },
            "statistical_significance": {"is_significant": True, "p_value": 0.02},
            "confidence_level": {"confidence_level": 0.95},
            "analysis_confidence": "high",
        },
        "business_impact": {
            "impact_status": "estimated",
            "estimated_annualized_impact": {
                "amount": 910000.0,
                "currency": "USD",
                "period": "annual",
            },
            "relative_lift": 0.0896,
            "confidence_level": "high",
            "summary": "Estimated annualized impact is USD 910000.",
        },
        "risk_assessment": {
            "risk_status": "assessed",
            "overall_risk_level": "low",
            "risk_score": 2,
            "confidence_level": "high",
        },
        "decision": {
            "decision_status": "decided",
            "recommendation": "rollout",
            "confidence": "high",
            "rationale": "Roll out because payment_success_rate improved from 0.67 to 0.73.",
        },
        "executive_summary": {
            "summary_status": "generated",
            "summary": "Roll out because payment_success_rate improved from 0.67 to 0.73.",
            "recommendation": "rollout",
            "confidence": "high",
            "decision_rationale": (
                "Roll out because payment_success_rate improved from 0.67 to 0.73."
            ),
        },
        "approval_status": "approved",
        "expected_min_citations": 1,
        "expected_failure_mode": None,
        "expected_decision_status": "decided",
        "expected_recommendation": "rollout",
        "expected_summary_status": "generated",
        "expected_approval_status": "approved",
        "prompt_id": None,
        "prompt_version": None,
        "metadata": {},
    }
    defaults.update(overrides)
    return FactualityCase(**defaults)


def _categories(result) -> set[str]:
    return {finding.category for finding in result.findings if not finding.passed}


def test_supported_numerical_claim_passes() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(_make_case())

    assert "unsupported_numerical_claim" not in _categories(result)


def test_unsupported_numerical_claim_fails() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="Roll out because payment_success_rate improved from 0.67 to 0.81.",
            decision={
                "decision_status": "decided",
                "recommendation": "rollout",
                "confidence": "high",
                "rationale": (
                    "Roll out because payment_success_rate improved from 0.67 to 0.81."
                ),
            },
        )
    )

    assert "unsupported_numerical_claim" in _categories(result)


def test_fabricated_roi_detection() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="The experiment delivered 42 percent ROI.",
            business_impact={
                "impact_status": "insufficient_data",
                "estimated_annualized_impact": None,
                "summary": "Cannot estimate ROI from the available inputs.",
            },
        )
    )

    assert "fabricated_revenue_or_roi" in _categories(result)


def test_fabricated_revenue_detection() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="This created USD 2,000,000 in revenue lift.",
            business_impact={
                "impact_status": "insufficient_data",
                "estimated_annualized_impact": None,
                "summary": "Cannot estimate revenue from the available inputs.",
            },
        )
    )

    assert "fabricated_revenue_or_roi" in _categories(result)


def test_fabricated_p_value_detection() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="The result was statistically significant with p-value 0.001.",
            experiment_analysis={
                "summary": "Directional improvement only.",
                "statistical_significance": {},
                "observed_lift": {},
                "treatment_control_comparison": {},
            },
        )
    )

    assert "fabricated_statistical_significance" in _categories(result)


def test_unsupported_significance_claim_detection() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="The result was statistically significant.",
            experiment_analysis={
                "summary": "Directional improvement only.",
                "statistical_significance": {"is_significant": False},
                "observed_lift": {"relative_lift": 0.01},
                "treatment_control_comparison": {"relative_lift": 0.01},
            },
        )
    )

    assert "fabricated_statistical_significance" in _categories(result)


def test_valid_citation_passes() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(_make_case())

    assert "citation_missing" not in _categories(result)
    assert "citation_does_not_support_claim" not in _categories(result)


def test_missing_citation_fails() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(_make_case(citations=(), expected_min_citations=1))

    assert "citation_missing" in _categories(result)


def test_unknown_citation_id_fails() -> None:
    from packages.evals.factuality.deterministic import evaluate_case
    from packages.evals.factuality.models import CitationRecord

    result = evaluate_case(
        _make_case(
            citations=(
                CitationRecord(
                    source_id="missing-doc",
                    source_type="document",
                    text="payment_success_rate improved from 0.67 to 0.73.",
                    metadata={},
                ),
            )
        )
    )

    assert "citation_does_not_support_claim" in _categories(result)


def test_structured_decision_contradiction_detected() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="Roll out immediately.",
            decision={
                "decision_status": "decided",
                "recommendation": "do_not_rollout",
                "confidence": "high",
                "rationale": "Do not roll out due to margin dilution.",
            },
            executive_summary={
                "summary_status": "generated",
                "summary": "Roll out immediately.",
                "recommendation": "rollout",
                "confidence": "high",
                "decision_rationale": "Roll out immediately.",
            },
        )
    )

    assert "contradiction_with_structured_experiment_data" in _categories(result)


def test_approval_state_contradiction_detected() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            approval_status="rejected",
            expected_approval_status="rejected",
            executive_summary={
                "summary_status": "generated",
                "summary": "Leadership approved rollout.",
                "recommendation": "rollout",
                "confidence": "high",
                "decision_rationale": "Leadership approved rollout.",
            },
        )
    )

    assert "contradiction_with_structured_experiment_data" in _categories(result)


def test_insufficient_evidence_requires_abstention() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="Roll out now. Revenue upside is clear.",
            expected_failure_mode="insufficient_business_evidence",
            decision={
                "decision_status": "needs_more_data",
                "recommendation": "needs_more_data",
                "confidence": "low",
                "rationale": "Need more data before rollout.",
            },
            executive_summary={
                "summary_status": "partial_summary",
                "summary": "Roll out now. Revenue upside is clear.",
                "recommendation": "rollout",
                "confidence": "high",
                "decision_rationale": "Roll out now. Revenue upside is clear.",
            },
            business_impact={
                "impact_status": "insufficient_data",
                "estimated_annualized_impact": None,
                "summary": "Cannot estimate business impact from the available inputs.",
            },
            approval_status="not_requested",
            expected_approval_status="not_requested",
            expected_decision_status="needs_more_data",
            expected_recommendation="needs_more_data",
            expected_summary_status="partial_summary",
        )
    )

    categories = _categories(result)
    assert "answer_generated_when_abstention_was_expected" in categories
    assert "overconfident_answer_with_insufficient_evidence" in categories


def test_conservative_unparsed_claim_handling_records_warning() -> None:
    from packages.evals.factuality.deterministic import evaluate_case

    result = evaluate_case(
        _make_case(
            answer="This feels directionally promising overall.",
            decision={
                "decision_status": "not_required",
                "recommendation": "unknown",
                "confidence": "unknown",
                "rationale": "",
            },
            executive_summary={
                "summary_status": "not_required",
                "summary": "",
                "recommendation": "",
                "confidence": "unknown",
                "decision_rationale": "",
            },
        )
    )

    assert result.unparsed_claims


def test_deterministic_policy_aggregation_fails_on_critical_violation() -> None:
    from packages.evals.factuality.deterministic import evaluate_case
    from packages.evals.factuality.models import FactualityPolicy
    from packages.evals.factuality.runner import apply_policy

    case_result = evaluate_case(
        _make_case(
            answer="The experiment delivered 42 percent ROI.",
            business_impact={
                "impact_status": "insufficient_data",
                "estimated_annualized_impact": None,
                "summary": "Cannot estimate ROI.",
            },
        )
    )
    policy = FactualityPolicy()

    policy_result = apply_policy([case_result], policy=policy, judge_metrics=())

    assert policy_result.status == "fail"


def test_build_legacy_rag_cases_preserves_prompt_provenance() -> None:
    from packages.evals.factuality.runner import build_legacy_rag_cases

    question = EvaluationQuestion(
        id="legacy-1",
        experiment_id="exp-001-payment-recommendation",
        question="What happened?",
        expected_documents=("Adaptive Payment Method Recommendation",),
        expected_keywords=("payment_success_rate",),
        category="legacy_rag_fallback",
        difficulty="easy",
        reference_answer="Grounded answer.",
        expected_citation_required=True,
    )
    sample = EvaluationSampleResult(
        question=question,
        answer="Grounded answer.",
        metrics=SampleMetrics(
            retrieval_latency_ms=10.0,
            llm_latency_ms=0.0,
            citation_coverage=1.0,
            retrieval_success=True,
            average_similarity=0.9,
            input_tokens=10,
            output_tokens=4,
            estimated_cost_usd=0.0,
        ),
        retrieved_documents=("Adaptive Payment Method Recommendation",),
        retrieved_contexts=("payment_success_rate improved from 0.67 to 0.73.",),
        error=None,
        prompt_id="rag.answer",
        prompt_version="1",
        citations=(
            {
                "document": "Adaptive Payment Method Recommendation",
                "experiment_id": "exp-001-payment-recommendation",
            },
        ),
    )
    run = EvaluationRun(
        samples=[sample],
        summary=EvaluationSummary.from_samples([sample.metrics]),
        embedding_provider="fake",
        embedding_model="fake",
        llm_provider="mock",
        llm_model="mock",
    )

    cases = build_legacy_rag_cases(run, dataset_identifier="data/eval/qa_dataset.json")

    assert cases[0].prompt_id == "rag.answer"
    assert cases[0].prompt_version == "1"


def test_build_agent_workflow_cases_supports_agent_workflow_surface() -> None:
    from packages.evals.factuality.runner import build_agent_workflow_cases

    case = AgentEvaluationCase(
        id="agent-1",
        question="Should we roll out the experiment?",
        category="rollout_decision",
        expected_intent="decision_support",
        expected_required_agents=("retrieval", "decision"),
        expected_decision_status="decided",
        expected_recommendation="rollout",
        expected_summary_status="generated",
        expected_approval_status="approved",
        expected_min_citations=1,
    )
    state = create_initial_state(case.question)
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-001-payment-recommendation",
            "quote": "payment_success_rate improved from 0.67 to 0.73.",
            "metadata": {"section": "Results"},
        }
    ]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "exp-001-payment-recommendation",
            "content": "payment_success_rate improved from 0.67 to 0.73.",
            "metadata": {"document_name": "Adaptive Payment Method Recommendation"},
        }
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "summary": "payment_success_rate improved from 0.67 to 0.73.",
        "observed_lift": {"relative_lift": 0.0896, "p_value": 0.02},
        "treatment_control_comparison": {
            "control_value": 0.67,
            "treatment_value": 0.73,
            "absolute_delta": 0.06,
            "relative_lift": 0.0896,
            "p_value": 0.02,
        },
        "statistical_significance": {"is_significant": True, "p_value": 0.02},
    }
    state["business_impact"] = {
        **state["business_impact"],
        "impact_status": "estimated",
        "estimated_annualized_impact": {
            "amount": 910000.0,
            "currency": "USD",
            "period": "annual",
        },
    }
    state["decision"] = {
        **state["decision"],
        "decision_status": "decided",
        "recommendation": "rollout",
        "confidence": "high",
        "rationale": "Roll out because payment_success_rate improved from 0.67 to 0.73.",
    }
    state["executive_summary"] = {
        **state["executive_summary"],
        "summary_status": "generated",
        "summary": "Roll out because payment_success_rate improved from 0.67 to 0.73.",
        "recommendation": "rollout",
    }
    state["human_approval"] = {
        **state["human_approval"],
        "status": "approved",
        "required": True,
    }

    sample = AgentEvaluationSampleResult(
        case=case,
        state=state,
        observation=None,
        metrics=AgentSampleMetrics(
            workflow_latency_ms=1.0,
            trace_completeness=1.0,
            planner_intent_accuracy=1.0,
            routing_accuracy=1.0,
            citation_coverage=1.0,
            recommendation_coverage=1.0,
            workflow_success=True,
            tool_call_count=0,
            tool_failure_count=0,
            decision_status="decided",
            approval_status="approved",
            passed=True,
            failure_reasons=(),
            per_agent_latency_ms={},
        ),
        error=None,
    )
    run = AgentEvaluationRun(
        samples=[sample],
        summary=AgentEvaluationSummary.from_samples([sample]),
    )

    cases = build_agent_workflow_cases(run, dataset_identifier="data/eval/agent_dataset.json")

    assert cases[0].surface == "agent_workflow"
    assert cases[0].decision["recommendation"] == "rollout"


def test_offline_mode_skips_judge_metrics_without_importing_frameworks(monkeypatch) -> None:
    from packages.evals.factuality.runner import run_judge_checks

    monkeypatch.setattr(
        "packages.evals.factuality.runner.import_deepeval_bindings",
        lambda: (_ for _ in ()).throw(AssertionError("deepeval should not be imported")),
    )

    metrics = run_judge_checks(cases=[_make_case()], mode="offline", judge_provider="none")

    assert metrics
    assert all(metric.skipped for metric in metrics)


def test_optional_judge_dependency_absence_is_reported_as_skipped(monkeypatch) -> None:
    from packages.evals.factuality.runner import run_judge_checks

    monkeypatch.setattr(
        "packages.evals.factuality.runner.import_deepeval_bindings",
        lambda: (_ for _ in ()).throw(ImportError("deepeval missing")),
    )

    metrics = run_judge_checks(
        cases=[_make_case()],
        mode="judge",
        judge_provider="openai",
        judge_model="gpt-4.1-mini",
    )

    assert metrics
    assert all(metric.skipped for metric in metrics)
    assert "DeepEval bindings unavailable" in (metrics[0].reason or "")


def test_report_generation_and_json_output() -> None:
    from packages.evals.factuality.deterministic import evaluate_case
    from packages.evals.factuality.models import FactualityPolicy, FactualityReport
    from packages.evals.factuality.report import factuality_report_to_json, render_factuality_report
    from packages.evals.factuality.runner import apply_policy

    case_result = evaluate_case(_make_case())
    policy = FactualityPolicy()
    policy_result = apply_policy([case_result], policy=policy, judge_metrics=())
    report = FactualityReport.build(
        generated_at="2026-07-10T00:00:00Z",
        target="agent_workflow",
        mode="offline",
        dataset_identifiers=("tests",),
        case_results=(case_result,),
        judge_metrics=(),
        policy_result=policy_result,
        judge_provider="none",
        judge_model=None,
        limitations=("Deterministic checks are conservative.",),
    )

    markdown = render_factuality_report(report)
    payload = json.loads(factuality_report_to_json(report))

    assert "Factuality Evaluation Report" in markdown
    assert payload["target"] == "agent_workflow"


def test_cli_writes_reports(tmp_path: Path, monkeypatch) -> None:
    from packages.evals.factuality.deterministic import evaluate_case
    from packages.evals.factuality.models import FactualityPolicy, FactualityReport
    from packages.evals.factuality.runner import apply_policy
    from packages.evals.run_factuality import main, parse_args

    case_result = evaluate_case(_make_case())
    policy = FactualityPolicy()
    policy_result = apply_policy([case_result], policy=policy, judge_metrics=())
    report = FactualityReport.build(
        generated_at="2026-07-10T00:00:00Z",
        target="all",
        mode="offline",
        dataset_identifiers=("tests",),
        case_results=(case_result,),
        judge_metrics=(),
        policy_result=policy_result,
        judge_provider="none",
        judge_model=None,
        limitations=(),
    )

    monkeypatch.setattr(
        "packages.evals.run_factuality.build_factuality_report",
        lambda _args: report,
    )

    output = tmp_path / "factuality_report.md"
    json_output = tmp_path / "factuality_report.json"
    args = parse_args(
        [
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ]
    )

    exit_code = main(args=args)

    assert exit_code == 0
    assert output.is_file()
    assert json_output.is_file()
