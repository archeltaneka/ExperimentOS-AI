from __future__ import annotations

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings


class CompositeObservabilityProvider(BaseObservabilityProvider):
    def __init__(self, providers: list[BaseObservabilityProvider]) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.providers = providers

    def _finish_root(self, record: BufferedSpanRecord) -> None:
        for provider in self.providers:
            before_failures = provider.failure_count
            try:
                provider._finish_root(record)
            except Exception:
                if provider.failure_count == before_failures:
                    provider.increment_failure()
                self.increment_failure()
                if provider.settings.strict:
                    raise
            else:
                for _ in range(provider.failure_count - before_failures):
                    self.increment_failure()

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        return None

    def force_flush(self) -> bool:
        return self._run_lifecycle_hook("force_flush")

    def shutdown(self) -> bool:
        return self._run_lifecycle_hook("shutdown")

    def _run_lifecycle_hook(self, hook_name: str) -> bool:
        success = True
        for provider in self.providers:
            hook = getattr(provider, hook_name)
            try:
                if not hook():
                    success = False
            except Exception:
                provider.increment_failure()
                self.increment_failure()
                success = False
        return success
