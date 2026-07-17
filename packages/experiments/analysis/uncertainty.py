"""Requested and estimate-level uncertainty contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, FiniteFloat, NonEmptyStr, OpenProbability, Probability


class RequestedConfidenceLevel(ContractModel):
    """Requested frequentist confidence level."""

    kind: Literal["confidence"] = "confidence"
    level: OpenProbability


class RequestedCredibleLevel(ContractModel):
    """Requested Bayesian credible level."""

    kind: Literal["credible"] = "credible"
    level: OpenProbability


type RequestedUncertainty = Annotated[
    RequestedConfidenceLevel | RequestedCredibleLevel,
    Field(discriminator="kind"),
]


class StandardError(ContractModel):
    """Finite nonnegative standard error."""

    kind: Literal["standard_error"] = "standard_error"
    value: Annotated[FiniteFloat, Field(ge=0)]


class ConfidenceInterval(ContractModel):
    """Frequentist interval with explicit confidence semantics."""

    kind: Literal["confidence_interval"] = "confidence_interval"
    lower: FiniteFloat
    upper: FiniteFloat
    confidence_level: OpenProbability

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("confidence interval lower bound must not exceed upper bound")
        return self


class CredibleInterval(ContractModel):
    """Bayesian interval with explicit credible-level semantics."""

    kind: Literal["credible_interval"] = "credible_interval"
    lower: FiniteFloat
    upper: FiniteFloat
    credible_level: OpenProbability

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("credible interval lower bound must not exceed upper bound")
        return self


class PosteriorProbability(ContractModel):
    """Posterior probability for an explicitly stated event."""

    kind: Literal["posterior_probability"] = "posterior_probability"
    probability: Probability
    event: NonEmptyStr


class UncertaintyUnavailable(ContractModel):
    """Explanation used when numerical uncertainty cannot be represented."""

    kind: Literal["unavailable"] = "unavailable"
    reason: NonEmptyStr


type UncertaintyMeasure = Annotated[
    StandardError
    | ConfidenceInterval
    | CredibleInterval
    | PosteriorProbability
    | UncertaintyUnavailable,
    Field(discriminator="kind"),
]


class UncertaintyBundle(ContractModel):
    """Non-empty collection of compatible uncertainty measures."""

    measures: Annotated[tuple[UncertaintyMeasure, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unavailable_exclusivity(self) -> Self:
        has_unavailable = any(
            isinstance(measure, UncertaintyUnavailable) for measure in self.measures
        )
        has_numeric = any(
            not isinstance(measure, UncertaintyUnavailable) for measure in self.measures
        )
        if has_unavailable and has_numeric:
            raise ValueError("unavailable uncertainty cannot coexist with numeric uncertainty")
        return self
