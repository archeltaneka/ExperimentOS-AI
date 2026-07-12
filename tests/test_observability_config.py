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


def test_phoenix_placeholder_provider_finish_is_non_crashing() -> None:
    from packages.observability.models import PhoenixSettings
    from packages.observability.noop import PhoenixObservabilityProvider

    provider = PhoenixObservabilityProvider(
        settings=PhoenixSettings(enabled=True, endpoint="http://localhost:6006")
    )

    root = provider.start_root_span("test")
    root.finish()

    assert provider.failure_count == 0


def test_observability_settings_compatibility_properties_reflect_phoenix_only_configuration(
) -> None:
    from packages.observability.models import ObservabilitySettings, PhoenixSettings

    settings = ObservabilitySettings(
        phoenix=PhoenixSettings(
            enabled=True,
            endpoint="http://localhost:6006",
            api_key="phoenix-key",
            project="phoenix-project",
            environment="staging",
            trace_inputs=True,
            trace_outputs=True,
            redact_sensitive_data=False,
            tags=("phoenix", "otel"),
        )
    )

    assert settings.enabled is True
    assert settings.api_key == "phoenix-key"
    assert settings.endpoint == "http://localhost:6006"
    assert settings.project == "phoenix-project"
    assert settings.environment == "staging"
    assert settings.trace_inputs is True
    assert settings.trace_outputs is True
    assert settings.redact_sensitive_data is False
    assert settings.tags == ("phoenix", "otel")


def test_observability_settings_accepts_legacy_top_level_langsmith_constructor_args() -> None:
    from packages.observability.models import ObservabilitySettings

    settings = ObservabilitySettings(
        enabled=True,
        api_key="ls-test-key",
        endpoint="https://langsmith.example.test",
        project="experimentos-test",
        environment="test",
        sampling_rate=0.5,
        trace_inputs=True,
        trace_outputs=False,
        redact_sensitive_data=False,
        tags=("api", "test"),
        strict=True,
        always_trace_errors=False,
        max_string_length=256,
        max_collection_length=7,
        max_metadata_depth=3,
        max_retrieval_records=4,
    )

    assert settings.langsmith.enabled is True
    assert settings.langsmith.api_key == "ls-test-key"
    assert settings.langsmith.endpoint == "https://langsmith.example.test"
    assert settings.langsmith.project == "experimentos-test"
    assert settings.langsmith.environment == "test"
    assert settings.langsmith.sampling_rate == 0.5
    assert settings.langsmith.trace_inputs is True
    assert settings.langsmith.trace_outputs is False
    assert settings.langsmith.redact_sensitive_data is False
    assert settings.langsmith.tags == ("api", "test")
    assert settings.langsmith.strict is True
    assert settings.langsmith.always_trace_errors is False
    assert settings.langsmith.max_string_length == 256
    assert settings.langsmith.max_collection_length == 7
    assert settings.langsmith.max_metadata_depth == 3
    assert settings.langsmith.max_retrieval_records == 4
