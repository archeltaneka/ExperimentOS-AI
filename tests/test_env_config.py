from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from packages.config.env import load_environment
from packages.db.session import get_database_url


def test_load_environment_overrides_stale_shell_values(monkeypatch, tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("LLM_PROVIDER=gemini\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    load_environment()

    assert os.environ["LLM_PROVIDER"] == "gemini"


def test_get_database_url_loads_dotenv(monkeypatch, tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "DATABASE_URL=postgresql+psycopg://file:pass@localhost:5433/app\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_database_url() == "postgresql+psycopg://file:pass@localhost:5433/app"


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


def test_ingestion_cli_uses_dotenv_embedding_provider_when_flag_omitted(
    monkeypatch, tmp_path: Path
) -> None:
    import packages.ingestion.load_experiment as load_experiment

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("EMBEDDING_PROVIDER=ollama\n", encoding="utf-8")
    experiment_dir = tmp_path / "experiment"
    experiment_dir.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)

    args = load_experiment.parse_args(["--experiment-dir", str(experiment_dir)])
    resolved = load_experiment.resolve_runtime_options(args)

    assert resolved.embedding_provider == "ollama"


def test_retrieval_cli_uses_dotenv_embedding_provider_when_flag_omitted(
    monkeypatch, tmp_path: Path
) -> None:
    import packages.retrieval.search as retrieval_search

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("EMBEDDING_PROVIDER=ollama\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)

    args = retrieval_search.parse_args(["--query", "payment recommendation"])
    resolved = retrieval_search.resolve_runtime_options(args)

    assert resolved.embedding_provider == "ollama"


def test_evaluation_cli_uses_dotenv_provider_defaults_when_flags_omitted(
    monkeypatch, tmp_path: Path
) -> None:
    import packages.evals.run as eval_run

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "EMBEDDING_PROVIDER=ollama",
                "LLM_PROVIDER=ollama",
                "OLLAMA_EMBEDDING_MODEL=nomic-embed-text",
                "OLLAMA_MODEL=qwen2.5:7b",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    args = eval_run.parse_args([])
    resolved = eval_run.resolve_runtime_options(args)

    assert resolved.embedding_provider == "ollama"
    assert resolved.embedding_model == "nomic-embed-text"
    assert resolved.llm_provider == "ollama"
    assert resolved.llm_model == "qwen2.5:7b"


def test_explicit_cli_flags_override_dotenv_provider_defaults(monkeypatch, tmp_path: Path) -> None:
    import packages.evals.run as eval_run

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "EMBEDDING_PROVIDER=ollama",
                "LLM_PROVIDER=ollama",
                "OLLAMA_EMBEDDING_MODEL=nomic-embed-text",
                "OLLAMA_MODEL=qwen2.5:7b",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    args = eval_run.parse_args(
        [
            "--embedding-provider",
            "gemini",
            "--embedding-model",
            "gemini-embedding-001",
            "--llm-provider",
            "gemini",
            "--llm-model",
            "gemini-3.5-flash",
        ]
    )
    resolved = eval_run.resolve_runtime_options(args)

    assert resolved.embedding_provider == "gemini"
    assert resolved.embedding_model == "gemini-embedding-001"
    assert resolved.llm_provider == "gemini"
    assert resolved.llm_model == "gemini-3.5-flash"
