from __future__ import annotations

import json
import types
from dataclasses import dataclass
from pathlib import Path

from packages.agents.observability import extract_workflow_observation
from packages.evals.agent_dataset import AgentEvaluationCase
from packages.evals.agent_e2e import (
    AgentE2ECase,
    AgentE2ERun,
    AgentE2ESampleResult,
    AgentE2ESummary,
)
from packages.evals.agent_evaluator import AgentEvaluationRun, AgentEvaluationSampleResult
from packages.evals.agent_metrics import AgentEvaluationSummary, calculate_agent_sample_metrics
from packages.evals.dataset import EvaluationQuestion
from packages.evals.evaluator import EvaluationRun, EvaluationSampleResult
from packages.evals.metrics import EvaluationSummary, SampleMetrics


def build_qa_run() -> EvaluationRun:
    question = EvaluationQuestion(
        id="payment-decision",
        experiment_id="exp-001-payment-recommendation",
        question="Why did the payment recommendation ship?",
        expected_documents=("Adaptive Payment Method Recommendation",),
        expected_keywords=("roll out",),
        category="rollout_decision",
        difficulty="easy",
        reference_answer="Roll out to clean markets while monitoring telemetry.",
        notes="Legacy-compatible rollout case.",
    )
    sample = EvaluationSampleResult(
        question=question,
        answer="Roll out to selected markets while monitoring wallet telemetry.",
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
        retrieved_contexts=(
            "The recommendation was to roll out to clean markets while monitoring telemetry.",
        ),
        error=None,
    )
    return EvaluationRun(
        samples=[sample],
        summary=EvaluationSummary.from_samples([sample.metrics]),
        embedding_provider="fake",
        embedding_model="fake",
        llm_provider="mock",
        llm_model="mock",
    )


def build_agent_workflow_run(*, unsupported_claim: bool = False) -> AgentEvaluationRun:
    from packages.evals.agent_evaluator import build_default_agent_workflow_service

    case = AgentEvaluationCase(
        id="decision-premium-needs-more-data",
        question="Should we roll out the premium subscription experiment?",
        category="insufficient_business_evidence",
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
        expected_decision_status="needs_more_data",
        expected_recommendation="needs_more_data",
        expected_summary_status="partial_summary",
        expected_approval_status="not_requested",
        expected_min_citations=1,
        expected_failure_mode="insufficient_business_evidence",
        notes="The workflow should avoid inventing ROI, revenue, or significance.",
    )
    state = build_default_agent_workflow_service().run(case.question)
    if unsupported_claim:
        state["executive_summary"]["summary"] = (
            "Annualized revenue lift is USD 100000 and statistically significant."
        )
    observation = extract_workflow_observation(state)
    metrics = calculate_agent_sample_metrics(case=case, observation=observation)
    sample = AgentEvaluationSampleResult(
        case=case,
        state=state,
        observation=observation,
        metrics=metrics,
        error=None,
    )
    return AgentEvaluationRun(
        samples=[sample],
        summary=AgentEvaluationSummary.from_samples([sample]),
    )


