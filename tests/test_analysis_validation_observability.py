from __future__ import annotations

import pytest

from packages.experiments.analysis import (
    AnalysisRequest,
    AnalysisStatus,
    RandomizedAnalysisMethod,
    RandomizedExperimentDesign,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisEligibilityService,
    AnalysisTable,
    MethodCapabilityRegistry,
)
from packages.experiments.analysis.validation import service as service_module
from packages.observability.base import (
    BaseObservabilityProvider,
    BufferedSpan,
    BufferedSpanRecord,
)
from packages.observability.models import ProviderSettings
from packages.observability.noop import NoOpObservabilityProvider
from tests.analysis_contract_fixtures import randomized_request
from tests.analysis_validation_fixtures import analysis_binding_fixture


class RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


class FailingEmitProvider(RecordingProvider):
    def _emit_root(self, record: BufferedSpanRecord) -> None:
        raise RuntimeError("observability transport failed")


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
        raise RuntimeError("observability start failed")


class ControlledLifecycleSpan(BufferedSpan):
    def __init__(
        self,
        provider: BaseObservabilityProvider,
        record: BufferedSpanRecord,
        *,
        failing_operation: str,
    ) -> None:
        super().__init__(provider, record)
        self.failing_operation = failing_operation
        self.calls: list[str] = []

    def add_metadata(self, metadata: dict[str, object]) -> None:
        self.calls.append("add_metadata")
        if self.failing_operation == "add_metadata":
            raise RuntimeError("metadata lifecycle failed")
        super().add_metadata(metadata)

    def record_error(
        self,
        error: BaseException | str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        self.calls.append("record_error")
        if self.failing_operation == "record_error":
            raise RuntimeError("error lifecycle failed")
        super().record_error(error, details=details)

    def finish(self, *, outputs: dict[str, object] | None = None) -> None:
        self.calls.append("finish")
        if self.failing_operation == "finish":
            raise RuntimeError("finish lifecycle failed")
        super().finish(outputs=outputs)


class ControlledLifecycleProvider(RecordingProvider):
    def __init__(self, failing_operation: str) -> None:
        super().__init__()
        self.failing_operation = failing_operation
        self.spans: list[ControlledLifecycleSpan] = []

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
        span = super().start_root_span(
            name,
            trace_id=trace_id,
            run_type=run_type,
            inputs=inputs,
            metadata=metadata,
            tags=tags,
        )
        controlled_span = ControlledLifecycleSpan(
            self,
            span.record,
            failing_operation=self.failing_operation,
        )
        self.spans.append(controlled_span)
        return controlled_span


class FailingFailureCountProvider(RecordingProvider):
    @property
    def failure_count(self) -> int:
        raise RuntimeError("failure counter unavailable")


def _eligible_request() -> AnalysisRequest:
    request = randomized_request()
    design = request.study_design
    assert isinstance(design, RandomizedExperimentDesign)
    return request.model_copy(
        update={
            "study_design": design.model_copy(
                update={"randomization_unit": request.unit_of_analysis}
            )
        }
    )


def _eligible_binding() -> AnalysisDataBinding:
    return analysis_binding_fixture().model_copy(update={"randomization_unit_column": "order_id"})


def _eligible_table(*, row_count: int = 100) -> AnalysisTable:
    return AnalysisTable(
        columns=("order_id", "arm", "outcome"),
        rows=tuple(
            (
                f"order-{index}",
                "control" if index % 2 == 0 else "treatment",
                float(index % 2),
            )
            for index in range(row_count)
        ),
    )


def _implemented_service(
    provider: BaseObservabilityProvider | None = None,
) -> AnalysisEligibilityService:
    return AnalysisEligibilityService(
        capability_registry=MethodCapabilityRegistry.with_implemented_methods(
            (RandomizedAnalysisMethod.FIXED_HORIZON_AB,)
        ),
        observability_provider=provider,
    )


def test_validation_span_contains_only_logical_metadata_without_table_content() -> None:
    provider = RecordingProvider()
    table = AnalysisTable(
        columns=("secret_unit_column", "secret_arm_column", "secret_outcome_column"),
        rows=tuple(
            (
                f"sensitive-customer-{index}",
                "control" if index % 2 == 0 else "treatment",
                float(index % 2),
            )
            for index in range(100)
        ),
    )
    binding = _eligible_binding()
    binding = binding.model_copy(
        update={
            "treatment_column": "secret_arm_column",
            "outcome": binding.outcome.model_copy(update={"value_column": "secret_outcome_column"}),
            "observation_unit_column": "secret_unit_column",
            "randomization_unit_column": "secret_unit_column",
        }
    )

    result = _implemented_service(provider).validate(_eligible_request(), table, binding)

    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "analysis_validation"
    assert record.inputs == {"row_count": 100, "column_count": 3}
    assert record.metadata["method"] == "fixed_horizon_ab"
    assert record.metadata["design"] == "randomized_experiment"
    assert record.metadata["status"] == result.status.value
    assert record.metadata["blocking_diagnostic_count"] == 0
    assert record.metadata["warning_diagnostic_count"] == 0
    assert record.metadata["needs_more_data"] is False
    assert record.metadata["method_unavailable"] is False
    assert record.metadata["validator_failure"] is False
    assert record.metadata["validation_started"] is True
    assert record.metadata["validation_completed"] is True
    assert isinstance(record.metadata["duration_ms"], float)
    assert record.metadata["duration_ms"] >= 0.0
    assert record.outputs == {
        "status": result.status.value,
        "validation_completed": True,
    }
    assert record.status == "completed"
    assert record.ended_at is not None
    serialized = repr(record.inputs) + repr(record.metadata) + repr(record.outputs)
    for forbidden in (
        "sensitive-customer",
        "secret_unit_column",
        "secret_arm_column",
        "secret_outcome_column",
        "control",
        "treatment",
    ):
        assert forbidden not in serialized


def test_validation_uses_one_child_span_inside_an_active_trace() -> None:
    provider = RecordingProvider()
    parent = provider.start_root_span("outer_operation")

    with parent.activate():
        result = _implemented_service(provider).validate(
            _eligible_request(),
            _eligible_table(),
            _eligible_binding(),
        )
    parent.finish(outputs={"status": result.status.value})

    assert len(provider.records) == 1
    assert provider.records[0] is parent.record
    assert [child.name for child in parent.record.children] == ["analysis_validation"]
    assert parent.record.children[0].status == "completed"


def test_default_provider_does_not_attach_to_a_foreign_recording_span() -> None:
    recording_provider = RecordingProvider()
    foreign_parent = recording_provider.start_root_span("foreign_operation")

    with foreign_parent.activate():
        result = _implemented_service().validate(
            _eligible_request(),
            _eligible_table(),
            _eligible_binding(),
        )
    foreign_parent.finish(outputs={"status": result.status.value})

    assert result.status is AnalysisStatus.ELIGIBLE
    assert foreign_parent.record.children == []
    assert recording_provider.records == [foreign_parent.record]


def test_recording_provider_exports_root_inside_a_foreign_noop_span() -> None:
    recording_provider = RecordingProvider()
    noop_provider = NoOpObservabilityProvider()
    foreign_parent = noop_provider.start_root_span("foreign_operation")

    with foreign_parent.activate():
        result = _implemented_service(recording_provider).validate(
            _eligible_request(),
            _eligible_table(),
            _eligible_binding(),
        )
    foreign_parent.finish(outputs={"status": result.status.value})

    assert result.status is AnalysisStatus.ELIGIBLE
    assert foreign_parent.record.children == []
    assert len(recording_provider.records) == 1
    assert recording_provider.records[0].name == "analysis_validation"
    assert recording_provider.records[0].parent is None


@pytest.mark.parametrize("provider_type", [FailingEmitProvider, FailingStartProvider])
def test_provider_failure_does_not_change_validation_result(
    provider_type: type[BaseObservabilityProvider],
) -> None:
    expected = _implemented_service().validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )
    provider = provider_type()

    actual = _implemented_service(provider).validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert actual == expected
    assert provider.failure_count == 1


