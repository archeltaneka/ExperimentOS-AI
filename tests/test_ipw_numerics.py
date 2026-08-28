"""Hand-reference checks for inverse-probability-weighting arithmetic."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal import CausalEstimandKind
from packages.experiments.analysis.causal.ipw.numerics import (
    IPWNumericalError,
    clip_weights,
    compute_raw_weights,
    effective_sample_size,
    stabilize_weights,
    weighted_mean,
)


def test_hand_reference_ate_weights_means_and_ess() -> None:
    scores = (0.25, 0.50, 0.75, 0.50)
    treated = (True, True, False, False)

    weights = compute_raw_weights(scores, treated, CausalEstimandKind.ATE)

    assert weights == pytest.approx((4.0, 2.0, 4.0, 2.0))
    assert weighted_mean((10.0, 14.0), weights[:2]) == pytest.approx(34.0 / 3.0)
    assert weighted_mean((4.0, 8.0), weights[2:]) == pytest.approx(16.0 / 3.0)
    assert effective_sample_size(weights) == pytest.approx(3.6)


def test_hand_reference_att_uses_unit_treated_and_control_odds_weights() -> None:
    scores = (0.25, 0.50, 0.75, 0.50)
    treated = (True, True, False, False)

    weights = compute_raw_weights(scores, treated, CausalEstimandKind.ATT)

    assert weights == pytest.approx((1.0, 1.0, 3.0, 1.0))
    assert weighted_mean((10.0, 14.0), weights[:2]) == pytest.approx(12.0)
    assert weighted_mean((4.0, 8.0), weights[2:]) == pytest.approx(5.0)


def test_ate_stabilization_uses_selected_population_prevalence() -> None:
    raw = (5.0, 1.25, 5.0 / 3.0, 2.5)
    treated = (True, False, False, False)

    stabilized = stabilize_weights(
        raw,
        treated,
        CausalEstimandKind.ATE,
        treatment_prevalence=0.25,
    )

    assert stabilized == pytest.approx((1.25, 0.9375, 1.25, 1.875))


def test_att_stabilization_keeps_treated_at_one_and_scales_control_odds() -> None:
    raw = (1.0, 0.25, 2.0 / 3.0, 1.5)
    treated = (True, False, False, False)

    stabilized = stabilize_weights(
        raw,
        treated,
        CausalEstimandKind.ATT,
        treatment_prevalence=0.25,
    )

    assert stabilized == pytest.approx((1.0, 0.75, 2.0, 4.5))


def test_explicit_clipping_reports_arm_counts_and_preserves_input() -> None:
    weights = (1.0, 5.0, 2.0, 8.0)
    treated = (True, True, False, False)

    result = clip_weights(weights, treated, maximum=3.0)

    assert weights == (1.0, 5.0, 2.0, 8.0)
    assert result.weights == (1.0, 3.0, 2.0, 3.0)
    assert result.affected_count == 2
    assert result.treated_affected_count == 1
    assert result.control_affected_count == 1
    assert result.affected_proportion == 0.5
    assert result.maximum_before == 8.0
    assert result.maximum_after == 3.0


def test_near_boundary_scores_produce_visible_extreme_finite_weights_and_ess_collapse() -> None:
    scores = (1e-12, 0.5, 1.0 - 1e-12, 0.5)
    treated = (True, True, False, False)

    weights = compute_raw_weights(scores, treated, CausalEstimandKind.ATE)

    assert weights[0] == pytest.approx(1e12)
    assert weights[2] == pytest.approx(1e12, rel=1e-4)
    assert max(weights) > 1e11
    assert effective_sample_size(weights) == pytest.approx(2.0, rel=1e-9)


@pytest.mark.parametrize(
    ("scores", "treated"),
    (((0.0,), (True,)), ((1.0,), (False,))),
)
def test_exact_boundary_denominators_fail_instead_of_overflowing(
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
) -> None:
    with pytest.raises(IPWNumericalError, match="denominator"):
        compute_raw_weights(scores, treated, CausalEstimandKind.ATE)


def test_ess_avoids_overflow_when_finite_weights_are_near_float_limit() -> None:
    assert effective_sample_size((1e308, 1e308, 1.0)) == pytest.approx(2.0)


@pytest.mark.parametrize("prevalence", (0.1, 0.9))
def test_ate_stabilization_is_finite_under_unequal_treatment_prevalence(
    prevalence: float,
) -> None:
    raw = (10.0, 10.0 / 9.0)
    treated = (True, False)

    stabilized = stabilize_weights(
        raw,
        treated,
        CausalEstimandKind.ATE,
        treatment_prevalence=prevalence,
    )

    assert stabilized == pytest.approx((prevalence * raw[0], (1.0 - prevalence) * raw[1]))
    assert effective_sample_size(stabilized) > 1.0
