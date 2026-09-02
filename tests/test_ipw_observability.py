"""Low-cardinality telemetry and provider-failure isolation for IPW."""

from __future__ import annotations

from packages.experiments.analysis.causal.ipw import IPWTreatmentEffectEstimator
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.causal_identification_fixtures import provenance
from tests.ipw_fixtures import ipw_execution, ipw_table


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


def run(provider: BaseObservabilityProvider):
    return IPWTreatmentEffectEstimator(observability_provider=provider).analyze(
        ipw_execution(),
        ipw_table(),
        provenance=provenance("ipw-observability"),
    )


def test_ipw_emits_only_controlled_aggregate_metadata() -> None:
    provider = RecordingProvider()

    result = run(provider)

    assert result.status.value == "completed"
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "ipw_treatment_effect"
    assert record.inputs == {"row_count": 80}
    assert set(record.metadata) == {
        "design",
        "method",
        "estimand",
        "stabilization_enabled",
        "clipping_enabled",
        "overlap_status",
        "ess_status",
        "balance_status",
        "outcome_type",
        "status",
        "identification_status",
        "overlap_gate_status",
        "raw_sample_count",
        "selected_sample_count",
        "diagnostic_codes",
        "assumption_codes",
        "duration_ms",
    }
    assert record.metadata["method"] == "ipw"
    assert record.outputs == {"status": "completed", "estimate_available": True}
    rendered = repr((record.inputs, record.metadata, record.outputs, record.error))
    for private in (
        "low-t-00",
        "conversion",
        "account_id",
        "prior_orders",
        "raw_weights",
    ):
        assert private not in rendered


def test_provider_failure_does_not_change_ipw_result() -> None:
    baseline = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(),
        ipw_table(),
        provenance=provenance("ipw-observability"),
    )
    provider = FailingStartProvider()

    result = run(provider)

    assert result == baseline
    assert provider.failure_count == 1
