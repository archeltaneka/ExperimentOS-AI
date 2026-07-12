from __future__ import annotations


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


def test_phoenix_provider_exports_manual_span_tree_with_safe_attributes() -> None:
    from packages.observability.models import PhoenixSettings
    from packages.observability.phoenix import PhoenixObservabilityProvider

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
            pass

        def record_exception(self, exc: Exception) -> None:
            pass

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
            project="experimentos-local",
            endpoint="http://127.0.0.1:6006",
            sampling_rate=1.0,
        ),
        tracer_provider=object(),
        tracer=FakeTracer(),
    )

    root = provider.start_root_span(
        "ask_request",
        trace_id="req-123",
        inputs={"question": "hello", "prompt": "hide me"},
        metadata={"surface": "ask", "request_id": "req-123"},
        tags=("ask",),
    )
    child = root.start_child("retrieval", run_type="retriever", metadata={"top_k": 3})
    child.finish(outputs={"retrieved_chunks": 2})
    root.finish(outputs={"answer": "hide me too", "status": "completed"})

    span_names = [name for name, _attrs in exported]
    assert "ask_request" in span_names
    assert "retrieval" in span_names
    assert any(attrs.get("experimentos.trace_id") == "req-123" for _name, attrs in exported)
    assert all("hide me" not in str(attrs) for _name, attrs in exported)


def test_phoenix_provider_flattens_or_serializes_nested_attributes_to_otel_safe_values() -> None:
    from packages.observability.models import PhoenixSettings
    from packages.observability.phoenix import PhoenixObservabilityProvider

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
            project="experimentos-local",
            endpoint="http://127.0.0.1:6006",
            sampling_rate=1.0,
            trace_outputs=True,
        ),
        tracer_provider=object(),
        tracer=FakeTracer(),
    )

    root = provider.start_root_span(
        "ask_request",
        trace_id="req-456",
        inputs={
            "question": "hello",
            "options": {"limit": 3, "filters": ["a", "b"]},
            "mixed_values": [1, "two"],
        },
        metadata={
            "surface": "ask",
            "request_context": {"top_k": 3, "flags": [True, False]},
        },
    )
    root.finish(
        outputs={
            "metrics": {"latency_ms": 12.5, "labels": ["fast", "local"]},
            "mixed_values": [1, "two"],
        }
    )

    assert exported
    assert any(
        "experimentos.metadata.request_context.top_k" in attrs for _name, attrs in exported
    )
    assert any("input.options.limit" in attrs for _name, attrs in exported)
    assert any("output.metrics.latency_ms" in attrs for _name, attrs in exported)
    for _name, attrs in exported:
        assert all(_is_otel_safe_attribute_value(value) for value in attrs.values())


def test_phoenix_provider_with_injected_tracer_does_not_import_trace_api_during_emit() -> None:
    from packages.observability.models import PhoenixSettings
    from packages.observability.phoenix import PhoenixObservabilityProvider

    statuses: list[object] = []

    class FakeSpan:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def set_status(self, status) -> None:
            statuses.append(status)

        def record_exception(self, exc: Exception) -> None:
            return None

        def set_attributes(self, attributes: dict[str, object]) -> None:
            return None

    class FakeTracer:
        def start_as_current_span(
            self,
            name: str,
            attributes: dict[str, object] | None = None,
        ):
            return FakeSpan()

    def forbidden_loader(name: str) -> object:
        raise AssertionError(f"unexpected module load during emit: {name}")

    provider = PhoenixObservabilityProvider(
        settings=PhoenixSettings(
            enabled=True,
            project="experimentos-local",
            endpoint="http://127.0.0.1:6006",
        ),
        tracer_provider=object(),
        tracer=FakeTracer(),
        module_loader=forbidden_loader,
    )

    root = provider.start_root_span("ask_request", trace_id="req-789")
    root.finish(outputs={"status": "completed"})

    assert statuses == ["OK"]


def test_phoenix_provider_force_flush_and_shutdown_use_tracer_provider() -> None:
    from packages.observability.models import PhoenixSettings
    from packages.observability.phoenix import PhoenixObservabilityProvider

    class FakeTracerProvider:
        def __init__(self) -> None:
            self.flushed = False
            self.stopped = False

        def force_flush(self, timeout_millis: int | None = None) -> bool:
            self.flushed = True
            return True

        def shutdown(self) -> bool:
            self.stopped = True
            return True

    fake = FakeTracerProvider()
    provider = PhoenixObservabilityProvider(
        settings=PhoenixSettings(
            enabled=True,
            project="experimentos-local",
            endpoint="http://127.0.0.1:6006",
        ),
        tracer_provider=fake,
        tracer=object(),
    )

    assert provider.force_flush() is True
    assert provider.shutdown() is True
    assert fake.flushed is True
    assert fake.stopped is True
