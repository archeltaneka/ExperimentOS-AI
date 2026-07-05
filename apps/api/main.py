from __future__ import annotations

import os
import uuid
from functools import lru_cache
from typing import Annotated, Any, Protocol

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from packages.db.models import Experiment
from packages.db.session import create_async_session_factory, create_database_engine
from packages.ingestion.embeddings import build_embedding_provider
from packages.llm.client import LLMClient, MockLLMClient, OpenAILLMClient
from packages.qa.question_answering_service import (
    EmbeddingFailureError,
    EmptyQuestionError,
    LLMGenerationError,
    QuestionAnsweringService,
    QuestionAnsweringServiceResponse,
    UnknownExperimentError,
)
from packages.retrieval.service import RetrievalService

load_dotenv()

app = FastAPI(title="ExperimentOS AI API", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be empty")
        return value


class CitationResponse(BaseModel):
    experiment_id: str
    document: str
    similarity: float

    model_config = ConfigDict(from_attributes=True)


class RetrievedChunkResponse(BaseModel):
    experiment_id: str
    experiment_name: str
    document: str
    text: str
    similarity: float
    metadata: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class LLMMetricsResponse(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float

    model_config = ConfigDict(from_attributes=True)


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    retrieved_chunks: list[RetrievedChunkResponse]
    retrieval_metrics: dict[str, float | int]
    llm_metrics: LLMMetricsResponse


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker:
    engine = create_database_engine()
    return create_async_session_factory(engine)


def get_llm_client() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "auto").lower()
    if provider == "mock":
        return MockLLMClient()
    if provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
        return OpenAILLMClient(model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    return MockLLMClient()


def get_embedding_provider_name() -> str:
    return os.environ.get("EMBEDDING_PROVIDER", "auto").lower()


class QuestionAnsweringDependency(Protocol):
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QuestionAnsweringServiceResponse:
        pass


class DatabaseQuestionAnsweringService:
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QuestionAnsweringServiceResponse:
        session_factory = get_session_factory()
        async with session_factory() as session:
            retrieval_service = RetrievalService(
                session,
                build_embedding_provider(get_embedding_provider_name()),
            )

            async def experiment_exists(candidate_experiment_id: str) -> bool:
                try:
                    parsed_experiment_id = uuid.UUID(str(candidate_experiment_id))
                except ValueError:
                    return False
                result = await session.execute(
                    select(Experiment.id).where(Experiment.id == parsed_experiment_id)
                )
                return result.scalar_one_or_none() is not None

            service = QuestionAnsweringService(
                retrieval_service=retrieval_service,
                llm_client=get_llm_client(),
                experiment_exists=experiment_exists,
            )
            return await service.answer_question(
                question=question,
                experiment_id=experiment_id,
                top_k=top_k,
            )


def get_question_answering_service() -> QuestionAnsweringDependency:
    return DatabaseQuestionAnsweringService()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "experimentos-api"}


@app.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    service: Annotated[QuestionAnsweringDependency, Depends(get_question_answering_service)],
) -> AskResponse:
    try:
        response = await service.answer_question(
            question=request.question,
            experiment_id=request.experiment_id,
            top_k=request.top_k,
        )
    except EmptyQuestionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UnknownExperimentError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmbeddingFailureError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except LLMGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return serialize_ask_response(response)


def serialize_ask_response(response: QuestionAnsweringServiceResponse) -> AskResponse:
    return AskResponse(
        answer=response.answer,
        citations=[CitationResponse.model_validate(citation) for citation in response.citations],
        retrieved_chunks=[
            RetrievedChunkResponse.model_validate(chunk) for chunk in response.retrieved_chunks
        ],
        retrieval_metrics=response.retrieval_metrics,
        llm_metrics=LLMMetricsResponse.model_validate(response.llm_metrics),
    )
