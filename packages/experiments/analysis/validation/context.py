"""Normalized immutable inputs shared by analysis validation rule families."""

from __future__ import annotations

from dataclasses import dataclass

from ..requests import AnalysisRequest
from .bindings import AnalysisDataBinding
from .policy import ValidationPolicy
from .table import AnalysisTable


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """One immutable request, table snapshot, role binding, and policy bundle."""

    request: AnalysisRequest
    table: AnalysisTable
    binding: AnalysisDataBinding
    policy: ValidationPolicy

    @property
    def design_type(self) -> str:
        """Return the normalized study-design discriminator."""
        return self.request.study_design.design_type

    @property
    def method(self) -> str:
        """Return the normalized requested method value."""
        return self.request.study_design.method.value
