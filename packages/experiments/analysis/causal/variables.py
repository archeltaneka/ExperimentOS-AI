"""Owned variable roles and explicit measurement-timing contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import field_validator, model_validator

from ..base import ContractModel, NonEmptyStr
from ..provenance import ProvenanceRecords
from ..study_designs import TimePeriod


class VariableRole(StrEnum):
    """Closed roles available to observational analysis variables."""

    TREATMENT = "treatment"
    OUTCOME = "outcome"
    ADJUSTMENT = "adjustment"
    EFFECT_MODIFIER = "effect_modifier"
    IDENTIFIER = "identifier"
    TIME = "time"
    CLUSTERING = "clustering"
    SEGMENTATION = "segmentation"
    POST_TREATMENT = "post_treatment"
    UNKNOWN = "unknown"


class MeasurementTiming(StrEnum):
    """Measurement timing relative to treatment assignment or exposure."""

    PRE_TREATMENT = "pre_treatment"
    AT_TREATMENT = "at_treatment"
    POST_TREATMENT = "post_treatment"
    TIME_INVARIANT = "time_invariant"
    UNKNOWN = "unknown"


class VariableTiming(ContractModel):
    """Explicit timing evidence without inference from variable names or values."""

    measurement_timing: MeasurementTiming
    reference_period: TimePeriod | None = None
    reference_timestamp: datetime | None = None
    treatment_start: datetime | None = None
    evidence: ProvenanceRecords

    @field_validator("reference_timestamp", "treatment_start")
    @classmethod
    def require_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("timing timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_reference_shape(self) -> Self:
        if self.reference_period is not None and self.reference_timestamp is not None:
            raise ValueError("timing may declare a reference period or timestamp, not both")
        return self


class CausalVariable(ContractModel):
    """One declared analysis variable with explicit roles and timing."""

    variable_id: NonEmptyStr
    label: NonEmptyStr
    roles: tuple[VariableRole, ...]
    timing: VariableTiming
    provenance: ProvenanceRecords

    @field_validator("roles")
    @classmethod
    def canonicalize_roles(cls, value: tuple[VariableRole, ...]) -> tuple[VariableRole, ...]:
        if not value:
            raise ValueError("a causal variable requires at least one explicit role")
        return tuple(sorted(value, key=lambda role: role.value))


__all__ = ["CausalVariable", "MeasurementTiming", "VariableRole", "VariableTiming"]
