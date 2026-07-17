"""Study-design, arm, clustering, and covariate contracts."""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, NonEmptyStr, OpenProbability, ScalarValue
from .metrics import AnalysisUnit, MetricDefinition


class RandomizedAnalysisMethod(StrEnum):
    """Declared randomized-analysis method family."""

    FIXED_HORIZON_AB = "fixed_horizon_ab"
    CUPED = "cuped"
    SEQUENTIAL_AB = "sequential_ab"
    BAYESIAN_AB = "bayesian_ab"
    HETEROGENEOUS_TREATMENT_EFFECT = "heterogeneous_treatment_effect"


class QuasiExperimentalMethod(StrEnum):
    """Declared quasi-experimental method family."""

    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"


class ObservationalAnalysisMethod(StrEnum):
    """Declared observational-analysis method family."""

    PROPENSITY_SCORE = "propensity_score"
    WEIGHTING = "weighting"
    DOUBLE_MACHINE_LEARNING = "double_machine_learning"
    HETEROGENEOUS_TREATMENT_EFFECT = "heterogeneous_treatment_effect"


class CovariateTiming(StrEnum):
    """Timing of a covariate relative to treatment."""

    PRE_TREATMENT = "pre_treatment"
    AT_TREATMENT = "at_treatment"
    POST_TREATMENT = "post_treatment"
    TIME_VARYING = "time_varying"
    UNKNOWN = "unknown"


class CovariateRole(StrEnum):
    """Declared analytical role of a covariate."""

    ADJUSTMENT = "adjustment"
    CONFOUNDER = "confounder"
    PRECISION = "precision"
    EFFECT_MODIFIER = "effect_modifier"
    CUPED = "cuped"
    TREATMENT_INDICATOR = "treatment_indicator"
    TREATMENT_PROXY = "treatment_proxy"


class TreatmentRelationship(StrEnum):
    """Known relationship between a covariate and treatment."""

    NONE_KNOWN = "none_known"
    ASSIGNMENT_DERIVED = "assignment_derived"
    PROXY = "proxy"
    UNKNOWN = "unknown"


class TimePeriod(ContractModel):
    """A strictly ordered period bounded by timezone-aware timestamps."""

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        if self.start.utcoffset() is None or self.end.utcoffset() is None:
            raise ValueError("time period timestamps must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("time period start must be before end")
        return self


class TreatmentDefinition(ContractModel):
    """Explicit treatment-arm definition."""

    treatment_id: NonEmptyStr
    label: NonEmptyStr
    assignment_value: ScalarValue
    description: NonEmptyStr


class ControlDefinition(ContractModel):
    """Explicit control-arm definition."""

    control_id: NonEmptyStr
    label: NonEmptyStr
    assignment_value: ScalarValue
    description: NonEmptyStr


class NoClustering(ContractModel):
    """Explicit declaration that observations are not clustered."""

    kind: Literal["none"] = "none"


class Clustered(ContractModel):
    """Clustering declaration with its own explicit unit."""

    kind: Literal["clustered"] = "clustered"
    unit: AnalysisUnit


type ClusteringSpecification = Annotated[
    NoClustering | Clustered,
    Field(discriminator="kind"),
]


class CovariateDefinition(ContractModel):
    """Covariate metadata that preserves timing and treatment relationships."""

    metric: MetricDefinition
    timing: CovariateTiming
    role: CovariateRole
    treatment_relationship: TreatmentRelationship
    measurement_period: TimePeriod


class PreTreatmentMetric(ContractModel):
    """Metric measured during an explicit candidate pre-treatment period."""

    metric: MetricDefinition
    measurement_period: TimePeriod


class RandomizedExperimentDesign(ContractModel):
    """Randomized design declaration without estimator behavior."""

    design_type: Literal["randomized_experiment"] = "randomized_experiment"
    method: RandomizedAnalysisMethod
    experiment_period: TimePeriod
    randomization_unit: AnalysisUnit
    treatment_allocation: OpenProbability
    control_allocation: OpenProbability

    @model_validator(mode="after")
    def validate_allocations(self) -> Self:
        total = self.treatment_allocation + self.control_allocation
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("treatment and control allocations must sum to one")
        return self


class QuasiExperimentalDesign(ContractModel):
    """Quasi-experimental design declaration with explicit before and after periods."""

    design_type: Literal["quasi_experimental"] = "quasi_experimental"
    method: QuasiExperimentalMethod
    pre_treatment_period: TimePeriod
    post_treatment_period: TimePeriod

    @model_validator(mode="after")
    def validate_periods(self) -> Self:
        if self.pre_treatment_period.end > self.post_treatment_period.start:
            raise ValueError(
                "pre-treatment period must end no later than post-treatment period starts"
            )
        return self


class ObservationalStudyDesign(ContractModel):
    """Observational design declaration without randomized-assignment implications."""

    design_type: Literal["observational_study"] = "observational_study"
    method: ObservationalAnalysisMethod
    observation_period: TimePeriod


type StudyDesign = Annotated[
    RandomizedExperimentDesign | QuasiExperimentalDesign | ObservationalStudyDesign,
    Field(discriminator="design_type"),
]
