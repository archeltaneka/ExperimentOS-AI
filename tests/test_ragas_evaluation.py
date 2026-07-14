from __future__ import annotations

import types
import uuid
from pathlib import Path

from packages.evals.dataset import EvaluationQuestion
from packages.evals.evaluator import EvaluationRun, EvaluationSampleResult
from packages.evals.metrics import EvaluationSummary, SampleMetrics
from packages.evals.ragas_adapter import (
    PreparedRagasDataset,
    RagasBindings,
    build_ragas_dataset,
    prepare_ragas_dataset,
)
from packages.evals.ragas_report import (
    RagasCaseResult,
    RagasEvaluationReport,
    RagasMetricResult,
    render_ragas_report,
)


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
    error_sample = EvaluationSampleResult(
        question=EvaluationQuestion(
            id="payment-error",
            experiment_id=str(uuid.uuid4()),
            question="What failed?",
            expected_documents=("Adaptive Payment Method Recommendation",),
            expected_keywords=("telemetry",),
            category="legacy_rag_fallback",
            difficulty="medium",
            reference_answer="The source evaluation failed.",
        ),
        answer="",
        metrics=None,
        retrieved_documents=(),
        retrieved_contexts=(),
        error="RuntimeError: boom",
    )
    return EvaluationRun(
        samples=[sample, error_sample],
        summary=EvaluationSummary.from_samples([sample.metrics]),
        embedding_provider="fake",
        embedding_model="fake",
        llm_provider="mock",
        llm_model="mock",
    )


def test_prepare_ragas_dataset_converts_samples_and_excludes_errors() -> None:
    prepared = prepare_ragas_dataset(build_qa_run())

    assert isinstance(prepared, PreparedRagasDataset)
    assert len(prepared.samples) == 1
    assert prepared.samples[0].question_id == "payment-decision"
    assert prepared.samples[0].retrieved_context_ids == ("Adaptive Payment Method Recommendation",)
    assert prepared.samples[0].reference_context_ids == ("Adaptive Payment Method Recommendation",)
    assert len(prepared.excluded_samples) == 1
    assert prepared.excluded_samples[0].question_id == "payment-error"


def test_render_ragas_report_includes_scores_skips_and_limitations() -> None:
    report = RagasEvaluationReport(
        generated_at="2026-07-09T10:00:00Z",
        dataset_path="data/eval/qa_dataset.json",
        dataset_size=2,
        eligible_sample_count=1,
        excluded_sample_count=1,
        ragas_available=True,
        ragas_version="0.4.3",
        ragas_import_note=None,
        qa_embedding_provider="fake",
        qa_embedding_model="fake",
        qa_llm_provider="mock",
        qa_llm_model="mock",
        judge_llm_provider="none",
        judge_llm_model="none",
        judge_embedding_provider="none",
        judge_embedding_model="none",
        metrics_requested=("id_based_context_precision", "faithfulness"),
        metrics_run=("id_based_context_precision",),
        metric_results=(
            RagasMetricResult(
                name="id_based_context_precision",
                status="computed",
                average_score=1.0,
            ),
            RagasMetricResult(
                name="faithfulness",
                status="skipped",
                average_score=None,
                reason="judge llm not configured",
            ),
        ),
        case_results=(
            RagasCaseResult(
                question_id="payment-decision",
                experiment_id="exp-001-payment-recommendation",
                category="rollout_decision",
                difficulty="easy",
                retrieved_context_count=1,
                retrieved_document_count=1,
                source_error=None,
                metric_scores={"id_based_context_precision": 1.0},
            ),
        ),
        limitations=("Judge-backed metrics are opt-in.",),
    )

    markdown = render_ragas_report(report)

    assert "# RAGAS Evaluation Report" in markdown
    assert "Metrics run: id_based_context_precision" in markdown
    assert "faithfulness" in markdown
    assert "Judge-backed metrics are opt-in." in markdown
    assert "payment-decision" in markdown


