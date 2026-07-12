from __future__ import annotations

import os
from dataclasses import dataclass, field

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


def _env_headers(*names: str) -> tuple[tuple[str, str], ...]:
    value = _env_first(*names)
    if value is None:
        return ()

    headers: list[tuple[str, str]] = []
    for part in value.split(","):
        entry = part.strip()
        if not entry or "=" not in entry:
            continue
        key, header_value = entry.split("=", 1)
        normalized_key = key.strip()
        normalized_value = header_value.strip()
        if normalized_key and normalized_value:
            headers.append((normalized_key, normalized_value))
    return tuple(headers)


@dataclass(frozen=True)
class ProviderSettings:
    enabled: bool = False
    endpoint: str | None = None
    environment: str = "development"
    trace_inputs: bool = False
    trace_outputs: bool = False
    redact_sensitive_data: bool = True
    tags: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        return ()


@dataclass(frozen=True)
class LangSmithSettings(ProviderSettings):
    api_key: str | None = None
    project: str | None = None
    sampling_rate: float = 0.0
    strict: bool = False
    always_trace_errors: bool = True
    max_string_length: int = 512
    max_collection_length: int = 25
    max_metadata_depth: int = 5
    max_retrieval_records: int = 10

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
        if self.max_metadata_depth < 1:
            errors.append("max_metadata_depth must be at least 1.")
        if self.max_retrieval_records < 1:
            errors.append("max_retrieval_records must be at least 1.")
        return tuple(errors)


@dataclass(frozen=True)
class PhoenixSettings(ProviderSettings):
    api_key: str | None = None
    project: str = "experimentos-local"
    protocol: str = "http/protobuf"
    trace_retrieval_content: bool = False
    trace_prompt_content: bool = False
    headers: tuple[tuple[str, str], ...] = ()

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.enabled and not self.endpoint:
            errors.append("Phoenix tracing is enabled but no endpoint is configured.")
        if self.protocol not in {"http/protobuf", "grpc"}:
            errors.append("Phoenix protocol must be either 'http/protobuf' or 'grpc'.")
        return tuple(errors)


@dataclass(frozen=True)
class ObservabilitySettings:
    langsmith: LangSmithSettings = field(default_factory=LangSmithSettings)
    phoenix: PhoenixSettings = field(default_factory=PhoenixSettings)

    @property
    def enabled(self) -> bool:
        return self.langsmith.enabled or self.phoenix.enabled

    @property
    def api_key(self) -> str | None:
        return self.langsmith.api_key

    @property
    def endpoint(self) -> str | None:
        return self.langsmith.endpoint

    @property
    def project(self) -> str | None:
        return self.langsmith.project

    @property
    def environment(self) -> str:
        return self.langsmith.environment

    @property
    def sampling_rate(self) -> float:
        return self.langsmith.sampling_rate

    @property
    def trace_inputs(self) -> bool:
        return self.langsmith.trace_inputs

    @property
    def trace_outputs(self) -> bool:
        return self.langsmith.trace_outputs

    @property
    def redact_sensitive_data(self) -> bool:
        return self.langsmith.redact_sensitive_data

    @property
    def tags(self) -> tuple[str, ...]:
        return self.langsmith.tags

    @property
    def strict(self) -> bool:
        return self.langsmith.strict

    @property
    def always_trace_errors(self) -> bool:
        return self.langsmith.always_trace_errors

    @property
    def max_string_length(self) -> int:
        return self.langsmith.max_string_length

    @property
    def max_collection_length(self) -> int:
        return self.langsmith.max_collection_length

    @property
    def max_metadata_depth(self) -> int:
        return self.langsmith.max_metadata_depth

    @property
    def max_retrieval_records(self) -> int:
        return self.langsmith.max_retrieval_records

    def validate(self) -> tuple[str, ...]:
        return self.langsmith.validate()


def load_observability_settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        langsmith=LangSmithSettings(
            enabled=_env_bool(False, "EXPERIMENTOS_LANGSMITH_ENABLED", "LANGSMITH_TRACING"),
            api_key=_env_first("EXPERIMENTOS_LANGSMITH_API_KEY", "LANGSMITH_API_KEY"),
            endpoint=_env_first("EXPERIMENTOS_LANGSMITH_ENDPOINT", "LANGSMITH_ENDPOINT"),
            project=_env_first("EXPERIMENTOS_LANGSMITH_PROJECT", "LANGSMITH_PROJECT"),
            environment=_env_first("EXPERIMENTOS_LANGSMITH_ENVIRONMENT", "APP_ENV")
            or "development",
            sampling_rate=_env_float(0.0, "EXPERIMENTOS_LANGSMITH_SAMPLING_RATE"),
            trace_inputs=_env_bool(False, "EXPERIMENTOS_LANGSMITH_TRACE_INPUTS"),
            trace_outputs=_env_bool(False, "EXPERIMENTOS_LANGSMITH_TRACE_OUTPUTS"),
            redact_sensitive_data=_env_bool(
                True,
                "EXPERIMENTOS_LANGSMITH_REDACT_SENSITIVE_DATA",
            ),
            tags=_env_tags("EXPERIMENTOS_LANGSMITH_TAGS"),
            strict=_env_bool(False, "EXPERIMENTOS_LANGSMITH_STRICT"),
            always_trace_errors=_env_bool(
                True,
                "EXPERIMENTOS_LANGSMITH_ALWAYS_TRACE_ERRORS",
            ),
            max_string_length=_env_int(512, "EXPERIMENTOS_LANGSMITH_MAX_STRING_LENGTH"),
            max_collection_length=_env_int(
                25,
                "EXPERIMENTOS_LANGSMITH_MAX_COLLECTION_LENGTH",
            ),
            max_metadata_depth=_env_int(5, "EXPERIMENTOS_LANGSMITH_MAX_METADATA_DEPTH"),
            max_retrieval_records=_env_int(
                10,
                "EXPERIMENTOS_LANGSMITH_MAX_RETRIEVAL_RECORDS",
            ),
        ),
        phoenix=PhoenixSettings(
            enabled=_env_bool(False, "EXPERIMENTOS_PHOENIX_ENABLED"),
            endpoint=_env_first("EXPERIMENTOS_PHOENIX_ENDPOINT"),
            api_key=_env_first("EXPERIMENTOS_PHOENIX_API_KEY"),
            project=_env_first("EXPERIMENTOS_PHOENIX_PROJECT") or "experimentos-local",
            environment=_env_first("EXPERIMENTOS_PHOENIX_ENVIRONMENT", "APP_ENV")
            or "development",
            protocol=_env_first("EXPERIMENTOS_PHOENIX_PROTOCOL") or "http/protobuf",
            trace_inputs=_env_bool(False, "EXPERIMENTOS_PHOENIX_TRACE_INPUTS"),
            trace_outputs=_env_bool(False, "EXPERIMENTOS_PHOENIX_TRACE_OUTPUTS"),
            trace_retrieval_content=_env_bool(
                False,
                "EXPERIMENTOS_PHOENIX_TRACE_RETRIEVAL_CONTENT",
            ),
            trace_prompt_content=_env_bool(
                False,
                "EXPERIMENTOS_PHOENIX_TRACE_PROMPT_CONTENT",
            ),
            redact_sensitive_data=_env_bool(
                True,
                "EXPERIMENTOS_PHOENIX_REDACT_SENSITIVE_DATA",
            ),
            tags=_env_tags("EXPERIMENTOS_PHOENIX_TAGS"),
            headers=_env_headers("EXPERIMENTOS_PHOENIX_HEADERS"),
        ),
    )
