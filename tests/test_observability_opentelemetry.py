from __future__ import annotations

from collections.abc import Iterable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _iter_metrics(metrics_data) -> Iterable[object]:
    for resource_metrics in metrics_data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            yield from scope_metrics.metrics


def _iter_data_points(metric) -> Iterable[object]:
    data = metric.data
    if hasattr(data, "data_points"):
        yield from data.data_points


def test_load_observability_settings_reads_opentelemetry_defaults(monkeypatch) -> None:
    from packages.observability.models import load_observability_settings

    monkeypatch.delenv("EXPERIMENTOS_OTEL_ENABLED", raising=False)
    monkeypatch.delenv("EXPERIMENTOS_OTEL_EXPORTER_TYPE", raising=False)
    monkeypatch.delenv("EXPERIMENTOS_OTEL_TRACE_ENABLED", raising=False)
    monkeypatch.delenv("EXPERIMENTOS_OTEL_METRICS_ENABLED", raising=False)
    monkeypatch.delenv("EXPERIMENTOS_OTEL_PROPAGATION_ENABLED", raising=False)

    settings = load_observability_settings()

    assert settings.otel.enabled is False
    assert settings.otel.exporter_type == "none"
    assert settings.otel.trace_enabled is True
    assert settings.otel.metrics_enabled is True
    assert settings.otel.propagation_enabled is True
    assert settings.otel.service_name == "experimentos-ai"


def test_resolve_provider_returns_opentelemetry_provider_when_enabled(monkeypatch) -> None:
    from packages.observability.factory import resolve_observability_provider
    from packages.observability.opentelemetry import OpenTelemetryObservabilityProvider

    monkeypatch.setenv("EXPERIMENTOS_OTEL_ENABLED", "true")
    monkeypatch.setenv("EXPERIMENTOS_OTEL_EXPORTER_TYPE", "console")
    monkeypatch.setenv("EXPERIMENTOS_OTEL_TRACE_ENABLED", "true")
    monkeypatch.setenv("EXPERIMENTOS_OTEL_METRICS_ENABLED", "false")

    provider = resolve_observability_provider()

    assert isinstance(provider, OpenTelemetryObservabilityProvider)


def test_opentelemetry_provider_exports_manual_span_tree_with_in_memory_exporter() -> None:
    from packages.observability.models import OpenTelemetrySettings
    from packages.observability.opentelemetry import OpenTelemetryObservabilityProvider

    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    provider = OpenTelemetryObservabilityProvider(
        settings=OpenTelemetrySettings(
            enabled=True,
            exporter_type="in_memory",
            trace_enabled=True,
            metrics_enabled=True,
            service_name="experimentos-ai",
            service_version="0.1.0",
            environment="test",
            instrument_fastapi=False,
        ),
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )

    root = provider.start_root_span(
        "ask_request",
        trace_id="req-otel-123",
        inputs={"question": "Should we ship this experiment?"},
        metadata={
            "surface": "ask",
            "request_id": "req-otel-123",
            "execution_mode": "api",
        },
        tags=("ask", "agent_workflow"),
    )
    child = root.start_child(
        "retrieval",
        run_type="retriever",
        metadata={
            "surface": "retrieval",
            "top_k": 3,
            "retrieved_count": 2,
            "empty_retrieval": False,
            "retrieval_latency_ms": 12.5,
        },
    )
    child.finish(
        outputs={
            "status": "completed",
            "retrieved_chunks": 2,
            "retrieval_latency_ms": 12.5,
        }
    )
    root.finish(outputs={"status_code": 200, "success": True})

    assert provider.force_flush() is True

    spans = span_exporter.get_finished_spans()
    span_names = [span.name for span in spans]
    assert span_names == ["retrieval", "ask_request"]
    ask_span = spans[-1]
    retrieval_span = spans[0]
    assert retrieval_span.parent is not None
    assert retrieval_span.parent.span_id == ask_span.context.span_id
    assert retrieval_span.context.trace_id == ask_span.context.trace_id
    assert ask_span.attributes["experimentos.trace_id"] == "req-otel-123"
    assert ask_span.attributes["experimentos.request_id"] == "req-otel-123"
    assert ask_span.attributes["experimentos.execution_mode"] == "api"


