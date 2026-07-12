from __future__ import annotations

import importlib

import pytest


def test_load_observability_settings_defaults_all_external_sinks_to_disabled(
    monkeypatch,
) -> None:
    from packages.observability.models import load_observability_settings

    monkeypatch.delenv("EXPERIMENTOS_LANGSMITH_ENABLED", raising=False)
    monkeypatch.delenv("EXPERIMENTOS_PHOENIX_ENABLED", raising=False)

    settings = load_observability_settings()

    assert settings.langsmith.enabled is False
    assert settings.phoenix.enabled is False
    assert settings.phoenix.protocol == "http/protobuf"
    assert settings.phoenix.trace_retrieval_content is False


def test_resolve_provider_returns_noop_when_all_external_sinks_disabled(
    monkeypatch,
) -> None:
    from packages.observability.factory import resolve_observability_provider
    from packages.observability.noop import NoOpObservabilityProvider

    monkeypatch.delenv("EXPERIMENTOS_LANGSMITH_ENABLED", raising=False)
    monkeypatch.delenv("EXPERIMENTOS_PHOENIX_ENABLED", raising=False)

    provider = resolve_observability_provider()

    assert isinstance(provider, NoOpObservabilityProvider)


def test_resolve_provider_raises_when_phoenix_enabled_and_dependency_missing(
    monkeypatch,
) -> None:
    from packages.observability.factory import (
        ObservabilityConfigurationError,
        resolve_observability_provider,
    )

    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_ENABLED", "true")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_PROJECT", "experimentos-local")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_ENDPOINT", "http://127.0.0.1:6006")

    original_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name.startswith("phoenix") or name.startswith("opentelemetry"):
            raise ModuleNotFoundError(name)
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(ObservabilityConfigurationError, match="Phoenix"):
        resolve_observability_provider()
