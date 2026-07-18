"""Typed operational thresholds for analysis eligibility validation."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from ..base import ContractModel, NonEmptyStr, Probability


class ValidationPolicy(ContractModel):
    """Explicit deterministic guardrails, not claims of statistical power or causality."""

    policy_version: NonEmptyStr = "analysis-validation-v1"
    minimum_total: int = Field(default=30, ge=1)
    minimum_per_arm: int = Field(default=10, ge=1)
    weak_total: int = Field(default=100, ge=1)
    weak_per_arm: int = Field(default=30, ge=1)
    minimum_per_segment_arm: int = Field(default=5, ge=1)
    minimum_clusters: int = Field(default=4, ge=2)
    weak_clusters: int = Field(default=20, ge=2)
    allocation_warning_deviation: Probability = 0.10
    allocation_blocking_deviation: Probability = 0.25
    maximum_segment_cardinality: int = Field(default=50, ge=1)
    maximum_outcome_missingness: Probability | None = None
    maximum_differential_missingness: Probability | None = None

    @model_validator(mode="after")
    def validate_threshold_order(self) -> Self:
        if self.weak_total < self.minimum_total:
            raise ValueError("weak_total must be at least minimum_total")
        if self.weak_per_arm < self.minimum_per_arm:
            raise ValueError("weak_per_arm must be at least minimum_per_arm")
        if self.weak_clusters < self.minimum_clusters:
            raise ValueError("weak_clusters must be at least minimum_clusters")
        if self.allocation_warning_deviation > self.allocation_blocking_deviation:
            raise ValueError(
                "allocation_warning_deviation must not exceed allocation_blocking_deviation"
            )
        return self
