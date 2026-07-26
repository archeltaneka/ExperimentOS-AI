from __future__ import annotations

from collections.abc import Callable

import pytest

from packages.experiments.analysis.validation import DiagnosticDisposition, ValidationPolicy
from packages.experiments.analysis.validation.context import ValidationContext
from packages.experiments.analysis.validation.data_rules import validate_data
from packages.experiments.analysis.validation.design_rules import validate_design
from tests.analysis_validation_fixtures import (
    context_with_absent_segment_value,
    context_with_aware_datetime_rows,
    context_with_bound_treatment_timestamps,
    context_with_covariate_missing_in_required_period,
    context_with_cross_sectional_covariate,
    context_with_duplicate_single_row_units,
    context_with_high_cardinality_segment,
    context_with_incompatible_segment_values,
    context_with_invalid_period_rows,
    context_with_longitudinal_covariate,
    context_with_missing_cluster,
    context_with_missing_optional_covariate_values,
    context_with_missing_segment_assignment,
    context_with_missing_segment_column,
    context_with_missing_unit,
    context_with_overlapping_assignment_conflict,
    context_with_quasi_treatment_timestamps,
    context_with_randomization_unit_in_both_arms,
    context_with_repeated_randomization_unit_treatment_timestamps,
    context_with_repeated_rows_without_cluster,
    context_with_schema_failure_and_segment,
    context_with_segment_missing_control,
    context_with_small_segment,
    context_with_stable_unit_mapping_mismatch,
    context_with_switching_unit,
    context_with_three_clusters,
    context_with_unhashable_observation_units,
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
    ],
)
def test_covariate_data_availability(
    context_factory: Callable[[], ValidationContext],
    code: str,
) -> None:
    context = context_factory()
    diagnostics = validate_design(context, validate_data(context)).diagnostics

    assert code in {item.code for item in diagnostics}


def test_cross_sectional_covariate_does_not_require_row_level_period_evidence() -> None:
    context = context_with_cross_sectional_covariate()

    diagnostics = validate_design(context, validate_data(context)).diagnostics

    assert "covariate.period_unavailable" not in {item.code for item in diagnostics}


def test_optional_covariate_missingness_is_non_blocking_without_threshold() -> None:
    context = context_with_missing_optional_covariate_values()

    diagnostics = validate_design(context, validate_data(context)).diagnostics

    assert not any(item.code.startswith("covariate.missing") for item in diagnostics)


def test_covariate_missingness_above_explicit_threshold_is_blocking() -> None:
    context = context_with_missing_optional_covariate_values(
        policy=ValidationPolicy(maximum_covariate_missing_rate=0.4)
    )

    diagnostics = validate_design(context, validate_data(context)).diagnostics

    diagnostic = next(
        item for item in diagnostics if item.code == "covariate.missingness_exceeds_threshold"
    )
    assert diagnostic.disposition is DiagnosticDisposition.BLOCKING
    assert {entry.key: entry.value for entry in diagnostic.context} == {
        "metric_id": "prior_order_count",
        "missing_count": 1,
        "missing_rate": 0.5,
        "threshold": 0.4,
    }


def test_covariate_missingness_equal_to_explicit_threshold_is_accepted() -> None:
    context = context_with_missing_optional_covariate_values(
        policy=ValidationPolicy(maximum_covariate_missing_rate=0.5)
    )
    data_result = validate_data(context)

    diagnostics = validate_design(context, data_result).diagnostics

    summary = next(
        item
        for item in data_result.missingness_summary
        if item.role == "covariate:prior_order_count"
    )
    assert summary.missing_count == 1
    assert summary.missing_rate == 0.5
    assert "covariate.missingness_exceeds_threshold" not in {item.code for item in diagnostics}


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


def test_later_missing_covariates_do_not_invalidate_valid_pre_period_evidence() -> None:
    context = context_with_longitudinal_covariate(missing_inside_period=False)

    result = validate_design(context, validate_data(context))

    codes = {item.code for item in result.diagnostics}
    assert "covariate.missing" not in codes
    assert "covariate.period_unavailable" not in codes


def test_missing_covariate_at_inclusive_period_start_is_blocking() -> None:
    context = context_with_longitudinal_covariate(
        missing_inside_period=True,
        policy=ValidationPolicy(maximum_covariate_missing_rate=0.4),
    )

    result = validate_design(context, validate_data(context))

    diagnostic = next(
        item
        for item in result.diagnostics
        if item.code == "covariate.missingness_exceeds_threshold"
    )
    assert {entry.key: entry.value for entry in diagnostic.context} == {
        "metric_id": "prior_order_count",
        "missing_count": 1,
        "missing_rate": 0.5,
        "threshold": 0.4,
    }


