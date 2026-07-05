from __future__ import annotations

from dataclasses import dataclass

from packages.retrieval.service import RetrievalResult

SYSTEM_INSTRUCTION = (
    "Only answer using retrieved context.\n"
    "If the answer cannot be supported by retrieved evidence, say that insufficient evidence "
    "exists.\n"
    "Never invent facts."
)


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
    prompt = "\n\n".join(
        [
            f"User Question: {question.strip()}",
            "Retrieved Context:",
            "\n\n".join(context_blocks),
            "Answer using only the retrieved context and cite the supporting documents.",
        ]
    )
    return GroundedPrompt(system_instruction=SYSTEM_INSTRUCTION, prompt=prompt)