@pytest.mark.parametrize("failing_operation", ["add_metadata", "finish"])
def test_successful_result_is_unchanged_when_span_completion_fails(
    failing_operation: str,
) -> None:
    expected = _implemented_service().validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )
    provider = ControlledLifecycleProvider(failing_operation)

    actual = _implemented_service(provider).validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert actual == expected
    assert provider.failure_count == 1
    assert failing_operation in provider.spans[0].calls


@pytest.mark.parametrize(
    "failing_operation",
    ["add_metadata", "record_error", "finish"],
)
def test_original_validator_error_survives_error_lifecycle_failure_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
    failing_operation: str,
) -> None:
    provider = ControlledLifecycleProvider(failing_operation)
    original = RuntimeError("validator failed with sensitive-customer-17")

    def raising_validator(*args: object, **kwargs: object) -> tuple[()]:
        raise original

    monkeypatch.setattr(service_module, "validate_request_consistency", raising_validator)

    with pytest.raises(RuntimeError) as captured:
        _implemented_service(provider).validate(
            _eligible_request(),
            _eligible_table(),
            _eligible_binding(),
        )

    assert captured.value is original
    assert provider.failure_count == 1
    assert failing_operation in provider.spans[0].calls
    record = provider.spans[0].record
    serialized = repr(record.error) + repr(record.metadata) + repr(record.outputs)
    assert "sensitive-customer-17" not in serialized


