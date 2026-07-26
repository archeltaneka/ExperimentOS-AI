"""Fixed-order descriptive limitations derived from typed population summaries."""

from __future__ import annotations

from .models import (
    BinarySummary,
    ContinuousSummary,
    CountSummary,
    DescriptiveDiagnostic,
    PopulationSummary,
)


def distribution_diagnostics(
    population: PopulationSummary,
    *,
    configured_missingness_limit: float | None,
) -> tuple[DescriptiveDiagnostic, ...]:
    """Return deterministic descriptive limitations, never a statistical test.

    No skewness or tail diagnostic is emitted: the current configuration has no
    declared scale-free rule for either condition.  Missingness is only called
    extreme at an existing validation-policy limit, avoiding an invented threshold.
    """
    diagnostics: list[DescriptiveDiagnostic] = []
    if population.row_count and population.valid_outcome_count == 0:
        diagnostics.append(
            DescriptiveDiagnostic(
                code="outcome.all_missing",
                message="All selected outcome observations are missing.",
            )
        )
    if 0 < population.valid_outcome_count < 2:
        diagnostics.append(
            DescriptiveDiagnostic(
                code="outcome.sparse_valid_sample",
                message="Fewer than two valid outcome observations are available.",
            )
        )
    if _has_zero_variance(population):
        diagnostics.append(
            DescriptiveDiagnostic(
                code="outcome.zero_variance",
                message="Valid outcome observations have zero sample variance.",
            )
        )
    if (
        configured_missingness_limit is not None
        and population.row_count
        and population.missing_outcome_count / population.row_count >= configured_missingness_limit
    ):
        diagnostics.append(
            DescriptiveDiagnostic(
                code="outcome.missingness_at_configured_limit",
                message="Outcome missingness is at or above the configured reporting limit.",
            )
        )
    return tuple(diagnostics)


def small_arm_warning(
    treatment: PopulationSummary | None,
    control: PopulationSummary | None,
    *,
    advisory_minimum: int,
) -> tuple[DescriptiveDiagnostic, ...]:
    """Report an existing policy's advisory arm-size limitation for a segment."""
    if treatment is None or control is None:
        return ()
    if min(treatment.valid_outcome_count, control.valid_outcome_count) >= advisory_minimum:
        return ()
    return (
        DescriptiveDiagnostic(
            code="segment.small_arm",
            message="A selected segment arm is below the configured advisory sample size.",
        ),
    )


def _has_zero_variance(population: PopulationSummary) -> bool:
    summary = population.summary
    if isinstance(summary, (ContinuousSummary, CountSummary)):
        return summary.variance == 0.0
    if isinstance(summary, BinarySummary):
        return summary.variance == 0.0
    return False
