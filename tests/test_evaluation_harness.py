from __future__ import annotations

import json
import uuid
from asyncio import run
from pathlib import Path

import pytest

from packages.llm.client import LLMMetrics
from packages.qa.question_answering_service import Citation, QAResponse
from packages.retrieval.service import RetrievalMetrics, RetrievalResult


def retrieval_result(
    *,
    experiment_id: str,
    document_name: str = "Adaptive Payment Method Recommendation",
    chunk_text: str = "The recommendation was to roll out after payment guardrails passed.",
    similarity: float = 0.87,
) -> RetrievalResult:
    return RetrievalResult(
        experiment_id=experiment_id,
        experiment_name="Adaptive Payment Method Recommendation",
        document_id=str(uuid.uuid4()),
        document_name=document_name,
        chunk_text=chunk_text,
        similarity=similarity,
        metadata={"section": "Recommendation"},
    )


def qa_response(*, experiment_id: str, document_name: str, chunk_text: str) -> QAResponse:
    result = retrieval_result(
        experiment_id=experiment_id,
        document_name=document_name,
        chunk_text=chunk_text,
        similarity=0.87,
    )
    return QAResponse(
        answer="Roll out to clean markets while monitoring wallet telemetry.",
        citations=[
            Citation(
                experiment_id=experiment_id,
                document=document_name,
                similarity=0.87,
            )
        ],
        retrieved_chunks=[result],
        retrieval_metrics=RetrievalMetrics(
            embedding_time_ms=11.0,
            vector_search_time_ms=7.0,
            retrieved_chunks=1,
            average_similarity=0.87,
        ),
        llm_metrics=LLMMetrics(
            model="mock",
            input_tokens=120,
            output_tokens=12,
            latency_ms=3.5,
        ),
    )


def test_load_evaluation_dataset_validates_records(tmp_path: Path) -> None:
    from packages.evals.dataset import load_evaluation_dataset

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "payment-decision",
                    "experiment_id": "exp-001-payment-recommendation",
                    "question": "Why did the payment recommendation ship?",
                    "expected_documents": ["Adaptive Payment Method Recommendation"],
                    "expected_keywords": ["roll out", "wallet telemetry"],
                    "category": "decision",
                    "difficulty": "easy",
                    "reference_answer": "Roll out to markets with clean wallet telemetry.",
                }
            ]
        ),
        encoding="utf-8",
    )

    dataset = load_evaluation_dataset(dataset_path)

    assert len(dataset) == 1
    assert dataset[0].id == "payment-decision"
    assert dataset[0].experiment_id == "exp-001-payment-recommendation"
    assert dataset[0].expected_documents == ("Adaptive Payment Method Recommendation",)
    assert dataset[0].expected_keywords == ("roll out", "wallet telemetry")
    assert dataset[0].expected_citation_required is True
    assert dataset[0].expected_failure_mode is None
    assert dataset[0].notes is None


def test_load_evaluation_dataset_supports_optional_metadata_fields(tmp_path: Path) -> None:
    from packages.evals.dataset import load_evaluation_dataset

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "payment-insufficient-evidence",
                    "experiment_id": "exp-001-payment-recommendation",
                    "question": "What ROI should we expect from payment recommendations in Japan?",
                    "expected_documents": ["Adaptive Payment Method Recommendation"],
                    "expected_keywords": ["under-counted", "Japan wallet", "needs more data"],
                    "category": "insufficient_evidence",
                    "difficulty": "medium",
                    "reference_answer": (
                        "The report does not support a grounded ROI estimate for Japan because "
                        "wallet success telemetry was under-counted."
                    ),
                    "expected_citation_required": True,
                    "expected_failure_mode": "unsupported_business_estimate",
                    "notes": "Avoid inventing ROI or revenue where the report only flags gaps.",
                }
            ]
        ),
        encoding="utf-8",
    )

    dataset = load_evaluation_dataset(dataset_path)

    assert len(dataset) == 1
    assert dataset[0].category == "insufficient_evidence"
    assert dataset[0].expected_citation_required is True
    assert dataset[0].expected_failure_mode == "unsupported_business_estimate"
    assert dataset[0].notes == "Avoid inventing ROI or revenue where the report only flags gaps."


def test_load_evaluation_dataset_rejects_invalid_optional_metadata(tmp_path: Path) -> None:
    from packages.evals.dataset import load_evaluation_dataset

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "payment-invalid-optional-fields",
                    "experiment_id": "exp-001-payment-recommendation",
                    "question": "Why did the payment recommendation ship?",
                    "expected_documents": ["Adaptive Payment Method Recommendation"],
                    "expected_keywords": ["roll out"],
                    "category": "rollout_decision",
                    "difficulty": "easy",
                    "reference_answer": "Roll out to clean markets while monitoring telemetry.",
                    "expected_citation_required": "yes",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_citation_required"):
        load_evaluation_dataset(dataset_path)


