"""Deterministic estimator-level reference cases required by issue #93."""

from __future__ import annotations

import json

import pytest

from packages.experiments.analysis.metrics import MetricDefinition, MetricType
from packages.experiments.analysis.randomized.cuped import (
    CupedStatus,
    VarianceReductionStatus,
)
from packages.experiments.analysis.study_designs import (
    CovariateRole,
    CovariateTiming,
    TimePeriod,
    TreatmentRelationship,
)
from packages.experiments.analysis.validation import (
    AnalysisTable,
    MetricColumnBinding,
)
from tests.analysis_contract_fixtures import utc
from tests.cuped_fixtures import (
    NEGATIVE_REDUCTION_CONTROL_COVARIATES,
    NEGATIVE_REDUCTION_CONTROL_OUTCOMES,
    NEGATIVE_REDUCTION_TREATMENT_COVARIATES,
    NEGATIVE_REDUCTION_TREATMENT_OUTCOMES,
    ZERO_REDUCTION_CONTROL_OUTCOMES,
    ZERO_REDUCTION_COVARIATES,
    ZERO_REDUCTION_TREATMENT_OUTCOMES,
)
from tests.test_cuped_service import _analyze, _binding, _policy, _request, _table


def test_exact_zero_reduction_is_valid_without_improvement_claim() -> None:
    result = _analyze(
        table=_table(
            control_outcomes=ZERO_REDUCTION_CONTROL_OUTCOMES,
            treatment_outcomes=ZERO_REDUCTION_TREATMENT_OUTCOMES,
            control_covariates=ZERO_REDUCTION_COVARIATES,
            treatment_covariates=ZERO_REDUCTION_COVARIATES,
        )
    )

    assert result.status is CupedStatus.NO_IMPROVEMENT
    assert result.coefficient is not None
    assert result.coefficient.theta == pytest.approx(0.0, abs=1e-15)
    assert result.variance_reduction.status is VarianceReductionStatus.NO_REDUCTION
    assert result.variance_reduction.fraction == pytest.approx(0.0, abs=1e-15)


def test_negative_reduction_is_preserved_as_degraded_precision() -> None:
    result = _analyze(
        table=_table(
            control_outcomes=NEGATIVE_REDUCTION_CONTROL_OUTCOMES,
            treatment_outcomes=NEGATIVE_REDUCTION_TREATMENT_OUTCOMES,
            control_covariates=NEGATIVE_REDUCTION_CONTROL_COVARIATES,
            treatment_covariates=NEGATIVE_REDUCTION_TREATMENT_COVARIATES,
        )
    )

    assert result.status is CupedStatus.DEGRADED_PRECISION
    assert result.coefficient is not None
    assert result.coefficient.theta == pytest.approx(13.0 / 24.0, abs=1e-12)
    assert result.variance_reduction.status is VarianceReductionStatus.NEGATIVE_REDUCTION
    assert result.variance_reduction.unadjusted_estimator_variance == pytest.approx(7.0 / 3.0)
    assert result.variance_reduction.adjusted_estimator_variance == pytest.approx(
        3.261501736111111
    )
    assert result.variance_reduction.fraction == pytest.approx(-0.3977864583333335)
    assert "cuped.degraded_precision" in {warning.code for warning in result.warnings}
    variance_diagnostic = next(
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == "cuped.variance_reduction.negative_reduction"
    )
    assert variance_diagnostic.status.value == "passed"


def test_arm_imbalance_is_advisory_and_does_not_block_cuped() -> None:
    result = _analyze(
        table=_table(
            control_outcomes=NEGATIVE_REDUCTION_CONTROL_OUTCOMES,
            treatment_outcomes=NEGATIVE_REDUCTION_TREATMENT_OUTCOMES,
            control_covariates=NEGATIVE_REDUCTION_CONTROL_COVARIATES,
            treatment_covariates=NEGATIVE_REDUCTION_TREATMENT_COVARIATES,
        )
    )

    assert result.balance is not None
    assert result.balance.status.value == "observed_difference"
    assert result.balance.treatment_mean == pytest.approx(1.75)
    assert result.balance.control_mean == pytest.approx(0.25)
    assert result.balance.standardized_mean_difference is not None
    assert "cuped.covariate_arm_difference_observed" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert "cuped.covariate_arm_difference_observed" in {
        warning.code for warning in result.warnings
    }
    balance_diagnostic = next(
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == "cuped.covariate_arm_difference_observed"
    )
    assert balance_diagnostic.status.value == "passed"


def test_configured_near_zero_variance_abstains() -> None:
    covariates = (0.0, 1e-8, 2e-8, 3e-8)
    result = _analyze(
        table=_table(
            control_covariates=covariates,
            treatment_covariates=covariates,
        ),
        policy=_policy(minimum_covariate_variance=1e-15),
    )

    assert result.status is CupedStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "constant_or_near_zero_covariate"


def test_insufficient_complete_cases_abstain_without_imputation() -> None:
    result = _analyze(
        table=_table(control_covariates=(None, None, None, 3.0))
    )

    assert result.status is CupedStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "insufficient_retained_sample"
    assert result.retention is not None
    assert result.retention.control.retained_count == 1
    assert result.retention.control.missing_covariate_count == 3


