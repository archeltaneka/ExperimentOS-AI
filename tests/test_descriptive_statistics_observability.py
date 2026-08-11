"""Observability contract coverage for deterministic descriptive summaries."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.descriptive import (
    DescriptiveStatisticsInvariantError,
    DescriptiveStatisticsService,
)
from packages.experiments.analysis.validation import AnalysisTable
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.test_descriptive_statistics_diagnostics import _input_for
from tests.test_descriptive_statistics_service import _eligible_input


class RecordingProvider(BaseObservabilityProvider):
    """Captures logical spans without using an external observability backend."""

    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


class FailingStartProvider(RecordingProvider):
    """Exercises failure isolation at the provider boundary."""

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
        raise RuntimeError("provider transport unavailable")


def test_service_records_only_low_cardinality_logical_descriptive_metadata() -> None:
    """Catches descriptive spans that leak source rows or omit computation coverage metadata."""
    provider = RecordingProvider()
    analysis_input = _eligible_input(
        (
            ("secret-customer-1", "secret-account-1", "control", 999.25),
            ("secret-customer-2", "secret-account-2", "control", 1.0),
            ("secret-customer-3", "secret-account-3", "treatment", 3.0),
            ("secret-customer-4", "secret-account-4", "treatment", 5.0),
        )
    )

    result = DescriptiveStatisticsService(observability_provider=provider).summarize(analysis_input)

    assert result.population.row_count == 4
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "descriptive_statistics"
    assert record.inputs == {"row_count": 4}
    assert record.metadata["metric_type"] == "continuous"
    assert record.metadata["group_count"] == 3
    assert record.metadata["segment_count"] == 0
    assert record.metadata["status"] == "completed"
    assert record.metadata["warning_count"] == 0
    assert record.metadata["unavailable_comparison_count"] == 0
    assert isinstance(record.metadata["duration_ms"], float)
    assert record.metadata["duration_ms"] >= 0.0
    assert record.outputs == {"status": "completed", "descriptive_statistics_completed": True}
    recorded_text = repr((record.inputs, record.metadata, record.outputs))
    assert "secret-customer" not in recorded_text
    assert "secret-account" not in recorded_text
    assert "999.25" not in recorded_text


def test_service_isolated_from_observability_start_failure() -> None:
    """Catches provider startup errors that prevent an authoritative statistical result."""
    provider = FailingStartProvider()
    analysis_input = _eligible_input(
        (
            ("o1", "a1", "control", 1.0),
            ("o2", "a2", "treatment", 3.0),
        )
    )

    result = DescriptiveStatisticsService(observability_provider=provider).summarize(analysis_input)

    assert result.raw_comparison is not None
    assert result.raw_comparison.absolute_difference == 2.0
    assert provider.failure_count == 1


def test_service_records_a_nonfinite_rejection_without_recording_the_value() -> None:
    """Catches numeric-safety failures that are neither observable nor safely redacted."""
    provider = RecordingProvider()
    unsafe_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome"),
            rows=(("o1", "a1", "control", 0.0), ("o2", "a2", "treatment", float("inf"))),
        ),
        allow_data_ineligible=True,
    )

    with pytest.raises(DescriptiveStatisticsInvariantError):
        DescriptiveStatisticsService(observability_provider=provider).summarize(unsafe_input)

    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.metadata["status"] == "failed"
    assert record.metadata["numeric_safety_failure"] is True
    assert record.outputs == {"status": "failed", "descriptive_statistics_completed": False}
    assert record.error == {
        "type": "DescriptiveStatisticsInvariantError",
        "message": "Descriptive statistics failed.",
    }
    assert "inf" not in repr((record.inputs, record.metadata, record.outputs, record.error))
