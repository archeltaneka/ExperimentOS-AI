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


def test_load_observability_settings_reads_extended_phoenix_environment_options(
    monkeypatch,
) -> None:
    from packages.observability.models import load_observability_settings

    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_ENABLED", "true")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_ENDPOINT", "http://127.0.0.1:6006/v1/traces")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_PROJECT", "experimentos-eval")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_TRANSPORT", "grpc")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_SAMPLING_RATE", "0.25")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_STRICT", "true")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_ALWAYS_TRACE_ERRORS", "false")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_MAX_STRING_LENGTH", "128")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_MAX_COLLECTION_LENGTH", "4")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_MAX_METADATA_DEPTH", "3")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_MAX_RETRIEVAL_RECORDS", "2")

    settings = load_observability_settings()

    assert settings.phoenix.enabled is True
    assert settings.phoenix.protocol == "grpc"
    assert settings.phoenix.sampling_rate == 0.25
    assert settings.phoenix.strict is True
    assert settings.phoenix.always_trace_errors is False
    assert settings.phoenix.max_string_length == 128
    assert settings.phoenix.max_collection_length == 4
    assert settings.phoenix.max_metadata_depth == 3
    assert settings.phoenix.max_retrieval_records == 2


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


def test_legacy_phoenix_import_path_resolves_real_provider_behavior() -> None:
    from packages.observability.models import PhoenixSettings
    from packages.observability.noop import PhoenixObservabilityProvider

    exported: list[tuple[str, dict[str, object]]] = []

    class FakeSpan:
        def __init__(self, name: str, attributes: dict[str, object]) -> None:
            self.name = name
            self.attributes = attributes

        def __enter__(self):
            exported.append((self.name, dict(self.attributes)))
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def set_status(self, status) -> None:
            return None

        def record_exception(self, exc: Exception) -> None:
            return None

        def set_attributes(self, attributes: dict[str, object]) -> None:
            exported.append((self.name, dict(attributes)))

    class FakeTracer:
        def start_as_current_span(
            self,
            name: str,
            attributes: dict[str, object] | None = None,
        ):
            return FakeSpan(name, attributes or {})

    provider = PhoenixObservabilityProvider(
        settings=PhoenixSettings(
            enabled=True,
            endpoint="http://localhost:6006",
            project="experimentos-local",
        ),
        tracer_provider=object(),
        tracer=FakeTracer(),
    )

    root = provider.start_root_span(
        "ask_request",
        trace_id="req-legacy",
        inputs={"question": "hello"},
        metadata={"surface": "ask"},
    )
    root.finish(outputs={"status": "ok"})

    assert any(name == "ask_request" for name, _attrs in exported)
    assert any(attrs.get("experimentos.trace_id") == "req-legacy" for _name, attrs in exported)
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


def test_resolve_provider_returns_shared_composite_for_multiple_enabled_sinks(
    monkeypatch,
) -> None:
    from packages.observability import factory
    from packages.observability.base import BaseObservabilityProvider
    from packages.observability.composite import CompositeObservabilityProvider
    from packages.observability.models import ProviderSettings

    monkeypatch.setenv("EXPERIMENTOS_LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("EXPERIMENTOS_LANGSMITH_API_KEY", "ls-test-key")
    monkeypatch.setenv("EXPERIMENTOS_LANGSMITH_PROJECT", "experimentos-test")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_ENABLED", "true")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_PROJECT", "experimentos-local")
    monkeypatch.setenv("EXPERIMENTOS_PHOENIX_ENDPOINT", "http://127.0.0.1:6006")

    class StubProvider(BaseObservabilityProvider):
        def __init__(self) -> None:
            super().__init__(ProviderSettings(enabled=True))

        def _emit_root(self, record) -> None:
            return None

    monkeypatch.setattr(factory, "_require_langsmith_dependency", lambda: None)
    monkeypatch.setattr(factory, "_require_phoenix_dependencies", lambda: None)
    monkeypatch.setattr(factory, "LangSmithObservabilityProvider", lambda settings: StubProvider())
    monkeypatch.setattr(factory, "PhoenixObservabilityProvider", lambda settings: StubProvider())

    provider = factory.resolve_observability_provider()

    assert isinstance(provider, CompositeObservabilityProvider)
