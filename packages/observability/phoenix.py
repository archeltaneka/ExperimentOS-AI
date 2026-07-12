from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import PhoenixSettings
from packages.observability.redaction import redact_payload


class PhoenixObservabilityProvider(BaseObservabilityProvider):
    def __init__(
        self,
        *,
        settings: PhoenixSettings,
        tracer_provider: object | None = None,
        tracer: object | None = None,
        module_loader: Callable[[str], object] | None = None,
    ) -> None:
        super().__init__(settings)
        self._tracer_provider = tracer_provider
        self._tracer = tracer
        self._module_loader = module_loader or importlib.import_module
        self._status_class: type[Any] | None = None
        self._status_code: Any | None = None
        if self._tracer_provider is None or self._tracer is None:
            self._load_defaults()

    def _load_defaults(self) -> None:
        phoenix_otel = self._module_loader("phoenix.otel")
        self._tracer_provider = phoenix_otel.register(
            project_name=self.settings.project,
            endpoint=self.settings.endpoint,
            protocol=self.settings.protocol,
            headers=dict(self.settings.headers),
            batch=True,
            auto_instrument=False,
            api_key=self.settings.api_key,
            set_global_tracer_provider=False,
        )
        self._tracer = self._tracer_provider.get_tracer("packages.observability.phoenix")
        self._load_trace_api()

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self._emit_record(record)

    def _emit_record(self, record: BufferedSpanRecord) -> None:
        attributes = self._build_span_attributes(record)
        with self._tracer.start_as_current_span(record.name, attributes=attributes) as span:
            for child in record.children:
                self._emit_record(child)
            if record.error is not None:
                message = _error_message(record) or record.name
                span.record_exception(RuntimeError(message))
                span.set_status(self._build_status(is_error=True))
            else:
                span.set_status(self._build_status(is_error=False))
            output_attributes = self._build_output_attributes(record)
            if output_attributes:
                span.set_attributes(output_attributes)

    def _build_span_attributes(self, record: BufferedSpanRecord) -> dict[str, object]:
        metadata = dict(redact_payload(record.metadata, settings=self.settings))
        return {
            "openinference.span.kind": _span_kind(record.run_type, record.name),
            "experimentos.trace_id": record.trace_id or "",
            "experimentos.span.name": record.name,
            "experimentos.surface": str(metadata.get("surface", "")),
            **_flatten_metadata(metadata),
            **_sanitize_input_attributes(record, self.settings),
        }

    def _build_output_attributes(self, record: BufferedSpanRecord) -> dict[str, object]:
        outputs = dict(redact_payload(record.outputs, settings=self.settings, is_output=True))
        return _flatten_attribute_mapping("output", outputs)

    def _build_status(self, *, is_error: bool) -> object:
        if self._status_class is None or self._status_code is None:
            return "ERROR" if is_error else "OK"
        code = self._status_code.ERROR if is_error else self._status_code.OK
        return self._status_class(code)

    def _load_trace_api(self) -> None:
        if self._status_class is not None and self._status_code is not None:
            return
        trace_module = self._module_loader("opentelemetry.trace")
        self._status_class = trace_module.Status
        self._status_code = trace_module.StatusCode

    def force_flush(self) -> bool:
        return self._run_lifecycle_hook("force_flush", timeout_millis=30_000)

    def shutdown(self) -> bool:
        return self._run_lifecycle_hook("shutdown")

    def _run_lifecycle_hook(self, hook_name: str, **kwargs: object) -> bool:
        if self._tracer_provider is None:
            return True
        hook = getattr(self._tracer_provider, hook_name, None)
        if hook is None:
            return True
        try:
            try:
                result = hook(**kwargs)
            except TypeError:
                result = hook()
            return result is not False
        except Exception:
            self.increment_failure()
            if self.settings.strict:
                raise
            return False


def _span_kind(run_type: str, name: str) -> str:
    if run_type == "retriever":
        return "RETRIEVER"
    if run_type == "llm":
        return "LLM"
    if name == "prompt_rendering":
        return "PROMPT"
    if name.startswith("evaluation."):
        return "EVALUATOR"
    if name in {"ask_request", "workflow"}:
        return "AGENT"
    return "CHAIN"


def _flatten_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return _flatten_attribute_mapping("experimentos.metadata", metadata)


def _sanitize_input_attributes(
    record: BufferedSpanRecord,
    settings: PhoenixSettings,
) -> dict[str, object]:
    inputs = dict(redact_payload(record.inputs, settings=settings))
    return _flatten_attribute_mapping("input", inputs)


def _flatten_attribute_mapping(prefix: str, values: Mapping[str, object]) -> dict[str, object]:
    attributes: dict[str, object] = {}
    for key, value in values.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        attributes.update(_flatten_attribute_value(f"{prefix}.{normalized_key}", value))
    return attributes


def _flatten_attribute_value(key: str, value: object) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        nested: dict[str, object] = {}
        for child_key, child_value in value.items():
            normalized_key = str(child_key).strip()
            if not normalized_key:
                continue
            nested.update(_flatten_attribute_value(f"{key}.{normalized_key}", child_value))
        if nested:
            return nested
        return {key: "{}"}
    if _is_otel_primitive(value):
        return {key: value}
    if _is_non_string_sequence(value):
        return {key: _normalize_sequence(value)}
    return {key: str(value)}


def _normalize_sequence(value: Sequence[object]) -> object:
    items = list(value)
    if not items:
        return "[]"
    if _is_homogeneous_primitive_sequence(items):
        return items
    return _serialize_attribute_value(items)


def _is_otel_primitive(value: object) -> bool:
    return type(value) in {str, bool, int, float}


def _is_non_string_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _is_homogeneous_primitive_sequence(values: list[object]) -> bool:
    if not values:
        return False
    first_type = type(values[0])
    if first_type not in {str, bool, int, float}:
        return False
    return all(type(value) is first_type for value in values)


def _serialize_attribute_value(value: object) -> str:
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _error_message(record: BufferedSpanRecord) -> str | None:
    if record.error is None:
        return None
    error_type = str(record.error.get("type", "Error")).strip()
    message = str(record.error.get("message", "")).strip()
    return f"{error_type}: {message}".strip(": ")
