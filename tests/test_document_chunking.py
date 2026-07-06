from packages.db.models import EMBEDDING_DIMENSION
from packages.ingestion.chunking import chunk_markdown_report
from packages.ingestion.embeddings import (
    BGE_SMALL_EN_MODEL,
    GEMINI_EMBEDDING_MODEL,
    OLLAMA_EMBEDDING_MODEL,
    FakeEmbeddingProvider,
    GeminiEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
    OllamaEmbeddingProvider,
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


class StubOllamaEmbeddingClient:
    def __init__(self) -> None:
        self.calls = []

    def embed(self, *, model: str, input: list[str]) -> dict[str, list[list[float]]]:
        self.calls.append({"model": model, "input": input})
        return {"embeddings": [[0.25, 0.75], [0.5, 0.5]]}


def test_ollama_embedding_provider_uses_nomic_default_and_pads_vectors() -> None:
    client = StubOllamaEmbeddingClient()
    provider = OllamaEmbeddingProvider(client=client, dimension=4)

    embeddings = provider.embed_texts(["first", "second"])

    assert provider.model == OLLAMA_EMBEDDING_MODEL
    assert client.calls == [{"model": "nomic-embed-text", "input": ["first", "second"]}]
    assert embeddings == [[0.25, 0.75, 0.0, 0.0], [0.5, 0.5, 0.0, 0.0]]


def test_build_embedding_provider_accepts_ollama(monkeypatch) -> None:
    import packages.ingestion.embeddings as embeddings_module

    class StubProvider:
        def __init__(self, *, model: str = OLLAMA_EMBEDDING_MODEL) -> None:
            self.dimension = EMBEDDING_DIMENSION
            self.model = model

    monkeypatch.setattr(embeddings_module, "OllamaEmbeddingProvider", StubProvider)

    provider = build_embedding_provider("ollama", model="custom-embed")

    assert isinstance(provider, StubProvider)
    assert provider.model == "custom-embed"


class StubGeminiEmbedding:
    def __init__(self, values: list[float]) -> None:
        self.values = values


class StubGeminiEmbeddingResponse:
    def __init__(self, embeddings: list[StubGeminiEmbedding]) -> None:
        self.embeddings = embeddings


class StubGeminiModels:
    def __init__(self) -> None:
        self.embed_calls = []

    def embed_content(
        self,
        *,
        model: str,
        contents: list[str],
        config: dict[str, int],
    ) -> StubGeminiEmbeddingResponse:
        self.embed_calls.append({"model": model, "contents": contents, "config": config})
        return StubGeminiEmbeddingResponse(
            [
                StubGeminiEmbedding([0.1, 0.2]),
                StubGeminiEmbedding([0.3, 0.4]),
            ]
        )


class StubGeminiClient:
    def __init__(self) -> None:
        self.models = StubGeminiModels()


def test_gemini_embedding_provider_requests_configured_dimension_and_pads_vectors() -> None:
    client = StubGeminiClient()
    provider = GeminiEmbeddingProvider(client=client, dimension=4)

    embeddings = provider.embed_texts(["first", "second"])

    assert provider.model == GEMINI_EMBEDDING_MODEL
    assert client.models.embed_calls == [
        {
            "model": "gemini-embedding-001",
            "contents": ["first", "second"],
            "config": {"output_dimensionality": 4},
        }
    ]
    assert embeddings == [[0.1, 0.2, 0.0, 0.0], [0.3, 0.4, 0.0, 0.0]]


def test_gemini_embedding_provider_returns_empty_list_for_empty_input() -> None:
    client = StubGeminiClient()
    provider = GeminiEmbeddingProvider(client=client, dimension=4)

    assert provider.embed_texts([]) == []
    assert client.models.embed_calls == []


def test_build_embedding_provider_accepts_gemini(monkeypatch) -> None:
    import packages.ingestion.embeddings as embeddings_module

    class StubProvider:
        def __init__(self, *, model: str = GEMINI_EMBEDDING_MODEL) -> None:
            self.dimension = EMBEDDING_DIMENSION
            self.model = model

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(embeddings_module, "GeminiEmbeddingProvider", StubProvider)

    provider = build_embedding_provider("gemini", model="custom-gemini-embedding")

    assert isinstance(provider, StubProvider)
    assert provider.model == "custom-gemini-embedding"


def test_build_embedding_provider_auto_prefers_gemini(monkeypatch) -> None:
    import packages.ingestion.embeddings as embeddings_module

    class StubGeminiProvider:
        def __init__(self, *, model: str = GEMINI_EMBEDDING_MODEL) -> None:
            self.dimension = EMBEDDING_DIMENSION
            self.model = model

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(embeddings_module, "GeminiEmbeddingProvider", StubGeminiProvider)

    assert isinstance(build_embedding_provider("auto"), StubGeminiProvider)


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


def test_ingestion_cli_accepts_gemini_provider(tmp_path) -> None:
    from packages.ingestion.load_experiment import parse_args

    args = parse_args(
        [
            "--experiment-dir",
            str(tmp_path),
            "--embedding-provider",
            "gemini",
        ]
    )

    assert args.embedding_provider == "gemini"
