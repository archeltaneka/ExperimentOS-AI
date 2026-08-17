"""Analytic references for Normal–Inverse-Gamma Bayesian A/B inference."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis import OutcomeDirection
from packages.experiments.analysis.randomized.bayesian import (
    BayesianComputationConfig,
    NormalInverseGammaPrior,
    PracticalEquivalenceRegion,
)
from packages.experiments.analysis.randomized.bayesian.continuous import (
    calculate_normal_inverse_gamma_posteriors,
)
from packages.experiments.analysis.randomized.bayesian.numerics import BayesianNumericalError
from tests.analysis_contract_fixtures import proportion_unit, source
from tests.bayesian_fixtures import NIG_SHIFTED_REFERENCE


def _calculate(
    *,
    direction: OutcomeDirection = OutcomeDirection.INCREASE,
    rope: PracticalEquivalenceRegion | None = None,
):
    control_prior = NormalInverseGammaPrior(
        mu_0=0.0,
        kappa_0=1.0,
        alpha_0=2.0,
        beta_0=2.0,
        provenance=(source(),),
    )
    treatment_prior = control_prior.model_copy(update={"mu_0": 1.0})
    return calculate_normal_inverse_gamma_posteriors(
        treatment_arm_id="treatment",
        treatment_values=(2.0, 3.0, 4.0),
        treatment_prior=treatment_prior,
        control_arm_id="control",
        control_values=(1.0, 2.0, 3.0),
        control_prior=control_prior,
        credible_level=0.95,
        metric_direction=direction,
        rope=rope,
        config=BayesianComputationConfig(),
    )


def test_nig_update_locks_inverse_gamma_shape_scale_convention() -> None:
    treatment, control, _ = _calculate()
    reference = NIG_SHIFTED_REFERENCE

    assert (
        control.posterior_mu,
        control.posterior_kappa,
        control.posterior_alpha,
        control.posterior_beta,
    ) == reference.posterior
    assert treatment.posterior_mu == 2.5
    assert treatment.posterior_kappa == 4.0
    assert treatment.posterior_alpha == 3.5
    assert treatment.posterior_beta == 4.5
    assert control.centered_sum_of_squares == 2.0
    assert control.marginal_degrees_of_freedom == reference.marginal_degrees_of_freedom
    assert control.marginal_location == 1.5
    assert control.marginal_scale == reference.marginal_scale
    assert control.marginal_mean_variance == reference.marginal_mean_variance
    assert control.parameterization == "inverse_gamma_shape_scale"


def test_continuous_effect_matches_independent_student_t_difference_reference() -> None:
    _, _, effect = _calculate()
    reference = NIG_SHIFTED_REFERENCE

    assert effect.posterior_mean == reference.effect_mean
    assert effect.posterior_median == reference.effect_mean
    assert effect.posterior_standard_deviation == reference.effect_standard_deviation
    assert effect.credible_interval.lower == pytest.approx(
        reference.effect_interval_95[0], abs=3e-9
    )
    assert effect.credible_interval.upper == pytest.approx(
        reference.effect_interval_95[1], abs=3e-9
    )
    assert effect.probability_of_superiority.probability == pytest.approx(
        reference.probability_superiority, abs=2e-10
    )
    assert effect.quadrature.reproducible is True


def test_continuous_rope_and_direction_semantics_are_explicit() -> None:
    rope = PracticalEquivalenceRegion(
        lower=0.75,
        upper=1.25,
        unit=proportion_unit(),
    )
    _, _, increase = _calculate(rope=rope)
    _, _, decrease = _calculate(direction=OutcomeDirection.DECREASE)
    reference = NIG_SHIFTED_REFERENCE

    assert increase.rope_probability is not None
    assert increase.rope_probability.probability_below == pytest.approx(
        reference.rope_cdf[0], abs=2e-10
    )
    assert increase.rope_probability.probability_inside == pytest.approx(
        reference.rope_cdf[1] - reference.rope_cdf[0], abs=2e-10
    )
    assert increase.rope_probability.probability_above == pytest.approx(
        1.0 - reference.rope_cdf[1], abs=2e-10
    )
    assert decrease.probability_of_superiority.probability == pytest.approx(
        reference.probability_superiority, abs=2e-10
    )
    assert decrease.probability_treatment_is_better is not None
    assert decrease.probability_treatment_is_better.probability == pytest.approx(
        1.0 - reference.probability_superiority, abs=2e-10
    )


def test_zero_observed_variance_remains_defined_under_proper_prior() -> None:
    prior = NormalInverseGammaPrior(
        mu_0=0.0,
        kappa_0=1.0,
        alpha_0=2.0,
        beta_0=2.0,
        provenance=(source(),),
    )

    treatment, control, effect = calculate_normal_inverse_gamma_posteriors(
        treatment_arm_id="treatment",
        treatment_values=(2.0, 2.0),
        treatment_prior=prior,
        control_arm_id="control",
        control_values=(2.0, 2.0),
        control_prior=prior,
        credible_level=0.9,
        metric_direction=OutcomeDirection.NO_PREFERENCE,
        rope=None,
        config=BayesianComputationConfig(),
    )

    assert treatment.centered_sum_of_squares == 0.0
    assert control.centered_sum_of_squares == 0.0
    assert treatment.posterior_beta > 0.0
    assert effect.posterior_standard_deviation > 0.0
    assert effect.probability_of_superiority.probability == pytest.approx(0.5, abs=2e-10)


def test_continuous_calculation_is_exactly_repeatable() -> None:
    assert _calculate() == _calculate()


def test_negative_effect_and_informative_priors_update_explicitly() -> None:
    treatment_prior = NormalInverseGammaPrior(
        mu_0=-1.0,
        kappa_0=10.0,
        alpha_0=5.0,
        beta_0=4.0,
        provenance=(source(),),
        label="Informative fixture",
    )
    control_prior = treatment_prior.model_copy(update={"mu_0": 1.0})
    treatment, control, effect = calculate_normal_inverse_gamma_posteriors(
        treatment_arm_id="treatment",
        treatment_values=(-2.0, -1.0, 0.0),
        treatment_prior=treatment_prior,
        control_arm_id="control",
        control_values=(0.0, 1.0, 2.0),
        control_prior=control_prior,
        credible_level=0.9,
        metric_direction=OutcomeDirection.INCREASE,
        rope=None,
        config=BayesianComputationConfig(),
    )

    assert treatment.posterior_kappa == 13.0
    assert treatment.posterior_mu == -1.0
    assert treatment.posterior_alpha == 6.5
    assert treatment.posterior_beta == 5.0
    assert control.posterior_mu == 1.0
    assert effect.posterior_mean == -2.0
    assert effect.probability_of_superiority.probability < 0.01


@pytest.mark.parametrize(
    "values",
    ((1.0,), (1.0, None), (1.0, math.inf), (1.0, True)),
)
def test_continuous_calculator_rejects_inadequate_or_invalid_values(
    values: tuple[object, ...],
) -> None:
    prior = NormalInverseGammaPrior(
        mu_0=0.0,
        kappa_0=1.0,
        alpha_0=2.0,
        beta_0=2.0,
        provenance=(source(),),
    )

    with pytest.raises(BayesianNumericalError):
        calculate_normal_inverse_gamma_posteriors(
            treatment_arm_id="treatment",
            treatment_values=values,
            treatment_prior=prior,
            control_arm_id="control",
            control_values=(1.0, 2.0),
            control_prior=prior,
            credible_level=0.95,
            metric_direction=OutcomeDirection.INCREASE,
            rope=None,
            config=BayesianComputationConfig(),
        )
