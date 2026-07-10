from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from packages.evals.dataset import EvaluationQuestion
from packages.evals.metrics import EvaluationSummary, SampleMetrics, calculate_sample_metrics
from packages.qa.question_answering_service import QAResponse


class QuestionAnsweringServiceLike(Protocol):
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int = 5,
    ) -> QAResponse:
        pass


@dataclass(frozen=True)
class EvaluationSampleResult:
    question: EvaluationQuestion
    answer: str
    metrics: SampleMetrics | None
    retrieved_documents: tuple[str, ...]
    retrieved_contexts: tuple[str, ...]
    error: str | None
    prompt_id: str | None = None
    prompt_version: str | None = None
    citations: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class EvaluationRun:
    samples: list[EvaluationSampleResult]
    summary: EvaluationSummary
    embedding_provider: str = ""
    embedding_model: str = ""
    llm_provider: str = ""
    llm_model: str = ""


class OfflineEvaluator:
    def __init__(
        self,
        *,
        qa_service: QuestionAnsweringServiceLike,
        questions: Iterable[EvaluationQuestion],
        top_k: int = 5,
        experiment_id_resolver: Callable[[EvaluationQuestion], str] | None = None,
        input_cost_per_1k_tokens: float = 0.0,
        output_cost_per_1k_tokens: float = 0.0,
        embedding_provider: str = "",
        embedding_model: str = "",
        llm_provider: str = "",
        llm_model: str = "",
    ) -> None:
        self.qa_service = qa_service
        self.questions = list(questions)
        self.top_k = top_k
        self.experiment_id_resolver = experiment_id_resolver
        self.input_cost_per_1k_tokens = input_cost_per_1k_tokens
        self.output_cost_per_1k_tokens = output_cost_per_1k_tokens
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        self.llm_provider = llm_provider
        self.llm_model = llm_model

    async def evaluate(self) -> EvaluationRun:
        samples: list[EvaluationSampleResult] = []
        for question in self.questions:
            try:
                service_experiment_id = (
                    self.experiment_id_resolver(question)
                    if self.experiment_id_resolver is not None
                    else question.experiment_id
                )
                response = await self.qa_service.answer_question(
                    question=question.question,
                    experiment_id=service_experiment_id,
                    top_k=self.top_k,
                )
                metrics = calculate_sample_metrics(
                    question,
                    response,
                    input_cost_per_1k_tokens=self.input_cost_per_1k_tokens,
                    output_cost_per_1k_tokens=self.output_cost_per_1k_tokens,
                )
                samples.append(
                    EvaluationSampleResult(
                        question=question,
                        answer=response.answer,
                        metrics=metrics,
                        retrieved_documents=tuple(
                            dict.fromkeys(
                                chunk.document_name for chunk in response.retrieved_chunks
                            )
                        ),
                        retrieved_contexts=tuple(
                            chunk.chunk_text for chunk in response.retrieved_chunks
                        ),
                        error=None,
                        prompt_id=response.prompt_id,
                        prompt_version=response.prompt_version,
                        citations=tuple(
                            {
                                "experiment_id": citation.experiment_id,
                                "document": citation.document,
                                "similarity": citation.similarity,
                            }
                            for citation in response.citations
                        ),
                    )
                )
            except Exception as exc:
                samples.append(
                    EvaluationSampleResult(
                        question=question,
                        answer="",
                        metrics=None,
                        retrieved_documents=(),
                        retrieved_contexts=(),
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        return EvaluationRun(
            samples=samples,
            summary=EvaluationSummary.from_samples(
                [sample.metrics for sample in samples if sample.metrics is not None]
            ),
            embedding_provider=self.embedding_provider,
            embedding_model=self.embedding_model,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
        )
