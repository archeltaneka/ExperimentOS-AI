"""Analytic and deterministic reference tests for Beta-Binomial inference."""

from __future__ import annotations

import pytest

from packages.experiments.analysis import OutcomeDirection
from packages.experiments.analysis.randomized.bayesian import (
    BayesianComputationConfig,
    BetaPrior,
    PracticalEquivalenceRegion,
)
from packages.experiments.analysis.randomized.bayesian.binary import (
    calculate_beta_binomial_posteriors,
)
from packages.experiments.analysis.randomized.bayesian.numerics import BayesianNumericalError
from tests.analysis_contract_fixtures import proportion_unit, source
from tests.bayesian_fixtures import BETA_POLYNOMIAL_REFERENCE


def _calculate(
    *,
    direction: OutcomeDirection = OutcomeDirection.INCREASE,
    rope: PracticalEquivalenceRegion | None = None,
):
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),), label="Uniform fixture")
    return calculate_beta_binomial_posteriors(
        treatment_arm_id="treatment",
        treatment_values=(1, 1),
        treatment_prior=prior,
        control_arm_id="control",
        control_values=(1, 0),
        control_prior=prior,
        credible_level=0.95,
        metric_direction=direction,
        rope=rope,
        config=BayesianComputationConfig(),
    )


def test_exact_beta_updates_and_arm_moments_match_reference() -> None:
    treatment, control, _ = _calculate()
    reference = BETA_POLYNOMIAL_REFERENCE

    assert (treatment.posterior_alpha, treatment.posterior_beta) == (reference.treatment_posterior)
    assert (control.posterior_alpha, control.posterior_beta) == reference.control_posterior
    assert treatment.posterior_mean == reference.treatment_mean
    assert treatment.posterior_variance == reference.treatment_variance
    assert control.posterior_mean == reference.control_mean
    assert control.posterior_variance == reference.control_variance
    assert treatment.successes == 2
    assert treatment.failures == 0
    assert control.successes == 1
    assert control.failures == 1
    assert treatment.prior.alpha == 1.0
    assert treatment.prior.beta == 1.0


def test_binary_effect_summary_matches_independent_difference_reference() -> None:
    _, _, effect = _calculate()
    reference = BETA_POLYNOMIAL_REFERENCE

    assert effect.posterior_mean == reference.effect_mean
    assert effect.posterior_standard_deviation == reference.effect_standard_deviation
    assert effect.posterior_median == pytest.approx(reference.effect_median, abs=2e-10)
    assert effect.credible_interval.lower == pytest.approx(
        reference.effect_interval_95[0], abs=2e-10
    )
    assert effect.credible_interval.upper == pytest.approx(
        reference.effect_interval_95[1], abs=2e-10
    )
    assert effect.probability_of_superiority.probability == pytest.approx(0.8, abs=1e-11)
    assert effect.probability_of_superiority.event == (
        "treatment outcome parameter > control outcome parameter"
    )
    assert effect.probability_treatment_is_better is not None
    assert effect.probability_treatment_is_better.probability == pytest.approx(0.8, abs=1e-11)
    assert effect.credible_interval.kind == "credible_interval"
    assert effect.interval_method == "equal_tailed"
    assert effect.computation_method == "deterministic_quadrature"


def test_metric_direction_changes_only_treatment_is_better_semantics() -> None:
    _, _, decrease = _calculate(direction=OutcomeDirection.DECREASE)
    _, _, neutral = _calculate(direction=OutcomeDirection.NO_PREFERENCE)

    assert decrease.probability_of_superiority.probability == pytest.approx(0.8, abs=1e-11)
    assert decrease.probability_treatment_is_better is not None
    assert decrease.probability_treatment_is_better.probability == pytest.approx(0.2, abs=1e-11)
    assert "direction=decrease" in decrease.probability_treatment_is_better.event
    assert neutral.probability_of_superiority.probability == pytest.approx(0.8, abs=1e-11)
    assert neutral.probability_treatment_is_better is None