def test_golden_dataset_covers_all_synthetic_experiments() -> None:
    from packages.evals.dataset import DEFAULT_DATASET_PATH, load_evaluation_dataset

    assert DEFAULT_DATASET_PATH == Path("data/eval/qa_dataset.json")
    assert DEFAULT_DATASET_PATH.is_file()

    dataset = load_evaluation_dataset(DEFAULT_DATASET_PATH)

    assert len(dataset) >= 60
    assert {item.experiment_id for item in dataset} == {
        "exp-001-payment-recommendation",
        "exp-002-hotel-image-quality",
        "exp-003-search-ranking",
        "exp-004-checkout-ux",
        "exp-005-pricing",
        "exp-006-loyalty",
        "exp-007-crm-notifications",
        "exp-008-recommendation-systems",
        "exp-009-search-filters",
        "exp-010-premium-subscriptions",
    }
    assert {
        "factual_retrieval",
        "result_interpretation",
        "business_impact",
        "risk_guardrail",
        "rollout_decision",
        "insufficient_evidence",
        "legacy_rag_fallback",
    }.issubset({item.category for item in dataset})


def test_sample_metrics_capture_latency_tokens_coverage_and_cost() -> None:
    from packages.evals.dataset import EvaluationQuestion
    from packages.evals.metrics import calculate_sample_metrics

    experiment_id = str(uuid.uuid4())
    question = EvaluationQuestion(
        id="payment-decision",
        experiment_id=experiment_id,
        question="Why did the payment recommendation ship?",
        expected_documents=("Adaptive Payment Method Recommendation",),
        expected_keywords=("roll out", "wallet telemetry"),
        category="decision",
        difficulty="easy",
        reference_answer="Roll out to markets with clean wallet telemetry.",
    )

    metrics = calculate_sample_metrics(
        question,
        qa_response(
            experiment_id=experiment_id,
            document_name="Adaptive Payment Method Recommendation",
            chunk_text="The recommendation was to roll out with wallet telemetry monitoring.",
        ),
        input_cost_per_1k_tokens=0.01,
        output_cost_per_1k_tokens=0.03,
    )

    assert metrics.retrieval_latency_ms == pytest.approx(18.0)
    assert metrics.llm_latency_ms == pytest.approx(3.5)
    assert metrics.citation_coverage == pytest.approx(1.0)
    assert metrics.retrieval_success is True
    assert metrics.average_similarity == pytest.approx(0.87)
    assert metrics.input_tokens == 120
    assert metrics.output_tokens == 12
    assert metrics.total_tokens == 132
    assert metrics.estimated_cost_usd == pytest.approx(0.00156)


def test_offline_evaluator_invokes_question_answering_service() -> None:
    from packages.evals.dataset import EvaluationQuestion
    from packages.evals.evaluator import OfflineEvaluator

    experiment_id = str(uuid.uuid4())

    class StubQAService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int]] = []

        async def answer_question(
            self,
            *,
            question: str,
            experiment_id: str,
            top_k: int = 5,
        ) -> QAResponse:
            self.calls.append((question, experiment_id, top_k))
            return qa_response(
                experiment_id=experiment_id,
                document_name="Adaptive Payment Method Recommendation",
                chunk_text="The recommendation was to roll out with wallet telemetry monitoring.",
            )

    question = EvaluationQuestion(
        id="payment-decision",
        experiment_id="exp-001-payment-recommendation",
        question="Why did the payment recommendation ship?",
        expected_documents=("Adaptive Payment Method Recommendation",),
        expected_keywords=("roll out",),
        category="decision",
        difficulty="easy",
        reference_answer="Roll out with telemetry monitoring.",
    )
    service = StubQAService()
    evaluator = OfflineEvaluator(
        qa_service=service,
        questions=[question],
        top_k=3,
        experiment_id_resolver=lambda item: experiment_id,
    )

    result = run(evaluator.evaluate())

    assert service.calls == [("Why did the payment recommendation ship?", experiment_id, 3)]
    assert result.summary.question_count == 1
    assert result.summary.retrieval_success_rate == pytest.approx(1.0)
    assert result.samples[0].metrics is not None
    assert result.samples[0].error is None


def test_report_renderer_includes_summary_and_low_performing_rows() -> None:
    from packages.evals.dataset import EvaluationQuestion
    from packages.evals.evaluator import EvaluationRun, EvaluationSampleResult
    from packages.evals.metrics import EvaluationSummary, SampleMetrics
    from packages.evals.report import render_evaluation_report

    question = EvaluationQuestion(
        id="payment-decision",
        experiment_id="exp-001-payment-recommendation",
        question="Why did the payment recommendation ship?",
        expected_documents=("Adaptive Payment Method Recommendation",),
        expected_keywords=("roll out",),
        category="decision",
        difficulty="easy",
        reference_answer="Roll out with telemetry monitoring.",
    )
    sample = EvaluationSampleResult(
        question=question,
        answer="Roll out to selected markets.",
        metrics=SampleMetrics(
            retrieval_latency_ms=18.0,
            llm_latency_ms=3.5,
            citation_coverage=1.0,
            retrieval_success=True,
            average_similarity=0.87,
            input_tokens=120,
            output_tokens=12,
            estimated_cost_usd=0.00156,
        ),
        retrieved_documents=("Adaptive Payment Method Recommendation",),
        retrieved_contexts=(
            "The recommendation was to roll out with wallet telemetry monitoring.",
        ),
        error=None,
    )
    run_result = EvaluationRun(
        samples=[sample],
        summary=EvaluationSummary.from_samples([sample.metrics]),
        embedding_provider="ollama",
        embedding_model="nomic-embed-text",
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
    )

    markdown = render_evaluation_report(run_result)

    assert "# Evaluation Harness Report" in markdown
    assert "Embedding provider: ollama" in markdown
    assert "Embedding model: nomic-embed-text" in markdown
    assert "LLM provider: ollama" in markdown
    assert "LLM model: qwen2.5:7b" in markdown
    assert "Questions evaluated: 1" in markdown
    assert "Retrieval success rate: 100.0%" in markdown
    assert "payment-decision" in markdown