def test_opentelemetry_provider_records_metrics_with_controlled_attributes_only() -> None:
    from packages.observability.models import OpenTelemetrySettings
    from packages.observability.opentelemetry import OpenTelemetryObservabilityProvider

    provider = OpenTelemetryObservabilityProvider(
        settings=OpenTelemetrySettings(
            enabled=True,
            exporter_type="in_memory",
            trace_enabled=False,
            metrics_enabled=True,
            service_name="experimentos-ai",
            instrument_fastapi=False,
        ),
        metric_reader=InMemoryMetricReader(),
    )

    root = provider.start_root_span(
        "ask_request",
        trace_id="req-cardinality",
        metadata={
            "surface": "ask",
            "request_id": "req-cardinality",
            "execution_mode": "api",
            "ask_mode": "agent_workflow",
        },
    )
    retrieval = root.start_child(
        "retrieval",
        run_type="retriever",
        metadata={
            "surface": "retrieval",
            "embedding_provider": "fake",
            "embedding_model": "fake-embedding",
            "top_k": 5,
            "retrieved_count": 0,
            "empty_retrieval": True,
            "request_id": "req-cardinality",
            "query": "never allow raw user text in metrics",
        },
    )
    retrieval.finish(outputs={"status": "completed", "retrieved_chunks": 0})
    root.finish(outputs={"status_code": 200, "success": True})

    assert provider.force_flush() is True

    metrics_data = provider.metric_reader.get_metrics_data()
    metrics = {metric.name: metric for metric in _iter_metrics(metrics_data)}
    assert "ask_requests_total" in metrics
    assert "retrieval_requests_total" in metrics
    for metric in metrics.values():
        for point in _iter_data_points(metric):
            assert "request_id" not in point.attributes
            assert "question" not in point.attributes
            assert "query" not in point.attributes
            assert "experimentos.trace_id" not in point.attributes


def test_opentelemetry_provider_records_prompt_experiment_attributes_safely() -> None:
    from packages.observability.models import OpenTelemetrySettings
    from packages.observability.opentelemetry import OpenTelemetryObservabilityProvider

    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    provider = OpenTelemetryObservabilityProvider(
        settings=OpenTelemetrySettings(
            enabled=True,
            exporter_type="in_memory",
            trace_enabled=True,
            metrics_enabled=True,
            service_name="experimentos-ai",
            service_version="0.1.0",
            environment="test",
            instrument_fastapi=False,
        ),
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )

    root = provider.start_root_span(
        "evaluation.prompt_experiment",
        trace_id="exp-trace",
        metadata={
            "surface": "evaluation.prompt_experiment",
            "execution_mode": "evaluation",
            "environment": "test",
            "experiment_id": "rag-answer-abstention-v1-v2",
            "experiment_variant": "treatment_2",
            "assignment_strategy": "deterministic_hash",
            "assignment_key_hash": "never-emit-this",
        },
    )
    root.finish(outputs={"status": "completed"})

    assert provider.force_flush() is True

    spans = span_exporter.get_finished_spans()
    attributes = spans[0].attributes
    assert attributes["experimentos.experiment.id"] == "rag-answer-abstention-v1-v2"
    assert attributes["experimentos.experiment.variant"] == "treatment_2"
    assert attributes["experimentos.experiment.assignment_strategy"] == "deterministic_hash"
    assert "experimentos.metadata.assignment_key_hash" not in attributes

    metrics_data = provider.metric_reader.get_metrics_data()
    for metric in _iter_metrics(metrics_data):
        for point in _iter_data_points(metric):
            assert "assignment_key_hash" not in point.attributes


def test_opentelemetry_fastapi_instrumentation_preserves_transport_parent_context() -> None:
    from packages.observability.models import OpenTelemetrySettings
    from packages.observability.opentelemetry import OpenTelemetryObservabilityProvider

    app = FastAPI()
    span_exporter = InMemorySpanExporter()
    provider = OpenTelemetryObservabilityProvider(
        settings=OpenTelemetrySettings(
            enabled=True,
            exporter_type="in_memory",
            trace_enabled=True,
            metrics_enabled=False,
            service_name="experimentos-ai",
            instrument_fastapi=True,
            excluded_urls="^/health$",
        ),
        span_exporter=span_exporter,
    )
    provider.instrument_fastapi_app(app)

    @app.post("/ask")
    async def ask() -> dict[str, str]:
        root = provider.start_root_span(
            "ask_request",
            trace_id="req-http-parent",
            metadata={
                "surface": "ask",
                "request_id": "req-http-parent",
                "execution_mode": "api",
            },
        )
        with root.activate():
            root.finish(outputs={"status_code": 200, "success": True})
        return {"status": "ok"}

    client = TestClient(app)
    response = client.post(
        "/ask",
        headers={
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        },
    )

    assert response.status_code == 200
    assert provider.force_flush() is True

    spans = span_exporter.get_finished_spans()
    ask_spans = [span for span in spans if span.name == "ask_request"]
    transport_spans = [span for span in spans if span.name != "ask_request"]
    assert len(ask_spans) == 1
    assert len(transport_spans) == 1
    assert ask_spans[0].context.trace_id == transport_spans[0].context.trace_id
    assert ask_spans[0].parent is not None
    assert ask_spans[0].parent.span_id == transport_spans[0].context.span_id
