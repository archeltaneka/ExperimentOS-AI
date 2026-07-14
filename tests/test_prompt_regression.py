from __future__ import annotations

import json
import uuid
from asyncio import run
from pathlib import Path

import pytest

from packages.evals.agent_e2e import AgentE2ECase
from packages.evals.dataset import EvaluationQuestion
from packages.llm.prompt_registry import PromptDefinition, PromptRegistry
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


def build_registry(
    *,
    baseline_user_template: str,
    candidate_user_template: str,
) -> PromptRegistry:
    registry = PromptRegistry()
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="1",
            description="Baseline prompt.",
            system_template=(
                "Only answer using retrieved context.\n"
                "If the answer cannot be supported by retrieved evidence, say that insufficient "
                "evidence exists.\n"
                "Never invent facts."
            ),
            user_template=baseline_user_template,
            input_variables=("question", "context"),
            output_contract="Grounded answer.",
            tags=("legacy_rag",),
            status="active",
            created_at="2026-07-10T00:00:00Z",
            metadata={"surface": "legacy_rag"},
        ),
        active=True,
    )
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="2",
            description="Candidate prompt.",
            system_template=(
                "Only answer using retrieved context.\n"
                "If the answer cannot be supported by retrieved evidence, say that insufficient "
                "evidence exists.\n"
                "Never invent facts."
            ),
            user_template=candidate_user_template,
            input_variables=("question", "context"),
            output_contract="Grounded answer.",
            tags=("legacy_rag",),
            status="experimental",
            created_at="2026-07-10T00:00:01Z",
            metadata={"surface": "legacy_rag"},
        )
    )
    registry.validate()
    return registry


def build_question() -> EvaluationQuestion:
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


def build_ask_case() -> AgentE2ECase:
    return AgentE2ECase(
        id="legacy-fallback",
        question="What happened in the payment recommendation experiment?",
        scenario="legacy_fallback",
        ask_mode="legacy_rag",
        expected_min_citations=1,
    )


def build_retrieval_results() -> list[RetrievalResult]:
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


def test_prompt_regression_runner_reports_unchanged_for_identical_prompt_behavior() -> None:
    from packages.evals.prompt_regression import PromptRegressionRunner

    template = "\n\n".join(
        [
            "User Question: {question}",
            "Retrieved Context:",
            "{context}",
            "Answer using only the retrieved context and cite the supporting documents.",
        ]
    )
    registry = build_registry(
        baseline_user_template=template,
        candidate_user_template=template,
    )
    runner = PromptRegressionRunner(
        prompt_registry=registry,
        prompt_id="rag.answer",
        baseline_version="1",
        candidate_version="2",
        qa_questions=[build_question()],
        ask_cases=[build_ask_case()],
        retrieval_service=StubRetrievalService(build_retrieval_results()),
    )

    report = run(runner.evaluate())

    assert report.summary.cases_run == 2
    assert report.summary.regressions == 0
    assert report.summary.improvements == 0
    assert report.summary.unchanged == 2
    assert report.summary.failures == 0
    assert report.ragas_comparison is not None
    assert report.deepeval_comparison is not None


def test_prompt_regression_runner_detects_improvements_and_regressions() -> None:
    from packages.evals.prompt_regression import PromptRegressionRunner

    improved_template = "\n\n".join(
        [
            "User Question: {question}",
            "Retrieved Context:",
            "{context}",
            "Answer using only the retrieved context, cite the supporting documents, "
            "and preserve insufficient-evidence handling.",
        ]
    )
    degraded_template = "\n\n".join(
        [
            "User Question: {question}",
            "Retrieved Context:",
            "{context}",
            "Answer quickly.",
        ]
    )

    improved_registry = build_registry(
        baseline_user_template=degraded_template,
        candidate_user_template=improved_template,
    )
    improved_report = run(
        PromptRegressionRunner(
            prompt_registry=improved_registry,
            prompt_id="rag.answer",
            baseline_version="1",
            candidate_version="2",
            qa_questions=[build_question()],
            ask_cases=[build_ask_case()],
            retrieval_service=StubRetrievalService(build_retrieval_results()),
        ).evaluate()
    )
    assert improved_report.summary.improvements >= 1
    assert improved_report.summary.regressions == 0

    degraded_registry = build_registry(
        baseline_user_template=improved_template,
        candidate_user_template=degraded_template,
    )
    degraded_report = run(
        PromptRegressionRunner(
            prompt_registry=degraded_registry,
            prompt_id="rag.answer",
            baseline_version="1",
            candidate_version="2",
            qa_questions=[build_question()],
            ask_cases=[build_ask_case()],
            retrieval_service=StubRetrievalService(build_retrieval_results()),
        ).evaluate()
    )
    assert degraded_report.summary.regressions >= 1
    assert any(case.regression_detected for case in degraded_report.case_results)


