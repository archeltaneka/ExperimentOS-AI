"""Public exports and deterministic sequential-history serialization."""

from __future__ import annotations

from packages.experiments import analysis
from packages.experiments.analysis.randomized import SequentialAnalysisService
from packages.experiments.analysis.randomized.sequential import SequentialAnalysisHistory
from packages.experiments.analysis.serialization import (
    sequential_analysis_history_from_json,
    to_canonical_json,
)
from tests.analysis_contract_fixtures import source
from tests.sequential_fixtures import sequential_plan
from tests.test_sequential_service import _look, _service


def test_sequential_contracts_and_service_are_exported_at_analysis_boundaries() -> None:
    assert analysis.SequentialAnalysisService is SequentialAnalysisService
    assert analysis.SequentialAnalysisHistory is SequentialAnalysisHistory


def test_sequential_history_round_trips_through_canonical_json() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    history = _service().analyze(
        plan,
        (_look(plan, 1, values, values),),
        provenance=(source(),),
    )

    payload = to_canonical_json(history)
    restored = sequential_analysis_history_from_json(payload)

    assert restored == history
    assert to_canonical_json(restored) == payload
