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
            code="sequential.cumulative_eligible_data",
            statement="Each look contains all eligible data observed through that look.",
            status=AssumptionStatus.UNTESTABLE,
        ),
        AssumptionAssessment(
            code="sequential.information_time_prespecified",
            statement="Information times were specified without using observed treatment effects.",
            status=AssumptionStatus.UNTESTABLE,
        ),
    )


__all__ = ["sequential_assumptions"]
