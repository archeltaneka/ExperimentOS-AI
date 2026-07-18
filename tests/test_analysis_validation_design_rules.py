from __future__ import annotations

from collections.abc import Callable

import pytest

from packages.experiments.analysis.validation import DiagnosticDisposition
from packages.experiments.analysis.validation.context import ValidationContext
from packages.experiments.analysis.validation.data_rules import validate_data
from packages.experiments.analysis.validation.design_rules import validate_design
from tests.analysis_validation_fixtures import (
    context_with_absent_segment_value,
    context_with_aware_datetime_rows,
    context_with_covariate_missing_in_required_period,
    context_with_duplicate_single_row_units,
    context_with_high_cardinality_segment,
    context_with_incompatible_segment_values,
    context_with_invalid_period_rows,
    context_with_missing_cluster,
    context_with_missing_optional_covariate_values,
    context_with_missing_segment_assignment,
    context_with_missing_segment_column,
    context_with_missing_unit,
    context_with_randomization_unit_in_both_arms,
    context_with_repeated_rows_without_cluster,
    context_with_schema_failure_and_segment,
    context_with_segment_missing_control,
    context_with_small_segment,
    context_with_switching_unit,
    context_with_three_clusters,
)


@pytest.mark.parametrize(
    ("context_factory", "code"),
    [
        (context_with_missing_unit, "unit.identifier_missing"),
        (context_with_duplicate_single_row_units, "unit.duplicate_observation"),
        (
            context_with_randomization_unit_in_both_arms,
            "treatment.unit_multiple_assignments",
        ),
        (context_with_switching_unit, "treatment.switching"),
        (context_with_repeated_rows_without_cluster, "unit.repeated_without_clustering"),
        (context_with_missing_cluster, "unit.cluster_identifier_missing"),
        (context_with_three_clusters, "sample.cluster_insufficient"),
    ],
)
def test_unit_integrity(
    context_factory: Callable[[], ValidationContext],
    code: str,
) -> None:
    context = context_factory()
    result = validate_design(context, validate_data(context))

    assert code in {item.code for item in result.diagnostics}


def test_unit_summary_preserves_exact_identifier_counts() -> None:
    context = context_with_randomization_unit_in_both_arms()

    result = validate_design(context, validate_data(context))

    assert result.unit_integrity_summary.observation_unit_count == 2
    assert result.unit_integrity_summary.assignment_conflict_count == 1


@pytest.mark.parametrize(
    ("context_factory", "code"),
    [
        (
            context_with_covariate_missing_in_required_period,
            "covariate.period_unavailable",
        ),
        (context_with_missing_optional_covariate_values, "covariate.missing"),
    ],
)
def test_covariate_data_availability(
    context_factory: Callable[[], ValidationContext],
    code: str,
) -> None:
    context = context_factory()
    diagnostics = validate_design(context, validate_data(context)).diagnostics

    assert code in {item.code for item in diagnostics}


def test_invalid_and_missing_period_observations_are_structured() -> None:
    context = context_with_invalid_period_rows()

    result = validate_design(context, validate_data(context))

    assert {item.code for item in result.diagnostics} >= {
        "time.invalid_timestamp",
        "time.period_coverage_missing",
    }
    assert result.time_summary is not None
    assert result.time_summary.invalid_count == 1
    assert result.time_summary.pre_period_count == 2
    assert result.time_summary.post_period_count == 0


def test_aware_datetime_values_are_checked_without_rewriting_table_cells() -> None:
    context = context_with_aware_datetime_rows()
    original_rows = context.table.rows

    result = validate_design(context, validate_data(context))

    assert result.time_summary is not None
    assert result.time_summary.valid_count == 2
    assert context.table.rows is original_rows
    assert context.table.rows == original_rows


@pytest.mark.parametrize(
    ("context_factory", "code"),
    [
        (context_with_missing_segment_column, "segment.column_missing"),
        (context_with_absent_segment_value, "segment.value_absent"),
        (context_with_segment_missing_control, "segment.arm_missing"),
        (context_with_small_segment, "segment.insufficient_sample"),
        (context_with_missing_segment_assignment, "segment.missing_assignment"),
        (context_with_high_cardinality_segment, "segment.high_cardinality"),
    ],
)
def test_segment_diagnostics(
    context_factory: Callable[[], ValidationContext],
    code: str,
) -> None:
    context = context_factory()
    diagnostics = validate_design(context, validate_data(context)).diagnostics

    assert code in {item.code for item in diagnostics}


def test_segment_summary_uses_derived_valid_outcome_indexes() -> None:
    context = context_with_small_segment()

    result = validate_design(context, validate_data(context))

    assert result.segment_summary is not None
    assert result.segment_summary.selected_count == 4
    assert result.segment_summary.treatment_count == 2
    assert result.segment_summary.control_count == 2
    diagnostic = next(
        item for item in result.diagnostics if item.code == "segment.insufficient_sample"
    )
    assert diagnostic.disposition is DiagnosticDisposition.NEEDS_MORE_DATA


def test_incompatible_ordered_segment_values_are_structured() -> None:
    context = context_with_incompatible_segment_values()

    result = validate_design(context, validate_data(context))

    assert "segment.criteria_incompatible" in {item.code for item in result.diagnostics}
    assert "segment.value_absent" not in {item.code for item in result.diagnostics}


def test_upstream_schema_failure_suppresses_dependent_segment_cascades() -> None:
    context = context_with_schema_failure_and_segment()
    data_result = validate_data(context)

    result = validate_design(context, data_result)

    assert data_result.population_row_indexes == ()
    assert result.diagnostics == ()
