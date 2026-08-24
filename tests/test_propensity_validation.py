"""Identification and table eligibility for propensity diagnostics."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal import MeasurementTiming, VariableRole
from packages.experiments.analysis.causal.propensity import (
    PropensityValidationDisposition,
    validate_propensity_input,
)
from tests.propensity_fixtures import (
    propensity_execution,
    propensity_request,
    propensity_table,
    propensity_variables,
    small_valid_rows,
)


def diagnostic_codes(result: object) -> set[str]:
    return {item.code for item in result.diagnostics}  # type: ignore[attr-defined]


def test_valid_declared_pre_treatment_covariates_preserve_source_row_alignment() -> None:
    result = validate_propensity_input(
        propensity_execution(),
        propensity_table(small_valid_rows()),
    )

    assert result.disposition is PropensityValidationDisposition.VALID
    assert tuple(item.variable_id for item in result.covariates) == (
        "country",
        "prior_orders",
    )
    assert tuple(row.unit_id for row in result.rows) == ("u-3", "u-1", "u-4", "u-2")
    assert tuple(row.treated for row in result.rows) == (True, False, True, False)
    assert result.sample_counts.raw == 4
    assert result.sample_counts.model == 4
    assert result.sample_counts.complete_case_excluded == 0


def test_complete_case_exclusions_are_visible_by_treatment_arm() -> None:
    rows = list(small_valid_rows())
    rows[0] = {**rows[0], "prior_orders": None}

    result = validate_propensity_input(propensity_execution(), propensity_table(rows))

    assert result.disposition is PropensityValidationDisposition.VALID
    assert result.sample_counts.raw == 4
    assert result.sample_counts.model == 3
    assert result.sample_counts.complete_case_excluded == 1
    assert result.sample_counts.treated_excluded == 1
    assert result.sample_counts.control_excluded == 0
    assert tuple(row.unit_id for row in result.rows) == ("u-1", "u-4", "u-2")


@pytest.mark.parametrize(
    ("role", "timing", "code"),
    (
        (VariableRole.POST_TREATMENT, MeasurementTiming.PRE_TREATMENT, "adjustment.post_treatment"),
        (VariableRole.TREATMENT, MeasurementTiming.PRE_TREATMENT, "adjustment.treatment_leakage"),
        (VariableRole.OUTCOME, MeasurementTiming.PRE_TREATMENT, "adjustment.outcome_leakage"),
        (VariableRole.IDENTIFIER, MeasurementTiming.TIME_INVARIANT, "adjustment.identifier_misuse"),
        (VariableRole.ADJUSTMENT, MeasurementTiming.POST_TREATMENT, "adjustment.post_treatment"),
        (VariableRole.ADJUSTMENT, MeasurementTiming.UNKNOWN, "adjustment.unknown_timing"),
    ),
)
def test_invalid_adjustment_role_or_timing_abstains(
    role: VariableRole,
    timing: MeasurementTiming,
    code: str,
) -> None:
    analysis_request = propensity_request(
        declared_variables=propensity_variables(
            prior_orders_role=role,
            prior_orders_timing=timing,
        )
    )

    result = validate_propensity_input(
        propensity_execution(analysis_request=analysis_request),
        propensity_table(small_valid_rows()),
    )

    assert result.disposition is PropensityValidationDisposition.ABSTAINED
    assert code in diagnostic_codes(result)
    assert result.rows == ()


def test_unknown_treatment_value_is_not_coerced_by_truthiness() -> None:
    rows = list(small_valid_rows())
    rows[0] = {**rows[0], "treated": True}

    result = validate_propensity_input(propensity_execution(), propensity_table(rows))

    assert result.disposition is PropensityValidationDisposition.INVALID
    assert "propensity.invalid_treatment_value" in diagnostic_codes(result)


def test_missing_bound_column_is_invalid_without_row_loss() -> None:
    rows = tuple(
        {key: value for key, value in row.items() if key != "country"} for row in small_valid_rows()
    )

    result = validate_propensity_input(propensity_execution(), propensity_table(rows))

    assert result.disposition is PropensityValidationDisposition.INVALID
    assert result.sample_counts.raw == 4
    assert result.sample_counts.model == 0
    assert "propensity.missing_column" in diagnostic_codes(result)


def test_nonfinite_numeric_covariate_is_invalid_not_missing() -> None:
    rows = list(small_valid_rows())
    rows[0] = {**rows[0], "prior_orders": float("inf")}

    result = validate_propensity_input(propensity_execution(), propensity_table(rows))

    assert result.disposition is PropensityValidationDisposition.INVALID
    assert "propensity.invalid_numeric_covariate" in diagnostic_codes(result)


def test_complete_cases_must_retain_both_treatment_arms() -> None:
    rows = tuple(
        {**row, "country": None} if row["treated"] == 1 else row for row in small_valid_rows()
    )

    result = validate_propensity_input(propensity_execution(), propensity_table(rows))

    assert result.disposition is PropensityValidationDisposition.ABSTAINED
    assert "propensity.missing_model_arm" in diagnostic_codes(result)
