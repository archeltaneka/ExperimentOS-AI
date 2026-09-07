"""Privacy-safe aggregate observability for DML."""

from __future__ import annotations

from packages.experiments.analysis.causal.dml import DoubleMachineLearningEstimator
from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_table
from tests.test_dml_service import _linear_rows


class RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


def test_dml_telemetry_contains_only_safe_aggregate_metadata() -> None:
    provider = RecordingProvider()
    result = DoubleMachineLearningEstimator(observability_provider=provider).analyze(
        dml_execution(fold_count=4, seed=812),
        dml_table(_linear_rows()),
        provenance=provenance("dml-observability"),
    )

    assert result.status.value == "completed"
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "double_machine_learning"
    assert record.inputs == {"row_count": 80}
    assert set(record.metadata) == {
        "method",
        "fold_count",
        "status",
        "estimand",
        "cross_fitting_status",
        "overlap_status",
        "outcome_nuisance_family",
        "treatment_nuisance_family",
        "diagnostic_codes",
        "retained_count",
        "duration_ms",
    }
    assert record.outputs == {"status": "completed", "dml_completed": True}
    rendered = repr((record.inputs, record.metadata, record.outputs, record.error))
    for forbidden in (
        "unit-000",
        "account_id",
        "prior_orders",
        "outcome_predictions",
        "treatment_predictions",
        "residuals",
        "fold_assignments",
    ):
        assert forbidden not in rendered
