from __future__ import annotations

from packages.agents.nodes import RetrievalAgentLike
from packages.agents.retrieval_agent import RetrievalAgent
from packages.agents.state import AgentState
from packages.agents.workflow import build_agent_workflow


class AgentWorkflowInputError(ValueError):
    pass


class AgentWorkflowService:
    def __init__(self, retrieval_agent: RetrievalAgentLike | None = None) -> None:
        if retrieval_agent is None:
            retrieval_agent = RetrievalAgent()
        self.workflow = build_agent_workflow(
            retrieval_agent=retrieval_agent
        )

    def run(self, question: str) -> AgentState:
        normalized_question = question.strip()
        if not normalized_question:
            raise AgentWorkflowInputError("question must not be empty")
        return self.workflow.invoke({"question": normalized_question})