def test_write_ragas_reports_runs_offline_metrics_and_skips_live_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from packages.evals import run_ragas

    async def fake_build_qa_run(_args):
        return build_qa_run()

    class FakeSingleTurnSample:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    class FakeEvaluationDataset:
        def __init__(self, samples, name=None) -> None:
            self.samples = samples
            self.name = name

    class FakeRunConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeMetric:
        def __init__(self, name: str) -> None:
            self.name = name

    def fake_evaluate(*, dataset, metrics, **kwargs):
        del kwargs
        metric_name = metrics[0].name
        scores = []
        for sample in dataset.samples:
            retrieved = set(sample.retrieved_context_ids)
            expected = set(sample.reference_context_ids)
            if metric_name == "id_based_context_precision":
                value = len(retrieved & expected) / len(retrieved)
            elif metric_name == "id_based_context_recall":
                value = len(retrieved & expected) / len(expected)
            else:
                raise AssertionError("Judge-backed metrics should be skipped by default.")
            scores.append({metric_name: value})
        return types.SimpleNamespace(scores=scores)

    fake_bindings = RagasBindings(
        version="0.4.3",
        EvaluationDataset=FakeEvaluationDataset,
        SingleTurnSample=FakeSingleTurnSample,
        RunConfig=FakeRunConfig,
        evaluate=fake_evaluate,
        llm_factory=lambda *args, **kwargs: None,
        embedding_factory=lambda *args, **kwargs: None,
        metric_factories={
            "id_based_context_precision": lambda: FakeMetric("id_based_context_precision"),
            "id_based_context_recall": lambda: FakeMetric("id_based_context_recall"),
            "context_precision": lambda: FakeMetric("context_precision"),
            "context_recall": lambda: FakeMetric("context_recall"),
            "faithfulness": lambda: FakeMetric("faithfulness"),
            "answer_relevancy": lambda: FakeMetric("answer_relevancy"),
        },
        shimmed_vertexai=False,
    )

    monkeypatch.setattr(run_ragas, "build_qa_evaluation_run", fake_build_qa_run)
    monkeypatch.setattr(run_ragas, "import_ragas_bindings", lambda: fake_bindings)

    output = tmp_path / "ragas_report.md"
    json_output = tmp_path / "ragas_report.json"
    args = run_ragas.parse_args(
        [
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

    report = run_ragas.write_ragas_reports(args)

    assert output.is_file()
    assert json_output.is_file()
    assert report.metrics_run == (
        "id_based_context_precision",
        "id_based_context_recall",
    )
    skipped = {
        metric.name: metric.reason for metric in report.metric_results if metric.status == "skipped"
    }
    assert "context_precision" in skipped
    assert "judge llm provider `none`" in skipped["context_precision"]
    assert "answer_relevancy" in skipped
    assert report.case_results[0].metric_scores["id_based_context_precision"] == 1.0
    assert report.case_results[0].metric_scores["id_based_context_recall"] == 1.0


def test_build_ragas_dataset_uses_single_turn_sample_shape() -> None:
    prepared = prepare_ragas_dataset(build_qa_run())

    class FakeSingleTurnSample:
        def __init__(self, **kwargs) -> None:
            self.payload = kwargs

    class FakeEvaluationDataset:
        def __init__(self, samples, name=None) -> None:
            self.samples = samples
            self.name = name

    bindings = RagasBindings(
        version="0.4.3",
        EvaluationDataset=FakeEvaluationDataset,
        SingleTurnSample=FakeSingleTurnSample,
        RunConfig=object,
        evaluate=None,
        llm_factory=None,
        embedding_factory=None,
        metric_factories={},
        shimmed_vertexai=False,
    )

    dataset = build_ragas_dataset(prepared, bindings)

    assert dataset.name == "experimentos-phase3-ragas"
    assert dataset.samples[0].payload["user_input"] == "Why did the payment recommendation ship?"
    assert dataset.samples[0].payload["retrieved_context_ids"] == [
        "Adaptive Payment Method Recommendation"
    ]
