"""Privacy and provider-failure isolation for CUPED telemetry."""

from __future__ import annotations

from packages.experiments.analysis.randomized.cuped import (
    CupedAnalysisExecutionRequest,
    CupedAnalysisService,
    CupedStatus,
)
from packages.experiments.analysis.randomized.models import AlternativeHypothesis
from packages.experiments.analysis.validation import AnalysisTable
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.analysis_contract_fixtures import source
from tests.test_cuped_service import _binding, _policy, _request, _table


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


def _execution() -> CupedAnalysisExecutionRequest:
    return CupedAnalysisExecutionRequest(
        request_id="private-high-cardinality-request-093",
        analysis_request=_request(),
        alternative=AlternativeHypothesis.TWO_SIDED,
    )


def _private_table() -> AnalysisTable:
    table = _table()
    return AnalysisTable(
        columns=table.columns + ("private_credential",),
        rows=tuple(row + ("sk-private-cuped-credential",) for row in table.rows),
    )


def _analyze(provider: BaseObservabilityProvider, *, constant: bool = False):
    table = (
        _table(
            control_covariates=(2.0, 2.0, 2.0, 2.0),
            treatment_covariates=(2.0, 2.0, 2.0, 2.0),
        )
        if constant
        else _private_table()
    )
    return CupedAnalysisService(
        validation_policy=_policy(),
        observability_provider=provider,
    ).analyze(
        _execution(),
        table,
        _binding(),
        provenance=(source(),),
    )


def _telemetry_payload(record: BufferedSpanRecord) -> object:
    return {
        "name": record.name,
        "inputs": record.inputs,
        "metadata": record.metadata,
        "outputs": record.outputs,
        "error": record.error,
        "children": [_telemetry_payload(child) for child in record.children],
    }


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_nested_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_nested_keys(item) for item in value), set())
    return set()


def test_success_emits_controlled_aggregate_cuped_metadata_only() -> None:
    provider = RecordingProvider()

    result = _analyze(provider)

    assert result.status is CupedStatus.COMPLETED
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "cuped_analysis"
    assert record.inputs == {"total_row_count": 8}
    assert record.metadata["analysis_method"] == "cuped"
    assert record.metadata["metric_type"] == "continuous"
    assert record.metadata["cuped_status"] == "completed"
    assert record.metadata["baseline_status"] == "completed"
    assert record.metadata["covariate_timing"] == "pre_treatment"
    assert record.metadata["retained_count"] == 8
    assert record.metadata["retained_proportion"] == 1.0
    assert record.metadata["variance_reduction_status"] == "positive_reduction"
    assert isinstance(record.metadata["duration_ms"], float)
    assert record.outputs == {"status": "completed", "analysis_completed": True}

    payload = _telemetry_payload(record)
    rendered = repr(payload)
    keys = _nested_keys(payload)
    forbidden_keys = {
        "rows",
        "outcomes",
        "covariates",
        "adjusted_outcomes",
        "treatment_values",
        "control_values",
        "theta",
        "request_id",
        "experiment_id",
    }
    assert forbidden_keys.isdisjoint(keys)
    assert "sk-private-cuped-credential" not in rendered
    assert "private-high-cardinality-request-093" not in rendered
    assert "private_credential" not in rendered


def test_abstention_telemetry_exposes_codes_but_not_raw_values() -> None:
    provider = RecordingProvider()

    result = _analyze(provider, constant=True)

    assert result.status is CupedStatus.ABSTAINED
    record = provider.records[0]
    assert record.metadata["cuped_status"] == "abstained"
    assert "constant_or_near_zero_covariate" in record.metadata["diagnostic_codes"]
    assert record.metadata["variance_reduction_status"] == "unavailable"
    assert "theta" not in _nested_keys(_telemetry_payload(record))


def test_provider_start_failure_does_not_change_cuped_result() -> None:
    expected = _analyze(RecordingProvider())
    provider = FailingStartProvider()

    actual = _analyze(provider)

    assert actual.model_dump_json() == expected.model_dump_json()
    assert provider.failure_count == 1
