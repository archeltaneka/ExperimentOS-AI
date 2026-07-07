from __future__ import annotations

from packages.agents.retrieval_agent import RetrievalAgent
from packages.agents.state import AgentState
from packages.agents.workflow import build_agent_workflow


class AgentWorkflowInputError(ValueError):
    pass


class AgentWorkflowService:
    def __init__(self, retrieval_agent: RetrievalAgent | None = None) -> None:
        self.workflow = build_agent_workflow(
            retrieval_agent=retrieval_agent or RetrievalAgent()
        )

    def run(self, question: str) -> AgentState:
        normalized_question = question.strip()
        if not normalized_question:
            raise AgentWorkflowInputError("question must not be empty")
        return self.workflow.invoke({"question": normalized_question})
