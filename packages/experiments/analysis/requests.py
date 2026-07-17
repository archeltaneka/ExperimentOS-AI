"""Composed statistical and causal analysis request contract."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from .base import SCHEMA_VERSION, ContractModel
from .estimands import EstimandDefinition
from .metrics import AnalysisUnit, OutcomeMetric, SampleCounts
from .populations import PopulationDefinition, SegmentDefinition
from .study_designs import (
    ClusteringSpecification,
    ControlDefinition,
    CovariateDefinition,
    PreTreatmentMetric,
    QuasiExperimentalDesign,
    RandomizedExperimentDesign,
    StudyDesign,
    TreatmentDefinition,
)
from .uncertainty import RequestedUncertainty


class AnalysisRequest(ContractModel):
    """Versioned request carrying all declared inputs without selecting an estimator."""

    schema_version: Literal["1"] = SCHEMA_VERSION
    population: PopulationDefinition
    segment: SegmentDefinition | None = None
    treatment: TreatmentDefinition
    control: ControlDefinition
    outcome: OutcomeMetric
    estimand: EstimandDefinition
    study_design: StudyDesign
    unit_of_analysis: AnalysisUnit
    clustering: ClusteringSpecification
    sample_counts: SampleCounts
    uncertainty: RequestedUncertainty
    covariates: tuple[CovariateDefinition, ...] = ()
    pre_treatment_metrics: tuple[PreTreatmentMetric, ...] = ()

    @model_validator(mode="after")
    def validate_request_structure(self) -> Self:
        if self.treatment.treatment_id == self.control.control_id:
            raise ValueError("treatment and control identifiers must differ")
        if self.treatment.label == self.control.label:
            raise ValueError("treatment and control labels must differ")
        if self.treatment.assignment_value == self.control.assignment_value:
            raise ValueError("treatment and control assignment values must differ")

        cutoff = None
        if isinstance(self.study_design, RandomizedExperimentDesign):
            cutoff = self.study_design.experiment_period.start
        elif isinstance(self.study_design, QuasiExperimentalDesign):
            cutoff = self.study_design.post_treatment_period.start

        if cutoff is not None:
            for metric in self.pre_treatment_metrics:
                if metric.measurement_period.end > cutoff:
                    raise ValueError(
                        "pre-treatment metric measurement must end no later than treatment starts"
                    )
        return self
