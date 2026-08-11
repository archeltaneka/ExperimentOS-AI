"""Eligibility-gated service tests for CUPED randomized analysis."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.estimands import EstimandKind
from packages.experiments.analysis.metrics import AnalysisUnit, MetricType, SampleCounts
from packages.experiments.analysis.randomized.cuped import (
    CupedAnalysisExecutionRequest,
    CupedAnalysisService,
    CupedStatus,
    VarianceReductionStatus,
)
from packages.experiments.analysis.randomized.models import (
    AlternativeHypothesis,
    ComputationStatus,
)
from packages.experiments.analysis.study_designs import (
    CovariateRole,
    CovariateTiming,
    RandomizedAnalysisMethod,
    TreatmentRelationship,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisTable,
    MetricColumnBinding,
    OutcomeDataBinding,
    ValidationPolicy,
)
from tests.analysis_contract_fixtures import (
    covariate,
    observational_request,
    randomized_request,
    source,
)

CONTROL_OUTCOMES = (0.0, 3.0, 3.0, 6.0)
TREATMENT_OUTCOMES = (4.0, 4.0, 7.0, 10.0)
CONTROL_COVARIATES = (0.0, 1.0, 2.0, 3.0)
TREATMENT_COVARIATES = (0.0, 1.0, 2.0, 3.0)


def _request(
    *,
    timing: CovariateTiming = CovariateTiming.PRE_TREATMENT,
    role: CovariateRole = CovariateRole.CUPED,
    relationship: TreatmentRelationship = TreatmentRelationship.NONE_KNOWN,
    total: int = 8,
    treatment: int = 4,
    control: int = 4,
):
    request = randomized_request()
    outcome = request.outcome.model_copy(
        update={
            "metric": request.outcome.metric.model_copy(
                update={"metric_type": MetricType.CONTINUOUS}
            )
        }
    )
    unit = AnalysisUnit(unit_id="account", label="Account")
    design = request.study_design.model_copy(
        update={"method": RandomizedAnalysisMethod.CUPED, "randomization_unit": unit}
    )
    return request.model_copy(
        update={
            "outcome": outcome,
            "study_design": design,
            "unit_of_analysis": unit,
            "sample_counts": SampleCounts(total=total, treatment=treatment, control=control),
            "covariates": (
                covariate(
                    timing=timing,
                    role=role,
                    treatment_relationship=relationship,
                ),
            ),
        }
    )


def _table(
    *,
    control_outcomes: Sequence[object] = CONTROL_OUTCOMES,
    treatment_outcomes: Sequence[object] = TREATMENT_OUTCOMES,
    control_covariates: Sequence[object] = CONTROL_COVARIATES,
    treatment_covariates: Sequence[object] = TREATMENT_COVARIATES,
) -> AnalysisTable:
    rows = tuple(
        (f"control-{index}", "control", outcome, control_covariates[index])
        for index, outcome in enumerate(control_outcomes)
    ) + tuple(
        (f"treatment-{index}", "treatment", outcome, treatment_covariates[index])
        for index, outcome in enumerate(treatment_outcomes)
    )
    return AnalysisTable(
        columns=("account_id", "arm", "outcome", "prior_orders"),
        rows=rows,
    )


def _binding(*, covariate_column: str = "prior_orders") -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="account_id",
        randomization_unit_column="account_id",
        covariates=(
            MetricColumnBinding(
                metric_id="prior_order_count",
                column=covariate_column,
            ),
        ),
    )


def _policy(**updates: object) -> ValidationPolicy:
    values: dict[str, object] = {
        "minimum_total": 4,
        "minimum_per_arm": 2,
        "weak_total": 4,
        "weak_per_arm": 2,
    }
    values.update(updates)
    return ValidationPolicy(**values)  # type: ignore[arg-type]


def _analyze(
    *,
    request=None,
    table: AnalysisTable | None = None,
    binding: AnalysisDataBinding | None = None,
    policy: ValidationPolicy | None = None,
    alternative: AlternativeHypothesis = AlternativeHypothesis.TWO_SIDED,
):
    resolved_request = request or _request()
    execution = CupedAnalysisExecutionRequest(
        request_id="request-093",
        analysis_request=resolved_request,
        alternative=alternative,
    )
    return CupedAnalysisService(validation_policy=policy or _policy()).analyze(
        execution,
        table or _table(),
        binding or _binding(),
        provenance=(source(),),
    )


def test_service_matches_hand_calculated_pooled_cuped_and_welch_inference() -> None:
    result = _analyze()

    assert result.status is CupedStatus.COMPLETED
    assert result.baseline_status is ComputationStatus.COMPLETED
    assert result.coefficient is not None
    assert result.coefficient.theta == pytest.approx(1.95, abs=1e-12)
    assert result.coefficient.covariance == pytest.approx(19.5 / 7.0, abs=1e-12)
    assert result.coefficient.covariate_variance == pytest.approx(10.0 / 7.0, abs=1e-12)
    assert result.coefficient.covariate_mean == pytest.approx(1.5, abs=1e-12)
    assert result.coefficient.outcome_variance == pytest.approx(63.875 / 7.0, abs=1e-12)
    assert result.coefficient.correlation == pytest.approx(0.7715590235427073, abs=1e-12)
    assert result.coefficient.sample_size == 8
    assert result.coefficient.degrees_of_freedom_correction == 1
    assert result.adjusted_result is not None
    assert result.adjusted_result.point_effect is not None
    assert result.adjusted_result.test_result is not None
    assert result.adjusted_result.point_effect.absolute_effect.value == pytest.approx(3.25)
    assert result.adjusted_result.test_result.standard_error == pytest.approx(0.6274950199005567)
    assert result.adjusted_result.test_result.degrees_of_freedom == pytest.approx(5.789934354485776)
    assert result.adjusted_result.test_result.statistic == pytest.approx(5.179323973782372)
    assert result.adjusted_result.test_result.p_value == pytest.approx(0.0022884169730441714)
    assert result.adjusted_result.test_result.confidence_interval.lower == pytest.approx(
        1.7009698326859795
    )
    assert result.adjusted_result.test_result.confidence_interval.upper == pytest.approx(
        4.7990301673140205
    )
    assert result.adjusted_result.estimand == result.analysis_request.estimand
    assert result.comparable_unadjusted_result is not None
    assert result.comparable_unadjusted_result.estimand == result.analysis_request.estimand
    assert result.variance_reduction.status is VarianceReductionStatus.POSITIVE_REDUCTION
    assert result.variance_reduction.fraction == pytest.approx(0.8894736842105263)


def test_nonrandomized_request_returns_typed_unsupported_result() -> None:
    request = _request().model_copy(update={"study_design": observational_request().study_design})

    result = _analyze(request=request)

    assert result.status is CupedStatus.UNSUPPORTED
    assert result.baseline_status is ComputationStatus.ABSTAINED
    assert {item.code for item in result.diagnostics} == {"unsupported_study_design"}


def test_incompatible_estimand_preserves_unsupported_status() -> None:
    request = _request()
    request = request.model_copy(
        update={
            "estimand": request.estimand.model_copy(update={"kind": EstimandKind.RELATIVE_LIFT})
        }
    )

    result = _analyze(request=request)

    assert result.status is CupedStatus.UNSUPPORTED
    assert result.baseline_status is ComputationStatus.UNSUPPORTED
    assert {item.code for item in result.diagnostics} == {"incompatible_estimand"}


def test_completed_result_preserves_centralized_eligibility_warnings() -> None:
    result = _analyze(policy=_policy(weak_total=9, weak_per_arm=5))

    assert result.status is CupedStatus.COMPLETED
    assert {warning.code for warning in result.warnings} >= {
        "eligibility.sample.arm_weak",
        "eligibility.sample.total_weak",
    }


def test_complete_case_missingness_reports_retention_and_same_sample_comparator() -> None:
    table = _table(
        control_covariates=(None, 1.0, 2.0, 3.0),
        treatment_covariates=(0.0, 1.0, 2.0, None),
    )
    original_rows = table.rows

    result = _analyze(table=table)

    assert result.retention is not None
    assert result.retention.original_total == 8
    assert result.retention.retained_total == 6
    assert result.retention.removed_total == 2
    assert result.retention.retained_proportion == pytest.approx(0.75)
    assert result.retention.treatment.original_count == 4
    assert result.retention.treatment.retained_count == 3
    assert result.retention.treatment.missing_covariate_count == 1
    assert result.retention.control.original_count == 4
    assert result.retention.control.retained_count == 3
    assert result.retention.control.missing_covariate_count == 1
    assert result.comparable_unadjusted_result is not None
    assert result.comparable_unadjusted_result.treatment_summary is not None
    assert result.comparable_unadjusted_result.control_summary is not None
    assert result.comparable_unadjusted_result.treatment_summary.n == 3
    assert result.comparable_unadjusted_result.control_summary.n == 3
    assert result.full_sample_unadjusted_result.treatment_summary is not None
    assert result.full_sample_unadjusted_result.control_summary is not None
    assert result.full_sample_unadjusted_result.treatment_summary.n == 4
    assert result.full_sample_unadjusted_result.control_summary.n == 4
    assert table.rows is original_rows


def test_constant_covariate_abstains_while_full_baseline_remains_valid() -> None:
    result = _analyze(
        table=_table(
            control_covariates=(2.0, 2.0, 2.0, 2.0),
            treatment_covariates=(2.0, 2.0, 2.0, 2.0),
        )
    )

    assert result.status is CupedStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "constant_or_near_zero_covariate"
    assert result.coefficient is None
    assert result.adjusted_result is None
    assert result.baseline_status is ComputationStatus.COMPLETED
    assert result.full_sample_unadjusted_result.status is ComputationStatus.COMPLETED


@pytest.mark.parametrize(
    ("timing", "expected_code"),
    [
        (CovariateTiming.POST_TREATMENT, "eligibility.covariate.post_treatment_leakage"),
        (CovariateTiming.UNKNOWN, "eligibility.covariate.timing_unknown"),
        (CovariateTiming.AT_TREATMENT, "cuped.covariate_not_pre_treatment"),
        (CovariateTiming.TIME_VARYING, "cuped.covariate_not_pre_treatment"),
    ],
)
def test_non_pre_treatment_covariate_blocks_cuped_but_not_baseline(
    timing: CovariateTiming,
    expected_code: str,
) -> None:
    result = _analyze(request=_request(timing=timing))

    assert result.status is CupedStatus.ABSTAINED
    assert expected_code in {diagnostic.code for diagnostic in result.diagnostics}
    assert result.baseline_status is ComputationStatus.COMPLETED


def test_treatment_derived_covariate_blocks_cuped() -> None:
    result = _analyze(request=_request(relationship=TreatmentRelationship.ASSIGNMENT_DERIVED))

    assert result.status is CupedStatus.ABSTAINED
    assert "eligibility.covariate.treatment_relationship_conflict" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


def test_non_cuped_role_is_unsupported() -> None:
    result = _analyze(request=_request(role=CovariateRole.ADJUSTMENT))

    assert result.status is CupedStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "cuped_covariate_required"


def test_outcome_metric_reused_as_covariate_blocks_cuped() -> None:
    request = _request()
    reused = request.covariates[0].model_copy(update={"metric": request.outcome.metric})
    request = request.model_copy(update={"covariates": (reused,)})
    binding = AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="account_id",
        randomization_unit_column="account_id",
        covariates=(
            MetricColumnBinding(metric_id=request.outcome.metric.metric_id, column="prior_orders"),
        ),
    )

    result = _analyze(request=request, binding=binding)

    assert result.status is CupedStatus.ABSTAINED
    assert "eligibility.request.covariate_role_conflict" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.parametrize("protected_column", ["arm", "outcome", "account_id"])
def test_protected_analytical_column_cannot_be_bound_as_covariate(
    protected_column: str,
) -> None:
    with pytest.raises(ValidationError, match="covariate columns must not reuse"):
        _binding(covariate_column=protected_column)


def test_configured_excessive_missingness_abstains_with_retention() -> None:
    result = _analyze(
        table=_table(control_covariates=(None, 1.0, 2.0, 3.0)),
        policy=_policy(maximum_covariate_missing_rate=0.10),
    )

    assert result.status is CupedStatus.ABSTAINED
    assert result.retention is not None
    assert result.retention.removed_total == 1
    assert "eligibility.covariate.missingness_exceeds_threshold" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.parametrize("invalid", [math.nan, math.inf, "3", True])
def test_present_invalid_covariate_blocks_without_silent_exclusion(invalid: object) -> None:
    result = _analyze(table=_table(control_covariates=(invalid, 1.0, 2.0, 3.0)))

    assert result.status is CupedStatus.INVALID
    assert result.retention is not None
    assert result.retention.removed_total == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "invalid_covariate_value"


def test_nonfinite_coefficient_moments_use_computation_error_not_constant_label() -> None:
    result = _analyze(
        table=_table(
            control_covariates=(-1e308, -5e307, 5e307, 1e308),
            treatment_covariates=(-1e308, -5e307, 5e307, 1e308),
        )
    )

    assert result.status is CupedStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "cuped_computation_error"


def test_one_sided_alternative_is_unsupported_for_cuped_and_baseline() -> None:
    result = _analyze(alternative=AlternativeHypothesis.GREATER_THAN)

    assert result.status is CupedStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "unsupported_alternative_hypothesis"
    assert result.baseline_status is ComputationStatus.UNSUPPORTED
