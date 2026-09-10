"""Privacy-safe aggregate observability for heterogeneous effects."""

from __future__ import annotations

from packages.evals.statistical.telemetry import telemetry_privacy_violations
from packages.experiments.analysis.causal import MeasurementTiming
from packages.experiments.analysis.causal.hte.service import HeterogeneousEffectEstimator
from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.causal_identification_fixtures import provenance
from tests.hte_fixtures import effect_rows, hte_execution, hte_modifier, hte_table


class RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


def test_hte_success_telemetry_contains_only_aggregate_dimensions() -> None:
    provider = RecordingProvider()
    HeterogeneousEffectEstimator(observability_provider=provider).analyze(
        hte_execution(fold_count=4), hte_table(effect_rows()), provenance=provenance("telemetry")
    )

    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "heterogeneous_treatment_effects"
    assert record.inputs == {"row_count": 160}
    assert set(record.metadata) == {
        "method",
        "estimand",
        "modifier_type",
        "subgroup_count",
        "global_heterogeneity_status",
        "multiplicity_method",
        "pre_specification_status",
        "abstained_group_count",
        "overlap_failure_count",
        "status",
        "diagnostic_codes",
        "retained_count",
        "duration_ms",
    }
    assert record.outputs == {"status": "completed", "hte_completed": True}
    assert telemetry_privacy_violations((record,)) == ()


def test_hte_invalid_telemetry_never_includes_modifier_membership_or_values() -> None:
    provider = RecordingProvider()
    modifier = hte_modifier(timing=MeasurementTiming.POST_TREATMENT)
    HeterogeneousEffectEstimator(observability_provider=provider).analyze(
        hte_execution(modifier=modifier),
        hte_table(effect_rows()),
        provenance=provenance("invalid-telemetry"),
    )

    assert len(provider.records) == 1
    assert provider.records[0].metadata["status"] == "invalid"
    rendered = repr(provider.records[0])
    for forbidden in ("ID-000", "SG-000", "outcome", "treated", "prior_orders"):
        assert forbidden not in rendered
    assert telemetry_privacy_violations((provider.records[0],)) == ()
