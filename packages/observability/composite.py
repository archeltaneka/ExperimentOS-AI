from __future__ import annotations

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings


class CompositeObservabilityProvider(BaseObservabilityProvider):
    def __init__(self, providers: list[BaseObservabilityProvider]) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.providers = providers

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        for provider in self.providers:
            try:
                provider._emit_root(record)
            except Exception:
                provider.increment_failure()
                self.increment_failure()
                if provider.settings.strict:
                    raise

    def force_flush(self) -> bool:
        return all(provider.force_flush() for provider in self.providers)

    def shutdown(self) -> bool:
        return all(provider.shutdown() for provider in self.providers)