def test_prompt_regression_runner_records_render_failures_without_crashing() -> None:
    from packages.evals.prompt_regression import PromptRegressionRunner

    registry = PromptRegistry()
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="1",
            description="Baseline prompt.",
            system_template="System {question}",
            user_template="Context: {context}",
            input_variables=("question", "context"),
            output_contract="Grounded answer.",
            tags=("legacy_rag",),
            status="active",
            created_at="2026-07-10T00:00:00Z",
            metadata={"surface": "legacy_rag"},
        ),
        active=True,
    )
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="2",
            description="Broken candidate prompt.",
            system_template="System {question}",
            user_template="Context: {context}\nAudience: {audience}",
            input_variables=("question", "context", "audience"),
            output_contract="Grounded answer.",
            tags=("legacy_rag",),
            status="experimental",
            created_at="2026-07-10T00:00:01Z",
            metadata={"surface": "legacy_rag"},
        )
    )
    registry.validate()

    report = run(
        PromptRegressionRunner(
            prompt_registry=registry,
            prompt_id="rag.answer",
            baseline_version="1",
            candidate_version="2",
            qa_questions=[build_question()],
            ask_cases=[],
            retrieval_service=StubRetrievalService(build_retrieval_results()),
        ).evaluate()
    )

    assert report.summary.failures == 1
    assert report.case_results[0].regression_detected is True
    assert "missing variables" in " ".join(report.case_results[0].notes).lower()


@pytest.mark.parametrize(
    ("prompt_id", "baseline_version", "candidate_version", "message"),
    [
        ("missing.prompt", "1", "2", "unknown prompt"),
        ("rag.answer", "9", "2", "unknown version"),
    ],
)
def test_prompt_regression_runner_rejects_unknown_prompt_or_version(
    prompt_id: str,
    baseline_version: str,
    candidate_version: str,
    message: str,
) -> None:
    from packages.evals.prompt_regression import PromptRegressionRunner

    registry = build_registry(
        baseline_user_template="Question: {question}\nContext: {context}",
        candidate_user_template="Question: {question}\nContext: {context}",
    )

    with pytest.raises(Exception, match=message):
        PromptRegressionRunner(
            prompt_registry=registry,
            prompt_id=prompt_id,
            baseline_version=baseline_version,
            candidate_version=candidate_version,
            qa_questions=[build_question()],
            ask_cases=[],
            retrieval_service=StubRetrievalService(build_retrieval_results()),
        )


def test_prompt_regression_report_writes_markdown_and_json(
    tmp_path: Path,
) -> None:
    from packages.evals.prompt_regression import (
        PromptRegressionRunner,
        prompt_regression_to_json,
        render_prompt_regression_report,
    )

    template = "\n\n".join(
        [
            "User Question: {question}",
            "Retrieved Context:",
            "{context}",
            "Answer using only the retrieved context and cite the supporting documents.",
        ]
    )
    registry = build_registry(
        baseline_user_template=template,
        candidate_user_template=template,
    )
    report = run(
        PromptRegressionRunner(
            prompt_registry=registry,
            prompt_id="rag.answer",
            baseline_version="1",
            candidate_version="2",
            qa_questions=[build_question()],
            ask_cases=[build_ask_case()],
            retrieval_service=StubRetrievalService(build_retrieval_results()),
        ).evaluate()
    )

    markdown_path = tmp_path / "prompt_regression.md"
    json_path = tmp_path / "prompt_regression.json"
    markdown_path.write_text(render_prompt_regression_report(report), encoding="utf-8")
    json_path.write_text(prompt_regression_to_json(report), encoding="utf-8")

    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert "# Prompt Regression Report" in markdown_path.read_text(encoding="utf-8")
    assert payload["prompt_id"] == "rag.answer"
    assert payload["baseline_version"] == "1"
    assert payload["candidate_version"] == "2"