def build_agent_response_run() -> AgentE2ERun:
    workflow_case = AgentE2ECase(
        id="decision-loyalty-default",
        question="Should we roll out the loyalty tier progress nudges experiment?",
        scenario="decision_support",
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
        expected_min_citations=1,
        expected_decision_status="decided",
        expected_recommendation="rollout",
        expected_summary_status="generated",
        expected_approval_status="pending",
        expect_decision=True,
        expect_executive_summary=True,
        expect_agent_trace=True,
        expect_agent_metrics=True,
    )
    workflow_sample = AgentE2ESampleResult(
        case=workflow_case,
        status_code=200,
        response_json={
            "answer": "Roll out to silver and gold members with a frequency cap.",
            "citations": [
                {
                    "document_id": "exp-006-loyalty-doc-1",
                    "experiment_id": "exp-006-loyalty",
                    "quote": "Roll out to silver and gold members with a frequency cap.",
                    "section": "Recommendation",
                    "metadata": {"section": "Recommendation"},
                }
            ],
            "retrieved_chunks": [],
            "retrieval_metrics": {},
            "llm_metrics": {"model": "agent-workflow"},
            "intent": "decision_support",
            "required_agents": list(workflow_case.expected_required_agents),
            "decision": {
                "decision_status": "decided",
                "recommendation": "rollout",
                "rationale": "Evidence supports a monitored rollout.",
            },
            "executive_summary": {
                "summary_status": "generated",
                "summary": "Roll out to silver and gold members with a frequency cap.",
            },
            "agent_trace": [{"node": "planner", "event": "planned"}],
            "agent_metrics": {"retrieval": {"retrieved_chunks": 1}},
            "approval_status": "pending",
        },
        latency_ms=12.0,
        used_agent_workflow=True,
        used_legacy_fallback=False,
        passed=True,
        failure_reasons=(),
    )
    legacy_case = AgentE2ECase(
        id="legacy-fallback",
        question="What happened in the payment recommendation experiment?",
        scenario="legacy_fallback",
        ask_mode="legacy_rag",
        expected_min_citations=1,
    )
    legacy_sample = AgentE2ESampleResult(
        case=legacy_case,
        status_code=200,
        response_json={
            "answer": "Legacy grounded answer.",
            "citations": [
                {
                    "document_id": "legacy-doc-1",
                    "experiment_id": "legacy-exp",
                    "quote": "Legacy evidence chunk.",
                    "section": "Results",
                    "metadata": {"section": "Results"},
                }
            ],
            "retrieved_chunks": [],
            "retrieval_metrics": {},
            "llm_metrics": {"model": "mock"},
            "intent": None,
            "required_agents": [],
            "decision": None,
            "executive_summary": None,
            "agent_trace": [],
            "agent_metrics": {},
            "approval_status": None,
        },
        latency_ms=5.0,
        used_agent_workflow=False,
        used_legacy_fallback=True,
        passed=True,
        failure_reasons=(),
    )
    samples = [workflow_sample, legacy_sample]
    return AgentE2ERun(samples=samples, summary=AgentE2ESummary.from_samples(samples))


@dataclass
class FakeLLMTestCase:
    input: str
    actual_output: str | None = None
    expected_output: str | None = None
    context: list[str] | None = None
    retrieval_context: list[str] | None = None
    metadata: dict[str, object] | None = None
    comments: str | None = None
    name: str | None = None
    tags: list[str] | None = None
    custom_column_key_values: dict[str, str] | None = None


@dataclass
class FakeGolden:
    input: str
    actual_output: str | None = None
    expected_output: str | None = None
    context: list[str] | None = None
    retrieval_context: list[str] | None = None
    additional_metadata: dict[str, object] | None = None
    comments: str | None = None
    name: str | None = None
    custom_column_key_values: dict[str, str] | None = None


class FakeEvaluationDataset:
    def __init__(self, goldens, confident_api_key=None) -> None:
        self.goldens = list(goldens)
        self.confident_api_key = confident_api_key
        self.test_cases: list[FakeLLMTestCase] = []

    def add_test_case(self, test_case: FakeLLMTestCase) -> None:
        self.test_cases.append(test_case)


@dataclass
class FakeConfig:
    kwargs: dict[str, object]

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


@dataclass
class FakeMetric:
    name: str
    threshold: float
    model: str | None
    async_mode: bool


def fake_metric_factory(name: str):
    def factory(*, threshold: float, model: str | None = None, async_mode: bool = False, **kwargs):
        del kwargs
        return FakeMetric(
            name=name,
            threshold=threshold,
            model=model,
            async_mode=async_mode,
        )

    return factory


def build_fake_bindings():
    from packages.evals.deepeval_adapter import DeepEvalBindings

    def fake_evaluate(*, test_cases, metrics, **kwargs):
        del kwargs
        metric = metrics[0]
        test_results = []
        for index, test_case in enumerate(test_cases):
            test_results.append(
                types.SimpleNamespace(
                    name=test_case.name or f"case-{index}",
                    success=True,
                    metrics_data=[
                        types.SimpleNamespace(
                            name=metric.name,
                            threshold=metric.threshold,
                            success=True,
                            score=0.9,
                            reason="looks good",
                            error=None,
                            evaluation_model=metric.model,
                        )
                    ],
                    index=index,
                    input=test_case.input,
                    actual_output=test_case.actual_output,
                    expected_output=test_case.expected_output,
                    context=test_case.context,
                    retrieval_context=test_case.retrieval_context,
                    metadata=test_case.metadata,
                )
            )
        return types.SimpleNamespace(
            test_results=test_results,
            confident_link=None,
            test_run_id="local-test-run",
        )

    return DeepEvalBindings(
        version="4.0.7",
        EvaluationDataset=FakeEvaluationDataset,
        Golden=FakeGolden,
        LLMTestCase=FakeLLMTestCase,
        evaluate=fake_evaluate,
        assert_test=lambda *args, **kwargs: None,
        AsyncConfig=FakeConfig,
        CacheConfig=FakeConfig,
        DisplayConfig=FakeConfig,
        ErrorConfig=FakeConfig,
        metric_factories={
            "answer_relevancy": fake_metric_factory("answer_relevancy"),
            "faithfulness": fake_metric_factory("faithfulness"),
            "hallucination": fake_metric_factory("hallucination"),
            "contextual_relevancy": fake_metric_factory("contextual_relevancy"),
        },
    )


