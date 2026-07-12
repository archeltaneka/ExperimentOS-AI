from __future__ import annotations

import importlib
from collections.abc import Callable
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
        return {f"output.{key}": value for key, value in outputs.items()}

    def _build_status(self, *, is_error: bool) -> object:
        self._load_trace_api()
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
                return bool(hook(**kwargs))
            except TypeError:
                return bool(hook())
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
    return {f"experimentos.metadata.{key}": value for key, value in metadata.items()}


def _sanitize_input_attributes(
    record: BufferedSpanRecord,
    settings: PhoenixSettings,
) -> dict[str, object]:
    inputs = dict(redact_payload(record.inputs, settings=settings))
    return {f"input.{key}": value for key, value in inputs.items()}


def _error_message(record: BufferedSpanRecord) -> str | None:
    if record.error is None:
        return None
    error_type = str(record.error.get("type", "Error")).strip()
    message = str(record.error.get("message", "")).strip()
    return f"{error_type}: {message}".strip(": ")
