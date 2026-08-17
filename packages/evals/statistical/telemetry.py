"""In-memory privacy evaluation for statistical reliability fixtures."""

from __future__ import annotations

from collections.abc import Mapping

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings

from .fixtures import run_statistical_fixture
from .models import StatisticalReferenceCase

FORBIDDEN_TELEMETRY_KEYS = {
    "adjusted_outcomes",
    "control_prior",
    "credentials",
    "outcomes",
    "posterior_draws",
    "raw_covariates",
    "raw_outcomes",
    "rows",
    "sequential_rows",
    "treatment_assignments",
    "treatment_prior",
}


class _RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


def evaluate_fixture_telemetry_privacy(
    case: StatisticalReferenceCase,
) -> tuple[bool, tuple[str, ...]]:
    """Execute one fixture with in-memory telemetry and inspect its complete payload."""
    provider = _RecordingProvider()
    run_statistical_fixture(case, observability_provider=provider)
    keys = set().union(
        *(_nested_keys(_record_payload(record)) for record in provider.records), set()
    )
    violations = tuple(sorted(keys & FORBIDDEN_TELEMETRY_KEYS))
    return not violations and len(provider.records) == 1, violations


def _record_payload(record: BufferedSpanRecord) -> dict[str, object]:
    return {
        "inputs": record.inputs,
        "metadata": record.metadata,
        "outputs": record.outputs,
        "error": record.error,
        "children": tuple(_record_payload(child) for child in record.children),
    }


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return {str(key) for key in value} | set().union(
            *(_nested_keys(item) for item in value.values()),
            set(),
        )
    if isinstance(value, (list, tuple)):
        return set().union(*(_nested_keys(item) for item in value), set())
    return set()


__all__ = ["evaluate_fixture_telemetry_privacy"]
