"""Central configuration for unadjusted randomized analyses."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..base import ContractModel, NonEmptyStr, OpenProbability, PositiveInt
from ..provenance import ProvenanceRecord, ProvenanceSourceType


class ZeroRelativeBaselinePolicy(StrEnum):
    """Deterministic behavior when the control baseline is zero."""

    UNAVAILABLE = "unavailable"


class RandomizedAnalysisConfig(ContractModel):
    """Frozen numerical choices declared alongside each randomized result."""

    configuration_version: Literal["1"] = "1"
    alpha: OpenProbability = 0.05
    confidence_level: OpenProbability = 0.95
    continuous_method: Literal["welch_t"] = "welch_t"
    binary_method: Literal["two_proportion_z"] = "two_proportion_z"
    minimum_observations_per_arm: Annotated[int, Field(strict=True, ge=2)] = 2
    sparse_cell_threshold: PositiveInt = 5
    zero_relative_baseline_policy: ZeroRelativeBaselinePolicy = (
        ZeroRelativeBaselinePolicy.UNAVAILABLE
    )
    configuration_id: NonEmptyStr = "randomized_analysis"

    @model_validator(mode="after")
    def validate_probability_complement(self) -> Self:
        if abs((self.alpha + self.confidence_level) - 1.0) > 1e-12:
            raise ValueError("alpha plus confidence_level must equal 1")
        return self

    def configuration_provenance(self) -> ProvenanceRecord:
        """Return the stable provenance record for this embedded configuration."""
        return ProvenanceRecord(
            source_type=ProvenanceSourceType.CONFIGURATION,
            source_id=self.configuration_id,
            source_version=self.configuration_version,
        )
