"""Hand-calculated DiD and canonical interaction-regression equivalence."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.did.numerics import (
    fit_interaction_ols,
    manual_did,
)
from packages.experiments.analysis.causal.did.validation import validate_did_input
from tests.did_fixtures import (
    did_execution,
    did_table,
    no_effect_rows,
    positive_effect_rows,
)


@pytest.mark.parametrize(
    ("rows", "expected"),
    (
        (
            no_effect_rows(),
            {
                "treated_pre_mean": 10.0,
                "treated_post_mean": 12.0,
                "control_pre_mean": 8.0,
                "control_post_mean": 10.0,
                "treated_change": 2.0,
                "control_change": 2.0,
                "did_estimate": 0.0,
            },
        ),
        (
            positive_effect_rows(),
            {
                "treated_pre_mean": 10.0,
                "treated_post_mean": 15.0,
                "control_pre_mean": 8.0,
                "control_post_mean": 10.0,
                "treated_change": 5.0,
                "control_change": 2.0,
                "did_estimate": 3.0,
            },
        ),
    ),
)
def test_manual_four_cell_estimate_matches_reference(
    rows: tuple[dict[str, object], ...],
    expected: dict[str, float],
) -> None:
    validated = validate_did_input(did_execution(), did_table(rows))

    result = manual_did(validated.observations)

    for field, value in expected.items():
        assert getattr(result, field) == pytest.approx(value, abs=1e-12)
    assert result.treated_pre_count == 10
    assert result.treated_post_count == 10
    assert result.control_pre_count == 10
    assert result.control_post_count == 10


@pytest.mark.parametrize(
    ("rows", "expected_beta"),
    (
        (no_effect_rows(), (8.0, 2.0, 2.0, 0.0)),
        (positive_effect_rows(), (8.0, 2.0, 2.0, 3.0)),
    ),
)
def test_interaction_regression_uses_control_and_pre_as_references(
    rows: tuple[dict[str, object], ...],
    expected_beta: tuple[float, float, float, float],
) -> None:
    validated = validate_did_input(did_execution(), did_table(rows))

    fit = fit_interaction_ols(validated.observations)
    manual = manual_did(validated.observations)

    assert fit.coefficient_names == ("intercept", "treated", "post", "treated_post")
    assert fit.coefficients == pytest.approx(expected_beta, abs=1e-12)
    assert fit.coefficients[3] == pytest.approx(manual.did_estimate, abs=1e-12)
    assert len(fit.residuals) == 40


def test_manual_and_regression_results_are_row_order_invariant() -> None:
    rows = positive_effect_rows()
    forward = validate_did_input(did_execution(), did_table(rows)).observations
    reverse = validate_did_input(did_execution(), did_table(tuple(reversed(rows)))).observations

    assert manual_did(forward) == manual_did(reverse)
    assert fit_interaction_ols(forward).coefficients == pytest.approx(
        fit_interaction_ols(reverse).coefficients,
        abs=1e-12,
    )
