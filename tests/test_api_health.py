from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app, get_embedding_provider_name, get_llm_client


def test_missing_provider_settings_ignore_live_api_keys(monkeypatch, tmp_path: Path) -> None:
    from packages.llm.client import MockLLMClient

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-be-used")

    assert isinstance(get_llm_client(), MockLLMClient)
    assert get_embedding_provider_name() == "fake"


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "experimentos-api"}


def test_embedding_provider_name_uses_dotenv(monkeypatch, tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("EMBEDDING_PROVIDER=huggingface\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)

    assert get_embedding_provider_name() == "huggingface"


def test_llm_client_auto_prefers_gemini_when_api_key_is_set(monkeypatch, tmp_path: Path) -> None:
    import apps.api.main as main_module

    class StubGeminiClient:
        def __init__(self, *, model: str) -> None:
            self.model = model

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "GEMINI_API_KEY=test-key",
                "OPENAI_API_KEY=openai-key",
                "GEMINI_MODEL=gemini-test-model",
                "LLM_PROVIDER=auto",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(main_module, "GeminiLLMClient", StubGeminiClient)

    client = get_llm_client()

    assert isinstance(client, StubGeminiClient)
    assert client.model == "gemini-test-model"


def test_llm_client_loads_dotenv_for_gemini_auto_provider(monkeypatch, tmp_path: Path) -> None:
    import apps.api.main as main_module

    class StubGeminiClient:
        def __init__(self, *, model: str) -> None:
            self.model = model

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=auto",
                "GEMINI_API_KEY=gemini-from-dotenv",
                "GEMINI_MODEL=gemini-dotenv-model",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(main_module, "GeminiLLMClient", StubGeminiClient)

    client = get_llm_client()

    assert isinstance(client, StubGeminiClient)
    assert client.model == "gemini-dotenv-model"


def test_llm_client_uses_ollama_provider_from_dotenv(monkeypatch, tmp_path: Path) -> None:
    import apps.api.main as main_module

    class StubOllamaClient:
        def __init__(self, *, model: str) -> None:
            self.model = model

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=ollama",
                "OLLAMA_MODEL=qwen2.5:7b",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(main_module, "OllamaLLMClient", StubOllamaClient)

    client = get_llm_client()

    assert isinstance(client, StubOllamaClient)
    assert client.model == "qwen2.5:7b"
