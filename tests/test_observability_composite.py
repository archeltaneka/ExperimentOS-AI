from __future__ import annotations


def test_composite_provider_isolates_provider_failures() -> None:
    from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
    from packages.observability.composite import CompositeObservabilityProvider
    from packages.observability.models import ProviderSettings

    class RecordingProvider(BaseObservabilityProvider):
        def __init__(self) -> None:
            super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
            self.records: list[BufferedSpanRecord] = []

        def _emit_root(self, record: BufferedSpanRecord) -> None:
            self.records.append(record)

    class FailingProvider(RecordingProvider):
        def _emit_root(self, record: BufferedSpanRecord) -> None:
            raise RuntimeError("boom")

    good = RecordingProvider()
    bad = FailingProvider()
    provider = CompositeObservabilityProvider([good, bad])

    root = provider.start_root_span("ask_request", trace_id="req-123")
    root.finish(outputs={"status": "ok"})

    assert len(good.records) == 1
    assert provider.failure_count == 1
    assert bad.failure_count == 1


def test_composite_provider_preserves_per_provider_emit_gating() -> None:
    from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
    from packages.observability.composite import CompositeObservabilityProvider
    from packages.observability.models import ProviderSettings

    class RecordingProvider(BaseObservabilityProvider):
        def __init__(self, *, sampling_rate: float) -> None:
            super().__init__(ProviderSettings(enabled=True, sampling_rate=sampling_rate))
            self.records: list[BufferedSpanRecord] = []

        def _emit_root(self, record: BufferedSpanRecord) -> None:
            self.records.append(record)

    always = RecordingProvider(sampling_rate=1.0)
    never = RecordingProvider(sampling_rate=0.0)
    provider = CompositeObservabilityProvider([always, never])

    root = provider.start_root_span("ask_request", trace_id="req-123")
    root.finish(outputs={"status": "ok"})

    assert len(always.records) == 1
    assert never.records == []


def test_composite_provider_force_flush_and_shutdown_do_not_short_circuit() -> None:
    from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
    from packages.observability.composite import CompositeObservabilityProvider
    from packages.observability.models import ProviderSettings

    class LifecycleProvider(BaseObservabilityProvider):
        def __init__(self, *, flush_result: bool = True, shutdown_result: bool = True) -> None:
            super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
            self.flush_result = flush_result
            self.shutdown_result = shutdown_result
            self.flush_calls = 0
            self.shutdown_calls = 0

        def _emit_root(self, record: BufferedSpanRecord) -> None:
            return None

        def force_flush(self) -> bool:
            self.flush_calls += 1
            return self.flush_result

        def shutdown(self) -> bool:
            self.shutdown_calls += 1
            return self.shutdown_result

    class FailingLifecycleProvider(LifecycleProvider):
        def force_flush(self) -> bool:
            self.flush_calls += 1
            raise RuntimeError("flush boom")

        def shutdown(self) -> bool:
            self.shutdown_calls += 1
            raise RuntimeError("shutdown boom")

    falsey = LifecycleProvider(flush_result=False, shutdown_result=False)
    failing = FailingLifecycleProvider()
    truthy = LifecycleProvider()
    provider = CompositeObservabilityProvider([falsey, failing, truthy])

    assert provider.force_flush() is False
    assert provider.shutdown() is False
    assert falsey.flush_calls == 1
    assert failing.flush_calls == 1
    assert truthy.flush_calls == 1
    assert falsey.shutdown_calls == 1
    assert failing.shutdown_calls == 1
    assert truthy.shutdown_calls == 1
    assert failing.failure_count == 2
    assert provider.failure_count == 2
