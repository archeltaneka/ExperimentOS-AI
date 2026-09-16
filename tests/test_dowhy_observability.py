from __future__ import annotations

from packages.experiments.analysis.causal.dowhy.adapter import DoWhyAdapter
from packages.experiments.analysis.causal.dowhy.dependency import DoWhyBackend
from tests.causal_identification_fixtures import provenance
from tests.dowhy_fixtures import execution
from tests.test_causal_identification_observability import (
    RecordingProvider,
    _nested_keys,
    _record_payload,
)
from tests.test_dowhy_identification import _Model


def test_dowhy_telemetry_is_aggregate_and_private(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    monkeypatch.setattr(
        adapter.dependency, "load_dowhy", lambda: DoWhyBackend(CausalModel=_Model, version="0.14")
    )
    provider = RecordingProvider()
    result = DoWhyAdapter(observability_provider=provider).analyze(
        execution(), provenance=provenance()
    )
    assert len(provider.records) == 1
    metadata = provider.records[0].metadata
    assert metadata["adapter"] == "dowhy"
    assert metadata["operation"] == "identification"
    assert metadata["status"] == result.status.value
    assert metadata["graph_node_count"] == 3
    forbidden = {"rows", "causal_graph", "graph_edges", "treated", "outcome", "prior_orders"}
    assert forbidden.isdisjoint(_nested_keys(_record_payload(provider.records[0])))
