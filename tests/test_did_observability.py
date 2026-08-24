"""Low-cardinality privacy and failure isolation for DiD telemetry."""

from __future__ import annotations

from packages.experiments.analysis.causal.did import DifferenceInDifferencesService
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.causal_identification_fixtures import provenance
from tests.did_fixtures import did_execution, did_table, positive_effect_rows


class RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


class FailingStartProvider(RecordingProvider):
    def start_root_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        run_type: str = "chain",
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
    ) -> BufferedSpan:
        raise RuntimeError("provider unavailable")


def test_completed_analysis_emits_only_controlled_aggregate_metadata() -> None:
    provider = RecordingProvider()

    result = DifferenceInDifferencesService(observability_provider=provider).analyze(
        did_execution(),
        did_table(positive_effect_rows()),
        provenance=provenance("did-input"),
    )

    assert result.status.value == "completed"
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "difference_in_differences"
    assert record.inputs == {"row_count": 40}
    assert record.metadata["method"] == "did"
    assert record.metadata["status"] == "completed"
    assert record.metadata["estimand_type"] == "did_att"
    assert record.metadata["panel_type"] == "balanced"
    assert record.metadata["cluster_robust"] is True
    assert record.metadata["cluster_count"] == 20
    assert record.metadata["pretrend_available"] is False
    assert record.metadata["diagnostic_codes"] == ("did.few_clusters",)
    assert isinstance(record.metadata["duration_ms"], float)
    assert record.outputs == {"status": "completed", "did_completed": True}
    rendered = repr((record.inputs, record.metadata, record.outputs, record.error))
    for private in ("t-01", "c-01", "19.5", "unit_id", "outcome", "treatment_start"):
        assert private not in rendered


def test_provider_failure_does_not_change_statistical_result() -> None:
    provider = FailingStartProvider()

    result = DifferenceInDifferencesService(observability_provider=provider).analyze(
        did_execution(),
        did_table(positive_effect_rows()),
        provenance=provenance("did-input"),
    )

    assert result.status.value == "completed"
    assert provider.failure_count == 1
