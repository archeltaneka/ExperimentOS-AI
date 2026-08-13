"""Independent reference checks for sequential alpha spending and boundaries."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.randomized.sequential import (
    generate_sequential_boundaries,
)
from tests.sequential_fixtures import FOUR_LOOK_REFERENCE, sequential_plan


def test_four_look_boundaries_match_documented_formula_reference() -> None:
    boundaries = generate_sequential_boundaries(sequential_plan())

    assert len(boundaries) == 4
    for actual, expected in zip(boundaries, FOUR_LOOK_REFERENCE, strict=True):
        index, information_time, cumulative, incremental, critical = expected
        assert actual.look_index == index
        assert actual.information_time == information_time
        assert actual.cumulative_alpha_spent == pytest.approx(cumulative, abs=1e-15)
        assert actual.nominal_alpha == pytest.approx(incremental, abs=1e-15)
        assert actual.critical_boundary == pytest.approx(critical, abs=1e-12)


def test_spending_is_monotone_finite_and_finishes_at_total_alpha() -> None:
    plan = sequential_plan()
    boundaries = generate_sequential_boundaries(plan)
    cumulative = tuple(boundary.cumulative_alpha_spent for boundary in boundaries)

    assert cumulative == tuple(sorted(cumulative))
    assert boundaries[-1].cumulative_alpha_spent == plan.total_alpha
    assert boundaries[-1].remaining_alpha == 0.0
    assert sum(boundary.nominal_alpha for boundary in boundaries) == pytest.approx(
        plan.total_alpha,
        abs=1e-15,
    )
    assert all(
        math.isfinite(value)
        for boundary in boundaries
        for value in (
            boundary.critical_boundary,
            boundary.nominal_alpha,
            boundary.cumulative_alpha_spent,
            boundary.remaining_alpha,
        )
    )


def test_boundary_generation_is_deterministic_from_plan_alone() -> None:
    plan = sequential_plan()

    assert generate_sequential_boundaries(plan) == generate_sequential_boundaries(plan)


def test_extreme_early_information_time_never_serializes_infinity() -> None:
    boundaries = generate_sequential_boundaries(
        sequential_plan(information_times=(1e-12, 0.5, 1.0))
    )

    assert boundaries[0].nominal_alpha == 0.0
    assert math.isfinite(boundaries[0].critical_boundary)
    assert "Infinity" not in boundaries[0].model_dump_json()
    assert "NaN" not in boundaries[0].model_dump_json()
