from __future__ import annotations

from asyncio import run
from pathlib import Path


def test_render_phase3_baseline_report_includes_sections_metrics_and_gaps() -> None:
    from packages.evals.baseline import (
        Phase3BaselineReport,
        Phase3BaselineSection,
        render_phase3_baseline_report,
    )

    report = Phase3BaselineReport(
        generated_at="2026-07-09T10:00:00Z",
        overall_status="pass",
        sections=[
            Phase3BaselineSection(
                name="RAG Evaluation",
                command=(
                    "uv run python -m packages.evals.run --embedding-provider fake "
                    "--llm-provider mock --output reports/evaluation.md"
                ),
                dataset="data/eval/qa_dataset.json",
                report_path="reports/evaluation.md",
                status="pass",
                status_reason="completed without sample errors",
                key_metrics=(
                    ("Questions evaluated", "40"),
                    ("Retrieval success rate", "100.0%"),
                    ("Average citation coverage", "100.0%"),
                ),
                missing_metrics=(
                    "factual grounding",
                    "hallucination risk",
                    "regression stability",
                ),
                known_limitations=("No direct hallucination score is calculated yet.",),
            ),
            Phase3BaselineSection(
                name="Agent Workflow E2E Evaluation",
                command=(
                    "uv run python -m packages.evals.run_agent_e2e "
                    "--output reports/agent_e2e_evaluation.md"
                ),
                dataset=None,
                report_path="reports/agent_e2e_evaluation.md",
                status="pass",
                status_reason="all deterministic API cases passed",
                key_metrics=(
                    ("Pass/fail summary", "7 passed, 0 failed"),
                    ("Legacy fallback coverage", "100.0%"),
                ),
                missing_metrics=("database-backed retrieval quality",),
                known_limitations=("Uses fake workflow fixtures rather than live DB retrieval.",),
            ),
        ],
        known_gaps=(
            "No threshold policy exists yet.",
            "No external observability export is enabled yet.",
        ),
        next_recommended_work=(
            "Expand the evaluation datasets.",
            "Add deterministic hallucination checks.",
        ),
        registered_prompts=(
            ("rag.answer", "1", "active"),
            ("rag.decision", "1", "experimental"),
            ("rag.summary", "1", "experimental"),
        ),
        prompt_provenance_notes=(
            "legacy_rag responses expose prompt_id and prompt_version metadata.",
            "agent_workflow remains prompt-free until an LLM-backed surface exists.",
        ),
    )

    markdown = render_phase3_baseline_report(report)

    assert "# Phase 3 Reliability Baseline Report" in markdown
    assert "Overall status: pass" in markdown
    assert "RAG Evaluation" in markdown
    assert "Agent Workflow E2E Evaluation" in markdown
    assert "Questions evaluated" in markdown
    assert "Legacy fallback coverage" in markdown
    assert "rag.answer" in markdown
    assert "legacy_rag responses expose prompt_id and prompt_version metadata." in markdown
    assert "No threshold policy exists yet." in markdown
    assert "Add deterministic hallucination checks." in markdown


def test_phase3_baseline_cli_parser_accepts_output_paths_and_provider_options() -> None:
    from packages.evals.run_baseline import parse_args

    args = parse_args(
        [
            "--output",
            "reports/phase3/baseline_report.md",
            "--rag-output",
            "reports/evaluation.md",
            "--agent-output",
            "reports/agent_evaluation.md",
            "--agent-e2e-output",
            "reports/agent_e2e_evaluation.md",
            "--embedding-provider",
            "fake",
            "--llm-provider",
            "mock",
            "--top-k",
            "4",
        ]
    )

    assert args.output == Path("reports/phase3/baseline_report.md")
    assert args.rag_output == Path("reports/evaluation.md")
    assert args.agent_output == Path("reports/agent_evaluation.md")
    assert args.agent_e2e_output == Path("reports/agent_e2e_evaluation.md")
    assert args.embedding_provider == "fake"
    assert args.llm_provider == "mock"
    assert args.top_k == 4