def patch_deepeval_dependencies(
    monkeypatch,
    run_deepeval,
    *,
    bindings=None,
    unsupported_claim: bool = False,
) -> None:
    if bindings is not None:
        monkeypatch.setattr(run_deepeval, "import_deepeval_bindings", lambda: bindings)
    monkeypatch.setattr(
        run_deepeval,
        "build_qa_evaluation_run",
        lambda args: build_qa_run(),
    )
    monkeypatch.setattr(
        run_deepeval,
        "build_agent_evaluation_run",
        lambda args: build_agent_workflow_run(unsupported_claim=unsupported_claim),
    )
    monkeypatch.setattr(
        run_deepeval,
        "build_agent_e2e_evaluation_run",
        lambda args: build_agent_response_run(),
    )
    monkeypatch.setattr(run_deepeval, "run_async", lambda value: value)


def test_prepare_qa_response_cases_maps_retrieval_context_and_expected_output() -> None:
    from packages.evals.deepeval_adapter import prepare_qa_response_cases

    cases = prepare_qa_response_cases(
        build_qa_run(),
        dataset_identifier="data/eval/qa_dataset.json",
    )

    assert len(cases) == 1
    assert cases[0].scope == "response"
    assert cases[0].surface == "legacy_rag"
    assert cases[0].expected_output == "Roll out to clean markets while monitoring telemetry."
    assert cases[0].retrieval_context == (
        "The recommendation was to roll out to clean markets while monitoring telemetry.",
    )


def test_prepare_agent_workflow_cases_maps_metadata_and_trace_information() -> None:
    from packages.evals.deepeval_adapter import prepare_agent_workflow_cases

    cases = prepare_agent_workflow_cases(
        build_agent_workflow_run(),
        dataset_identifier="data/eval/agent_dataset.json",
    )

    assert len(cases) == 1
    assert cases[0].scope == "workflow"
    assert cases[0].metadata["expected_decision_status"] == "needs_more_data"
    assert cases[0].metadata["trace_completeness"] == 1.0
    assert cases[0].metadata["approval_status"] == "not_requested"


def test_build_deepeval_dataset_converts_cases_to_goldens_and_test_cases() -> None:
    from packages.evals.deepeval_adapter import build_deepeval_dataset, prepare_qa_response_cases

    dataset = build_deepeval_dataset(
        prepare_qa_response_cases(build_qa_run(), dataset_identifier="data/eval/qa_dataset.json"),
        bindings=build_fake_bindings(),
        name="experimentos-phase3-deepeval-response",
    )

    assert len(dataset.goldens) == 1
    assert len(dataset.test_cases) == 1
    assert dataset.test_cases[0].name == "legacy_rag::payment-decision"
    assert (
        dataset.goldens[0].expected_output
        == "Roll out to clean markets while monitoring telemetry."
    )


def test_build_llm_test_case_rejects_blank_input() -> None:
    from packages.evals.deepeval_adapter import DeepEvalPreparedCase, build_llm_test_case

    case = DeepEvalPreparedCase(
        case_id="broken",
        category="invalid",
        scope="response",
        surface="legacy_rag",
        dataset_identifier="dataset",
        input_text="",
        actual_output="answer",
        expected_output=None,
        context=(),
        retrieval_context=(),
        metadata={},
        source_error=None,
    )

    try:
        build_llm_test_case(case, bindings=build_fake_bindings())
    except ValueError as exc:
        assert "input_text" in str(exc)
    else:
        raise AssertionError("expected build_llm_test_case() to reject blank input")


