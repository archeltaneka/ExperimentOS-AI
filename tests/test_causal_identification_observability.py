from __future__ import annotations

from collections.abc import Mapping

from packages.experiments.analysis import CausalIdentificationService
from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.causal_identification_fixtures import request


class RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


def test_identification_telemetry_is_aggregate_and_private() -> None:
    provider = RecordingProvider()
    result = CausalIdentificationService(observability_provider=provider).identify(request())

    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.metadata["design_type"] == "generic_observational"
    assert record.metadata["estimand"] == "ate"
    assert record.metadata["identification_status"] == result.status.value
    assert record.metadata["adjustment_variable_count"] == 1
    assert record.metadata["effect_modifier_count"] == 0
    assert isinstance(record.metadata["assumption_codes"], tuple)
    assert isinstance(record.metadata["diagnostic_codes"], tuple)
    assert isinstance(record.metadata["duration_ms"], float)

    forbidden = {
        "raw_covariates",
        "raw_treatment",
        "raw_outcome",
        "treated_value",
        "control_value",
        "causal_graph",
        "graph_edges",
        "rows",
    }
    assert forbidden.isdisjoint(_nested_keys(_record_payload(record)))


def _record_payload(record: BufferedSpanRecord) -> dict[str, object]:
    return {
        "inputs": record.inputs,
        "metadata": record.metadata,
        "outputs": record.outputs,
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
