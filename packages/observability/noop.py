from __future__ import annotations

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ObservabilitySettings


class NoOpObservabilityProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ObservabilitySettings())

    def _should_emit(self, record: BufferedSpanRecord) -> bool:
        return False

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        return None
