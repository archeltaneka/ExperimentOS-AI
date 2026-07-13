from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import OpenTelemetrySettings, PhoenixSettings
from packages.observability.redaction import redact_payload

_TRACE_SCOPE = "packages.observability.opentelemetry"
_METER_SCOPE = "packages.observability.opentelemetry"
_FASTAPI_APP_MARKER = "_experimentos_otel_instrumented"
_HTTP_ROUTE_ATTRIBUTE = "http.route"
_HTTP_STATUS_CODE_ATTRIBUTE = "http.response.status_code"
_WORKFLOW_NODE_NAMES = {
    "planner",
    "retrieval",
    "experiment_analysis",
    "business_impact",
    "risk_assessment",
    "decision",
    "human_approval",
    "executive_summary",
}
_STATUS_ATTRIBUTE_KEYS = {
    "approval_status",
    "decision_status",
    "execution_status",
    "impact_status",
    "result_status",
    "risk_status",
    "status",
    "summary_status",
    "workflow_success",
}
_METRIC_ATTRIBUTE_KEYS = {
    "agent_name",
    "environment",
    "experiment_id",
    "experiment_variant",
    "evaluation_type",
    "execution_mode",
    "provider",
    "assignment_strategy",
    "status",
    "surface",
    "workflow_mode",
}


