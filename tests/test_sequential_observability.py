"""Privacy and failure isolation for sequential-analysis telemetry."""

from __future__ import annotations

from packages.experiments.analysis.randomized.sequential import (
    SequentialAnalysisService,
    SequentialLookExecution,
    SequentialStoppingStatus,
)
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.analysis_contract_fixtures import source
from tests.sequential_fixtures import sequential_plan
from tests.test_sequential_service import _binding, _table


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


def _execution(plan) -> SequentialLookExecution:
    values = tuple(float(value) for value in range(15))
    table = _table(values, values)
    table = table.__class__(
        columns=(*table.columns, "raw_covariate", "secret"),
        rows=tuple((*row, 123456.789, "sk-private") for row in table.rows),
    )
    return SequentialLookExecution(
        look_index=1,
        information_time=1.0,
        plan_fingerprint=plan.plan_fingerprint,  # type: ignore[arg-type]
        analysis_request=plan.analysis_request,
        table=table,
        binding=_binding(),
    )


def _render(record: BufferedSpanRecord) -> str:
    return repr(
        {
            "name": record.name,
            "inputs": record.inputs,
            "metadata": record.metadata,
            "outputs": record.outputs,
            "children": [_render(child) for child in record.children],
        }
    )


def test_sequential_observability_emits_only_controlled_aggregate_metadata() -> None:
    plan = sequential_plan(information_times=(1.0,))
    provider = RecordingProvider()

    result = SequentialAnalysisService(observability_provider=provider).analyze(
        plan,
        (_execution(plan),),
        provenance=(source(),),
    )

    assert result.current_status is SequentialStoppingStatus.CONTINUE
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "sequential_analysis"
    assert record.inputs == {"look_count": 1}
    assert record.metadata["method"] == "sequential"
    assert record.metadata["boundary_family"] == "obrien_fleming_weighted_bonferroni"
    assert record.metadata["look_index"] == 1
    assert record.metadata["status"] == "continue"
    assert record.metadata["boundary_crossed"] is False
    assert record.metadata["plan_integrity"] == "valid"
    assert isinstance(record.metadata["duration_ms"], float)
    rendered = _render(record)
    assert plan.plan_id not in rendered
    assert "123456.789" not in rendered
    assert "sk-private" not in rendered
    assert "raw_covariate" not in rendered
    assert "rows" not in rendered


def test_observability_start_failure_does_not_change_sequential_result() -> None:
    plan = sequential_plan(information_times=(1.0,))
    provider = FailingStartProvider()

    actual = SequentialAnalysisService(observability_provider=provider).analyze(
        plan,
        (_execution(plan),),
        provenance=(source(),),
    )
    expected = SequentialAnalysisService().analyze(
        plan,
        (_execution(plan),),
        provenance=(source(),),
    )

    assert actual.model_dump_json() == expected.model_dump_json()
    assert provider.failure_count == 1
