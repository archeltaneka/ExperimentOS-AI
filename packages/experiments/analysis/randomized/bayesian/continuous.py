"""Normal–Inverse-Gamma updates with deterministic effect quadrature."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from numbers import Real

from ...metrics import OutcomeDirection
from ...uncertainty import CredibleInterval, PosteriorProbability
from .models import (
    BayesianComputationConfig,
    NormalInverseGammaPosteriorSummary,
    NormalInverseGammaPrior,
    PosteriorEffectSummary,
    PracticalEquivalenceRegion,
    QuadratureDiagnostics,
    RopeProbabilitySummary,
)
from .numerics import (
    BayesianNumericalError,
    NumericalProbability,
    invert_unbounded_cdf,
    student_t_difference_cdf,
    student_t_equal_tailed_interval,
)


def calculate_normal_inverse_gamma_posteriors(
    *,
    treatment_arm_id: str,
    treatment_values: Sequence[object],
    treatment_prior: NormalInverseGammaPrior,
    control_arm_id: str,
    control_values: Sequence[object],
    control_prior: NormalInverseGammaPrior,
    credible_level: float,
    metric_direction: OutcomeDirection,
    rope: PracticalEquivalenceRegion | None,
    config: BayesianComputationConfig,
) -> tuple[
    NormalInverseGammaPosteriorSummary,
    NormalInverseGammaPosteriorSummary,
    PosteriorEffectSummary,
]:
    """Return exact arm posteriors and deterministic mean-difference quantities."""
    treatment = _arm_posterior(
        arm_id=treatment_arm_id,
        values=treatment_values,
        prior=treatment_prior,
        credible_level=credible_level,
    )
    control = _arm_posterior(
        arm_id=control_arm_id,
        values=control_values,
        prior=control_prior,
        credible_level=credible_level,
    )
    effect = _effect_summary(
        treatment,
        control,
        credible_level=credible_level,
        metric_direction=metric_direction,
        rope=rope,
        config=config,
    )
    return (treatment, control, effect)


def _arm_posterior(
    *,
    arm_id: str,
    values: Sequence[object],
    prior: NormalInverseGammaPrior,
    credible_level: float,
) -> NormalInverseGammaPosteriorSummary:
    observations = _continuous_values(values)
    n = len(observations)
    try:
        sample_mean = math.fsum(observations) / n
        centered_sum = math.fsum((value - sample_mean) ** 2 for value in observations)
        posterior_kappa = prior.kappa_0 + n
        posterior_mu = (prior.kappa_0 * prior.mu_0 + n * sample_mean) / posterior_kappa
        posterior_alpha = prior.alpha_0 + n / 2.0
        mean_shift = sample_mean - prior.mu_0
        posterior_beta = (
            prior.beta_0
            + centered_sum / 2.0
            + (prior.kappa_0 * n * mean_shift * mean_shift) / (2.0 * posterior_kappa)
        )
        degrees_of_freedom = 2.0 * posterior_alpha
        marginal_scale = math.sqrt(posterior_beta / (posterior_alpha * posterior_kappa))
        marginal_mean_variance = posterior_beta / (posterior_kappa * (posterior_alpha - 1.0))
    except (OverflowError, ValueError, ZeroDivisionError) as exc:
        raise BayesianNumericalError("continuous posterior calculation was not finite") from exc
    calculated = (
        sample_mean,
        centered_sum,
        posterior_kappa,
        posterior_mu,
        posterior_alpha,
        posterior_beta,
        degrees_of_freedom,
        marginal_scale,
        marginal_mean_variance,
    )
    if any(not math.isfinite(value) for value in calculated):
        raise BayesianNumericalError("continuous posterior calculation was not finite")
    if centered_sum < 0.0 or posterior_beta <= 0.0 or marginal_scale <= 0.0:
        raise BayesianNumericalError("continuous posterior parameters were invalid")
    lower, upper = student_t_equal_tailed_interval(
        degrees_of_freedom,
        posterior_mu,
        marginal_scale,
        credible_level,
    )
    return NormalInverseGammaPosteriorSummary(
        arm_id=arm_id,
        n=n,
        sample_mean=sample_mean,
        centered_sum_of_squares=centered_sum,
        prior=prior,
        posterior_mu=posterior_mu,
        posterior_kappa=posterior_kappa,
        posterior_alpha=posterior_alpha,
        posterior_beta=posterior_beta,
        marginal_degrees_of_freedom=degrees_of_freedom,
        marginal_location=posterior_mu,
        marginal_scale=marginal_scale,
        marginal_mean_variance=marginal_mean_variance,
        credible_interval=CredibleInterval(
            lower=lower,
            upper=upper,
            credible_level=credible_level,
        ),
    )


def _effect_summary(
    treatment: NormalInverseGammaPosteriorSummary,
    control: NormalInverseGammaPosteriorSummary,
    *,
    credible_level: float,
    metric_direction: OutcomeDirection,
    rope: PracticalEquivalenceRegion | None,
    config: BayesianComputationConfig,
) -> PosteriorEffectSummary:
    errors: list[float] = []

    def cdf(value: float) -> NumericalProbability:
        result = student_t_difference_cdf(
            value,
            treatment_degrees_of_freedom=treatment.marginal_degrees_of_freedom,
            treatment_location=treatment.marginal_location,
            treatment_scale=treatment.marginal_scale,
            control_degrees_of_freedom=control.marginal_degrees_of_freedom,
            control_location=control.marginal_location,
            control_scale=control.marginal_scale,
            config=config,
        )
        errors.append(result.absolute_error)
        return result

    effect_mean = treatment.posterior_mu - control.posterior_mu
    initial_width = max(treatment.marginal_scale + control.marginal_scale, 1e-12)
    tail = (1.0 - credible_level) / 2.0
    lower = invert_unbounded_cdf(
        cdf,
        target=tail,
        center=effect_mean,
        initial_half_width=initial_width,
        config=config,
    )
    upper = invert_unbounded_cdf(
        cdf,
        target=1.0 - tail,
        center=effect_mean,
        initial_half_width=initial_width,
        config=config,
    )
    at_zero = cdf(0.0)
    superiority = _unit_probability(1.0 - at_zero.value)
    if metric_direction is OutcomeDirection.INCREASE:
        probability_better = PosteriorProbability(
            probability=superiority,
            event="treatment outcome mean > control outcome mean; direction=increase",
        )
    elif metric_direction is OutcomeDirection.DECREASE:
        probability_better = PosteriorProbability(
            probability=_unit_probability(at_zero.value),
            event="treatment outcome mean < control outcome mean; direction=decrease",
        )
    else:
        probability_better = None
    rope_summary = _rope_summary(cdf, rope) if rope is not None else None
    variance = treatment.marginal_mean_variance + control.marginal_mean_variance
    return PosteriorEffectSummary(
        posterior_mean=effect_mean,
        posterior_median=effect_mean,
        posterior_standard_deviation=math.sqrt(variance),
        credible_interval=CredibleInterval(
            lower=lower,
            upper=upper,
            credible_level=credible_level,
        ),
        probability_of_superiority=PosteriorProbability(
            probability=superiority,
            event="treatment outcome mean > control outcome mean",
        ),
        probability_treatment_is_better=probability_better,
        metric_direction=metric_direction,
        rope_probability=rope_summary,
        quadrature=QuadratureDiagnostics(
            maximum_absolute_error=max(errors, default=0.0),
            absolute_tolerance=config.quadrature_absolute_tolerance,
            relative_tolerance=config.quadrature_relative_tolerance,
        ),
    )


def _rope_summary(
    cdf: Callable[[float], NumericalProbability],
    rope: PracticalEquivalenceRegion,
) -> RopeProbabilitySummary:
    below = _unit_probability(cdf(rope.lower).value)
    through_upper = _unit_probability(cdf(rope.upper).value)
    inside = _unit_probability(through_upper - below)
    above = _unit_probability(1.0 - through_upper)
    total = below + inside + above
    if not math.isfinite(total) or total <= 0.0:
        raise BayesianNumericalError("ROPE probabilities do not form a finite partition")
    return RopeProbabilitySummary(
        rope=rope,
        probability_below=below / total,
        probability_inside=inside / total,
        probability_above=above / total,
    )


def _continuous_values(values: Sequence[object]) -> tuple[float, ...]:
    if len(values) < 2:
        raise BayesianNumericalError("each continuous arm requires at least two observations")
    converted: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise BayesianNumericalError("continuous observations must be finite real numbers")
        try:
            number = float(value)
        except OverflowError as exc:
            raise BayesianNumericalError(
                "continuous observations must be finite real numbers"
            ) from exc
        if not math.isfinite(number):
            raise BayesianNumericalError("continuous observations must be finite real numbers")
        converted.append(number)
    return tuple(converted)


def _unit_probability(value: float) -> float:
    if not math.isfinite(value):
        raise BayesianNumericalError("posterior probability must be finite")
    tolerance = 1e-12
    if value < -tolerance or value > 1.0 + tolerance:
        raise BayesianNumericalError("posterior probability must be between zero and one")
    return min(1.0, max(0.0, value))


__all__ = ["calculate_normal_inverse_gamma_posteriors"]