class OpenTelemetryObservabilityProvider(BaseObservabilityProvider):
    def __init__(
        self,
        *,
        settings: OpenTelemetrySettings,
        phoenix_settings: PhoenixSettings | None = None,
        tracer_provider: object | None = None,
        meter_provider: object | None = None,
        tracer: object | None = None,
        meter: object | None = None,
        span_exporter: object | None = None,
        metric_reader: object | None = None,
        module_loader: Any | None = None,
        fastapi_instrumentor_cls: type[object] | None = None,
    ) -> None:
        super().__init__(settings)
        self.phoenix_settings = phoenix_settings
        self._module_loader = module_loader or importlib.import_module
        self._tracer_provider = tracer_provider
        self._meter_provider = meter_provider
        self._tracer = tracer
        self._meter = meter
        self._status_class: type[Any] | None = None
        self._status_code: Any | None = None
        self._fastapi_instrumentor_cls = fastapi_instrumentor_cls
        self.metric_reader = metric_reader
        self._instruments: dict[str, Any] = {}

        if self._needs_runtime_initialization():
            self._initialize_runtime(
                span_exporter=span_exporter,
                metric_reader=metric_reader,
            )
        if self._tracer is None and self._tracer_provider is not None:
            self._tracer = self._tracer_provider.get_tracer(
                _TRACE_SCOPE,
                self.settings.service_version,
            )
        if (
            self.settings.metrics_enabled
            and self._meter is None
            and self._meter_provider is not None
        ):
            self._meter = self._meter_provider.get_meter(
                _METER_SCOPE,
                self.settings.service_version,
            )
        if self.settings.metrics_enabled and self._meter is not None:
            self._instruments = self._create_instruments()

    def _needs_runtime_initialization(self) -> bool:
        needs_tracing = self.settings.trace_enabled and (
            self._tracer_provider is None or self._tracer is None
        )
        needs_metrics = self.settings.metrics_enabled and (
            self._meter_provider is None or self._meter is None
        )
        return needs_tracing or needs_metrics

    def _initialize_runtime(
        self,
        *,
        span_exporter: object | None,
        metric_reader: object | None,
    ) -> None:
        resources_module = self._module_loader("opentelemetry.sdk.resources")
        sdk_trace_module = self._module_loader("opentelemetry.sdk.trace")
        sampling_module = self._module_loader("opentelemetry.sdk.trace.sampling")
        trace_export_module = self._module_loader("opentelemetry.sdk.trace.export")
        sdk_metrics_module = self._module_loader("opentelemetry.sdk.metrics")
        metrics_export_module = self._module_loader("opentelemetry.sdk.metrics.export")

        resource = resources_module.Resource.create(self._resource_attributes())
        sampler = sampling_module.ALWAYS_ON
        if self.settings.sampling_rate <= 0.0:
            sampler = sampling_module.ALWAYS_OFF
        elif self.settings.sampling_rate < 1.0:
            sampler = sampling_module.TraceIdRatioBased(self.settings.sampling_rate)

        if self.settings.trace_enabled and self._tracer_provider is None:
            self._tracer_provider = sdk_trace_module.TracerProvider(
                resource=resource,
                sampler=sampler,
            )
            for processor in self._build_span_processors(
                trace_export_module=trace_export_module,
                span_exporter=span_exporter,
            ):
                self._tracer_provider.add_span_processor(processor)
            self._load_trace_api()

        if self.settings.metrics_enabled and self._meter_provider is None:
            readers = self._build_metric_readers(
                metrics_export_module=metrics_export_module,
                metric_reader=metric_reader,
            )
            self._meter_provider = sdk_metrics_module.MeterProvider(
                metric_readers=readers,
                resource=resource,
            )
            if metric_reader is not None:
                self.metric_reader = metric_reader

    def _build_span_processors(
        self,
        *,
        trace_export_module: Any,
        span_exporter: object | None,
    ) -> list[object]:
        processors: list[object] = []
        exporter_type = self._normalized_exporter_type()

        if exporter_type == "console":
            exporter = trace_export_module.ConsoleSpanExporter()
            processors.append(self._build_span_processor(trace_export_module, exporter))
        elif exporter_type == "in_memory":
            exporter = span_exporter or self._module_loader(
                "opentelemetry.sdk.trace.export.in_memory_span_exporter"
            ).InMemorySpanExporter()
            processors.append(self._build_span_processor(trace_export_module, exporter))
        elif exporter_type == "otlp_http":
            exporter = self._module_loader(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter"
            ).OTLPSpanExporter(
                endpoint=self.settings.endpoint,
                headers=dict(self.settings.headers),
                timeout=self.settings.export_timeout_ms / 1000.0,
            )
            processors.append(self._build_span_processor(trace_export_module, exporter))

        if self.phoenix_settings is not None and self.phoenix_settings.enabled:
            phoenix_module = self._module_loader("phoenix.otel")
            headers = _phoenix_headers(self.phoenix_settings)
            if self.phoenix_settings.protocol == "grpc":
                phoenix_exporter = phoenix_module.GRPCSpanExporter(
                    endpoint=self.phoenix_settings.endpoint,
                    headers=headers,
                )
            else:
                phoenix_exporter = phoenix_module.HTTPSpanExporter(
                    endpoint=self.phoenix_settings.endpoint,
                    headers=headers,
                )
            processors.append(self._build_span_processor(trace_export_module, phoenix_exporter))

        return processors

    def _build_span_processor(self, trace_export_module: Any, exporter: object) -> object:
        if self.settings.batch_export:
            return trace_export_module.BatchSpanProcessor(exporter)
        return trace_export_module.SimpleSpanProcessor(exporter)

    def _build_metric_readers(
        self,
        *,
        metrics_export_module: Any,
        metric_reader: object | None,
    ) -> list[object]:
        exporter_type = self._normalized_exporter_type()
        if exporter_type == "in_memory":
            reader = metric_reader or metrics_export_module.InMemoryMetricReader()
            self.metric_reader = reader
            return [reader]

        if exporter_type == "console":
            exporter = metrics_export_module.ConsoleMetricExporter()
            return [
                metrics_export_module.PeriodicExportingMetricReader(
                    exporter,
                    export_interval_millis=self.settings.metric_export_interval_ms,
                )
            ]

        if exporter_type == "otlp_http":
            exporter = self._module_loader(
                "opentelemetry.exporter.otlp.proto.http.metric_exporter"
            ).OTLPMetricExporter(
                endpoint=_metrics_endpoint(self.settings.endpoint),
                headers=dict(self.settings.headers),
                timeout=self.settings.export_timeout_ms / 1000.0,
            )
            return [
                metrics_export_module.PeriodicExportingMetricReader(
                    exporter,
                    export_interval_millis=self.settings.metric_export_interval_ms,
                )
            ]

        return []

    def _normalized_exporter_type(self) -> str:
        if self.settings.exporter_type == "otlp":
            return "otlp_http"
        return self.settings.exporter_type

    def _resource_attributes(self) -> dict[str, object]:
        resource_module = self._module_loader("opentelemetry.semconv.resource")
        attributes: dict[str, object] = {
            resource_module.ResourceAttributes.SERVICE_NAME: self.settings.service_name,
            resource_module.ResourceAttributes.SERVICE_NAMESPACE: self.settings.service_namespace,
            resource_module.ResourceAttributes.SERVICE_VERSION: self.settings.service_version,
            resource_module.ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.settings.environment,
            "experimentos.component": "backend",
            "experimentos.project": "ExperimentOS-AI",
        }
        for key, value in self.settings.resource_attributes:
            attributes[key] = value
        if self.phoenix_settings is not None and self.phoenix_settings.enabled:
            project_name = self._module_loader("phoenix.otel").PROJECT_NAME
            attributes[project_name] = self.phoenix_settings.project
        return attributes

    def _create_instruments(self) -> dict[str, object]:
        return {
            "ask_requests_total": self._meter.create_counter(
                "ask_requests_total",
                unit="{request}",
                description="Total ask requests processed by ExperimentOS AI.",
            ),
            "ask_failures_total": self._meter.create_counter(
                "ask_failures_total",
                unit="{request}",
                description="Total ask requests that ended in failure.",
            ),
            "workflow_executions_total": self._meter.create_counter(
                "workflow_executions_total",
                unit="{workflow}",
                description="Total logical workflow executions.",
            ),
            "agent_executions_total": self._meter.create_counter(
                "agent_executions_total",
                unit="{agent}",
                description="Total logical agent node executions.",
            ),
            "retrieval_requests_total": self._meter.create_counter(
                "retrieval_requests_total",
                unit="{request}",
                description="Total retrieval requests.",
            ),
            "empty_retrieval_total": self._meter.create_counter(
                "empty_retrieval_total",
                unit="{request}",
                description="Total retrieval requests that returned no results.",
            ),
            "evaluation_runs_total": self._meter.create_counter(
                "evaluation_runs_total",
                unit="{run}",
                description="Total evaluation runs.",
            ),
            "ask_request_duration_ms": self._meter.create_histogram(
                "ask_request_duration_ms",
                unit="ms",
                description="End-to-end ask request latency in milliseconds.",
            ),
            "workflow_duration_ms": self._meter.create_histogram(
                "workflow_duration_ms",
                unit="ms",
                description="Workflow latency in milliseconds.",
            ),
            "agent_duration_ms": self._meter.create_histogram(
                "agent_duration_ms",
                unit="ms",
                description="Agent node latency in milliseconds.",
            ),
            "retrieval_duration_ms": self._meter.create_histogram(
                "retrieval_duration_ms",
                unit="ms",
                description="Retrieval latency in milliseconds.",
            ),
            "llm_duration_ms": self._meter.create_histogram(
                "llm_duration_ms",
                unit="ms",
                description="LLM generation latency in milliseconds.",
            ),
            "evaluation_duration_ms": self._meter.create_histogram(
                "evaluation_duration_ms",
                unit="ms",
                description="Evaluation duration in milliseconds.",
            ),
            "retrieved_result_count": self._meter.create_histogram(
                "retrieved_result_count",
                unit="{result}",
                description="Retrieved result count per retrieval operation.",
            ),
            "citation_count": self._meter.create_histogram(
                "citation_count",
                unit="{citation}",
                description="Citation count per traced workflow or request.",
            ),
        }

    def _finish_root(self, record: BufferedSpanRecord) -> None:
        if not self.settings.enabled:
            return
        if self.settings.metrics_enabled:
            self._run_safely(lambda: self._record_metrics(record))
        if self.settings.trace_enabled:
            self._run_safely(lambda: self._emit_root(record))

    def _run_safely(self, operation: Any) -> None:
        try:
            operation()
        except Exception:
            self.increment_failure()
            if self.settings.strict:
                raise

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self._emit_record(record)

    def _emit_record(self, record: BufferedSpanRecord) -> None:
        attributes = self._build_span_attributes(record)
        with self._tracer.start_as_current_span(record.name, attributes=attributes) as span:
            for child in record.children:
                self._emit_record(child)
            output_attributes = self._build_output_attributes(record)
            if output_attributes:
                span.set_attributes(output_attributes)
            if record.error is not None:
                message = _error_message(record) or record.name
                span.record_exception(RuntimeError(message))
                span.set_status(self._build_status(is_error=True))
            else:
                span.set_status(self._build_status(is_error=False))

    def _build_span_attributes(self, record: BufferedSpanRecord) -> dict[str, object]:
        metadata = dict(redact_payload(record.metadata, settings=self.settings))
        metadata.pop("assignment_key_hash", None)
        attributes = {
            "experimentos.trace_id": record.trace_id or "",
            "experimentos.span.name": record.name,
            "experimentos.surface": str(metadata.get("surface", "")),
            "openinference.span.kind": _span_kind(record.run_type, record.name),
            **_experimentos_metadata_attributes(record, metadata),
            **_tag_attributes(record.tags),
            **_flatten_attribute_mapping("experimentos.metadata", metadata),
            **_sanitize_input_attributes(record, self.settings),
        }
        endpoint = str(metadata.get("endpoint", "")).strip()
        if endpoint:
            attributes[_HTTP_ROUTE_ATTRIBUTE] = endpoint
        if record.name in {"ask_request", "legacy_rag", "workflow"}:
            attributes["experimentos.execution_mode"] = str(
                metadata.get("execution_mode", "workflow")
            )
        if record.name in _WORKFLOW_NODE_NAMES:
            attributes["experimentos.agent_name"] = record.name
        return {
            key: value
            for key, value in attributes.items()
            if _is_otel_safe_attribute_value(value)
        }

    def _build_output_attributes(self, record: BufferedSpanRecord) -> dict[str, object]:
        outputs = dict(redact_payload(record.outputs, settings=self.settings, is_output=True))
        attributes = _flatten_attribute_mapping("output", outputs)
        status_code = outputs.get("status_code")
        if type(status_code) is int:
            attributes[_HTTP_STATUS_CODE_ATTRIBUTE] = status_code
        return attributes

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

    def _record_metrics(self, record: BufferedSpanRecord) -> None:
        self._record_metric_for_record(record)
        for child in record.children:
            self._record_metrics(child)

    def _record_metric_for_record(self, record: BufferedSpanRecord) -> None:
        duration_ms = _duration_ms(record)
        outputs = record.outputs
        metadata = record.metadata

        if record.name == "ask_request":
            attributes = _metric_attributes(record)
            self._instruments["ask_requests_total"].add(1, attributes)
            self._instruments["ask_request_duration_ms"].record(duration_ms, attributes)
            self._record_citation_count(attributes, metadata, outputs)
            status_code = outputs.get("status_code")
            if record.error is not None or (type(status_code) is int and status_code >= 400):
                failure_attributes = dict(attributes)
                failure_attributes["status"] = "failed"
                self._instruments["ask_failures_total"].add(1, failure_attributes)
            return

        if record.name == "workflow":
            attributes = _metric_attributes(record)
            self._instruments["workflow_executions_total"].add(1, attributes)
            self._instruments["workflow_duration_ms"].record(duration_ms, attributes)
            self._record_citation_count(attributes, metadata, outputs)
            return

        if record.name == "retrieval":
            attributes = _metric_attributes(record, provider=_metric_provider_name(metadata))
            self._instruments["retrieval_requests_total"].add(1, attributes)
            self._instruments["retrieval_duration_ms"].record(duration_ms, attributes)
            retrieved_count = _first_number(
                metadata.get("retrieved_count"),
                outputs.get("retrieved_chunks"),
            )
            if retrieved_count is not None:
                self._instruments["retrieved_result_count"].record(retrieved_count, attributes)
            if bool(metadata.get("empty_retrieval")):
                self._instruments["empty_retrieval_total"].add(1, attributes)
            return

        if record.name == "llm_generation":
            attributes = _metric_attributes(record, provider=str(metadata.get("provider", "")))
            self._instruments["llm_duration_ms"].record(duration_ms, attributes)
            return

        if record.name.startswith("evaluation."):
            evaluation_type = record.name.split(".", 1)[1]
            attributes = _metric_attributes(record, evaluation_type=evaluation_type)
            self._instruments["evaluation_runs_total"].add(1, attributes)
            self._instruments["evaluation_duration_ms"].record(duration_ms, attributes)
            return

        if record.name in _WORKFLOW_NODE_NAMES:
            attributes = _metric_attributes(record, agent_name=record.name)
            self._instruments["agent_executions_total"].add(1, attributes)
            self._instruments["agent_duration_ms"].record(duration_ms, attributes)

    def _record_citation_count(
        self,
        attributes: dict[str, object],
        metadata: Mapping[str, object],
        outputs: Mapping[str, object],
    ) -> None:
        citation_count = _first_number(
            metadata.get("citation_count"),
            outputs.get("citation_count"),
        )
        if citation_count is not None:
            self._instruments["citation_count"].record(citation_count, attributes)

    def force_flush(self) -> bool:
        return self._run_lifecycle_hooks(
            "force_flush",
            timeout_millis=self.settings.export_timeout_ms,
        )

    def shutdown(self) -> bool:
        return self._run_lifecycle_hooks("shutdown")

    def _run_lifecycle_hooks(self, hook_name: str, **kwargs: object) -> bool:
        success = True
        for owner in (self._tracer_provider, self._meter_provider):
            if owner is None:
                continue
            hook = getattr(owner, hook_name, None)
            if hook is None:
                continue
            try:
                try:
                    result = hook(**kwargs)
                except TypeError:
                    result = hook()
                if result is False:
                    success = False
            except Exception:
                self.increment_failure()
                success = False
                if self.settings.strict:
                    raise
        return success

    def instrument_fastapi_app(self, app: object) -> bool:
        if (
            not self.settings.enabled
            or not self.settings.trace_enabled
            or not self.settings.instrument_fastapi
            or not self.settings.propagation_enabled
            or self._tracer_provider is None
        ):
            return False
        state = getattr(app, "state", None)
        if state is not None and getattr(state, _FASTAPI_APP_MARKER, False):
            return False
        instrumentor_cls = self._fastapi_instrumentor_cls
        if instrumentor_cls is None:
            instrumentor_cls = self._module_loader(
                "opentelemetry.instrumentation.fastapi"
            ).FastAPIInstrumentor
            self._fastapi_instrumentor_cls = instrumentor_cls
        instrumentor_cls.instrument_app(
            app,
            tracer_provider=self._tracer_provider,
            meter_provider=self._meter_provider,
            excluded_urls=self.settings.excluded_urls or None,
            http_capture_headers_server_request=[],
            http_capture_headers_server_response=[],
            http_capture_headers_sanitize_fields=["authorization", "cookie", "set-cookie"],
            exclude_spans=["receive", "send"],
            server_request_hook=_server_request_hook,
        )
        if state is not None:
            setattr(state, _FASTAPI_APP_MARKER, True)
        return True


