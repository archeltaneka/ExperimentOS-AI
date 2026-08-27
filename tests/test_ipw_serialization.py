"""Canonical owned serialization for observational treatment effects."""

from __future__ import annotations

import json

from packages.experiments.analysis import to_canonical_json
from packages.experiments.analysis.causal.ipw import IPWTreatmentEffectEstimator
from packages.experiments.analysis.serialization import treatment_effect_result_from_json
from tests.causal_identification_fixtures import provenance
from tests.ipw_fixtures import ipw_execution, ipw_table


def test_treatment_effect_result_round_trips_deterministically_without_nonfinite_json() -> None:
    estimator = IPWTreatmentEffectEstimator()
    first = estimator.analyze(
        ipw_execution(),
        ipw_table(),
        provenance=provenance("ipw-serialization"),
    )
    second = estimator.analyze(
        ipw_execution(),
        ipw_table(),
        provenance=provenance("ipw-serialization"),
    )

    payload = to_canonical_json(first)
    restored = treatment_effect_result_from_json(payload)

    assert first == second == restored
    assert to_canonical_json(restored) == payload
    assert "NaN" not in payload
    assert "Infinity" not in payload
    decoded = json.loads(payload)
    assert decoded["method"] == "ipw"
    assert decoded["score_model"]["score_model_version"]
    assert _contains_only_json_values(decoded)


def _contains_only_json_values(value: object) -> bool:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_contains_only_json_values(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _contains_only_json_values(item)
            for key, item in value.items()
        )
    return False
