"""Requested uncertainty semantics for analysis requests."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .base import ContractModel, OpenProbability


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
