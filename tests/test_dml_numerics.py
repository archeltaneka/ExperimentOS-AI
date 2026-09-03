"""Hand-reference orthogonal-score, residual, nuisance, and overlap tests."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.causal.dml.models import DMLConfig
from packages.experiments.analysis.causal.dml.numerics import (
    DMLNumericalError,
    assess_dml_overlap,
    build_nuisance_diagnostics,
    estimate_partialling_out,
    summarize_residuals,
)
from packages.experiments.analysis.causal.propensity import OverlapStatus


def config(**updates: object) -> DMLConfig:
    return DMLConfig(fold_count=2, random_seed=17).model_copy(update=updates)


def test_partialling_out_matches_hand_calculated_orthogonal_score() -> None:
    result = estimate_partialling_out(
        outcome=(1.0, 2.0, 3.0, 4.0),
        treatment=(0.0, 0.0, 1.0, 1.0),
        outcome_prediction=(1.2, 1.8, 2.5, 3.5),
        treatment_prediction=(0.25, 0.25, 0.75, 0.75),
        config=config(),
    )

    assert result.outcome_residuals == pytest.approx((-0.2, 0.2, 0.5, 0.5))
    assert result.treatment_residuals == pytest.approx((-0.25, -0.25, 0.25, 0.25))
    assert result.numerator == pytest.approx(0.25)
    assert result.denominator == pytest.approx(0.25)
    assert result.point_estimate == pytest.approx(1.0)
    assert result.influence_values == pytest.approx((-0.2, -1.8, 1.0, 1.0))
    assert math.fsum(result.influence_values) == pytest.approx(0.0, abs=1e-14)


def test_residual_summary_reports_finite_distribution_and_squared_norm() -> None:
    summary = summarize_residuals((-1.0, 0.0, 1.0))

    assert summary.count == 3
    assert summary.mean == 0.0
    assert summary.standard_deviation == 1.0
    assert summary.minimum == -1.0
    assert summary.maximum == 1.0
    assert summary.variance == 1.0
    assert summary.squared_norm == 2.0
    assert summary.nonfinite_count == 0


def test_partialling_out_rejects_degenerate_treatment_without_epsilon_patch() -> None:
    with pytest.raises(DMLNumericalError) as captured:
        estimate_partialling_out(
            outcome=(1.0, 2.0, 3.0, 4.0),
            treatment=(0.0, 0.0, 1.0, 1.0),
            outcome_prediction=(0.0, 0.0, 0.0, 0.0),
            treatment_prediction=(0.0, 0.0, 1.0, 1.0),
            config=config(),
        )

    assert captured.value.code == "dml.degenerate_treatment_residual"


def test_treatment_degeneracy_takes_priority_when_both_residuals_are_zero() -> None:
    with pytest.raises(DMLNumericalError) as captured:
        estimate_partialling_out(
            outcome=(1.0, 1.0),
            treatment=(0.0, 1.0),
            outcome_prediction=(1.0, 1.0),
            treatment_prediction=(0.0, 1.0),
            config=config(),
        )

    assert captured.value.code == "dml.degenerate_treatment_residual"


def test_partialling_out_rejects_degenerate_outcome_residual() -> None:
    with pytest.raises(DMLNumericalError) as captured:
        estimate_partialling_out(
            outcome=(1.0, 2.0, 3.0, 4.0),
            treatment=(0.0, 0.0, 1.0, 1.0),
            outcome_prediction=(1.0, 2.0, 3.0, 4.0),
            treatment_prediction=(0.25, 0.25, 0.75, 0.75),
            config=config(),
        )

    assert captured.value.code == "dml.degenerate_outcome_residual"


def test_partialling_out_rejects_nonfinite_inputs_and_shape_mismatch() -> None:
    with pytest.raises(DMLNumericalError, match="align"):
        estimate_partialling_out(
            outcome=(1.0, 2.0),
            treatment=(0.0,),
            outcome_prediction=(1.0, 2.0),
            treatment_prediction=(0.5, 0.5),
            config=config(),
        )
    with pytest.raises(DMLNumericalError) as captured:
        estimate_partialling_out(
            outcome=(1.0, float("nan")),
            treatment=(0.0, 1.0),
            outcome_prediction=(0.0, 0.0),
            treatment_prediction=(0.5, 0.5),
            config=config(),
        )
    assert captured.value.code == "dml.nonfinite_residual"


def test_nuisance_metrics_match_independent_reference_values() -> None:
    diagnostics = build_nuisance_diagnostics(
        outcome=(1.0, 2.0, 3.0, 4.0),
        outcome_prediction=(1.0, 2.0, 2.0, 5.0),
        treatment=(False, False, True, True),
        treatment_prediction=(0.1, 0.2, 0.8, 0.9),
        config=config(),
    )

    assert diagnostics.outcome.rmse == pytest.approx(math.sqrt(0.5))
    assert diagnostics.outcome.mae == pytest.approx(0.5)
    assert diagnostics.outcome.r_squared == pytest.approx(0.6)
    assert diagnostics.treatment.log_loss == pytest.approx(0.164252033486018)
    assert diagnostics.treatment.brier_score == pytest.approx(0.025)
    assert diagnostics.treatment.roc_auc == pytest.approx(1.0)
    assert "does not establish causal validity" in diagnostics.interpretation


def test_nuisance_r_squared_and_auc_are_unavailable_when_undefined() -> None:
    diagnostics = build_nuisance_diagnostics(
        outcome=(2.0, 2.0, 2.0),
        outcome_prediction=(1.0, 2.0, 3.0),
        treatment=(True, True, True),
        treatment_prediction=(0.2, 0.5, 0.8),
        config=config(),
    )

    assert diagnostics.outcome.r_squared is None
    assert diagnostics.treatment.roc_auc is None


def test_dml_overlap_distinguishes_healthy_and_fatal_score_support() -> None:
    healthy = assess_dml_overlap(
        scores=(0.30, 0.30, 0.40, 0.40, 0.50, 0.50, 0.60, 0.60),
        treated=(False, True, False, True, False, True, False, True),
        config=config(),
    )
    fatal = assess_dml_overlap(
        scores=(0.01, 0.02, 0.98, 0.99),
        treated=(False, False, True, True),
        config=config(),
    )

    assert healthy.status is OverlapStatus.ACCEPTABLE
    assert healthy.common_support.lower == pytest.approx(0.30)
    assert healthy.common_support.upper == pytest.approx(0.60)
    assert fatal.status is OverlapStatus.SEVERE
    assert fatal.common_support.status.value == "empty"
    assert "dml.overlap.empty_support" in fatal.diagnostic_codes


def test_dml_overlap_accepts_shared_nonextreme_constant_propensity() -> None:
    overlap = assess_dml_overlap(
        scores=(0.5, 0.5, 0.5, 0.5),
        treated=(False, True, False, True),
        config=config(),
    )

    assert overlap.status is OverlapStatus.ACCEPTABLE
    assert overlap.target_outside_support_fraction == 0.0
