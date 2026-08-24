"""Finite deterministic serialization for DiD outcomes."""

from __future__ import annotations

from packages.experiments.analysis.causal.did import (
    DifferenceInDifferencesResult,
    DifferenceInDifferencesService,
)
from tests.causal_identification_fixtures import provenance
from tests.did_fixtures import did_execution, did_table, positive_effect_rows


def test_result_round_trip_contains_no_nonfinite_or_library_values() -> None:
    result = DifferenceInDifferencesService().analyze(
        did_execution(),
        did_table(positive_effect_rows()),
        provenance=provenance("did-input"),
    )

    payload = result.model_dump_json()
    restored = DifferenceInDifferencesResult.model_validate_json(payload)

    assert restored == result
    assert "NaN" not in payload
    assert "Infinity" not in payload
    assert "statsmodels" not in payload
    assert "numpy" not in payload
