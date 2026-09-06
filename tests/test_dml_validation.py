"""Identification, binding, feature, and retention validation for DML."""

from __future__ import annotations

import math

from packages.experiments.analysis import MetricType
from packages.experiments.analysis.causal import (
    CausalEstimandKind,
    MeasurementTiming,
    ObservationalDesignType,
)
from packages.experiments.analysis.causal.dml.models import (
    DMLCovariateBinding,
    DMLDataBinding,
)
from packages.experiments.analysis.causal.dml.validation import (
    DMLValidationDisposition,
    validate_dml_input,
)
from tests.dml_fixtures import (
    dml_binding,
    dml_execution,
    dml_identification,
    dml_rows,
    dml_table,
)


def diagnostic_codes(result: object) -> set[str]:
    return {item.code for item in result.diagnostics}  # type: ignore[attr-defined]


def test_valid_dml_input_retains_canonical_complete_population() -> None:
    result = validate_dml_input(dml_execution(), dml_table(tuple(reversed(dml_rows()))))

    assert result.disposition is DMLValidationDisposition.VALID
    assert tuple(row.observation_id for row in result.rows) == (
        "c-0",
        "c-1",
        "c-2",
        "c-3",
        "t-0",
        "t-1",
        "t-2",
        "t-3",
    )
    assert result.sample_counts.raw_count == 8
    assert result.sample_counts.retained_count == 8
    assert result.sample_counts.treated_count == 4
    assert result.sample_counts.control_count == 4
    assert result.sample_counts.complete_case_excluded_count == 0
    assert result.diagnostics == ()


def test_complete_case_filtering_is_reported_before_fold_planning() -> None:
    rows = (
        *dml_rows(),
        {"account_id": "missing-y", "treated": 0, "outcome": None, "prior_orders": 1.0},
        {"account_id": "missing-x", "treated": 1, "outcome": 3.0, "prior_orders": None},
    )

    result = validate_dml_input(dml_execution(), dml_table(rows))

    assert result.disposition is DMLValidationDisposition.VALID
    assert result.sample_counts.raw_count == 10
    assert result.sample_counts.retained_count == 8
    assert result.sample_counts.complete_case_excluded_count == 2
    assert {row.observation_id for row in result.rows} == {
        "c-0",
        "c-1",
        "c-2",
        "c-3",
        "t-0",
        "t-1",
        "t-2",
        "t-3",
    }


def test_dml_rejects_unsupported_estimand_design_and_outcome() -> None:
    identification = dml_identification()
    unsupported_score = identification.model_copy(
        update={
            "identification_request": identification.identification_request.model_copy(
                update={
                    "design": identification.identification_request.design.model_copy(
                        update={"method": "another_dml_score"}
                    )
                }
            )
        }
    )
    cases = (
        (
            dml_identification(estimand_kind=CausalEstimandKind.ATT),
            "dml.estimand.unsupported",
        ),
        (
            dml_identification(design_type=ObservationalDesignType.GENERIC),
            "dml.design.unsupported",
        ),
        (
            dml_identification(outcome_type=MetricType.BINARY),
            "dml.outcome.unsupported",
        ),
        (unsupported_score, "dml.score.unsupported"),
    )
    for identification, expected_code in cases:
        result = validate_dml_input(
            dml_execution(identification_result=identification),
            dml_table(),
        )

        assert result.disposition is DMLValidationDisposition.UNSUPPORTED
        assert expected_code in diagnostic_codes(result)


def test_dml_rejects_invalid_issue_97_identification() -> None:
    identification = dml_identification(adjustment_timing=MeasurementTiming.POST_TREATMENT)

    result = validate_dml_input(
        dml_execution(identification_result=identification),
        dml_table(),
    )

    assert result.disposition is DMLValidationDisposition.INVALID
    assert "dml.identification.invalid" in diagnostic_codes(result)


