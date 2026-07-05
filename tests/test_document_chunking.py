from packages.db.models import EMBEDDING_DIMENSION
from packages.ingestion.chunking import chunk_markdown_report
from packages.ingestion.embeddings import (
    BGE_SMALL_EN_MODEL,
    FakeEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
    build_embedding_provider,
)


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


class StubSentenceTransformer:
    def __init__(self) -> None:
        self.model_name = None
        self.encode_calls = []

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool,
        convert_to_numpy: bool,
        show_progress_bar: bool,
    ) -> list[list[float]]:
        self.encode_calls.append(
            {
                "texts": texts,
                "normalize_embeddings": normalize_embeddings,
                "convert_to_numpy": convert_to_numpy,
                "show_progress_bar": show_progress_bar,
            }
        )
        return [[0.6, 0.8], [1.0, 0.0]]


def test_huggingface_embedding_provider_normalizes_and_pads_to_configured_dimension() -> None:
    model = StubSentenceTransformer()
    provider = HuggingFaceEmbeddingProvider(model=model, dimension=4)

    embeddings = provider.embed_texts(["first", "second"])

    assert provider.model_name == BGE_SMALL_EN_MODEL
    assert model.encode_calls == [
        {
            "texts": ["first", "second"],
            "normalize_embeddings": True,
            "convert_to_numpy": True,
            "show_progress_bar": False,
        }
    ]
    assert embeddings == [[0.6, 0.8, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]


def test_huggingface_embedding_provider_rejects_vectors_larger_than_storage_dimension() -> None:
    model = StubSentenceTransformer()
    provider = HuggingFaceEmbeddingProvider(model=model, dimension=1)

    try:
        provider.embed_texts(["too wide"])
    except ValueError as exc:
        assert "exceeds configured storage dimension" in str(exc)
    else:
        raise AssertionError("Expected ValueError for vectors larger than storage dimension")


def test_build_embedding_provider_accepts_huggingface_aliases(monkeypatch) -> None:
    import packages.ingestion.embeddings as embeddings_module

    class StubProvider:
        def __init__(self) -> None:
            self.dimension = EMBEDDING_DIMENSION

    monkeypatch.setattr(embeddings_module, "HuggingFaceEmbeddingProvider", StubProvider)

    assert isinstance(build_embedding_provider("huggingface"), StubProvider)
    assert isinstance(build_embedding_provider("hf"), StubProvider)


def test_ingestion_cli_accepts_huggingface_provider(tmp_path) -> None:
    from packages.ingestion.load_experiment import parse_args

    args = parse_args(
        [
            "--experiment-dir",
            str(tmp_path),
            "--embedding-provider",
            "huggingface",
        ]
    )

    assert args.embedding_provider == "huggingface"


def test_ingestion_cli_accepts_ollama_provider(tmp_path) -> None:
    from packages.ingestion.load_experiment import parse_args

    args = parse_args(
        [
            "--experiment-dir",
            str(tmp_path),
            "--embedding-provider",
            "ollama",
        ]
    )

    assert args.embedding_provider == "ollama"
