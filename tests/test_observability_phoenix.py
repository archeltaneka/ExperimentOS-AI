from __future__ import annotations


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
