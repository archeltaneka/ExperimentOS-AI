from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from packages.evals.prompt_experiments.exposure import PromptExperimentExposureRecorder
from packages.evals.prompt_experiments.models import PromptExperimentContext
from packages.llm.client import LLMClient, LLMClientError, LLMMetrics
from packages.llm.prompts import GroundedPrompt, build_grounded_prompt
from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider
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
PromptBuilder = Callable[..., GroundedPrompt]


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
    prompt_id: str | None = None
    prompt_version: str | None = None

    model_config = ConfigDict(frozen=True)


QuestionAnsweringServiceResponse = QAResponse


class QuestionAnsweringService:
    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        llm_client: LLMClient,
        experiment_exists: ExperimentExists | None = None,
        prompt_builder: PromptBuilder = build_grounded_prompt,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.llm_client = llm_client
        self.experiment_exists = experiment_exists
        self.prompt_builder = prompt_builder
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int = 5,
        prompt_experiment_context: PromptExperimentContext | None = None,
        prompt_exposure_recorder: PromptExperimentExposureRecorder | None = None,
    ) -> QAResponse:
        normalized_question = question.strip()
        if not normalized_question:
            raise EmptyQuestionError("question must not be empty")

        if self.experiment_exists is not None and not await self.experiment_exists(
            str(experiment_id)
        ):
            raise UnknownExperimentError(f"experiment {experiment_id} was not found")

        parent_span = self.observability_provider.current_span()
        if parent_span is None:
            execution_id = str(uuid4())
            trace_span = self.observability_provider.start_root_span(
                "legacy_rag",
                trace_id=execution_id,
                inputs={
                    "question": normalized_question,
                    "experiment_id": str(experiment_id),
                    "top_k": top_k,
                },
                metadata={
                    "surface": "legacy_rag",
                    "workflow_mode": "legacy_rag",
                    "legacy_rag_execution_id": execution_id,
                    "execution_mode": "workflow",
                    "environment": os.environ.get("APP_ENV", "local"),
                    **_prompt_experiment_metadata(prompt_experiment_context),
                },
                tags=("legacy_rag",),
            )
        else:
            trace_span = self.observability_provider.start_span(
                "legacy_rag",
                inputs={
                    "question": normalized_question,
                    "experiment_id": str(experiment_id),
                    "top_k": top_k,
                },
                metadata={
                    "surface": "legacy_rag",
                    "workflow_mode": "legacy_rag",
                    "legacy_rag_execution_id": str(uuid4()),
                    "execution_mode": "workflow",
                    "environment": os.environ.get("APP_ENV", "local"),
                    **_prompt_experiment_metadata(prompt_experiment_context),
                },
                tags=("legacy_rag",),
            )
        with trace_span.activate():
            try:
                results = await self.retrieval_service.search_by_experiment(
                    experiment_id,
                    normalized_question,
                    top_k=top_k,
                )
            except Exception as exc:
                trace_span.record_error(exc, details={"stage": "retrieval"})
                trace_span.finish(outputs={"status": "failed"})
                raise EmbeddingFailureError(str(exc)) from exc

            retrieval_metrics = self._resolve_retrieval_metrics(
                self.retrieval_service.last_metrics,
                retrieved_chunks=len(results),
            )
            trace_span.add_metadata(
                {
                    "retrieved_chunks": len(results),
                    "embedding_time_ms": retrieval_metrics.embedding_time_ms,
                    "vector_search_time_ms": retrieval_metrics.vector_search_time_ms,
                }
            )
            if not results:
                trace_span.finish(
                    outputs={
                        "status": "completed",
                        "answer": INSUFFICIENT_EVIDENCE_ANSWER,
                        "citation_count": 0,
                    }
                )
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

            prompt_span = self.observability_provider.start_span(
                "prompt_rendering",
                metadata={
                    "surface": "legacy_rag",
                    "workflow_mode": "legacy_rag",
                    "execution_mode": "workflow",
                    **_prompt_experiment_metadata(prompt_experiment_context),
                },
            )
            with prompt_span.activate():
                prompt = self.prompt_builder(
                    question=normalized_question,
                    retrieved_chunks=results,
                    experiment_context=prompt_experiment_context,
                    exposure_recorder=prompt_exposure_recorder,
                    trace_id=trace_span.record.trace_id or "",
                    execution_mode="workflow",
                )
                prompt_span.add_metadata(
                    {
                        "prompt_id": prompt.prompt_id,
                        "prompt_version": prompt.version,
                        "input_variables": ["question", "context"],
                        "rendered_prompt_length": (
                            len(prompt.prompt) + len(prompt.system_instruction)
                        ),
                        "provider_model": str(getattr(self.llm_client, "model", "unknown")),
                        **_prompt_experiment_metadata(prompt_experiment_context),
                    }
                )
                prompt_span.finish(outputs={"status": "completed"})
            generation_span = self.observability_provider.start_span(
                "llm_generation",
                run_type="llm",
                metadata={
                    "surface": "legacy_rag",
                    "workflow_mode": "legacy_rag",
                    "execution_mode": "workflow",
                    "provider_model": str(getattr(self.llm_client, "model", "unknown")),
                    **_prompt_experiment_metadata(prompt_experiment_context),
                },
            )
            with generation_span.activate():
                try:
                    llm_response = await self.llm_client.generate(
                        prompt=prompt.prompt,
                        system_instruction=prompt.system_instruction,
                    )
                except LLMClientError as exc:
                    generation_span.record_error(exc, details={"stage": "llm_generation"})
                    generation_span.finish(outputs={"status": "failed"})
                    trace_span.record_error(exc, details={"stage": "llm_generation"})
                    trace_span.finish(outputs={"status": "failed"})
                    raise LLMGenerationError(str(exc)) from exc
                except Exception as exc:
                    generation_span.record_error(exc, details={"stage": "llm_generation"})
                    generation_span.finish(outputs={"status": "failed"})
                    trace_span.record_error(exc, details={"stage": "llm_generation"})
                    trace_span.finish(outputs={"status": "failed"})
                    raise LLMGenerationError(str(exc)) from exc
                generation_span.finish(
                    outputs={
                        "status": "completed",
                        "model": llm_response.metrics.model,
                        "input_tokens": llm_response.metrics.input_tokens,
                        "output_tokens": llm_response.metrics.output_tokens,
                        "latency_ms": llm_response.metrics.latency_ms,
                    }
                )
                generation_span.add_metadata(
                    {
                        "provider": self.llm_client.__class__.__name__,
                        "model": llm_response.metrics.model,
                        "operation_type": "answer_generation",
                        "prompt_id": prompt.prompt_id,
                        "prompt_version": prompt.version,
                        "input_length": len(prompt.prompt) + len(prompt.system_instruction),
                        "output_length": len(llm_response.answer),
                    }
                )

            response = QAResponse(
                answer=llm_response.answer,
                citations=self._build_citations(results),
                retrieved_chunks=results,
                retrieval_metrics=retrieval_metrics,
                llm_metrics=llm_response.metrics,
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
            )
            trace_span.finish(
                outputs={
                    "status": "completed",
                    "answer": response.answer,
                    "citation_count": len(response.citations),
                    "prompt_id": response.prompt_id or "",
                    "prompt_version": response.prompt_version or "",
                }
            )
            return response

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


def _prompt_experiment_metadata(
    context: PromptExperimentContext | None,
) -> dict[str, object]:
    if context is None:
        return {}
    return {
        "experiment_id": context.experiment_id,
        "experiment_variant": context.variant,
        "prompt_id": context.prompt_id,
        "prompt_version": context.prompt_version,
        "assignment_strategy": context.assignment_strategy,
    }