class PhoenixObservabilityProvider(OpenTelemetryObservabilityProvider):
    def __init__(
        self,
        *,
        settings: PhoenixSettings,
        tracer_provider: object | None = None,
        meter_provider: object | None = None,
        tracer: object | None = None,
        meter: object | None = None,
        span_exporter: object | None = None,
        metric_reader: object | None = None,
        module_loader: Any | None = None,
        fastapi_instrumentor_cls: type[object] | None = None,
    ) -> None:
        otel_settings = OpenTelemetrySettings(
            enabled=settings.enabled,
            endpoint=None,
            environment=settings.environment,
            service_name="experimentos-ai",
            service_namespace="experimentos",
            service_version="0.1.0",
            exporter_type="none",
            protocol=settings.protocol,
            trace_enabled=True,
            metrics_enabled=False,
            propagation_enabled=True,
            instrument_fastapi=False,
            batch_export=True,
            sampling_rate=settings.sampling_rate,
            trace_inputs=settings.trace_inputs,
            trace_outputs=settings.trace_outputs,
            redact_sensitive_data=settings.redact_sensitive_data,
            tags=settings.tags,
            strict=settings.strict,
            always_trace_errors=settings.always_trace_errors,
            max_string_length=settings.max_string_length,
            max_collection_length=settings.max_collection_length,
            max_metadata_depth=settings.max_metadata_depth,
            max_retrieval_records=settings.max_retrieval_records,
        )
        super().__init__(
            settings=otel_settings,
            phoenix_settings=settings,
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            tracer=tracer,
            meter=meter,
            span_exporter=span_exporter,
            metric_reader=metric_reader,
            module_loader=module_loader,
            fastapi_instrumentor_cls=fastapi_instrumentor_cls,
        )


