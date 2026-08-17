"""Exact Beta-Binomial updates with deterministic effect quadrature."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from numbers import Real

from ...metrics import OutcomeDirection
from ...uncertainty import CredibleInterval, PosteriorProbability
from .models import (
    BayesianComputationConfig,
    BetaPosteriorSummary,
    BetaPrior,
    PosteriorEffectSummary,
    PracticalEquivalenceRegion,
    QuadratureDiagnostics,
    RopeProbabilitySummary,
)
from .numerics import (
    BayesianNumericalError,
    NumericalProbability,
    beta_difference_cdf,
    beta_equal_tailed_interval,
    beta_moments,
    invert_bounded_cdf,
)


def calculate_beta_binomial_posteriors(
    *,
    treatment_arm_id: str,
    treatment_values: Sequence[object],
    treatment_prior: BetaPrior,
    control_arm_id: str,
    control_values: Sequence[object],
    control_prior: BetaPrior,
    credible_level: float,
    metric_direction: OutcomeDirection,
    rope: PracticalEquivalenceRegion | None,
    config: BayesianComputationConfig,
) -> tuple[BetaPosteriorSummary, BetaPosteriorSummary, PosteriorEffectSummary]:
    """Return exact arm posteriors and a deterministic difference summary."""
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
    prior: BetaPrior,
    credible_level: float,
) -> BetaPosteriorSummary:
    successes, failures = _binary_counts(values)
    posterior_alpha = prior.alpha + successes
    posterior_beta = prior.beta + failures
    posterior_mean, posterior_variance = beta_moments(posterior_alpha, posterior_beta)
    lower, upper = beta_equal_tailed_interval(
        posterior_alpha,
        posterior_beta,
        credible_level,
    )
    return BetaPosteriorSummary(
        arm_id=arm_id,
        n=successes + failures,
        successes=successes,
        failures=failures,
        prior=prior,
        posterior_alpha=posterior_alpha,
        posterior_beta=posterior_beta,
        posterior_mean=posterior_mean,
        posterior_variance=posterior_variance,
        credible_interval=CredibleInterval(
            lower=lower,
            upper=upper,
            credible_level=credible_level,
        ),
    )


def _effect_summary(
    treatment: BetaPosteriorSummary,
    control: BetaPosteriorSummary,
    *,
    credible_level: float,
    metric_direction: OutcomeDirection,
    rope: PracticalEquivalenceRegion | None,
    config: BayesianComputationConfig,
) -> PosteriorEffectSummary:
    errors: list[float] = []

    def cdf(value: float) -> NumericalProbability:
        result = beta_difference_cdf(
            value,
            treatment_alpha=treatment.posterior_alpha,
            treatment_beta=treatment.posterior_beta,
            control_alpha=control.posterior_alpha,
            control_beta=control.posterior_beta,
            config=config,
        )
        errors.append(result.absolute_error)
        return result

    tail = (1.0 - credible_level) / 2.0
    lower = invert_bounded_cdf(cdf, target=tail, lower=-1.0, upper=1.0, config=config)
    median = invert_bounded_cdf(cdf, target=0.5, lower=-1.0, upper=1.0, config=config)
    upper = invert_bounded_cdf(cdf, target=1.0 - tail, lower=-1.0, upper=1.0, config=config)
    at_zero = cdf(0.0)
    superiority = _unit_probability(1.0 - at_zero.value)

    probability_better: PosteriorProbability | None
    if metric_direction is OutcomeDirection.INCREASE:
        probability_better = PosteriorProbability(
            probability=superiority,
            event="treatment outcome parameter > control outcome parameter; direction=increase",
        )
    elif metric_direction is OutcomeDirection.DECREASE:
        probability_better = PosteriorProbability(
            probability=_unit_probability(at_zero.value),
            event="treatment outcome parameter < control outcome parameter; direction=decrease",
        )
    else:
        probability_better = None

    rope_summary = _rope_summary(cdf, rope) if rope is not None else None
    effect_variance = treatment.posterior_variance + control.posterior_variance
    return PosteriorEffectSummary(
        posterior_mean=treatment.posterior_mean - control.posterior_mean,
        posterior_median=median,
        posterior_standard_deviation=math.sqrt(effect_variance),
        credible_interval=CredibleInterval(
            lower=lower,
            upper=upper,
            credible_level=credible_level,
        ),
        probability_of_superiority=PosteriorProbability(
            probability=superiority,
            event="treatment outcome parameter > control outcome parameter",
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


def _binary_counts(values: Sequence[object]) -> tuple[int, int]:
    if not values:
        raise BayesianNumericalError("each binary arm requires at least one observation")
    successes = 0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise BayesianNumericalError("binary observations must be finite zero-or-one numbers")
        try:
            converted = float(value)
        except OverflowError as exc:
            raise BayesianNumericalError(
                "binary observations must be finite zero-or-one numbers"
            ) from exc
        if not math.isfinite(converted) or converted not in {0.0, 1.0}:
            raise BayesianNumericalError("binary observations must be finite zero-or-one numbers")
        successes += int(converted)
    return (successes, len(values) - successes)


def _unit_probability(value: float) -> float:
    if not math.isfinite(value):
        raise BayesianNumericalError("posterior probability must be finite")
    tolerance = 1e-12
    if value < -tolerance or value > 1.0 + tolerance:
        raise BayesianNumericalError("posterior probability must be between zero and one")
    return min(1.0, max(0.0, value))


__all__ = ["calculate_beta_binomial_posteriors"]
