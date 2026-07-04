from packages.db.models import EMBEDDING_DIMENSION
from packages.ingestion.chunking import chunk_markdown_report
from packages.ingestion.embeddings import FakeEmbeddingProvider


def test_markdown_report_is_split_into_multiple_section_chunks() -> None:
    report = "\n\n".join(
        [
            "# Experiment Report",
            "## Background\n" + "Background context sentence. " * 120,
            "## Results\n" + "Results sentence with metric detail. " * 120,
            "## Risks\n" + "Risk sentence with caveat detail. " * 80,
            "## Recommendation\n" + "Recommendation sentence. " * 80,
        ]
    )

    chunks = chunk_markdown_report(report, target_chunk_chars=900, overlap_chars=120)

    assert len(chunks) > 1
    assert {chunk.metadata["section"] for chunk in chunks} >= {
        "Background",
        "Results",
        "Risks",
        "Recommendation",
    }
    assert all(chunk.text.strip() for chunk in chunks)
    assert all(chunk.metadata["chunk_index"] == index for index, chunk in enumerate(chunks))


def test_fake_embedding_provider_is_deterministic_and_uses_configured_dimension() -> None:
    provider = FakeEmbeddingProvider(dimension=EMBEDDING_DIMENSION)

    first = provider.embed_texts(["same text"])[0]
    second = provider.embed_texts(["same text"])[0]
    different = provider.embed_texts(["different text"])[0]

    assert first == second
    assert first != different
    assert len(first) == EMBEDDING_DIMENSION
    assert all(-1.0 <= value <= 1.0 for value in first)