def _server_request_hook(span: object, scope: dict[str, object]) -> None:
    if span is None or not getattr(span, "is_recording", lambda: False)():
        return
    span.set_attribute("experimentos.execution_mode", "api")
    route = str(scope.get("path", "")).strip()
    if route:
        span.set_attribute("experimentos.http_path", route)


def _phoenix_headers(settings: PhoenixSettings) -> dict[str, str]:
    headers = {key.lower(): value for key, value in settings.headers}
    if settings.api_key and "authorization" not in headers:
        headers["authorization"] = f"Bearer {settings.api_key}"
    return headers


def _metrics_endpoint(endpoint: str | None) -> str | None:
    if endpoint is None:
        return None
    parsed = urlparse(endpoint)
    if parsed.path.endswith("/v1/traces"):
        return parsed._replace(path=parsed.path[:-len("/v1/traces")] + "/v1/metrics").geturl()
    return endpoint


def _span_kind(run_type: str, name: str) -> str:
    if run_type == "retriever":
        return "RETRIEVER"
    if run_type == "llm":
        return "LLM"
    if name == "prompt_rendering":
        return "PROMPT"
    if name.startswith("evaluation."):
        return "EVALUATOR"
    if name in {"ask_request", "workflow", "legacy_rag"}:
        return "AGENT"
    return "CHAIN"


