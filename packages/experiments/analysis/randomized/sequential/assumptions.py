"""Declared assumptions for pre-registered sequential monitoring."""

from __future__ import annotations

from ...provenance import AssumptionAssessment, AssumptionStatus


def sequential_assumptions() -> tuple[AssumptionAssessment, ...]:
    """Return stable declarations without claiming external preregistration proof."""
    return (
        AssumptionAssessment(
            code="sequential.plan_preregistered",
            statement="The immutable sequential plan existed before the first observed look.",
            status=AssumptionStatus.UNTESTABLE,
        ),
        AssumptionAssessment(
            code="sequential.plan_immutable",
            statement="The registered plan and its fingerprint remain immutable across looks.",
            status=AssumptionStatus.SUPPORTED,
        ),
        AssumptionAssessment(
            code="sequential.fixed_treatment_control",
            statement="Treatment and control definitions remain fixed across cumulative looks.",
            status=AssumptionStatus.SUPPORTED,
        ),
        AssumptionAssessment(
            code="sequential.fixed_primary_outcome",
            statement="The registered primary outcome remains fixed across cumulative looks.",
            status=AssumptionStatus.SUPPORTED,
        ),
        AssumptionAssessment(
            code="sequential.cumulative_eligible_data",
            statement="Each look contains all eligible data observed through that look.",
            status=AssumptionStatus.UNTESTABLE,
        ),
        AssumptionAssessment(
            code="sequential.information_time_prespecified",
            statement="Information times were specified without using observed treatment effects.",
            status=AssumptionStatus.UNTESTABLE,
        ),
        AssumptionAssessment(
            code="sequential.valid_look_schedule",
            statement="Every evaluated look follows the registered information-time schedule.",
            status=AssumptionStatus.SUPPORTED,
        ),
        AssumptionAssessment(
            code="sequential.alpha_spending_controlled",
            statement="Sequential boundaries control cumulative alpha under the registered plan.",
            status=AssumptionStatus.SUPPORTED,
        ),
    )


__all__ = ["sequential_assumptions"]