@pytest.mark.parametrize(
    ("values", "expected_missing_count"),
    [
        ((None, None), 2),
        ((None, "not-a-timestamp"), 1),
    ],
)
def test_bound_treatment_timestamp_missingness_is_blocking(
    values: tuple[object, object],
    expected_missing_count: int,
) -> None:
    context = context_with_bound_treatment_timestamps(values)

    result = validate_design(context, validate_data(context))

    diagnostic = next(
        item for item in result.diagnostics if item.code == "time.treatment_timestamp_missing"
    )
    assert diagnostic.disposition is DiagnosticDisposition.BLOCKING
    assert {entry.key: entry.value for entry in diagnostic.context} == {
        "column": "treated_at",
        "missing_count": expected_missing_count,
    }
    codes = tuple(item.code for item in result.diagnostics)
    if "time.invalid_treatment_timestamp" in codes:
        assert codes.index("time.treatment_timestamp_missing") < codes.index(
            "time.invalid_treatment_timestamp"
        )


def test_randomized_treatment_timestamps_outside_experiment_are_blocking() -> None:
    context = context_with_bound_treatment_timestamps(
        ("2026-06-30T23:59:59Z", "2026-07-15T00:00:00Z")
    )

    diagnostics = validate_design(context, validate_data(context)).diagnostics

    diagnostic = next(
        item for item in diagnostics if item.code == "time.treatment_timestamp_out_of_bounds"
    )
    assert diagnostic.disposition is DiagnosticDisposition.BLOCKING
    assert {entry.key: entry.value for entry in diagnostic.context} == {
        "allowed_end": "2026-07-15T00:00:00+00:00",
        "allowed_start": "2026-07-01T00:00:00+00:00",
        "column": "treated_at",
        "end_inclusive": False,
        "out_of_bounds_count": 2,
    }


def test_quasi_treatment_timestamp_must_fall_at_pre_post_boundary() -> None:
    context = context_with_quasi_treatment_timestamps(
        ("2026-06-30T23:59:59Z", "2026-07-01T00:00:01Z")
    )

    diagnostics = validate_design(context, validate_data(context)).diagnostics

    diagnostic = next(
        item for item in diagnostics if item.code == "time.treatment_timestamp_out_of_bounds"
    )
    assert {entry.key: entry.value for entry in diagnostic.context} == {
        "allowed_end": "2026-07-01T00:00:00+00:00",
        "allowed_start": "2026-07-01T00:00:00+00:00",
        "column": "treated_at",
        "end_inclusive": True,
        "out_of_bounds_count": 2,
    }


def test_compatible_treatment_timestamps_pass_boundary_and_consistency_checks() -> None:
    randomized = context_with_repeated_randomization_unit_treatment_timestamps(
        ("2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z")
    )
    quasi = context_with_quasi_treatment_timestamps(
        ("2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z")
    )

    for context in (randomized, quasi):
        codes = {item.code for item in validate_design(context, validate_data(context)).diagnostics}
        assert "time.treatment_timestamp_out_of_bounds" not in codes
        assert "treatment.timing_inconsistent" not in codes


def test_randomized_treatment_timing_consistency_uses_randomization_unit() -> None:
    context = context_with_repeated_randomization_unit_treatment_timestamps(
        ("2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z")
    )

    diagnostics = validate_design(context, validate_data(context)).diagnostics

    diagnostic = next(item for item in diagnostics if item.code == "treatment.timing_inconsistent")
    assert {entry.key: entry.value for entry in diagnostic.context} == {
        "inconsistent_unit_count": 1,
        "unit_role": "randomization",
    }


def test_overlapping_observation_and_randomization_conflict_counts_once() -> None:
    context = context_with_overlapping_assignment_conflict()

    result = validate_design(context, validate_data(context))

    assert {item.code for item in result.diagnostics} >= {
        "treatment.switching",
        "treatment.unit_multiple_assignments",
    }
    assert result.unit_integrity_summary.assignment_conflict_count == 1


def test_stable_unit_mapping_mismatch_is_not_an_assignment_conflict() -> None:
    context = context_with_stable_unit_mapping_mismatch()

    result = validate_design(context, validate_data(context))

    assert "unit.randomization_observation_mismatch" in {item.code for item in result.diagnostics}
    assert result.unit_integrity_summary.assignment_conflict_count == 0


def test_unhashable_unit_identifiers_preserve_exact_first_seen_grouping() -> None:
    context = context_with_unhashable_observation_units()

    result = validate_design(context, validate_data(context))

    assert result.unit_integrity_summary.observation_unit_count == 2
    assert result.unit_integrity_summary.duplicate_identifier_count == 1


def test_predefined_segment_does_not_emit_exploratory_cardinality_warning() -> None:
    context = context_with_high_cardinality_segment()

    diagnostics = validate_design(context, validate_data(context)).diagnostics

    assert "segment.high_cardinality" not in {item.code for item in diagnostics}
