"""Structured assumptions shared by randomized estimators."""

from __future__ import annotations

from ..provenance import AssumptionAssessment, AssumptionStatus


def randomized_assumptions() -> tuple[AssumptionAssessment, ...]:
    """Return stable assumption claims without treating declarations as proof."""
    return (
        AssumptionAssessment(
            code="random_assignment",
            statement="Treatment assignment is randomized for the analyzed population.",
            status=AssumptionStatus.UNASSESSED,
        ),
        AssumptionAssessment(
            code="treatment_control_consistency",
            statement="Observed treatment and control labels represent the declared interventions.",
            status=AssumptionStatus.UNTESTABLE,
        ),
        AssumptionAssessment(
            code="stable_unit_treatment_value",
            statement="Each unit has well-defined potential outcomes under each arm.",
            status=AssumptionStatus.UNTESTABLE,
        ),
        AssumptionAssessment(
            code="no_interference",
            statement="One unit's assignment does not affect another unit's outcome.",
            status=AssumptionStatus.UNTESTABLE,
        ),
        AssumptionAssessment(
            code="compatible_analysis_randomization_units",
            statement="Analysis and randomization units satisfy the supported unit structure.",
            status=AssumptionStatus.UNASSESSED,
        ),
        AssumptionAssessment(
            code="independent_supported_units",
            statement="Analyzed outcomes are independent within and between arms.",
            status=AssumptionStatus.UNASSESSED,
        ),
        AssumptionAssessment(
            code="valid_outcome_measurement",
            statement="The declared primary outcome is measured validly and consistently.",
            status=AssumptionStatus.UNASSESSED,
        ),
        AssumptionAssessment(
            code="fixed_horizon_analysis",
            statement="Inference occurs once at the declared fixed analysis horizon.",
            status=AssumptionStatus.UNASSESSED,
        ),
        AssumptionAssessment(
            code="no_uncorrected_repeated_peeking",
            statement="No uncorrected repeated testing or optional stopping occurred.",
            status=AssumptionStatus.UNTESTABLE,
        ),
    )


__all__ = ["randomized_assumptions"]