def test_rope_is_omitted_unless_explicit_and_partitions_probability() -> None:
    _, _, absent = _calculate()
    rope = PracticalEquivalenceRegion(
        lower=-0.1,
        upper=0.1,
        unit=proportion_unit(),
    )
    _, _, present = _calculate(rope=rope)
    reference = BETA_POLYNOMIAL_REFERENCE

    assert absent.rope_probability is None
    assert present.rope_probability is not None
    assert present.rope_probability.rope == rope
    assert present.rope_probability.probability_below == pytest.approx(
        reference.rope_cdf[0], abs=2e-10
    )
    assert present.rope_probability.probability_inside == pytest.approx(
        reference.rope_cdf[1] - reference.rope_cdf[0], abs=2e-10
    )
    assert present.rope_probability.probability_above == pytest.approx(
        1.0 - reference.rope_cdf[1], abs=2e-10
    )


def test_informative_priors_update_without_data_dependent_defaults() -> None:
    treatment_prior = BetaPrior(alpha=20.0, beta=10.0, provenance=(source(),))
    control_prior = BetaPrior(alpha=5.0, beta=15.0, provenance=(source(),))

    treatment, control, _ = calculate_beta_binomial_posteriors(
        treatment_arm_id="treatment",
        treatment_values=(1, 0, 1),
        treatment_prior=treatment_prior,
        control_arm_id="control",
        control_values=(0, 0, 1),
        control_prior=control_prior,
        credible_level=0.9,
        metric_direction=OutcomeDirection.INCREASE,
        rope=None,
        config=BayesianComputationConfig(),
    )

    assert (treatment.posterior_alpha, treatment.posterior_beta) == (22.0, 11.0)
    assert (control.posterior_alpha, control.posterior_beta) == (6.0, 17.0)
    assert treatment.credible_interval.credible_level == 0.9


def test_sparse_zero_and_all_events_remain_defined_and_repeatable() -> None:
    first = _calculate()
    second = _calculate()

    assert first == second
    assert first[0].posterior_mean == 0.75
    assert 0.0 <= first[2].probability_of_superiority.probability <= 1.0


def test_control_better_reverses_effect_without_reversing_superiority_definition() -> None:
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),))
    _, _, effect = calculate_beta_binomial_posteriors(
        treatment_arm_id="treatment",
        treatment_values=(1, 0),
        treatment_prior=prior,
        control_arm_id="control",
        control_values=(1, 1),
        control_prior=prior,
        credible_level=0.95,
        metric_direction=OutcomeDirection.INCREASE,
        rope=None,
        config=BayesianComputationConfig(),
    )

    assert effect.posterior_mean == -0.25
    assert effect.probability_of_superiority.probability == pytest.approx(0.2, abs=1e-11)


def test_rope_mass_can_be_inside_above_or_below_without_classification() -> None:
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),))
    wide_rope = PracticalEquivalenceRegion(
        lower=-0.5,
        upper=0.5,
        unit=proportion_unit(),
    )
    narrow_rope = PracticalEquivalenceRegion(
        lower=-0.05,
        upper=0.05,
        unit=proportion_unit(),
    )

    def effect(treatment_values: tuple[int, ...], control_values: tuple[int, ...], rope):
        return calculate_beta_binomial_posteriors(
            treatment_arm_id="treatment",
            treatment_values=treatment_values,
            treatment_prior=prior,
            control_arm_id="control",
            control_values=control_values,
            control_prior=prior,
            credible_level=0.9,
            metric_direction=OutcomeDirection.INCREASE,
            rope=rope,
            config=BayesianComputationConfig(),
        )[2]

    inside = effect((1, 0) * 10, (1, 0) * 10, wide_rope).rope_probability
    above = effect((1,) * 18 + (0,) * 2, (1,) * 2 + (0,) * 18, narrow_rope).rope_probability
    below = effect((1,) * 2 + (0,) * 18, (1,) * 18 + (0,) * 2, narrow_rope).rope_probability

    assert inside is not None and inside.probability_inside > 0.9
    assert above is not None and above.probability_above > 0.99
    assert below is not None and below.probability_below > 0.99


@pytest.mark.parametrize("values", ((), (0, 2), (0, None)))
def test_binary_calculator_rejects_empty_or_nonbinary_observations(
    values: tuple[object, ...],
) -> None:
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),))

    with pytest.raises(BayesianNumericalError):
        calculate_beta_binomial_posteriors(
            treatment_arm_id="treatment",
            treatment_values=values,
            treatment_prior=prior,
            control_arm_id="control",
            control_values=(0,),
            control_prior=prior,
            credible_level=0.95,
            metric_direction=OutcomeDirection.INCREASE,
            rope=None,
            config=BayesianComputationConfig(),
        )
