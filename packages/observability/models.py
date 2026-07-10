from __future__ import annotations

import os
from dataclasses import dataclass

from packages.config.env import load_environment


def _env_first(*names: str) -> str | None:
    load_environment()
    for name in names:
        value = os.environ.get(name)
        if value is None:
            continue
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _env_bool(default: bool, *names: str) -> bool:
    value = _env_first(*names)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_float(default: float, *names: str) -> float:
    value = _env_first(*names)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(default: int, *names: str) -> int:
    value = _env_first(*names)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_tags(*names: str) -> tuple[str, ...]:
    value = _env_first(*names)
    if value is None:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class ObservabilitySettings:
    enabled: bool = False
    api_key: str | None = None
    endpoint: str | None = None
    project: str | None = None
    environment: str = "development"
    sampling_rate: float = 0.0
    trace_inputs: bool = False
    trace_outputs: bool = False
    redact_sensitive_data: bool = True
    tags: tuple[str, ...] = ()
    strict: bool = False
    always_trace_errors: bool = True
    max_string_length: int = 512
    max_collection_length: int = 25

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.enabled and not self.api_key:
            errors.append("LangSmith tracing is enabled but no API key is configured.")
        if self.enabled and not self.project:
            errors.append("LangSmith tracing is enabled but no project is configured.")
        if self.sampling_rate < 0.0 or self.sampling_rate > 1.0:
            errors.append("LangSmith sampling rate must be between 0.0 and 1.0.")
        if self.max_string_length < 8:
            errors.append("max_string_length must be at least 8.")
        if self.max_collection_length < 1:
            errors.append("max_collection_length must be at least 1.")
        return tuple(errors)


def load_observability_settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=_env_bool(False, "EXPERIMENTOS_LANGSMITH_ENABLED", "LANGSMITH_TRACING"),
        api_key=_env_first("EXPERIMENTOS_LANGSMITH_API_KEY", "LANGSMITH_API_KEY"),
        endpoint=_env_first("EXPERIMENTOS_LANGSMITH_ENDPOINT", "LANGSMITH_ENDPOINT"),
        project=_env_first("EXPERIMENTOS_LANGSMITH_PROJECT", "LANGSMITH_PROJECT"),
        environment=_env_first("EXPERIMENTOS_LANGSMITH_ENVIRONMENT", "APP_ENV") or "development",
        sampling_rate=_env_float(0.0, "EXPERIMENTOS_LANGSMITH_SAMPLING_RATE"),
        trace_inputs=_env_bool(False, "EXPERIMENTOS_LANGSMITH_TRACE_INPUTS"),
        trace_outputs=_env_bool(False, "EXPERIMENTOS_LANGSMITH_TRACE_OUTPUTS"),
        redact_sensitive_data=_env_bool(True, "EXPERIMENTOS_LANGSMITH_REDACT_SENSITIVE_DATA"),
        tags=_env_tags("EXPERIMENTOS_LANGSMITH_TAGS"),
        strict=_env_bool(False, "EXPERIMENTOS_LANGSMITH_STRICT"),
        always_trace_errors=_env_bool(True, "EXPERIMENTOS_LANGSMITH_ALWAYS_TRACE_ERRORS"),
        max_string_length=_env_int(512, "EXPERIMENTOS_LANGSMITH_MAX_STRING_LENGTH"),
        max_collection_length=_env_int(25, "EXPERIMENTOS_LANGSMITH_MAX_COLLECTION_LENGTH"),
    )
