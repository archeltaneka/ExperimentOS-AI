"""Canonical finite serialization for propensity diagnostic outcomes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import to_canonical_json
from packages.experiments.analysis.causal.propensity import (
    DeterministicLogisticPropensityEstimator,
    PropensityResult,
)
from packages.experiments.analysis.serialization import propensity_result_from_json
from tests.causal_identification_fixtures import provenance
from tests.propensity_fixtures import (
    good_overlap_rows,
    propensity_execution,
    propensity_table,
)


def test_propensity_result_round_trips_without_library_or_effect_types() -> None:
    result = DeterministicLogisticPropensityEstimator().fit_predict(
        propensity_execution(),
        propensity_table(good_overlap_rows()),
        provenance=provenance("propensity-serialization"),
    )

    payload = to_canonical_json(result)
    restored = propensity_result_from_json(payload)

    assert isinstance(restored, PropensityResult)
    assert restored == result
    assert to_canonical_json(restored) == payload
    assert "NaN" not in payload
    assert "Infinity" not in payload
    assert "sklearn.linear_model" not in payload
    assert "numpy" not in payload
    assert '"effect_estimate"' not in payload
    assert '"treatment_effect"' not in payload


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    (
        (("overlap", "status"), "severe"),
        (("weights", "ess", "status"), "collapsed"),
    ),
)
def test_completed_result_rejects_blocking_diagnostics_on_deserialization(
    path: tuple[str, ...],
    invalid_value: str,
) -> None:
    result = DeterministicLogisticPropensityEstimator().fit_predict(
        propensity_execution(),
        propensity_table(good_overlap_rows()),
        provenance=provenance("propensity-serialization-invalid"),
    )
    payload = result.model_dump(mode="json")
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid_value

    with pytest.raises(ValidationError, match="completed propensity results"):
        PropensityResult.model_validate(payload)


def test_completed_result_rejects_fatal_diagnostic_on_direct_construction() -> None:
    result = DeterministicLogisticPropensityEstimator().fit_predict(
        propensity_execution(),
        propensity_table(good_overlap_rows()),
        provenance=provenance("propensity-fatal-diagnostic"),
    )
    payload = result.model_dump(mode="json")
    payload["diagnostics"].append(
        {
            "code": "model.unsafe",
            "category": "model",
            "severity": "fatal",
            "status": "failed",
            "message": "The model is unsafe for downstream use.",
        }
    )

    with pytest.raises(ValidationError, match="fatal diagnostics"):
        PropensityResult.model_validate(payload)
