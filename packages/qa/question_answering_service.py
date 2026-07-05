from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict

from packages.llm.client import LLMClient, LLMClientError, LLMMetrics
from packages.llm.prompts import build_grounded_prompt
from packages.retrieval.service import RetrievalMetrics, RetrievalResult, RetrievalService

INSUFFICIENT_EVIDENCE_ANSWER = "Insufficient evidence exists to answer the question."


class QuestionAnsweringServiceError(RuntimeError):
    pass


class EmptyQuestionError(QuestionAnsweringServiceError):
    pass


class UnknownExperimentError(QuestionAnsweringServiceError):
    pass


class EmbeddingFailureError(QuestionAnsweringServiceError):
    pass


class LLMGenerationError(QuestionAnsweringServiceError):
    pass


ExperimentExists = Callable[[str], Awaitable[bool]]


class Citation(BaseModel):
    experiment_id: str
    document: str
    similarity: float

    model_config = ConfigDict(frozen=True)


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievalResult]
    retrieval_metrics: RetrievalMetrics
    llm_metrics: LLMMetrics

    model_config = ConfigDict(frozen=True)


QuestionAnsweringServiceResponse = QAResponse


class QuestionAnsweringService:
    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        llm_client: LLMClient,
        experiment_exists: ExperimentExists | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.llm_client = llm_client
        self.experiment_exists = experiment_exists

    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int = 5,
    ) -> QAResponse:
        normalized_question = question.strip()
        if not normalized_question:
            raise EmptyQuestionError("question must not be empty")

        if self.experiment_exists is not None and not await self.experiment_exists(
            str(experiment_id)
        ):
            raise UnknownExperimentError(f"experiment {experiment_id} was not found")

        try:
            results = await self.retrieval_service.search_by_experiment(
                experiment_id,
                normalized_question,
                top_k=top_k,
            )
        except Exception as exc:
            raise EmbeddingFailureError(str(exc)) from exc

        retrieval_metrics = self._resolve_retrieval_metrics(
            self.retrieval_service.last_metrics,
            retrieved_chunks=len(results),
        )
        if not results:
            return QAResponse(
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                citations=[],
                retrieved_chunks=[],
                retrieval_metrics=retrieval_metrics,
                llm_metrics=LLMMetrics(
                    model="mock",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=0.0,
                ),
            )

        prompt = build_grounded_prompt(question=normalized_question, retrieved_chunks=results)
        try:
            llm_response = await self.llm_client.generate(
                prompt=prompt.prompt,
                system_instruction=prompt.system_instruction,
            )
        except LLMClientError as exc:
            raise LLMGenerationError(str(exc)) from exc
        except Exception as exc:
            raise LLMGenerationError(str(exc)) from exc

        return QAResponse(
            answer=llm_response.answer,
            citations=self._build_citations(results),
            retrieved_chunks=results,
            retrieval_metrics=retrieval_metrics,
            llm_metrics=llm_response.metrics,
        )

    def _build_citations(self, results: list[RetrievalResult]) -> list[Citation]:
        return [
            Citation(
                experiment_id=result.experiment_id,
                document=result.document_name,
                similarity=result.similarity,
            )
            for result in results
        ]

    def _resolve_retrieval_metrics(
        self,
        metrics: RetrievalMetrics | None,
        *,
        retrieved_chunks: int,
    ) -> RetrievalMetrics:
        if metrics is None:
            return RetrievalMetrics(
                embedding_time_ms=0.0,
                vector_search_time_ms=0.0,
                retrieved_chunks=retrieved_chunks,
                average_similarity=0.0,
            )
        return metrics