def test_failure_counter_property_cannot_escape_observability_isolation() -> None:
    expected = _implemented_service().validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )
    provider = FailingFailureCountProvider()

    actual = _implemented_service(provider).validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert actual == expected
    assert len(provider.records) == 1


def test_default_provider_is_noop() -> None:
    service = _implemented_service()

    result = service.validate(_eligible_request(), _eligible_table(), _eligible_binding())

    assert isinstance(service.observability_provider, NoOpObservabilityProvider)
    assert result.status is AnalysisStatus.ELIGIBLE
    assert service.observability_provider.failure_count == 0


def test_method_unavailable_is_recorded_as_a_logical_flag() -> None:
    provider = RecordingProvider()

    result = AnalysisEligibilityService(observability_provider=provider).validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.INELIGIBLE
    assert provider.records[0].metadata["method_unavailable"] is True
    assert provider.records[0].metadata["needs_more_data"] is False


def test_needs_more_data_is_recorded_as_a_logical_flag() -> None:
    provider = RecordingProvider()

    result = _implemented_service(provider).validate(
        _eligible_request(),
        _eligible_table(row_count=20),
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.NEEDS_MORE_DATA
    assert provider.records[0].metadata["needs_more_data"] is True
    assert provider.records[0].metadata["method_unavailable"] is False


def test_unexpected_validator_failure_is_safely_recorded_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = RecordingProvider()

    def raising_validator(*args: object, **kwargs: object) -> tuple[()]:
        raise RuntimeError("validator failed with sensitive-customer-17")

    monkeypatch.setattr(service_module, "validate_request_consistency", raising_validator)
    service = _implemented_service(provider)

    with pytest.raises(RuntimeError, match="validator failed with sensitive-customer-17"):
        service.validate(_eligible_request(), _eligible_table(), _eligible_binding())

    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.error == {
        "type": "RuntimeError",
        "message": "Analysis validation failed.",
        "stage": "request_and_capability",
    }
    assert record.metadata["validator_failure"] is True
    assert record.metadata["validator_failure_stage"] == "request_and_capability"
    assert record.metadata["validation_completed"] is False
    assert record.outputs == {"validation_completed": False}
    assert record.status == "error"
    serialized = repr(record.error) + repr(record.metadata) + repr(record.outputs)
    assert "sensitive-customer-17" not in serialized
