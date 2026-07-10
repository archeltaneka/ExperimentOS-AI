from __future__ import annotations

import importlib

from packages.observability.langsmith import LangSmithObservabilityProvider
from packages.observability.models import ObservabilitySettings, load_observability_settings
from packages.observability.noop import NoOpObservabilityProvider


class ObservabilityConfigurationError(RuntimeError):
    pass


def resolve_observability_provider(
    settings: ObservabilitySettings | None = None,
):
    resolved = settings or load_observability_settings()
    if not resolved.enabled:
        return NoOpObservabilityProvider()
    errors = resolved.validate()
    if errors:
        raise ObservabilityConfigurationError(" ".join(errors))
    try:
        importlib.import_module("langsmith")
        importlib.import_module("langsmith.run_trees")
    except ModuleNotFoundError as exc:
        raise ObservabilityConfigurationError(
            "LangSmith tracing is enabled but the optional 'langsmith' dependency is not installed."
        ) from exc
    return LangSmithObservabilityProvider(settings=resolved)