def test_cli_parser_accepts_dataset_output_and_provider_options() -> None:
    from packages.evals.run import parse_args

    default_args = parse_args([])

    assert default_args.dataset == Path("data/eval/qa_dataset.json")

    args = parse_args(
        [
            "--dataset",
            "custom.json",
            "--output",
            "reports/custom.md",
            "--top-k",
            "4",
            "--embedding-provider",
            "ollama",
            "--embedding-model",
            "nomic-embed-text",
            "--llm-provider",
            "ollama",
            "--llm-model",
            "qwen2.5:7b",
        ]
    )

    assert args.dataset == Path("custom.json")
    assert args.output == Path("reports/custom.md")
    assert args.top_k == 4
    assert args.embedding_provider == "ollama"
    assert args.embedding_model == "nomic-embed-text"
    assert args.llm_provider == "ollama"
    assert args.llm_model == "qwen2.5:7b"

    gemini_args = parse_args(
        [
            "--embedding-provider",
            "gemini",
            "--embedding-model",
            "gemini-embedding-001",
            "--llm-provider",
            "gemini",
            "--llm-model",
            "gemini-3.5-flash",
        ]
    )

    assert gemini_args.embedding_provider == "gemini"
    assert gemini_args.embedding_model == "gemini-embedding-001"
    assert gemini_args.llm_provider == "gemini"
    assert gemini_args.llm_model == "gemini-3.5-flash"


class StubOllamaLLMClient:
    def __init__(self) -> None:
        self.calls = []

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "system": system,
                "options": options,
            }
        )
        return {
            "response": "Use the cited experiment context.",
            "prompt_eval_count": 10,
            "eval_count": 6,
        }


def test_ollama_llm_client_uses_qwen_default_and_reports_tokens() -> None:
    from packages.llm.client import OLLAMA_LLM_MODEL, OllamaLLMClient

    client = StubOllamaLLMClient()
    llm = OllamaLLMClient(client=client)

    response = run(
        llm.generate(
            prompt="Question and context",
            system_instruction="Only answer using retrieved context.",
        )
    )

    assert llm.model == OLLAMA_LLM_MODEL
    assert client.calls == [
        {
            "model": "qwen2.5:7b",
            "prompt": "Question and context",
            "system": "Only answer using retrieved context.",
            "options": {"temperature": 0},
        }
    ]
    assert response.answer == "Use the cited experiment context."
    assert response.metrics.model == "qwen2.5:7b"
    assert response.metrics.input_tokens == 10
    assert response.metrics.output_tokens == 6


class StubGeminiUsageMetadata:
    prompt_token_count = 11
    candidates_token_count = 7


class StubGeminiLLMResponse:
    text = "Use the cited Gemini context."
    usage_metadata = StubGeminiUsageMetadata()


class StubGeminiAsyncModels:
    def __init__(self) -> None:
        self.generate_calls = []

    async def generate_content(
        self,
        *,
        model: str,
        contents: str,
    ) -> StubGeminiLLMResponse:
        self.generate_calls.append({"model": model, "contents": contents})
        return StubGeminiLLMResponse()


class StubGeminiAio:
    def __init__(self) -> None:
        self.models = StubGeminiAsyncModels()


class StubGeminiLLMClient:
    def __init__(self) -> None:
        self.aio = StubGeminiAio()


def test_gemini_llm_client_uses_flash_default_and_reports_tokens() -> None:
    from packages.llm.client import GEMINI_LLM_MODEL, GeminiLLMClient

    client = StubGeminiLLMClient()
    llm = GeminiLLMClient(client=client)

    response = run(
        llm.generate(
            prompt="Question and context",
            system_instruction="Only answer using retrieved context.",
        )
    )

    assert llm.model == GEMINI_LLM_MODEL
    assert client.aio.models.generate_calls == [
        {
            "model": "gemini-3.5-flash",
            "contents": "Only answer using retrieved context.\n\nQuestion and context",
        }
    ]
    assert response.answer == "Use the cited Gemini context."
    assert response.metrics.model == "gemini-3.5-flash"
    assert response.metrics.input_tokens == 11
    assert response.metrics.output_tokens == 7
