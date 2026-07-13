from __future__ import annotations

import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
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
    ExperimentExistsDependency,
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
from packages.observability.base import BaseObservabilityProvider
from packages.observability.factory import resolve_observability_provider
from packages.qa.question_answering_service import (
    EmbeddingFailureError,
    EmptyQuestionError,
    LLMGenerationError,
    QAResponse,
    QuestionAnsweringService,
    UnknownExperimentError,
)
from packages.retrieval.service import RetrievalService

if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_environment()

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    get_observability_provider().instrument_fastapi_app(app)
    yield


app = FastAPI(title="ExperimentOS AI API", version="0.1.0", lifespan=app_lifespan)


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
    def __init__(self, observability_provider: BaseObservabilityProvider) -> None:
        self.observability_provider = observability_provider

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
                observability_provider=self.observability_provider,
            )

            service = QuestionAnsweringService(
                retrieval_service=retrieval_service,
                llm_client=get_llm_client(),
                experiment_exists=experiment_exists,
                observability_provider=self.observability_provider,
            )
            return await service.answer_question(
                question=question,
                experiment_id=experiment_id,
                top_k=top_k,
            )


@lru_cache(maxsize=1)
def get_observability_provider() -> BaseObservabilityProvider:
    return resolve_observability_provider()


def get_question_answering_service(
    observability_provider: Annotated[
        BaseObservabilityProvider,
        Depends(get_observability_provider),
    ],
) -> QuestionAnsweringDependency:
    return DatabaseQuestionAnsweringService(observability_provider)


def get_agent_workflow_service(
    observability_provider: Annotated[
        BaseObservabilityProvider,
        Depends(get_observability_provider),
    ],
) -> AgentWorkflowService:
    return AgentWorkflowService(observability_provider=observability_provider)


def get_experiment_exists_dependency() -> ExperimentExistsDependency:
    return experiment_exists


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


def get_ask_service(
    workflow_service: Annotated[
        AgentWorkflowService,
        Depends(get_agent_workflow_service),
    ],
    qa_service: Annotated[
        QuestionAnsweringDependency,
        Depends(get_question_answering_service),
    ],
    experiment_exists_dependency: Annotated[
        ExperimentExistsDependency,
        Depends(get_experiment_exists_dependency),
    ],
    observability_provider: Annotated[
        BaseObservabilityProvider,
        Depends(get_observability_provider),
    ],
) -> AskService:
    if get_ask_mode() == "legacy_rag":
        return LegacyRagAskService(
            qa_service,
            observability_provider=observability_provider,
        )
    return AgentWorkflowAskService(
        workflow_service,
        experiment_exists=experiment_exists_dependency,
        observability_provider=observability_provider,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "experimentos-api"}


@app.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    service: Annotated[AskService, Depends(get_ask_service)],
    observability_provider: Annotated[
        BaseObservabilityProvider,
        Depends(get_observability_provider),
    ],
) -> AskResponse:
    ask_mode = get_ask_mode()
    request_id = str(uuid.uuid4())
    root_span = observability_provider.start_root_span(
        "ask_request",
        trace_id=request_id,
        inputs={
            "question": request.question,
            "experiment_id": request.experiment_id,
            "top_k": request.top_k,
        },
        metadata={
            "surface": "ask",
            "endpoint": "/ask",
            "ask_mode": ask_mode,
            "request_id": request_id,
            "execution_mode": "api",
            "environment": os.environ.get("APP_ENV", "local"),
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
        tags=("ask", ask_mode),
    )
    with root_span.activate():
        try:
            response = await service.answer(request)
            root_span.add_metadata(
                {
                    "citation_count": len(response.citations),
                    "approval_status": response.approval_status or "",
                    "intent": response.intent or "",
                }
            )
            root_span.finish(
                outputs={
                    "status_code": 200,
                    "success": True,
                    "answer": response.answer,
                }
            )
            return response
        except EmptyQuestionError as exc:
            root_span.record_error(exc, details={"status_code": status.HTTP_400_BAD_REQUEST})
            root_span.finish(outputs={"status_code": status.HTTP_400_BAD_REQUEST})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except UnknownExperimentError as exc:
            root_span.record_error(exc, details={"status_code": status.HTTP_404_NOT_FOUND})
            root_span.finish(outputs={"status_code": status.HTTP_404_NOT_FOUND})
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except (EmbeddingFailureError, LLMGenerationError, AgentWorkflowExecutionError) as exc:
            root_span.record_error(exc, details={"status_code": status.HTTP_502_BAD_GATEWAY})
            root_span.finish(outputs={"status_code": status.HTTP_502_BAD_GATEWAY})
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
