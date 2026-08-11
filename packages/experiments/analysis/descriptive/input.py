"""Validated input boundary for deterministic descriptive statistics."""

from __future__ import annotations

from dataclasses import dataclass

from ..validation.context import ValidationContext
from ..validation.models import EligibilityValidationResult


class DescriptiveStatisticsInvariantError(ValueError):
    """Raised when a validated input is unsafe for descriptive computation."""


@dataclass(frozen=True, slots=True)
class DescriptiveStatisticsInput:
    """Immutable references to eligibility-owned validation evidence and source table."""

    context: ValidationContext
    eligibility: EligibilityValidationResult

    def assert_data_eligible(self) -> None:
        """Require data eligibility while allowing an unavailable future estimator."""
        if not self.eligibility.method_support.data_eligible:
            raise DescriptiveStatisticsInvariantError(
                "descriptive statistics require a data-eligible validation result"
            )
