"""Issue #101 propensity reliability references through the production estimator."""

from __future__ import annotations

import pytest

from packages.evals.statistical.observational_fixtures import run_propensity_fixture
from packages.experiments.analysis.causal.propensity import (
    EffectiveSampleSizeStatus,
    OverlapStatus,
    PropensityFitStatus,
    PropensityStatus,
)


def _codes(result: object) -> set[str]:
    return {item.code for item in result.diagnostics}  # type: ignore[attr-defined]


def test_healthy_propensity_reference_reports_overlap_balance_weights_and_ess() -> None:
    result = run_propensity_fixture("propensity_good_overlap")

    assert result.status is PropensityStatus.COMPLETED
    assert result.estimand.value == "ate"
    assert result.model_fit.status is PropensityFitStatus.CONVERGED
    assert result.sample_counts.model == 60
    assert result.overlap.status is OverlapStatus.ACCEPTABLE
    assert result.common_support.lower is not None
    assert result.common_support.upper is not None
    assert result.common_support.lower < result.common_support.upper
    assert result.weights is not None
    assert result.weights.ess.status is EffectiveSampleSizeStatus.ACCEPTABLE
    assert result.balance is not None
    assert result.balance.raw_max_absolute_smd > 0.10
    assert result.balance.weighted_max_absolute_smd < result.balance.raw_max_absolute_smd
    assert result.balance.improved_count > 0
    first = result.scores[0]
    first_weight = result.weights.raw[0]
    expected_weight = 1.0 / (1.0 - first.score)
    assert first.treated is False
    assert first_weight.value == pytest.approx(expected_weight, abs=1e-12)


def test_propensity_scores_weights_and_diagnostics_are_repeatable() -> None:
    first = run_propensity_fixture("propensity_good_overlap")
    repeated = run_propensity_fixture("propensity_good_overlap")

    assert first.model_dump(mode="json") == repeated.model_dump(mode="json")


def test_weak_overlap_is_advisory_but_eligible() -> None:
    result = run_propensity_fixture("propensity_weak_overlap")

    assert result.status is PropensityStatus.COMPLETED
    assert result.overlap.status is OverlapStatus.WEAK
    assert any(item.code.startswith("overlap.") for item in result.diagnostics)
    assert result.weights is not None
    assert result.weights.ess.status is EffectiveSampleSizeStatus.ACCEPTABLE


@pytest.mark.parametrize(
    ("fixture_id", "diagnostic_code"),
    [
        ("propensity_no_overlap", "overlap.empty_common_support"),
        ("propensity_separation", "model.separation"),
    ],
)
def test_no_overlap_or_separation_abstains_without_usable_success(
    fixture_id: str,
    diagnostic_code: str,
) -> None:
    result = run_propensity_fixture(fixture_id)

    assert result.status is PropensityStatus.ABSTAINED
    assert result.overlap.status is OverlapStatus.SEVERE
    assert diagnostic_code in _codes(result)
    assert result.abstention_reason is not None


def test_convergence_failure_has_no_scores_weights_or_fabricated_completion() -> None:
    result = run_propensity_fixture("propensity_convergence_failure")

    assert result.status is PropensityStatus.ABSTAINED
    assert result.model_fit.status is PropensityFitStatus.NON_CONVERGED
    assert result.scores == ()
    assert result.score_diagnostics is None
    assert result.weights is None
    assert "model.convergence_failure" in _codes(result)


def test_extreme_weights_are_explicit_and_advisory_when_still_finite() -> None:
    result = run_propensity_fixture("propensity_extreme_weights")

    assert result.weights is not None
    assert result.weights.extreme_weight_count >= 1
    assert result.weights.overall.maximum > 10.0
    assert result.weights.ess.overall_ratio < 0.75
    assert "weight.extreme_tail" in _codes(result)


def test_low_effective_sample_size_abstains() -> None:
    result = run_propensity_fixture("propensity_low_ess")

    assert result.status is PropensityStatus.ABSTAINED
    assert result.weights is not None
    assert result.weights.ess.status is EffectiveSampleSizeStatus.COLLAPSED
    assert result.abstention_reason is not None
