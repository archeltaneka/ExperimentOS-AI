from __future__ import annotations

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings


class NoOpObservabilityProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings())

    def _should_emit(self, record: BufferedSpanRecord) -> bool:
        return False

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        return None


class PhoenixObservabilityProvider(BaseObservabilityProvider):
    def _emit_root(self, record: BufferedSpanRecord) -> None:
        return None


class CompositeObservabilityProvider(BaseObservabilityProvider):
    def __init__(self, providers: list[BaseObservabilityProvider]) -> None:
        super().__init__(ProviderSettings(enabled=bool(providers)))
        self._providers = providers

    def _should_emit(self, record: BufferedSpanRecord) -> bool:
        return bool(self._providers)

    def _finish_root(self, record: BufferedSpanRecord) -> None:
        for provider in self._providers:
            provider._finish_root(record)

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        return None
