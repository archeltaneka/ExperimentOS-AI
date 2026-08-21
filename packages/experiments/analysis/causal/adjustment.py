"""Explicit repository-owned adjustment-set declaration."""

from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator

from ..base import ContractModel, NonEmptyStr
from ..provenance import ProvenanceRecords
from .estimands import CausalEstimandKind


class AdjustmentPurpose(StrEnum):
    """Declared reason variables are included in an adjustment set."""

    CONFOUNDING_CONTROL = "confounding_control"
    PRECISION = "precision"


class AdjustmentValidationStatus(StrEnum):
    """Lifecycle state of caller-supplied adjustment-set validation."""

    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"


class AdjustmentSet(ContractModel):
    """Caller-supplied adjustment variables and their declared purpose."""

    variable_ids: tuple[NonEmptyStr, ...]
    purpose: AdjustmentPurpose
    estimand_type: CausalEstimandKind
    source: NonEmptyStr
    validation_status: AdjustmentValidationStatus
    diagnostics: tuple[NonEmptyStr, ...]
    provenance: ProvenanceRecords

    @field_validator("variable_ids")
    @classmethod
    def canonicalize_variables(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("diagnostics")
    @classmethod
    def canonicalize_diagnostics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))


__all__ = ["AdjustmentPurpose", "AdjustmentSet", "AdjustmentValidationStatus"]