def test_prompt_regression_cli_runs_offline_without_live_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import packages.evals.run_prompt_regression as run_prompt_regression_module
    from packages.evals.prompt_regression import (
        PromptRegressionCaseResult,
        PromptRegressionFrameworkComparison,
        PromptRegressionMetricComparison,
        PromptRegressionReport,
        PromptRegressionSummary,
    )

    output = tmp_path / "prompt_regression.md"
    json_output = tmp_path / "prompt_regression.json"

    async def fake_build_prompt_regression_report(_args):
        return PromptRegressionReport(
            prompt_id="rag.answer",
            baseline_version="1",
            candidate_version="1",
            dataset="data/eval/qa_dataset.json",
            case_results=(
                PromptRegressionCaseResult(
                    case_id="payment-decision",
                    surface="legacy_rag",
                    baseline_output="Answer.",
                    candidate_output="Answer.",
                    metric_scores={
                        "answer_generated": {
                            "baseline": 1.0,
                            "candidate": 1.0,
                            "delta": 0.0,
                            "regression": False,
                            "improvement": False,
                        }
                    },
                    regression_detected=False,
                    improvement_detected=False,
                    failed=False,
                    notes=(),
                ),
            ),
            metrics=(
                PromptRegressionMetricComparison(
                    name="answer_generated",
                    baseline=1.0,
                    candidate=1.0,
                    delta=0.0,
                    regressions=0,
                    improvements=0,
                ),
            ),
            ragas_comparison=PromptRegressionFrameworkComparison(
                framework="ragas",
                metrics=(),
                notes=(),
            ),
            deepeval_comparison=PromptRegressionFrameworkComparison(
                framework="deepeval",
                metrics=(),
                notes=(),
            ),
            summary=PromptRegressionSummary(
                cases_run=1,
                regressions=0,
                improvements=0,
                unchanged=1,
                failures=0,
                skipped=0,
                passed=True,
            ),
        )

    monkeypatch.setattr(
        run_prompt_regression_module,
        "build_prompt_regression_report",
        fake_build_prompt_regression_report,
    )

    exit_code = run_prompt_regression_module.main(
        [
            "--prompt-id",
            "rag.answer",
            "--baseline-version",
            "1",
            "--candidate-version",
            "1",
            "--offline",
            "--dataset",
            "data/eval/qa_dataset.json",
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

    assert exit_code == 0
    assert output.is_file()
    assert json_output.is_file()
    assert "Prompt Regression Report" in output.read_text(encoding="utf-8")


def test_build_prompt_regression_report_runs_offline_without_database(
    monkeypatch,
) -> None:
    import packages.evals.run_prompt_regression as module
    from packages.evals.prompt_regression import (
        PromptRegressionFrameworkComparison,
        PromptRegressionMetricComparison,
        PromptRegressionReport,
        PromptRegressionSummary,
    )

    captured = {}

    async def fake_evaluate(self):
        captured["retrieval_service"] = self.retrieval_service
        return PromptRegressionReport(
            prompt_id="rag.answer",
            baseline_version="1",
            candidate_version="1",
            dataset="data/eval/ci_smoke_dataset.json",
            case_results=(),
            metrics=(
                PromptRegressionMetricComparison(
                    name="answer_generated",
                    baseline=1.0,
                    candidate=1.0,
                    delta=0.0,
                    regressions=0,
                    improvements=0,
                ),
            ),
            ragas_comparison=PromptRegressionFrameworkComparison(
                framework="ragas",
                metrics=(),
                notes=(),
            ),
            deepeval_comparison=PromptRegressionFrameworkComparison(
                framework="deepeval",
                metrics=(),
                notes=(),
            ),
            summary=PromptRegressionSummary(
                cases_run=0,
                regressions=0,
                improvements=0,
                unchanged=0,
                failures=0,
                skipped=0,
                passed=True,
            ),
        )

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(module, "_resolve_questions", lambda _path: [build_question()])
    monkeypatch.setattr(
        module,
        "create_database_engine",
        lambda: (_ for _ in ()).throw(
            AssertionError("offline prompt regression should not create a database engine")
        ),
    )
    monkeypatch.setattr(module.PromptRegressionRunner, "evaluate", fake_evaluate)

    report = module.run_async(
        module.build_prompt_regression_report(
            module.parse_args(
                [
                    "--prompt-id",
                    "rag.answer",
                    "--baseline-version",
                    "1",
                    "--candidate-version",
                    "1",
                    "--offline",
                    "--dataset",
                    "data/eval/ci_smoke_dataset.json",
                    "--embedding-provider",
                    "fake",
                    "--llm-provider",
                    "mock",
                ]
            )
        )
    )

    assert report.prompt_id == "rag.answer"
    assert captured["retrieval_service"].__class__.__name__.startswith("_Offline")


def test_build_prompt_regression_report_stays_offline_when_runtime_resolution_loads_dotenv(
    monkeypatch,
) -> None:
    import packages.evals.run_prompt_regression as module
    from packages.evals.prompt_regression import (
        PromptRegressionFrameworkComparison,
        PromptRegressionMetricComparison,
        PromptRegressionReport,
        PromptRegressionSummary,
    )

    captured = {}

    async def fake_evaluate(self):
        captured["retrieval_service"] = self.retrieval_service
        return PromptRegressionReport(
            prompt_id="rag.answer",
            baseline_version="1",
            candidate_version="1",
            dataset="data/eval/ci_smoke_dataset.json",
            case_results=(),
            metrics=(
                PromptRegressionMetricComparison(
                    name="answer_generated",
                    baseline=1.0,
                    candidate=1.0,
                    delta=0.0,
                    regressions=0,
                    improvements=0,
                ),
            ),
            ragas_comparison=PromptRegressionFrameworkComparison(
                framework="ragas",
                metrics=(),
                notes=(),
            ),
            deepeval_comparison=PromptRegressionFrameworkComparison(
                framework="deepeval",
                metrics=(),
                notes=(),
            ),
            summary=PromptRegressionSummary(
                cases_run=0,
                regressions=0,
                improvements=0,
                unchanged=0,
                failures=0,
                skipped=0,
                passed=True,
            ),
        )

    def fake_resolve_runtime_options(args):
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://from-dotenv/test")
        return args

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(module, "_resolve_questions", lambda _path: [build_question()])
    monkeypatch.setattr(module, "resolve_runtime_options", fake_resolve_runtime_options)
    monkeypatch.setattr(
        module,
        "create_database_engine",
        lambda: (_ for _ in ()).throw(
            AssertionError("offline prompt regression should ignore dotenv database URLs")
        ),
    )
    monkeypatch.setattr(module.PromptRegressionRunner, "evaluate", fake_evaluate)

    report = module.run_async(
        module.build_prompt_regression_report(
            module.parse_args(
                [
                    "--prompt-id",
                    "rag.answer",
                    "--baseline-version",
                    "1",
                    "--candidate-version",
                    "1",
                    "--offline",
                    "--dataset",
                    "data/eval/ci_smoke_dataset.json",
                    "--embedding-provider",
                    "fake",
                    "--llm-provider",
                    "mock",
                ]
            )
        )
    )

    assert report.prompt_id == "rag.answer"
    assert captured["retrieval_service"].__class__.__name__.startswith("_Offline")