def test_write_deepeval_reports_offline_skips_judge_metrics_without_evaluate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from packages.evals import run_deepeval

    def explode(*args, **kwargs):
        raise AssertionError("offline mode should not invoke DeepEval judge evaluation")

    bindings_payload = vars(build_fake_bindings()).copy()
    bindings_payload["evaluate"] = explode
    bindings = types.SimpleNamespace(**bindings_payload)

    patch_deepeval_dependencies(monkeypatch, run_deepeval, bindings=bindings)

    output = tmp_path / "deepeval_report.md"
    json_output = tmp_path / "deepeval_report.json"
    args = run_deepeval.parse_args(
        [
            "--mode",
            "offline",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
            "--embedding-provider",
            "fake",
            "--llm-provider",
            "mock",
        ]
    )

    report = run_deepeval.write_deepeval_reports(args)

    assert output.is_file()
    assert json_output.is_file()
    assert report.deepeval_available is True
    skipped = {
        result.metric_name: result.skip_reason
        for result in report.metric_results
        if result.skipped
    }
    assert "answer_relevancy" in skipped
    assert "offline mode" in skipped["answer_relevancy"]


def test_build_deepeval_report_handles_missing_optional_dependency(monkeypatch) -> None:
    from packages.evals import run_deepeval

    monkeypatch.setattr(
        run_deepeval,
        "import_deepeval_bindings",
        lambda: (_ for _ in ()).throw(ModuleNotFoundError("deepeval")),
    )
    patch_deepeval_dependencies(monkeypatch, run_deepeval)

    args = run_deepeval.parse_args(
        ["--mode", "offline", "--embedding-provider", "fake", "--llm-provider", "mock"]
    )
    report = run_deepeval.build_deepeval_report(args)

    assert report.deepeval_available is False
    assert any(
        result.metric_name == "answer_relevancy" and result.skipped
        for result in report.metric_results
    )


def test_main_returns_nonzero_when_judge_mode_is_unconfigured() -> None:
    from packages.evals import run_deepeval

    exit_code = run_deepeval.main(["--mode", "judge"])

    assert exit_code == 1


def test_offline_report_includes_legacy_rag_fallback_case(monkeypatch) -> None:
    from packages.evals import run_deepeval

    patch_deepeval_dependencies(
        monkeypatch,
        run_deepeval,
        bindings=build_fake_bindings(),
    )

    report = run_deepeval.build_deepeval_report(
        run_deepeval.parse_args(
            ["--mode", "offline", "--embedding-provider", "fake", "--llm-provider", "mock"]
        )
    )

    legacy_results = [
        result
        for result in report.metric_results
        if result.case_id == "legacy_rag::legacy-fallback"
    ]
    assert legacy_results
    assert any(
        result.metric_name == "fallback_compatibility" and result.passed
        for result in legacy_results
    )


def test_unsupported_claim_metric_flags_incomplete_business_evidence(monkeypatch) -> None:
    from packages.evals import run_deepeval

    patch_deepeval_dependencies(
        monkeypatch,
        run_deepeval,
        bindings=build_fake_bindings(),
        unsupported_claim=True,
    )

    report = run_deepeval.build_deepeval_report(
        run_deepeval.parse_args(
            ["--mode", "offline", "--embedding-provider", "fake", "--llm-provider", "mock"]
        )
    )

    failures = [
        result
        for result in report.metric_results
        if result.metric_name == "unsupported_claim_avoidance"
    ]
    assert failures
    assert failures[0].passed is False


def test_write_deepeval_reports_writes_markdown_and_json(tmp_path: Path, monkeypatch) -> None:
    from packages.evals import run_deepeval

    patch_deepeval_dependencies(
        monkeypatch,
        run_deepeval,
        bindings=build_fake_bindings(),
    )

    output = tmp_path / "deepeval_report.md"
    json_output = tmp_path / "deepeval_report.json"
    report = run_deepeval.write_deepeval_reports(
        run_deepeval.parse_args(
            [
                "--mode",
                "offline",
                "--output",
                str(output),
                "--json-output",
                str(json_output),
                "--embedding-provider",
                "fake",
                "--llm-provider",
                "mock",
            ]
        )
    )

    markdown = output.read_text(encoding="utf-8")
    payload = json.loads(json_output.read_text(encoding="utf-8"))

    assert "# DeepEval Evaluation Report" in markdown
    assert payload["deepeval_version"] == report.deepeval_version
    assert payload["evaluation_mode"] == "offline"
