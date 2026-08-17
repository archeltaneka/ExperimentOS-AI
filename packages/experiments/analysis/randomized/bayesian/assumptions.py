"""Stable assumptions for conjugate Bayesian randomized analysis."""

from __future__ import annotations

from ...provenance import AssumptionAssessment, AssumptionStatus
from ..assumptions import randomized_assumptions
from .models import BayesianLikelihood, BernoulliBinomialLikelihood


def bayesian_assumptions(
    likelihood: BayesianLikelihood,
) -> tuple[AssumptionAssessment, ...]:
    """Return randomized and likelihood-specific assumptions without claiming proof."""
    if isinstance(likelihood, BernoulliBinomialLikelihood):
        model_specific = (
            AssumptionAssessment(
                code="binary_bernoulli_likelihood",
                statement=(
                    "Each validated binary observation is a Bernoulli outcome with success "
                    "encoded as one."
                ),
                status=AssumptionStatus.SUPPORTED,
            ),
            AssumptionAssessment(
                code="proper_beta_priors",
                statement="Both arm probabilities have explicit proper Beta priors.",
                status=AssumptionStatus.SUPPORTED,
            ),
        )
    else:
        model_specific = (
            AssumptionAssessment(
                code="normal_arm_likelihood",
                statement=(
                    "Outcomes are conditionally Normal with an unknown arm-specific mean "
                    "and variance."
                ),
                status=AssumptionStatus.UNASSESSED,
            ),
            AssumptionAssessment(
                code="proper_normal_inverse_gamma_priors",
                statement=(
                    "Both arm means and variances have explicit proper Normal-Inverse-Gamma "
                    "priors using the documented shape/scale convention."
                ),
                status=AssumptionStatus.SUPPORTED,
            ),
        )
    return randomized_assumptions() + model_specific


__all__ = ["bayesian_assumptions"]
