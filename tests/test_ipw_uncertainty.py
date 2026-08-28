"""Independent references for fixed-propensity robust IPW uncertainty."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.causal.ipw import IPWTreatmentEffectEstimator, IPWVarianceMethod
from packages.experiments.analysis.causal.ipw.uncertainty import (
    compute_fixed_score_robust_inference,
)
from tests.causal_identification_fixtures import provenance
from tests.ipw_fixtures import ipw_execution, ipw_table


def test_robust_uncertainty_matches_hand_calculated_hajek_reference() -> None:
    treatment_outcomes = (10.0, 14.0)
    treatment_weights = (4.0, 2.0)
    control_outcomes = (4.0, 8.0)
    control_weights = (4.0, 2.0)
    treatment_mean = 34.0 / 3.0
    control_mean = 16.0 / 3.0
    effect = 6.0
    treatment_variance = (
        (2.0 / 1.0)
        * (4.0**2 * (10.0 - treatment_mean) ** 2 + 2.0**2 * (14.0 - treatment_mean) ** 2)
        / 6.0**2
    )
    control_variance = (
        (2.0 / 1.0)
        * (4.0**2 * (4.0 - control_mean) ** 2 + 2.0**2 * (8.0 - control_mean) ** 2)
        / 6.0**2
    )
    expected_se = math.sqrt(treatment_variance + control_variance)
    expected_statistic = effect / expected_se
    expected_p_value = math.erfc(abs(expected_statistic) / math.sqrt(2.0))
    critical = 1.959963984540054

    result = compute_fixed_score_robust_inference(
        treatment_outcomes=treatment_outcomes,
        treatment_weights=treatment_weights,
        control_outcomes=control_outcomes,
        control_weights=control_weights,
        treatment_mean=treatment_mean,
        control_mean=control_mean,
        effect=effect,
        confidence_level=0.95,
    )

    assert result.variance_method is IPWVarianceMethod.FIXED_PROPENSITY_HAJEK_HC1
    assert result.propensity_scores_treated_as_fixed is True
    assert result.finite_sample_correction == "arm_n_over_n_minus_one"
    assert result.reference_distribution == "standard_normal"
    assert result.degrees_of_freedom is None
    assert result.standard_error == pytest.approx(expected_se)
    assert result.statistic == pytest.approx(expected_statistic)
    assert result.p_value == pytest.approx(expected_p_value)
    assert result.confidence_interval.lower == pytest.approx(effect - critical * expected_se)
    assert result.confidence_interval.upper == pytest.approx(effect + critical * expected_se)


def test_zero_effect_with_zero_variance_has_finite_null_inference() -> None:
    result = compute_fixed_score_robust_inference(
        treatment_outcomes=(3.0, 3.0),
        treatment_weights=(1.0, 1.0),
        control_outcomes=(3.0, 3.0),
        control_weights=(1.0, 1.0),
        treatment_mean=3.0,
        control_mean=3.0,
        effect=0.0,
        confidence_level=0.95,
    )

    assert result.standard_error == 0.0
    assert result.statistic == 0.0
    assert result.p_value == 1.0
    assert result.confidence_interval.lower == 0.0
    assert result.confidence_interval.upper == 0.0


def test_result_discloses_fixed_propensity_uncertainty_limitation() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(),
        ipw_table(),
        provenance=provenance("ipw-uncertainty-limitation"),
    )

    assert "inference.propensity_scores_treated_as_fixed" in {
        item.code for item in result.diagnostics
    }
    assert "inference.propensity_scores_treated_as_fixed" in {item.code for item in result.warnings}
