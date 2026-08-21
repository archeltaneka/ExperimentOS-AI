"""Observational design, outcome, time, and unit contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import field_validator

from ..base import ContractModel, NonEmptyStr
from ..metrics import AnalysisUnit, OutcomeMetric
from ..provenance import ProvenanceRecords
from ..study_designs import TimePeriod


class ObservationalDesignType(StrEnum):
    """Supported and explicitly representable observational design families."""

    GENERIC = "generic_observational"
    DID = "difference_in_differences"
    PROPENSITY_WEIGHTING = "propensity_weighting"
    DML = "double_machine_learning"
    HETEROGENEOUS_EFFECTS = "heterogeneous_effects"
    CUSTOM = "custom"


class ObservationalDesign(ContractModel):
    """Declared design semantics without estimator selection."""

    design_type: ObservationalDesignType
    method: NonEmptyStr
    treated_group: NonEmptyStr | None = None
    comparison_group: NonEmptyStr | None = None
    stable_treatment_adoption: NonEmptyStr | None = None
    provenance: ProvenanceRecords


class CausalOutcome(ContractModel):
    """Outcome variable reference paired with the existing metric contract."""

    variable_id: NonEmptyStr
    metric: OutcomeMetric


class UnitSemantics(ContractModel):
    """Analysis, observation, and optional clustering unit declarations."""

    analysis_unit: AnalysisUnit
    observation_unit: AnalysisUnit
    clustering_unit: AnalysisUnit | None = None


class TimeSemantics(ContractModel):
    """Treatment and pre/post time declarations used by observational designs."""

    time_variable: NonEmptyStr | None
    treatment_start: datetime | None
    pre_period: TimePeriod | None = None
    post_period: TimePeriod | None = None
    provenance: ProvenanceRecords

    @field_validator("treatment_start")
    @classmethod
    def require_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("treatment_start must be timezone-aware")
        return value


__all__ = [
    "CausalOutcome",
    "ObservationalDesign",
    "ObservationalDesignType",
    "TimeSemantics",
    "UnitSemantics",
]
