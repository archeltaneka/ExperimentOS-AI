from __future__ import annotations

from collections.abc import Mapping, Sequence

from packages.observability.models import ObservabilitySettings

SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "cookies",
    "database_url",
    "dsn",
    "password",
    "secret",
    "token",
}
CONTENT_KEYS = {
    "answer",
    "chunk_text",
    "content",
    "document_chunks",
    "documents",
    "output",
    "outputs",
    "prompt",
    "quote",
    "response",
    "retrieved_chunks",
    "system_instruction",
    "system_prompt",
    "text",
    "user_prompt",
}
SAFE_KEYS = {
    "citation_count",
    "confidence",
    "document_count",
    "embedding_model",
    "embedding_provider",
    "environment",
    "error_type",
    "experiment_id",
    "experimentos_trace_id",
    "latency_ms",
    "model",
    "node",
    "prompt_id",
    "prompt_version",
    "provider",
    "query_id",
    "request_id",
    "retrieved_chunks",
    "score",
    "similarity",
    "status",
    "surface",
    "top_k",
    "workflow",
}


def redact_payload(
    payload: object,
    *,
    settings: ObservabilitySettings,
    is_output: bool = False,
    key_hint: str | None = None,
) -> object:
    if payload is None:
        return None
    if settings.redact_sensitive_data:
        if key_hint and key_hint.lower() in SENSITIVE_KEYS:
            return "<redacted>"
    if isinstance(payload, Mapping):
        return {
            str(key): redact_payload(
                value,
                settings=settings,
                is_output=is_output,
                key_hint=str(key),
            )
            for key, value in payload.items()
        }
    if isinstance(payload, (list, tuple)):
        return _redact_sequence(payload, settings=settings, is_output=is_output)
    if isinstance(payload, str):
        return _redact_string(
            payload,
            settings=settings,
            is_output=is_output,
            key_hint=key_hint,
        )
    return payload


def _redact_sequence(
    values: Sequence[object],
    *,
    settings: ObservabilitySettings,
    is_output: bool,
) -> list[object]:
    truncated = [
        redact_payload(value, settings=settings, is_output=is_output)
        for value in values[: settings.max_collection_length]
    ]
    if len(values) > settings.max_collection_length:
        truncated.append("<truncated>")
    return truncated


def _redact_string(
    value: str,
    *,
    settings: ObservabilitySettings,
    is_output: bool,
    key_hint: str | None,
) -> str:
    key = (key_hint or "").lower()
    if settings.redact_sensitive_data and key in SENSITIVE_KEYS:
        return "<redacted>"
    if key in CONTENT_KEYS or (not key and is_output):
        if (
            (is_output and not settings.trace_outputs)
            or (not is_output and not settings.trace_inputs)
        ):
            if key in SAFE_KEYS:
                return value
            return "<omitted>"
    if len(value) <= settings.max_string_length:
        return value
    return f"{value[: settings.max_string_length - 3]}..."
