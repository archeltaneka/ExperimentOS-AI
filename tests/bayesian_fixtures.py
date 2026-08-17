"""Independent deterministic references for conjugate Bayesian tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BetaDifferenceReference:
    treatment_posterior: tuple[float, float]
    control_posterior: tuple[float, float]
    treatment_mean: float
    treatment_variance: float
    control_mean: float
    control_variance: float
    effect_mean: float
    effect_standard_deviation: float
    effect_median: float
    effect_interval_95: tuple[float, float]
    probability_superiority: float
    rope_cdf: tuple[float, float]


# Prior Beta(1,1), treatment observations (1,1), and control observations (1,0)
# produce Beta(3,1) and Beta(2,2). P(T>C)=0.8 follows from integrating the
# polynomial 3*x^2 * (3*x^2 - 2*x^3). Quantiles were independently evaluated
# from that piecewise polynomial difference CDF, outside production helpers.
BETA_POLYNOMIAL_REFERENCE = BetaDifferenceReference(
    treatment_posterior=(3.0, 1.0),
    control_posterior=(2.0, 2.0),
    treatment_mean=0.75,
    treatment_variance=0.0375,
    control_mean=0.5,
    control_variance=0.05,
    effect_mean=0.25,
    effect_standard_deviation=0.0875**0.5,
    effect_median=0.25950440790548623,
    effect_interval_95=(-0.3618270634960254, 0.7811646899596558),
    probability_superiority=0.8,
    rope_cdf=(0.1240029, 0.3030031),
)


@dataclass(frozen=True, slots=True)
class NormalInverseGammaReference:
    posterior: tuple[float, float, float, float]
    marginal_degrees_of_freedom: float
    marginal_scale: float
    marginal_mean_variance: float
    effect_mean: float
    effect_standard_deviation: float
    effect_interval_95: tuple[float, float]
    probability_superiority: float
    rope_cdf: tuple[float, float]


# Control prior (mu0=0,kappa0=1,alpha0=2,beta0=2) and data (1,2,3)
# yield (mu_n=1.5,kappa_n=4,alpha_n=3.5,beta_n=4.5). A treatment prior
# shifted to mu0=1 with data (2,3,4) has the identical posterior shape shifted
# by one. Difference references were independently integrated from two t_7
# densities with scale sqrt(4.5/14), outside production helpers.
NIG_SHIFTED_REFERENCE = NormalInverseGammaReference(
    posterior=(1.5, 4.0, 3.5, 4.5),
    marginal_degrees_of_freedom=7.0,
    marginal_scale=(4.5 / 14.0) ** 0.5,
    marginal_mean_variance=0.45,
    effect_mean=1.0,
    effect_standard_deviation=0.9**0.5,
    effect_interval_95=(-0.8854815206046078, 2.8854815206046105),
    probability_superiority=0.8662116898198173,
    rope_cdf=(0.38793245734649345, 0.6120675426535065),
)


__all__ = [
    "BETA_POLYNOMIAL_REFERENCE",
    "NIG_SHIFTED_REFERENCE",
    "BetaDifferenceReference",
    "NormalInverseGammaReference",
]
