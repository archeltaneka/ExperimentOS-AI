"""Independent influence-function uncertainty references for DML."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.causal.dml.models import DMLConfig
from packages.experiments.analysis.causal.dml.numerics import (
    DMLNumericalError,
    estimate_partialling_out,
)


def config() -> DMLConfig:
    return DMLConfig(fold_count=2, random_seed=17)


def reference_result():
    return estimate_partialling_out(
        outcome=(1.0, 2.0, 3.0, 4.0),
        treatment=(0.0, 0.0, 1.0, 1.0),
        outcome_prediction=(1.2, 1.8, 2.5, 3.5),
        treatment_prediction=(0.25, 0.25, 0.75, 0.75),
        config=config(),
    )


def test_influence_uncertainty_matches_independent_hc1_reference() -> None:
    inference = reference_result().inference

    assert inference.variance_method.value == "orthogonal_score_influence_hc1"
    assert inference.finite_sample_correction == "n_over_n_minus_one"
    assert inference.reference_distribution == "standard_normal"
    assert inference.standard_error == pytest.approx(0.6633249580710799)
    assert inference.statistic == pytest.approx(1.5075567228888183)
    assert inference.p_value == pytest.approx(0.1316680160228142)
    assert inference.confidence_interval.lower == pytest.approx(-0.30009302786585823)
    assert inference.confidence_interval.upper == pytest.approx(2.3000930278658585)
    assert inference.confidence_interval.confidence_level == 0.95
    assert inference.interval_method == "standard_normal_influence_function"


def test_influence_diagnostics_are_finite_aggregates_not_raw_values() -> None:
    result = reference_result()

    assert result.influence_diagnostics.count == 4
    assert result.influence_diagnostics.variance == pytest.approx(1.76)
    assert result.influence_diagnostics.maximum_absolute == pytest.approx(1.8)
    assert result.influence_diagnostics.nonfinite_count == 0
    assert not hasattr(result.influence_diagnostics, "values")


def test_zero_or_nonfinite_inference_is_not_fabricated() -> None:
    with pytest.raises(DMLNumericalError) as captured:
        estimate_partialling_out(
            outcome=(-0.5, 0.5, -0.5, 0.5),
            treatment=(0.0, 1.0, 0.0, 1.0),
            outcome_prediction=(0.0, 0.0, 0.0, 0.0),
            treatment_prediction=(0.5, 0.5, 0.5, 0.5),
            config=config(),
        )

    assert captured.value.code == "dml.inference.degenerate_standard_error"
    assert math.isfinite(reference_result().inference.standard_error)
