"""Typed descriptive, associational, and causal estimate contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from .base import AnalysisStatus, ContractModel, PositiveInt
from .estimands import EstimandDefinition
from .metrics import MeasuredValue, MetricDefinition, OutcomeMetric, SampleCounts
from .provenance import (
    AnalysisWarning,
    AssumptionAssessment,
    Diagnostic,
    ProvenanceRecords,
)
from .uncertainty import UncertaintyBundle


class ConclusionType(StrEnum):
    """Epistemic meaning asserted by an estimate or projection."""

    ASSOCIATION = "association"
    CAUSAL_EFFECT = "causal_effect"
    PROJECTION = "projection"


class DescriptiveStatisticType(StrEnum):
    """Supported descriptive summaries that do not carry an estimand."""

    SAMPLE_MEAN = "sample_mean"
    SAMPLE_PROPORTION = "sample_proportion"
    SAMPLE_COUNT = "sample_count"


type FindingStatus = Literal[
    AnalysisStatus.COMPLETED,
    AnalysisStatus.INCONCLUSIVE,
]


class EffectEstimateDetails(ContractModel):
    """Shared measured details for an explicit effect-estimate category."""

    status: FindingStatus
    estimand: EstimandDefinition
    outcome: OutcomeMetric
    point_estimate: MeasuredValue
    uncertainty: UncertaintyBundle
    sample_counts: SampleCounts
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords


class DescriptiveStatistic(ContractModel):
    """Descriptive sample statistic without a treatment-effect estimand."""

    finding_type: Literal["descriptive_statistic"] = "descriptive_statistic"
    statistic_type: DescriptiveStatisticType
    status: FindingStatus
    metric: MetricDefinition
    value: MeasuredValue
    uncertainty: UncertaintyBundle
    sample_size: PositiveInt
    provenance: ProvenanceRecords


class AssociationalEstimate(ContractModel):
    """Effect-shaped estimate restricted to an associational conclusion."""

    finding_type: Literal["associational_estimate"] = "associational_estimate"
    conclusion_type: Literal[ConclusionType.ASSOCIATION]
    estimate: EffectEstimateDetails


class RandomizedExperimentEstimate(ContractModel):
    """Estimate from a randomized design with an explicit conclusion type."""

    finding_type: Literal["randomized_experiment_estimate"] = "randomized_experiment_estimate"
    conclusion_type: Literal[ConclusionType.ASSOCIATION, ConclusionType.CAUSAL_EFFECT]
    estimate: EffectEstimateDetails


class QuasiExperimentalEstimate(ContractModel):
    """Estimate from a quasi-experimental design with explicit evidence strength."""

    finding_type: Literal["quasi_experimental_estimate"] = "quasi_experimental_estimate"
    conclusion_type: Literal[ConclusionType.ASSOCIATION, ConclusionType.CAUSAL_EFFECT]
    estimate: EffectEstimateDetails


class ObservationalEstimate(ContractModel):
    """Estimate from an observational design with explicit evidence strength."""

    finding_type: Literal["observational_estimate"] = "observational_estimate"
    conclusion_type: Literal[ConclusionType.ASSOCIATION, ConclusionType.CAUSAL_EFFECT]
    estimate: EffectEstimateDetails


type EffectEstimate = Annotated[
    AssociationalEstimate
    | RandomizedExperimentEstimate
    | QuasiExperimentalEstimate
    | ObservationalEstimate,
    Field(discriminator="finding_type"),
]

type AnalysisFinding = Annotated[
    DescriptiveStatistic
    | AssociationalEstimate
    | RandomizedExperimentEstimate
    | QuasiExperimentalEstimate
    | ObservationalEstimate,
    Field(discriminator="finding_type"),
]
