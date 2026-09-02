"""In-memory privacy evaluation for statistical reliability fixtures."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

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
    "raw_panel_observations",
    "raw_score_arrays",
    "rows",
    "outcome",
    "propensity_score",
    "scores",
    "sequential_rows",
    "treatment_assignments",
    "treatment_values",
    "treated",
    "unit_id",
    "treatment_prior",
    "unit_identifiers",
    "unit_level_weights",
    "weights",
}
_UNIT_IDENTIFIER = re.compile(
    r"(?:"
    r"(?:account|unit|user|customer|subject|participant|record|low|high|sep|tail|c|t)"
    r"[-_][A-Za-z0-9_-]+"
    r"|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
    r"|[^@\s]+@[^@\s]+\.[^@\s]+"
    r")"
)


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
    violations = telemetry_privacy_violations(tuple(provider.records))
    if len(provider.records) != 1:
        violations = tuple(sorted((*violations, "invalid_record_count")))
    return not violations, violations


def telemetry_privacy_violations(
    records: tuple[BufferedSpanRecord, ...],
) -> tuple[str, ...]:
    """Return stable violations found in complete nested telemetry payloads."""
    violations: set[str] = set()
    for record in records:
        _inspect_value(_record_payload(record), violations)
    return tuple(sorted(violations))


def _record_payload(record: BufferedSpanRecord) -> dict[str, object]:
    return {
        "inputs": record.inputs,
        "metadata": record.metadata,
        "outputs": record.outputs,
        "error": record.error,
        "children": tuple(_record_payload(child) for child in record.children),
    }


def _inspect_value(value: object, violations: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _normalize_key(str(key))
            if normalized in FORBIDDEN_TELEMETRY_KEYS:
                violations.add(f"forbidden_key:{normalized}")
            _inspect_value(item, violations)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if value and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
        ):
            violations.add("forbidden_value:numeric_sequence")
        for item in value:
            _inspect_value(item, violations)
        return
    if isinstance(value, str) and _UNIT_IDENTIFIER.fullmatch(value):
        violations.add("forbidden_value:unit_identifier")


def _normalize_key(key: str) -> str:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", separated).strip("_").lower()
    return re.sub(r"_+", "_", normalized)


__all__ = ["evaluate_fixture_telemetry_privacy", "telemetry_privacy_violations"]
