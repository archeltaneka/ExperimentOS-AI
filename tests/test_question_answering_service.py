from __future__ import annotations

import uuid
from asyncio import run
from collections.abc import Callable

import pytest

from packages.llm.client import LLMClientError, LLMMetrics, MockLLMClient
from packages.qa.question_answering_service import (
    EmbeddingFailureError,
    LLMGenerationError,
    QAResponse,
    QuestionAnsweringService,
    UnknownExperimentError,
)
from packages.retrieval.service import RetrievalMetrics, RetrievalResult


class StubRetrievalService:
    def __init__(
        self,
        results: list[RetrievalResult],
        *,
        metrics: RetrievalMetrics | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.results = results
        self.failure = failure
        self.last_metrics = metrics or RetrievalMetrics(
            embedding_time_ms=4.0,
            vector_search_time_ms=6.0,
            retrieved_chunks=len(results),
            average_similarity=0.91 if results else 0.0,
        )
        self.calls: list[tuple[str, str, int]] = []

    async def search_by_experiment(
        self,
        experiment_id: uuid.UUID | str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        self.calls.append((str(experiment_id), query, top_k))
        if self.failure is not None:
            raise self.failure
        return self.results


def retrieval_result(
    *,
    experiment_id: str | None = None,
    document_name: str = "Launch Report",
    chunk_text: str = "Conversion increased after payment guardrails passed.",
    similarity: float = 0.91,
    metadata: dict[str, str] | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        experiment_id=experiment_id or str(uuid.uuid4()),
        experiment_name="Payment Recommendation Launch",
        document_id=str(uuid.uuid4()),
        document_name=document_name,
        chunk_text=chunk_text,
        similarity=similarity,
        metadata=metadata or {"section": "Results"},
    )


def experiment_exists(value: bool) -> Callable[[str], object]:
    async def lookup(_experiment_id: str) -> bool:
        return value

    return lookup


@pytest.mark.parametrize("top_k", [1, 3])
def test_question_answering_service_returns_grounded_answer_and_citations(top_k: int) -> None:
    experiment_id = str(uuid.uuid4())
    result = retrieval_result(experiment_id=experiment_id)
    retrieval = StubRetrievalService([result])
    llm = MockLLMClient(answer="The launch passed guardrails.", model="mock-answerer")
    service = QuestionAnsweringService(
        retrieval_service=retrieval,
        llm_client=llm,
        experiment_exists=experiment_exists(True),
    )

    answer = run(service.answer_question(
        question="Why was it launched?",
        experiment_id=experiment_id,
        top_k=top_k,
    ))

    assert answer.answer == "The launch passed guardrails."
    assert isinstance(answer, QAResponse)
    assert retrieval.calls == [(experiment_id, "Why was it launched?", top_k)]
    assert answer.citations[0].experiment_id == experiment_id
    assert answer.citations[0].document == "Launch Report"
    assert answer.citations[0].similarity == pytest.approx(0.91)
    assert answer.retrieved_chunks[0] == result
    assert answer.retrieved_chunks[0].chunk_text == result.chunk_text
    assert answer.retrieved_chunks[0].metadata == {"section": "Results"}
    assert answer.retrieval_metrics.retrieved_chunks == 1
    assert answer.llm_metrics.model == "mock-answerer"
    assert answer.llm_metrics.input_tokens > 0
    assert answer.llm_metrics.output_tokens > 0
    assert answer.llm_metrics.latency_ms >= 0.0
    assert "Only answer using retrieved context." in llm.last_system_instruction
    assert "Similarity: 0.9100" in llm.last_prompt
    assert "Metadata: {'section': 'Results'}" in llm.last_prompt


def test_question_answering_service_returns_no_context_answer_without_llm_call() -> None:
    experiment_id = str(uuid.uuid4())
    retrieval = StubRetrievalService([])
    llm = MockLLMClient(answer="This should not be used")
    service = QuestionAnsweringService(
        retrieval_service=retrieval,
        llm_client=llm,
        experiment_exists=experiment_exists(True),
    )

    answer = run(service.answer_question(
        question="What changed?",
        experiment_id=experiment_id,
        top_k=5,
    ))

    assert answer.answer == "Insufficient evidence exists to answer the question."
    assert isinstance(answer, QAResponse)
    assert answer.citations == []
    assert answer.retrieved_chunks == []
    assert answer.retrieval_metrics.retrieved_chunks == 0
    assert answer.llm_metrics.model == "mock"
    assert llm.calls == 0


def test_qa_response_serializes_shared_models() -> None:
    from packages.qa.question_answering_service import Citation

    result = retrieval_result()
    metrics = RetrievalMetrics(
        embedding_time_ms=1.0,
        vector_search_time_ms=2.0,
        retrieved_chunks=1,
        average_similarity=0.91,
    )

    response = QAResponse(
        answer="The answer.",
        citations=[
            Citation(
                experiment_id=result.experiment_id,
                document=result.document_name,
                similarity=result.similarity,
            )
        ],
        retrieved_chunks=[result],
        retrieval_metrics=metrics,
        llm_metrics=LLMMetrics(
            model="mock",
            input_tokens=10,
            output_tokens=2,
            latency_ms=0.5,
        ),
    )

    assert response.model_dump()["retrieved_chunks"][0]["chunk_text"] == result.chunk_text
    assert response.model_dump()["retrieval_metrics"]["retrieved_chunks"] == 1
    assert response.model_dump()["llm_metrics"]["model"] == "mock"


def test_question_answering_service_rejects_unknown_experiment() -> None:
    retrieval = StubRetrievalService([])
    service = QuestionAnsweringService(
        retrieval_service=retrieval,
        llm_client=MockLLMClient(answer="unused"),
        experiment_exists=experiment_exists(False),
    )

    with pytest.raises(UnknownExperimentError):
        run(service.answer_question(
            question="What happened?",
            experiment_id=str(uuid.uuid4()),
            top_k=5,
        ))


def test_question_answering_service_maps_embedding_failures() -> None:
    retrieval = StubRetrievalService([], failure=RuntimeError("embedding provider failed"))
    service = QuestionAnsweringService(
        retrieval_service=retrieval,
        llm_client=MockLLMClient(answer="unused"),
        experiment_exists=experiment_exists(True),
    )

    with pytest.raises(EmbeddingFailureError, match="embedding provider failed"):
        run(service.answer_question(
            question="What happened?",
            experiment_id=str(uuid.uuid4()),
            top_k=5,
        ))


def test_question_answering_service_maps_llm_failures() -> None:
    result = retrieval_result()
    retrieval = StubRetrievalService([result])
    service = QuestionAnsweringService(
        retrieval_service=retrieval,
        llm_client=MockLLMClient(answer="unused", failure=LLMClientError("rate limited")),
        experiment_exists=experiment_exists(True),
    )

    with pytest.raises(LLMGenerationError, match="rate limited"):
        run(service.answer_question(
            question="What happened?",
            experiment_id=result.experiment_id,
            top_k=5,
        ))


def test_prompt_templates_are_centralized_and_used_for_qa_prompt() -> None:
    from packages.llm.prompts import (
        DECISION_PROMPT,
        QA_PROMPT,
        SUMMARY_PROMPT,
        SYSTEM_PROMPT,
        build_grounded_prompt,
    )

    result = retrieval_result(
        chunk_text="The payment recommendation shipped after guardrails passed.",
        metadata={"section": "Decision"},
    )

    prompt = build_grounded_prompt(
        question="Why did it ship?",
        retrieved_chunks=[result],
    )

    assert "Only answer using retrieved context." in SYSTEM_PROMPT
    assert "{question}" in QA_PROMPT
    assert "{context}" in QA_PROMPT
    assert DECISION_PROMPT
    assert SUMMARY_PROMPT
    assert prompt.system_instruction == SYSTEM_PROMPT
    assert prompt.prompt == QA_PROMPT.format(
        question="Why did it ship?",
        context="\n\n".join(
            [
                "\n".join(
                    [
                        "Chunk 1",
                        f"Experiment ID: {result.experiment_id}",
                        f"Experiment: {result.experiment_name}",
                        f"Document: {result.document_name}",
                        f"Similarity: {result.similarity:.4f}",
                        f"Metadata: {result.metadata}",
                        "Text:",
                        result.chunk_text,
                    ]
                )
            ]
        ),
    )
