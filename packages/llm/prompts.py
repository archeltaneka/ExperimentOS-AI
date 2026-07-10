from __future__ import annotations

from dataclasses import dataclass

from packages.llm.prompt_registry import PromptRegistry, get_prompt_registry
from packages.retrieval.service import RetrievalResult

_PROMPT_REGISTRY = get_prompt_registry()
_RAG_ANSWER_DEFINITION = _PROMPT_REGISTRY.get_active("rag.answer")
_RAG_DECISION_DEFINITION = _PROMPT_REGISTRY.get_active("rag.decision")
_RAG_SUMMARY_DEFINITION = _PROMPT_REGISTRY.get_active("rag.summary")

SYSTEM_PROMPT = _RAG_ANSWER_DEFINITION.system_template
QA_PROMPT = _RAG_ANSWER_DEFINITION.user_template
DECISION_PROMPT = _RAG_DECISION_DEFINITION.user_template
SUMMARY_PROMPT = _RAG_SUMMARY_DEFINITION.user_template

# Backward-compatible alias for existing imports while new code uses SYSTEM_PROMPT.
SYSTEM_INSTRUCTION = SYSTEM_PROMPT


@dataclass(frozen=True)
class GroundedPrompt:
    system_instruction: str
    prompt: str
    prompt_id: str
    version: str


def build_grounded_prompt(
    *,
    question: str,
    retrieved_chunks: list[RetrievalResult],
    version: str | None = None,
    registry: PromptRegistry | None = None,
    prompt_id: str = "rag.answer",
) -> GroundedPrompt:
    prompt_registry = registry or _PROMPT_REGISTRY
    context_blocks = [
        "\n".join(
            [
                f"Chunk {index}",
                f"Experiment ID: {chunk.experiment_id}",
                f"Experiment: {chunk.experiment_name}",
                f"Document: {chunk.document_name}",
                f"Similarity: {chunk.similarity:.4f}",
                f"Metadata: {chunk.metadata}",
                "Text:",
                chunk.chunk_text,
            ]
        )
        for index, chunk in enumerate(retrieved_chunks, start=1)
    ]
    rendered = prompt_registry.render(
        prompt_id,
        {
            "question": question.strip(),
            "context": "\n\n".join(context_blocks),
        },
        version=version,
    )
    return GroundedPrompt(
        system_instruction=rendered.system_prompt,
        prompt=rendered.user_prompt,
        prompt_id=rendered.prompt_id,
        version=rendered.version,
    )
