"""Independent numerical checks for bounded subgroup interactions."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.hte.numerics import (
    estimate_grouped_orthogonal_effects,
    holm_adjust,
)
from tests.hte_fixtures import grouped_orthogonal_fixture, significance_trap_fixture


def _estimate(effects: tuple[tuple[str, float], ...], *, noise: float = 0.2):
    fixture = grouped_orthogonal_fixture(effects, noise=noise)
    return estimate_grouped_orthogonal_effects(
        outcomes=fixture.outcomes,
        treatments=fixture.treatments,
        outcome_predictions=fixture.outcome_predictions,
        treatment_predictions=fixture.treatment_predictions,
        subgroup_ids=fixture.subgroup_ids,
        confidence_level=0.95,
        residual_tolerance=1e-12,
    )


def test_known_binary_effects_recover_direct_interaction() -> None:
    result = _estimate((("control_segment", 1.0), ("priority_segment", 3.0)))

    assert tuple(group.subgroup_id for group in result.groups) == (
        "control_segment",
        "priority_segment",
    )
    assert tuple(group.estimate for group in result.groups) == pytest.approx((1.0, 3.0))
    assert all(group.standard_error > 0.0 for group in result.groups)
    assert result.contrasts[0].estimate == pytest.approx(2.0)
    assert result.contrasts[0].p_value < 0.001
    assert result.global_heterogeneity.degrees_of_freedom == 1
    assert result.global_heterogeneity.p_value < 0.001
    assert result.global_heterogeneity.detected is True


def test_homogeneous_and_null_effects_do_not_fabricate_heterogeneity() -> None:
    homogeneous = _estimate((("a", 2.0), ("b", 2.0)))
    null = _estimate((("a", 0.0), ("b", 0.0)))

    assert homogeneous.global_heterogeneity.p_value == pytest.approx(1.0)
    assert homogeneous.global_heterogeneity.detected is False
    assert null.global_heterogeneity.p_value == pytest.approx(1.0)
    assert null.global_heterogeneity.detected is False
    assert all(group.p_value == pytest.approx(1.0) for group in null.groups)
    assert all(group.confidence_interval_lower < 0.0 for group in null.groups)
    assert all(group.confidence_interval_upper > 0.0 for group in null.groups)


def test_multilevel_omnibus_test_uses_all_reference_interactions() -> None:
    result = _estimate((("a", 0.0), ("b", 1.0), ("c", 2.0)))

    assert tuple(item.comparison_subgroup_id for item in result.contrasts) == ("b", "c")
    assert tuple(item.estimate for item in result.contrasts) == pytest.approx((1.0, 2.0))
    assert result.global_heterogeneity.degrees_of_freedom == 2
    assert result.global_heterogeneity.p_value < 0.001


def test_significant_vs_nonsignificant_subgroups_require_direct_difference() -> None:
    fixture = significance_trap_fixture()
    result = estimate_grouped_orthogonal_effects(
        outcomes=fixture.outcomes,
        treatments=fixture.treatments,
        outcome_predictions=fixture.outcome_predictions,
        treatment_predictions=fixture.treatment_predictions,
        subgroup_ids=fixture.subgroup_ids,
        confidence_level=0.95,
        residual_tolerance=1e-12,
    )

    assert result.groups[0].p_value < 0.05
    assert result.groups[1].p_value > 0.05
    assert result.contrasts[0].p_value > 0.05
    assert result.global_heterogeneity.p_value > 0.05
    assert result.global_heterogeneity.detected is False


def test_holm_adjustment_is_deterministic_monotone_and_index_preserving() -> None:
    assert holm_adjust((0.01, 0.04, 0.03)) == pytest.approx((0.03, 0.06, 0.06))
    assert holm_adjust((0.02, 0.02, 0.50)) == pytest.approx((0.06, 0.06, 0.50))
