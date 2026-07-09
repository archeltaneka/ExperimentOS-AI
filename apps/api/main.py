from __future__ import annotations

import os
import uuid
from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from apps.api.ask_service import (
    AgentWorkflowAskService,
    AgentWorkflowExecutionError,
    AskRequest,
    AskResponse,
    AskService,
    LegacyRagAskService,
    get_ask_mode,
)
from packages.agents.service import AgentWorkflowService
from packages.config.env import load_environment
from packages.db.models import Experiment
from packages.db.session import create_async_session_factory, create_database_engine
from packages.ingestion.embeddings import build_embedding_provider
from packages.llm.client import (
    GeminiLLMClient,
    LLMClient,
    MockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
)
from packages.qa.question_answering_service import (
    EmbeddingFailureError,
    EmptyQuestionError,
    LLMGenerationError,
    QAResponse,
    QuestionAnsweringService,
    UnknownExperimentError,
)
from packages.retrieval.service import RetrievalService

load_environment()

app = FastAPI(title="ExperimentOS AI API", version="0.1.0")


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker:
    load_environment()
    engine = create_database_engine()
    return create_async_session_factory(engine)


def get_llm_client() -> LLMClient:
    load_environment()
    provider = os.environ.get("LLM_PROVIDER", "auto").lower()
    if provider == "mock":
        return MockLLMClient()
    if provider == "ollama":
        return OllamaLLMClient(model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"))
    if provider == "gemini":
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is required for the gemini LLM provider")
        return GeminiLLMClient(model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"))
    if provider == "auto" and os.environ.get("GEMINI_API_KEY"):
        return GeminiLLMClient(model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"))
    if provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
        return OpenAILLMClient(model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    return MockLLMClient()


def get_embedding_provider_name() -> str:
    load_environment()
    return os.environ.get("EMBEDDING_PROVIDER", "auto").lower()


class QuestionAnsweringDependency(Protocol):
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QAResponse:
        pass


class DatabaseQuestionAnsweringService:
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QAResponse:
        session_factory = get_session_factory()
        async with session_factory() as session:
            retrieval_service = RetrievalService(
                session,
                build_embedding_provider(get_embedding_provider_name()),
            )

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


async def experiment_exists(candidate_experiment_id: str) -> bool:
    try:
        parsed_experiment_id = uuid.UUID(str(candidate_experiment_id))
    except ValueError:
        return False

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(Experiment.id).where(Experiment.id == parsed_experiment_id)
        )
        return result.scalar_one_or_none() is not None


def get_ask_service() -> AskService:
    if get_ask_mode() == "legacy_rag":
        return LegacyRagAskService(get_question_answering_service())
    return AgentWorkflowAskService(
        AgentWorkflowService(),
        experiment_exists=experiment_exists,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "experimentos-api"}


@app.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    service: Annotated[AskService, Depends(get_ask_service)],
) -> AskResponse:
    try:
        return await service.answer(request)
    except EmptyQuestionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UnknownExperimentError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (EmbeddingFailureError, LLMGenerationError, AgentWorkflowExecutionError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
