"""Low-cardinality privacy and provider-failure isolation for propensity telemetry."""

from __future__ import annotations

from packages.experiments.analysis.causal.propensity import (
    DeterministicLogisticPropensityEstimator,
)
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.causal_identification_fixtures import provenance
from tests.propensity_fixtures import (
    good_overlap_rows,
    propensity_execution,
    propensity_table,
)


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
    return DeterministicLogisticPropensityEstimator(observability_provider=provider).fit_predict(
        propensity_execution(),
        propensity_table(good_overlap_rows()),
        provenance=provenance("propensity-observability"),
    )


def test_service_emits_only_controlled_aggregate_metadata() -> None:
    provider = RecordingProvider()

    result = run(provider)

    assert result.status.value == "completed"
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "propensity_score_diagnostics"
    assert record.inputs == {"row_count": 60}
    assert set(record.metadata) == {
        "method",
        "estimand",
        "model_family",
        "status",
        "convergence_status",
        "overlap_status",
        "ess_status",
        "weighting_enabled",
        "trimming_enabled",
        "capping_enabled",
        "diagnostic_codes",
        "duration_ms",
    }
    assert record.metadata["method"] == "propensity"
    assert record.metadata["estimand"] == "ate"
    assert record.metadata["model_family"] == "regularized_logistic_regression"
    assert record.outputs == {"status": "completed", "scores_valid": True}
    rendered = repr((record.inputs, record.metadata, record.outputs, record.error))
    for private in (
        "c-00",
        "t-00",
        "prior_orders",
        "country",
        "account_id",
        "model_matrix",
        "balance_matrix",
        "raw_weights",
        "coefficients",
    ):
        assert private not in rendered


def test_provider_failure_does_not_change_propensity_result() -> None:
    baseline = DeterministicLogisticPropensityEstimator().fit_predict(
        propensity_execution(),
        propensity_table(good_overlap_rows()),
        provenance=provenance("propensity-observability"),
    )
    provider = FailingStartProvider()

    result = run(provider)

    assert result == baseline
    assert provider.failure_count == 1
