from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from packages.agents.service import AgentWorkflowService
from packages.agents.state import AgentState
from packages.config.env import resolve_setting
from packages.qa.question_answering_service import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    QAResponse,
    UnknownExperimentError,
)


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


class AskResponse(BaseModel):
    answer: str
    citations: list[dict[str, object]]
    retrieved_chunks: list[dict[str, object]]
    retrieval_metrics: dict[str, object]
    llm_metrics: dict[str, object]
    prompt_metadata: dict[str, str] | None = None
    intent: str | None = None
    required_agents: list[str] = Field(default_factory=list)
    decision: dict[str, object] | None = None
    executive_summary: dict[str, object] | None = None
    agent_trace: list[dict[str, object]] = Field(default_factory=list)
    agent_metrics: dict[str, object] = Field(default_factory=dict)
    approval_status: str | None = None


class AskService(Protocol):
    async def answer(self, request: AskRequest) -> AskResponse:
        raise NotImplementedError


class QuestionAnsweringDependency(Protocol):
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int,
    ) -> QAResponse:
        raise NotImplementedError


class ExperimentExistsDependency(Protocol):
    async def __call__(self, experiment_id: str) -> bool:
        raise NotImplementedError


class AgentWorkflowExecutionError(RuntimeError):
    pass


class LegacyRagAskService:
    def __init__(self, qa_service: QuestionAnsweringDependency) -> None:
        self.qa_service = qa_service

    async def answer(self, request: AskRequest) -> AskResponse:
        qa_response = await self.qa_service.answer_question(
            question=request.question,
            experiment_id=request.experiment_id,
            top_k=request.top_k,
        )
        return AskResponse(
            answer=qa_response.answer,
            citations=[citation.model_dump() for citation in qa_response.citations],
            retrieved_chunks=[asdict(chunk) for chunk in qa_response.retrieved_chunks],
            retrieval_metrics=asdict(qa_response.retrieval_metrics),
            llm_metrics=vars(qa_response.llm_metrics),
            prompt_metadata=_build_prompt_metadata(
                qa_response.prompt_id,
                qa_response.prompt_version,
            ),
            intent=None,
            required_agents=[],
            decision=None,
            executive_summary=None,
            agent_trace=[],
            agent_metrics={},
            approval_status=None,
        )


class AgentWorkflowAskService:
    def __init__(
        self,
        workflow_service: AgentWorkflowService,
        *,
        experiment_exists: ExperimentExistsDependency | None = None,
    ) -> None:
        self.workflow_service = workflow_service
        self.experiment_exists = experiment_exists

    async def answer(self, request: AskRequest) -> AskResponse:
        if self.experiment_exists is not None and not await self.experiment_exists(
            request.experiment_id
        ):
            raise UnknownExperimentError(f"experiment {request.experiment_id} was not found")
        try:
            state = await asyncio.to_thread(
                self.workflow_service.run,
                request.question,
                experiment_id=request.experiment_id,
                top_k=request.top_k,
            )
        except Exception as exc:
            raise AgentWorkflowExecutionError(str(exc)) from exc
        return map_agent_state_to_ask_response(state)


def get_ask_mode() -> str:
    return resolve_setting(
        None,
        env_var="ASK_MODE",
        default="agent_workflow",
        lowercase=True,
    )


def map_agent_state_to_ask_response(state: AgentState) -> AskResponse:
    answer = _resolve_agent_answer(state)
    retrieval_metrics = dict(state["metrics"].get("retrieval", {}))
    llm_metrics = {
        "model": "agent-workflow",
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": 0.0,
    }
    return AskResponse(
        answer=answer,
        citations=[dict(citation) for citation in state["citations"]],
        retrieved_chunks=[
            {
                "experiment_id": chunk.get("experiment_id", ""),
                "metadata": chunk.get("metadata", {}),
                "experiment_name": state["experiment_analysis"].get("experiment_name", ""),
                "document_id": chunk.get("document_id", ""),
                "document_name": str(chunk.get("metadata", {}).get("document_name", "")),
                "chunk_text": chunk.get("content", ""),
                "similarity": chunk.get("score", 0.0),
            }
            for chunk in state["retrieved_chunks"]
        ],
        retrieval_metrics={
            "embedding_time_ms": retrieval_metrics.get("embedding_time_ms", 0.0),
            "vector_search_time_ms": retrieval_metrics.get("vector_search_time_ms", 0.0),
            "retrieved_chunks": retrieval_metrics.get("retrieved_chunks", 0),
            "average_similarity": retrieval_metrics.get("average_similarity", 0.0),
        },
        llm_metrics=llm_metrics,
        prompt_metadata=None,
        intent=state["intent"],
        required_agents=list(state["required_agents"]),
        decision=dict(state["decision"]),
        executive_summary=dict(state["executive_summary"]),
        agent_trace=[dict(entry) for entry in state["trace"]],
        agent_metrics=dict(state["metrics"]),
        approval_status=state["human_approval"]["status"],
    )


def _resolve_agent_answer(state: AgentState) -> str:
    candidate_answers = (
        state["executive_summary"]["summary"],
        state["decision"]["rationale"],
        state["experiment_analysis"]["summary"],
        state["business_impact"]["summary"],
        state["retrieved_chunks"][0]["content"] if state["retrieved_chunks"] else "",
    )
    for answer in candidate_answers:
        if str(answer).strip():
            return str(answer)
    return INSUFFICIENT_EVIDENCE_ANSWER


def _build_prompt_metadata(
    prompt_id: str | None,
    prompt_version: str | None,
) -> dict[str, str] | None:
    if prompt_id is None or prompt_version is None:
        return None
    return {
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
    }
