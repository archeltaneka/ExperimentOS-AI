from __future__ import annotations

from dataclasses import dataclass

from packages.retrieval.service import RetrievalResult

SYSTEM_PROMPT = (
    "Only answer using retrieved context.\n"
    "If the answer cannot be supported by retrieved evidence, say that insufficient evidence "
    "exists.\n"
    "Never invent facts."
)

QA_PROMPT = "\n\n".join(
    [
        "User Question: {question}",
        "Retrieved Context:",
        "{context}",
        "Answer using only the retrieved context and cite the supporting documents.",
    ]
)

DECISION_PROMPT = "\n\n".join(
    [
        "Decision Question: {question}",
        "Evidence:",
        "{context}",
        "Summarize the decision, supporting evidence, and any unresolved uncertainty.",
    ]
)

SUMMARY_PROMPT = "\n\n".join(
    [
        "Summary Request: {question}",
        "Source Context:",
        "{context}",
        "Produce a concise summary grounded only in the source context.",
    ]
)

# Backward-compatible alias for existing imports while new code uses SYSTEM_PROMPT.
SYSTEM_INSTRUCTION = SYSTEM_PROMPT


@dataclass(frozen=True)
class GroundedPrompt:
    system_instruction: str
    prompt: str


def build_grounded_prompt(
    *,
    question: str,
    retrieved_chunks: list[RetrievalResult],
) -> GroundedPrompt:
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
    prompt = QA_PROMPT.format(
        question=question.strip(),
        context="\n\n".join(context_blocks),
    )
    return GroundedPrompt(system_instruction=SYSTEM_PROMPT, prompt=prompt)