def test_dml_revalidates_required_identification_assumptions() -> None:
    identification = dml_identification()
    assumptions = tuple(
        item for item in identification.assumptions if item.code.value != "positivity"
    )
    incomplete = identification.model_copy(
        update={
            "assumptions": assumptions,
            "identification_request": identification.identification_request.model_copy(
                update={"assumptions": assumptions}
            ),
        }
    )

    result = validate_dml_input(
        dml_execution(identification_result=incomplete),
        dml_table(),
    )

    assert result.disposition is DMLValidationDisposition.INVALID
    assert "dml.assumption.insufficient" in diagnostic_codes(result)


def test_dml_rejects_binding_that_does_not_exactly_match_adjustment_set() -> None:
    binding = dml_binding().model_copy(
        update={
            "covariates": (
                DMLCovariateBinding(variable_id="unapproved_covariate", column="prior_orders"),
            )
        }
    )

    result = validate_dml_input(dml_execution(binding=binding), dml_table())

    assert result.disposition is DMLValidationDisposition.INVALID
    assert "dml.binding.covariate_mismatch" in diagnostic_codes(result)


def test_dml_rejects_treatment_or_outcome_binding_identity_mismatch() -> None:
    treatment_binding = dml_binding().model_copy(
        update={"treatment_variable_id": "another_treatment"}
    )
    outcome_binding = dml_binding().model_copy(update={"outcome_variable_id": "another_outcome"})

    treatment_result = validate_dml_input(dml_execution(binding=treatment_binding), dml_table())
    outcome_result = validate_dml_input(dml_execution(binding=outcome_binding), dml_table())

    assert treatment_result.disposition is DMLValidationDisposition.INVALID
    assert outcome_result.disposition is DMLValidationDisposition.INVALID
    assert "dml.binding.treatment_mismatch" in diagnostic_codes(treatment_result)
    assert "dml.binding.outcome_mismatch" in diagnostic_codes(outcome_result)


def test_dml_rejects_missing_binding_column_and_duplicate_ids() -> None:
    missing = DMLDataBinding(
        observation_id_column="unknown_id",
        treatment_variable_id="treated",
        treatment_column="treated",
        outcome_variable_id="outcome",
        outcome_column="outcome",
        covariates=dml_binding().covariates,
    )
    missing_result = validate_dml_input(dml_execution(binding=missing), dml_table())
    duplicated_rows = (*dml_rows(), dml_rows()[0])
    duplicate_result = validate_dml_input(dml_execution(), dml_table(duplicated_rows))

    assert missing_result.disposition is DMLValidationDisposition.INVALID
    assert "dml.binding.missing_column" in diagnostic_codes(missing_result)
    assert duplicate_result.disposition is DMLValidationDisposition.INVALID
    assert "dml.sample.duplicate_observation_id" in diagnostic_codes(duplicate_result)


def test_dml_rejects_nonfinite_values_and_unknown_treatment_values() -> None:
    nonfinite = list(dml_rows())
    nonfinite[0] = nonfinite[0] | {"outcome": math.inf}
    unknown_treatment = list(dml_rows())
    unknown_treatment[0] = unknown_treatment[0] | {"treated": 2}

    nonfinite_result = validate_dml_input(dml_execution(), dml_table(nonfinite))
    treatment_result = validate_dml_input(dml_execution(), dml_table(unknown_treatment))

    assert nonfinite_result.disposition is DMLValidationDisposition.INVALID
    assert "dml.outcome.invalid" in diagnostic_codes(nonfinite_result)
    assert treatment_result.disposition is DMLValidationDisposition.INVALID
    assert "dml.treatment.invalid" in diagnostic_codes(treatment_result)


def test_dml_abstains_when_retained_population_cannot_fill_stratified_folds() -> None:
    rows = tuple(row for row in dml_rows() if row["account_id"] != "c-3")
    execution = dml_execution(fold_count=4)

    result = validate_dml_input(execution, dml_table(rows))

    assert result.disposition is DMLValidationDisposition.ABSTAINED
    assert "dml.fold.inadequate_class_count" in diagnostic_codes(result)
