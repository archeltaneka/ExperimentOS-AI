from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from packages.config.env import load_environment


def test_load_environment_overrides_stale_shell_values(monkeypatch, tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("LLM_PROVIDER=gemini\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    load_environment()

    assert os.environ["LLM_PROVIDER"] == "gemini"


def test_ingestion_cli_loads_dotenv_before_running(monkeypatch, tmp_path: Path) -> None:
    import packages.ingestion.load_experiment as load_experiment

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+psycopg://file:pass@localhost:5433/app",
                "GEMINI_API_KEY=gemini-from-dotenv",
            ]
        ),
        encoding="utf-8",
    )
    experiment_dir = tmp_path / "experiment"
    experiment_dir.mkdir()
    captured: dict[str, Any] = {}

    def fake_run_cli(
        experiment_dir: Path,
        *,
        embedding_provider: str,
        skip_embeddings: bool,
    ) -> object:
        captured["experiment_dir"] = experiment_dir
        captured["embedding_provider"] = embedding_provider
        captured["skip_embeddings"] = skip_embeddings
        return object()

    def fake_run_async(coro: object) -> object:
        captured["gemini_api_key"] = os.environ.get("GEMINI_API_KEY")
        captured["database_url"] = os.environ.get("DATABASE_URL")
        return coro

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(load_experiment, "_run_cli", fake_run_cli)
    monkeypatch.setattr(load_experiment, "run_async", fake_run_async)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "load_experiment",
            "--experiment-dir",
            str(experiment_dir),
            "--embedding-provider",
            "gemini",
        ],
    )

    load_experiment.main()

    assert captured["embedding_provider"] == "gemini"
    assert captured["skip_embeddings"] is False
    assert captured["gemini_api_key"] == "gemini-from-dotenv"
    assert captured["database_url"] == "postgresql+psycopg://file:pass@localhost:5433/app"


def test_embedding_provider_factory_loads_dotenv_for_gemini(monkeypatch, tmp_path: Path) -> None:
    import packages.ingestion.embeddings as embeddings_module

    class StubGeminiProvider:
        def __init__(self, *, model: str) -> None:
            self.model = model
            self.dimension = 1536

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "GEMINI_API_KEY=gemini-from-dotenv",
                "GEMINI_EMBEDDING_MODEL=gemini-test-embedding",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr(embeddings_module, "GeminiEmbeddingProvider", StubGeminiProvider)

    provider = embeddings_module.build_embedding_provider("gemini")

    assert provider.model == "gemini-test-embedding"
