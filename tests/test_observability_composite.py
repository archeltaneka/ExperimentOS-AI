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
