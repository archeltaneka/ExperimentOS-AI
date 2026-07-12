from __future__ import annotations

import importlib

from packages.observability.base import BaseObservabilityProvider
from packages.observability.composite import CompositeObservabilityProvider
from packages.observability.langsmith import LangSmithObservabilityProvider
from packages.observability.models import (
    LangSmithSettings,
    ObservabilitySettings,
    OpenTelemetrySettings,
    PhoenixSettings,
    load_observability_settings,
)
from packages.observability.noop import NoOpObservabilityProvider
from packages.observability.opentelemetry import (
    OpenTelemetryObservabilityProvider,
    PhoenixObservabilityProvider,
)


class ObservabilityConfigurationError(RuntimeError):
    pass


def resolve_observability_provider(
    settings: ObservabilitySettings | None = None,
) -> BaseObservabilityProvider:
    resolved = settings or load_observability_settings()
    providers: list[BaseObservabilityProvider] = []

    if resolved.langsmith.enabled:
        _validate_langsmith(resolved.langsmith)
        _require_langsmith_dependency()
        providers.append(LangSmithObservabilityProvider(settings=resolved.langsmith))

    if resolved.otel.enabled:
        _validate_otel(resolved.otel)
        _require_opentelemetry_dependencies()
        if resolved.phoenix.enabled:
            _validate_phoenix(resolved.phoenix)
            _require_phoenix_dependencies()
        providers.append(
            OpenTelemetryObservabilityProvider(
                settings=resolved.otel,
                phoenix_settings=resolved.phoenix if resolved.phoenix.enabled else None,
            )
        )
    elif resolved.phoenix.enabled:
        _validate_phoenix(resolved.phoenix)
        _require_phoenix_dependencies()
        providers.append(PhoenixObservabilityProvider(settings=resolved.phoenix))

    if not providers:
        return NoOpObservabilityProvider()
    if len(providers) == 1:
        return providers[0]
    return CompositeObservabilityProvider(providers)


def _validate_langsmith(settings: LangSmithSettings) -> None:
    errors = settings.validate()
    if errors:
        raise ObservabilityConfigurationError(" ".join(errors))


def _validate_phoenix(settings: PhoenixSettings) -> None:
    errors = settings.validate()
    if errors:
        raise ObservabilityConfigurationError(" ".join(errors))


def _validate_otel(settings: OpenTelemetrySettings) -> None:
    errors = settings.validate()
    if errors:
        raise ObservabilityConfigurationError(" ".join(errors))


def _require_langsmith_dependency() -> None:
    try:
        importlib.import_module("langsmith")
        importlib.import_module("langsmith.run_trees")
    except ModuleNotFoundError as exc:
        raise ObservabilityConfigurationError(
            "LangSmith tracing is enabled but the optional 'langsmith' dependency is not installed."
        ) from exc


def _require_phoenix_dependencies() -> None:
    try:
        importlib.import_module("phoenix.otel")
        importlib.import_module("opentelemetry.trace")
    except ModuleNotFoundError as exc:
        raise ObservabilityConfigurationError(
            "Phoenix tracing is enabled but the optional Phoenix dependencies are not installed."
        ) from exc


def _require_opentelemetry_dependencies() -> None:
    try:
        importlib.import_module("opentelemetry.trace")
        importlib.import_module("opentelemetry.sdk.trace")
        importlib.import_module("opentelemetry.sdk.metrics")
        importlib.import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    except ModuleNotFoundError as exc:
        raise ObservabilityConfigurationError(
            "OpenTelemetry is enabled but the optional OpenTelemetry dependencies are "
            "not installed."
        ) from exc