def test_measurement_period_after_treatment_blocks_declared_pre_treatment_covariate() -> None:
    request = _request()
    contradictory = request.covariates[0].model_copy(
        update={
            "measurement_period": TimePeriod(
                start=utc(2026, 6, 20),
                end=utc(2026, 7, 2),
            )
        }
    )
    request = request.model_copy(update={"covariates": (contradictory,)})

    result = _analyze(request=request)

    assert result.status is CupedStatus.ABSTAINED
    assert "eligibility.covariate.measurement_after_treatment" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.parametrize("covariate_count", [0, 2])
def test_zero_or_multiple_covariates_are_unsupported(covariate_count: int) -> None:
    request = _request()
    binding = _binding()
    table = _table()
    if covariate_count == 0:
        request = request.model_copy(update={"covariates": ()})
        binding = binding.model_copy(update={"covariates": ()})
    else:
        second_metric = request.covariates[0].metric.model_copy(
            update={"metric_id": "prior_order_count_2", "label": "Second prior count"}
        )
        second_covariate = request.covariates[0].model_copy(update={"metric": second_metric})
        request = request.model_copy(
            update={"covariates": (request.covariates[0], second_covariate)}
        )
        binding = binding.model_copy(
            update={
                "covariates": binding.covariates
                + (
                    MetricColumnBinding(
                        metric_id="prior_order_count_2",
                        column="prior_orders_2",
                    ),
                )
            }
        )
        table = AnalysisTable(
            columns=table.columns + ("prior_orders_2",),
            rows=tuple(row + (index,) for index, row in enumerate(table.rows)),
        )

    result = _analyze(request=request, binding=binding, table=table)

    assert result.status is CupedStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "single_cuped_covariate_required"


def test_outcome_metric_type_must_be_continuous() -> None:
    request = _request()
    binary_metric = request.outcome.metric.model_copy(update={"metric_type": MetricType.BINARY})
    outcome = request.outcome.model_copy(update={"metric": binary_metric})
    request = request.model_copy(update={"outcome": outcome})

    result = _analyze(request=request)

    assert result.status is CupedStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "unsupported_outcome_type"


def test_zero_outcome_variance_leaves_randomized_baseline_unavailable() -> None:
    result = _analyze(
        table=_table(
            control_outcomes=(2.0, 2.0, 2.0, 2.0),
            treatment_outcomes=(5.0, 5.0, 5.0, 5.0),
        )
    )

    assert result.status is CupedStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "randomized_baseline_unavailable"
    assert result.full_sample_unadjusted_result.abstention_reason is not None
    assert result.full_sample_unadjusted_result.abstention_reason.code == "zero_standard_error"


def test_repeated_and_row_reordered_execution_is_deterministic() -> None:
    table = _table(
        control_outcomes=NEGATIVE_REDUCTION_CONTROL_OUTCOMES,
        treatment_outcomes=NEGATIVE_REDUCTION_TREATMENT_OUTCOMES,
        control_covariates=NEGATIVE_REDUCTION_CONTROL_COVARIATES,
        treatment_covariates=NEGATIVE_REDUCTION_TREATMENT_COVARIATES,
    )
    first = _analyze(table=table)
    repeated = _analyze(table=table)
    reordered = _analyze(
        table=AnalysisTable(columns=table.columns, rows=tuple(reversed(table.rows)))
    )

    first_json = first.model_dump_json()
    assert repeated.model_dump_json() == first_json
    assert reordered.model_dump_json() == first_json
    payload = json.loads(first_json)
    keys = _nested_keys(payload)
    assert "adjusted_outcomes" not in keys
    assert "rows" not in keys


def test_cuped_assumptions_preserve_untestable_claims() -> None:
    result = _analyze()
    assumptions = {assumption.code: assumption.status.value for assumption in result.assumptions}

    assert assumptions["covariate_pre_treatment"] == "supported"
    assert assumptions["covariate_unaffected_by_treatment"] == "untestable"
    assert assumptions["no_data_dependent_covariate_selection"] == "untestable"
    assert assumptions["estimand_preserved"] == "supported"


def test_failed_temporal_and_relationship_assumptions_are_not_marked_supported() -> None:
    post_treatment = _analyze(request=_request(timing=CovariateTiming.POST_TREATMENT))
    unknown_timing = _analyze(request=_request(timing=CovariateTiming.UNKNOWN))
    treatment_derived = _analyze(
        request=_request(relationship=TreatmentRelationship.ASSIGNMENT_DERIVED)
    )

    post_assumptions = {
        assumption.code: assumption.status.value for assumption in post_treatment.assumptions
    }
    unknown_assumptions = {
        assumption.code: assumption.status.value for assumption in unknown_timing.assumptions
    }
    derived_assumptions = {
        assumption.code: assumption.status.value for assumption in treatment_derived.assumptions
    }
    assert post_assumptions["covariate_pre_treatment"] == "violated"
    assert unknown_assumptions["covariate_pre_treatment"] == "unassessed"
    assert derived_assumptions["covariate_unaffected_by_treatment"] == "violated"


def test_covariate_definition_remains_library_independent() -> None:
    result = _analyze()

    assert isinstance(result.covariate.metric, MetricDefinition)
    assert result.covariate.timing is CovariateTiming.PRE_TREATMENT
    assert result.covariate.role is CovariateRole.CUPED


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_nested_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_nested_keys(item) for item in value), set())
    return set()