def test_run_phase3_baseline_writes_aggregate_report(tmp_path: Path, monkeypatch) -> None:
    from packages.evals.run_baseline import parse_args, run_phase3_baseline

    output = tmp_path / "phase3" / "baseline_report.md"
    rag_output = tmp_path / "evaluation.md"
    agent_output = tmp_path / "agent_evaluation.md"
    agent_e2e_output = tmp_path / "agent_e2e_evaluation.md"

    args = parse_args(
        [
            "--output",
            str(output),
            "--rag-output",
            str(rag_output),
            "--agent-output",
            str(agent_output),
            "--agent-e2e-output",
            str(agent_e2e_output),
            "--embedding-provider",
            "fake",
            "--llm-provider",
            "mock",
        ]
    )

    from packages.evals.agent_dataset import AgentEvaluationCase
    from packages.evals.agent_e2e import AgentE2ERun, AgentE2ESummary
    from packages.evals.agent_evaluator import AgentEvaluationRun, AgentEvaluationSampleResult
    from packages.evals.agent_metrics import AgentEvaluationSummary, AgentSampleMetrics
    from packages.evals.dataset import EvaluationQuestion
    from packages.evals.evaluator import EvaluationRun, EvaluationSampleResult
    from packages.evals.metrics import EvaluationSummary, SampleMetrics

    qa_question = EvaluationQuestion(
        id="payment-decision",
        experiment_id="exp-001-payment-recommendation",
        question="Why did the payment recommendation ship?",
        expected_documents=("Adaptive Payment Method Recommendation",),
        expected_keywords=("roll out",),
        category="decision",
        difficulty="easy",
        reference_answer="Roll out with telemetry monitoring.",
    )
    qa_sample = EvaluationSampleResult(
        question=qa_question,
        answer="Roll out to selected markets.",
        metrics=SampleMetrics(
            retrieval_latency_ms=18.0,
            llm_latency_ms=0.0,
            citation_coverage=1.0,
            retrieval_success=True,
            average_similarity=0.87,
            input_tokens=120,
            output_tokens=12,
            estimated_cost_usd=0.0,
        ),
        retrieved_documents=("Adaptive Payment Method Recommendation",),
        retrieved_contexts=("Roll out with telemetry monitoring.",),
        error=None,
    )
    qa_run = EvaluationRun(
        samples=[qa_sample],
        summary=EvaluationSummary.from_samples([qa_sample.metrics]),
        embedding_provider="fake",
        embedding_model="fake",
        llm_provider="mock",
        llm_model="mock",
    )

    agent_case = AgentEvaluationCase(
        id="payment-rollout",
        question="Should we roll out the payment recommendation experiment?",
        category="rollout_decision",
        expected_intent="decision_support",
        expected_required_agents=("retrieval", "decision"),
        expected_recommendation="rollout",
        expected_min_citations=1,
    )
    agent_sample = AgentEvaluationSampleResult(
        case=agent_case,
        state={},
        observation=None,
        metrics=AgentSampleMetrics(
            workflow_latency_ms=3.0,
            trace_completeness=1.0,
            planner_intent_accuracy=1.0,
            routing_accuracy=1.0,
            citation_coverage=1.0,
            recommendation_coverage=1.0,
            workflow_success=True,
            tool_call_count=2,
            tool_failure_count=0,
            decision_status="decided",
            approval_status="approved",
            passed=True,
            failure_reasons=(),
            per_agent_latency_ms={"planner": 0.0},
        ),
        error=None,
    )
    agent_run = AgentEvaluationRun(
        samples=[agent_sample],
        summary=AgentEvaluationSummary.from_samples([agent_sample]),
    )
    agent_e2e_run = AgentE2ERun(
        samples=[],
        summary=AgentE2ESummary(
            sample_count=1,
            pass_count=1,
            fail_count=0,
            default_agent_workflow_coverage=1.0,
            legacy_fallback_coverage=1.0,
            intent_accuracy=1.0,
            routing_accuracy=1.0,
            citation_coverage=1.0,
            decision_coverage=1.0,
            executive_summary_coverage=1.0,
            approval_status_coverage=1.0,
            average_latency_ms=5.0,
            failure_cases=(),
        ),
    )

    import packages.evals.run_baseline as run_baseline_module

    async def fake_build_qa_run(_args):
        return qa_run

    monkeypatch.setattr(run_baseline_module, "_build_qa_run", fake_build_qa_run)
    monkeypatch.setattr(run_baseline_module, "_build_agent_run", lambda _args: agent_run)
    monkeypatch.setattr(run_baseline_module, "_build_agent_e2e_run", lambda _args: agent_e2e_run)

    report = run(run_phase3_baseline(args))

    assert output.is_file()
    assert rag_output.is_file()
    assert agent_output.is_file()
    assert agent_e2e_output.is_file()
    assert report.startswith("# Phase 3 Reliability Baseline Report")
