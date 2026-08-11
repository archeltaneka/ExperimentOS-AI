"""Privacy and failure-isolation checks for randomized-analysis telemetry."""

from __future__ import annotations

from collections.abc import Sequence

from packages.evals.analysis_validation_cases import build_validation_golden_cases
from packages.experiments.analysis import AnalysisTable, MetricType, ValidationPolicy
from packages.experiments.analysis.randomized import (
    AlternativeHypothesis,
    ComputationStatus,
    RandomizedAnalysisExecutionRequest,
    RandomizedAnalysisService,
)
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.analysis_contract_fixtures import source
from tests.test_randomized_service import _binding, _request


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


def _table(treatment: Sequence[object], control: Sequence[object]) -> AnalysisTable:
    rows = tuple(
        (f"t-{index}", "treatment", value, 123456.789, "sk-private-credential")
        for index, value in enumerate(treatment)
    ) + tuple(
        (f"c-{index}", "control", value, 987654.321, "sk-private-credential")
        for index, value in enumerate(control)
    )
    return AnalysisTable(
        columns=("unit_id", "arm", "outcome", "raw_covariate", "credential"),
        rows=rows,
    )


def _execution(metric_type: MetricType) -> RandomizedAnalysisExecutionRequest:
    return RandomizedAnalysisExecutionRequest(
        request_id="arbitrary-high-cardinality-analysis-id",
        analysis_request=_request(metric_type),
        alternative=AlternativeHypothesis.TWO_SIDED,
    )


def _compact_policy() -> ValidationPolicy:
    case = next(
        item for item in build_validation_golden_cases() if item.case_id == "valid-randomized"
    )
    return case.policy


def _telemetry_payload(record: BufferedSpanRecord) -> object:
    return {
        "name": record.name,
        "inputs": record.inputs,
        "metadata": record.metadata,
        "outputs": record.outputs,
        "error": record.error,
        "children": [_telemetry_payload(child) for child in record.children],
    }


def _assert_private_values_absent(record: BufferedSpanRecord) -> None:
    payload = _telemetry_payload(record)
    rendered = repr(payload)
    assert "123456.789" not in rendered
    assert "987654.321" not in rendered
    assert "sk-private-credential" not in rendered
    assert "arbitrary-high-cardinality-analysis-id" not in rendered
    assert "raw_covariate" not in rendered
    assert "credential" not in rendered
    assert "rows" not in rendered
    assert "treatment_values" not in rendered
    assert "control_values" not in rendered


def test_successful_analysis_emits_only_controlled_aggregate_metadata() -> None:
    provider = RecordingProvider()
    treatment = (999.25,) + tuple(float(value) for value in range(12, 31))
    control = tuple(float(value) for value in range(1, 21))

    result = RandomizedAnalysisService(observability_provider=provider).analyze(
        _execution(MetricType.CONTINUOUS),
        _table(treatment, control),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.COMPLETED
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "randomized_analysis"
    assert record.inputs == {"total_row_count": 40}
    assert record.metadata["analysis_method"] == "fixed_horizon_ab"
    assert record.metadata["estimand"] == "difference_in_means"
    assert record.metadata["metric_type"] == "continuous"
    assert record.metadata["analysis_status"] == "completed"
    assert record.metadata["treatment_count"] == 20
    assert record.metadata["control_count"] == 20
    assert record.metadata["total_eligible_count"] == 40
    assert record.metadata["abstention_state"] is False
    assert isinstance(record.metadata["duration_ms"], float)
    assert record.children[0].name == "analysis_validation"
    _assert_private_values_absent(record)


def test_abstained_analysis_telemetry_contains_codes_but_no_raw_payload() -> None:
    provider = RecordingProvider()
    service = RandomizedAnalysisService(
        validation_policy=_compact_policy(),
        observability_provider=provider,
    )

    result = service.analyze(
        _execution(MetricType.CONTINUOUS),
        _table((999.25,), (1.0,)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.ABSTAINED
    record = provider.records[0]
    assert record.metadata["analysis_status"] == "abstained"
    assert record.metadata["abstention_state"] is True
    assert record.metadata["diagnostic_codes"] == ("one_observation_arm",)
    _assert_private_values_absent(record)


def test_abstained_analysis_telemetry_counts_only_valid_rows() -> None:
    provider = RecordingProvider()
    treatment = tuple(float(value) for value in range(11, 31)) + (None,)
    control = tuple(float(value) for value in range(1, 21))

    result = RandomizedAnalysisService(
        validation_policy=_compact_policy(),
        observability_provider=provider,
    ).analyze(
        _execution(MetricType.CONTINUOUS),
        _table(treatment, control),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.ABSTAINED
    record = provider.records[0]
    assert record.metadata["treatment_count"] == 20
    assert record.metadata["control_count"] == 20
    assert record.metadata["total_eligible_count"] == 40


def test_observability_provider_failure_does_not_change_analysis_result() -> None:
    provider = FailingStartProvider()
    treatment = tuple(float(value) for value in range(11, 31))
    control = tuple(float(value) for value in range(1, 21))

    result = RandomizedAnalysisService(observability_provider=provider).analyze(
        _execution(MetricType.CONTINUOUS),
        _table(treatment, control),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.COMPLETED
    assert provider.failure_count == 1
