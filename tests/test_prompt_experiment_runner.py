from __future__ import annotations

import json
import uuid
from asyncio import run
from pathlib import Path

from packages.evals.dataset import EvaluationQuestion
from packages.llm.client import MockLLMClient
from packages.retrieval.service import RetrievalMetrics, RetrievalResult


class StubRetrievalService:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.last_metrics = RetrievalMetrics(
            embedding_time_ms=4.0,
            vector_search_time_ms=6.0,
            retrieved_chunks=len(results),
            average_similarity=0.91 if results else 0.0,
        )
        self.calls: list[tuple[str, str, int]] = []

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        self.calls.append((experiment_id, query, top_k))
        return self.results


def _definition(*, primary_metric: str = "factuality_pass_rate"):
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition

    return PromptExperimentDefinition(
        experiment_id="rag-answer-abstention-v1-v2",
        name="RAG answer abstention wording",
        description="Compare current control and stronger abstention wording.",
        prompt_id="rag.answer",
        control_version="1",
        treatment_versions=("2",),
        hypothesis="Stronger abstention wording reduces unsupported claims.",
        primary_metric=primary_metric,
        secondary_metrics=("citation_coverage", "regression_pass_rate"),
        guardrail_metrics=(
            "critical_factuality_violations",
            "fabricated_revenue_or_roi",
            "citation_coverage_non_regression",
        ),
        dataset_id="qa_dataset",
        assignment_strategy="fixed",
        allocation={"control": 0.5, "treatment_2": 0.5},
        randomization_unit="dataset_case",
        seed="prompt-exp-seed",
        status="validated",
        allow_deprecated_versions=False,
        metadata={},
    )


def _question() -> EvaluationQuestion:
    return EvaluationQuestion(
        id="payment-decision",
        experiment_id="exp-001-payment-recommendation",
        question="Why did the payment recommendation ship?",
        expected_documents=("Adaptive Payment Method Recommendation",),
        expected_keywords=("roll out", "wallet telemetry"),
        category="rollout_decision",
        difficulty="easy",
        reference_answer="Roll out to clean markets while monitoring wallet telemetry.",
    )


def _retrieval_results() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            experiment_id="exp-001-payment-recommendation",
            experiment_name="Adaptive Payment Method Recommendation",
            document_id=str(uuid.uuid4()),
            document_name="Adaptive Payment Method Recommendation",
            chunk_text=(
                "Roll out to clean markets while monitoring wallet telemetry. "
                "Japan wallet success events were under-counted."
            ),
            similarity=0.91,
            metadata={"section": "Recommendation"},
        )
    ]


def _safe_variant_llm() -> MockLLMClient:
    def build_answer(_prompt: str, system_instruction: str) -> str:
        if "Prefer abstaining over guessing." in system_instruction:
            return "Insufficient evidence exists to answer the question."
        return (
            "Roll out to clean markets while monitoring wallet telemetry. "
            "Source: Adaptive Payment Method Recommendation."
        )

    return MockLLMClient(model="mock-prompt-experiment", response_builder=build_answer)


def _unsafe_treatment_llm() -> MockLLMClient:
    def build_answer(_prompt: str, system_instruction: str) -> str:
        if "Prefer abstaining over guessing." in system_instruction:
            return (
                "Annualized revenue lift was USD 1.2M and the result was statistically "
                "significant. Source: Adaptive Payment Method Recommendation."
            )
        return (
            "Roll out to clean markets while monitoring wallet telemetry. "
            "Source: Adaptive Payment Method Recommendation."
        )

    return MockLLMClient(model="mock-prompt-experiment", response_builder=build_answer)


def test_prompt_experiment_runner_reuses_same_retrieval_for_control_and_treatment() -> None:
    from packages.evals.prompt_experiments.runner import PromptExperimentRunner

    runner = PromptExperimentRunner(
        definition=_definition(),
        qa_questions=[_question()],
        ask_cases=(),
        retrieval_service=StubRetrievalService(_retrieval_results()),
        llm_client_factory=_safe_variant_llm,
    )

    report = run(runner.run())

    assert report.validity_status == "valid"
    assert report.production_traffic_involved is False
    assert report.variants["control"].sample_size == 1
    assert report.variants["treatment_2"].sample_size == 1
    assert report.config_fingerprint["retrieval_reused"] is True


def test_guardrail_failure_blocks_treatment_recommendation() -> None:
    from packages.evals.prompt_experiments.runner import PromptExperimentRunner

    runner = PromptExperimentRunner(
        definition=_definition(primary_metric="citation_coverage"),
        qa_questions=[_question()],
        ask_cases=(),
        retrieval_service=StubRetrievalService(_retrieval_results()),
        llm_client_factory=_unsafe_treatment_llm,
    )

    report = run(runner.run())

    assert report.recommendation.outcome == "retain_control"
    assert "critical factuality violations" in " ".join(report.recommendation.reasons).lower()


def test_prompt_experiment_report_writes_markdown_and_json(tmp_path: Path) -> None:
    from packages.evals.prompt_experiments.reporting import (
        prompt_experiment_report_to_json,
        render_prompt_experiment_report,
    )
    from packages.evals.prompt_experiments.runner import PromptExperimentRunner

    report = run(
        PromptExperimentRunner(
            definition=_definition(),
            qa_questions=[_question()],
            ask_cases=(),
            retrieval_service=StubRetrievalService(_retrieval_results()),
            llm_client_factory=_safe_variant_llm,
        ).run()
    )

    markdown_path = tmp_path / "prompt_experiment.md"
    json_path = tmp_path / "prompt_experiment.json"
    markdown_path.write_text(render_prompt_experiment_report(report), encoding="utf-8")
    json_path.write_text(prompt_experiment_report_to_json(report), encoding="utf-8")

    payload = json.loads(json_path.read_text(encoding="utf-8"))

    markdown = markdown_path.read_text(encoding="utf-8")

    assert "Offline evaluation results do not establish production causal impact." in markdown
    assert payload["experiment_id"] == "rag-answer-abstention-v1-v2"
    assert payload["production_traffic_involved"] is False