def _experimentos_metadata_attributes(
    record: BufferedSpanRecord,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    workflow_id = metadata.get("workflow_execution_id") or metadata.get("legacy_rag_execution_id")
    attributes: dict[str, object] = {
        "experimentos.request_id": metadata.get("request_id", ""),
        "experimentos.execution_mode": metadata.get("execution_mode", ""),
        "experimentos.workflow_mode": metadata.get("workflow_mode", ""),
        "experimentos.ask_mode": metadata.get("ask_mode", ""),
        "experimentos.workflow_name": metadata.get("workflow", ""),
        "experimentos.workflow_id": workflow_id or "",
        "experimentos.intent": metadata.get("intent", ""),
        "experimentos.approval_status": metadata.get("approval_status", ""),
        "experimentos.prompt_id": metadata.get("prompt_id", ""),
        "experimentos.prompt_version": metadata.get("prompt_version", ""),
        "experimentos.experiment_id": metadata.get("experiment_id", ""),
        "experimentos.prompt.id": metadata.get("prompt_id", ""),
        "experimentos.prompt.version": metadata.get("prompt_version", ""),
        "experimentos.experiment.id": metadata.get("experiment_id", ""),
        "experimentos.experiment.variant": metadata.get("experiment_variant", ""),
        "experimentos.experiment.assignment_strategy": metadata.get(
            "assignment_strategy",
            "",
        ),
    }
    if record.name == "retrieval":
        attributes["experimentos.top_k"] = metadata.get("top_k", "")
        attributes["experimentos.empty_retrieval"] = metadata.get("empty_retrieval", False)
    return {
        key: value
        for key, value in attributes.items()
        if value not in {"", None} and _is_otel_safe_attribute_value(value)
    }


def _sanitize_input_attributes(
    record: BufferedSpanRecord,
    settings: OpenTelemetrySettings,
) -> dict[str, object]:
    inputs = dict(redact_payload(record.inputs, settings=settings))
    return _flatten_attribute_mapping("input", inputs)


def _tag_attributes(tags: Sequence[str]) -> dict[str, object]:
    if not tags:
        return {}
    normalized = [str(tag) for tag in tags if str(tag).strip()]
    if not normalized:
        return {}
    return {"experimentos.tags": normalized}


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
    if _is_otel_safe_attribute_value(value):
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


def _is_otel_safe_attribute_value(value: object) -> bool:
    primitive_types = (str, bool, int, float)
    if type(value) in primitive_types:
        return True
    if isinstance(value, list):
        if not value:
            return False
        first_type = type(value[0])
        if first_type not in primitive_types:
            return False
        return all(type(item) is first_type for item in value)
    return False


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


def _metric_attributes(
    record: BufferedSpanRecord,
    *,
    agent_name: str | None = None,
    evaluation_type: str | None = None,
    provider: str | None = None,
) -> dict[str, object]:
    metadata = record.metadata
    outputs = record.outputs
    raw_attributes: dict[str, object] = {
        "surface": metadata.get("surface", ""),
        "execution_mode": metadata.get("execution_mode", ""),
        "workflow_mode": metadata.get("workflow_mode", metadata.get("ask_mode", "")),
        "environment": metadata.get("environment", ""),
        "status": _metric_status(metadata, outputs, record),
        "agent_name": agent_name or "",
        "evaluation_type": evaluation_type or "",
        "provider": provider or "",
        "experiment_id": metadata.get("experiment_id", ""),
        "experiment_variant": metadata.get("experiment_variant", ""),
        "assignment_strategy": metadata.get("assignment_strategy", ""),
    }
    attributes: dict[str, object] = {}
    for key in _METRIC_ATTRIBUTE_KEYS:
        value = raw_attributes.get(key)
        if value in {"", None}:
            continue
        if _is_otel_safe_attribute_value(value):
            attributes[key] = value
    return attributes


def _metric_status(
    metadata: Mapping[str, object],
    outputs: Mapping[str, object],
    record: BufferedSpanRecord,
) -> str:
    if record.error is not None:
        return "error"
    for key in _STATUS_ATTRIBUTE_KEYS:
        value = outputs.get(key)
        if value not in {None, ""}:
            return str(value)
    for key in _STATUS_ATTRIBUTE_KEYS:
        value = metadata.get(key)
        if value not in {None, ""}:
            return str(value)
    return record.status


def _metric_provider_name(metadata: Mapping[str, object]) -> str:
    for key in ("provider", "embedding_provider", "provider_model"):
        value = metadata.get(key)
        if value not in {None, ""}:
            return str(value)
    return ""


def _duration_ms(record: BufferedSpanRecord) -> float:
    if record.ended_at is None:
        return 0.0
    started = _parse_utc(record.started_at)
    ended = _parse_utc(record.ended_at)
    return max((ended - started).total_seconds() * 1000.0, 0.0)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _first_number(*values: object) -> int | float | None:
    for value in values:
        if type(value) in {int, float}:
            return value
    return None


def _error_message(record: BufferedSpanRecord) -> str | None:
    if record.error is None:
        return None
    error_type = str(record.error.get("type", "Error")).strip()
    message = str(record.error.get("message", "")).strip()
    return f"{error_type}: {message}".strip(": ")
