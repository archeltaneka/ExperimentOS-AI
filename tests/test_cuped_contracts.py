"""Strict public-contract tests for CUPED analysis results."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.randomized.continuous import analyze_continuous_welch
from packages.experiments.analysis.randomized.cuped.models import (
    CovariateBalanceStatus,
    CupedAbstentionReason,
    CupedAnalysisResult,
    CupedCoefficient,
    CupedCovariateBalance,
    CupedSampleRetention,
    CupedStatus,
    RetainedArmSummary,
    VarianceReduction,
    VarianceReductionStatus,
)
from packages.experiments.analysis.randomized.models import (
    ComputationStatus,
    RandomizedDiagnostic,
    RandomizedDiagnosticCategory,
    RandomizedDiagnosticStatus,
)
from packages.experiments.analysis.study_designs import CovariateRole, RandomizedAnalysisMethod
from packages.experiments.analysis.uncertainty import RequestedConfidenceLevel
from tests.analysis_contract_fixtures import covariate, randomized_request, source


def _request():
    request = randomized_request(uncertainty=RequestedConfidenceLevel(level=0.95))
    cuped_covariate = covariate().model_copy(update={"role": CovariateRole.CUPED})
    design = request.study_design.model_copy(update={"method": RandomizedAnalysisMethod.CUPED})
    return request.model_copy(update={"study_design": design, "covariates": (cuped_covariate,)})


def _randomized_result(*, adjusted: bool = False):
    request = _request()
    offset = 0.2 if adjusted else 0.0
    return analyze_continuous_welch(
        request_id="request-093-adjusted" if adjusted else "request-093-unadjusted",
        metric=request.outcome.metric,
        estimand=request.estimand,
        treatment_arm_id=request.treatment.treatment_id,
        treatment_values=(5.0 + offset, 7.0, 9.0 - offset),
        control_arm_id=request.control.control_id,
        control_values=(2.0 + offset, 4.0, 6.0 - offset),
        provenance=(source(),),
    )


def _retention() -> CupedSampleRetention:
    return CupedSampleRetention(
        original_total=8,
        retained_total=6,
        removed_total=2,
        retained_proportion=0.75,
        treatment=RetainedArmSummary(
            original_count=4,
            retained_count=3,
            removed_count=1,
            missing_covariate_count=1,
            retained_proportion=0.75,
            missing_covariate_rate=0.25,
        ),
        control=RetainedArmSummary(
            original_count=4,
            retained_count=3,
            removed_count=1,
            missing_covariate_count=1,
            retained_proportion=0.75,
            missing_covariate_rate=0.25,
        ),
    )


def _coefficient() -> CupedCoefficient:
    return CupedCoefficient(
        theta=2.4,
        covariance=4.0,
        covariate_variance=5.0 / 3.0,
        covariate_mean=1.5,
        outcome_variance=29.0 / 3.0,
        correlation=12.0 / (145.0**0.5),
        sample_size=4,
    )


def _balance() -> CupedCovariateBalance:
    return CupedCovariateBalance(
        status=CovariateBalanceStatus.OBSERVED_DIFFERENCE,
        treatment_count=3,
        control_count=3,
        treatment_mean=2.5,
        control_mean=0.5,
        treatment_variance=0.5,
        control_variance=0.5,
        pooled_standard_deviation=0.5**0.5,
        standardized_mean_difference=2.0 / (0.5**0.5),
    )


def _variance(status: VarianceReductionStatus) -> VarianceReduction:
    values = {
        VarianceReductionStatus.POSITIVE_REDUCTION: (4.0, 1.0, 0.75),
        VarianceReductionStatus.NO_REDUCTION: (4.0, 4.0, 0.0),
        VarianceReductionStatus.NEGATIVE_REDUCTION: (4.0, 5.0, -0.25),
        VarianceReductionStatus.UNAVAILABLE: (None, None, None),
    }[status]
    return VarianceReduction(
        status=status,
        unadjusted_estimator_variance=values[0],
        adjusted_estimator_variance=values[1],
        fraction=values[2],
        percentage=None if values[2] is None else values[2] * 100.0,
    )


def _result(
    *,
    status: CupedStatus = CupedStatus.COMPLETED,
    variance_status: VarianceReductionStatus = VarianceReductionStatus.POSITIVE_REDUCTION,
) -> CupedAnalysisResult:
    request = _request()
    baseline = _randomized_result()
    return CupedAnalysisResult(
        request_id="request-093",
        analysis_request=request,
        adjustment_method="cuped",
        status=status,
        baseline_status=baseline.status,
        covariate=request.covariates[0],
        retention=_retention(),
        coefficient=_coefficient(),
        balance=_balance(),
        adjusted_result=_randomized_result(adjusted=True),
        comparable_unadjusted_result=baseline,
        full_sample_unadjusted_result=baseline,
        variance_reduction=_variance(variance_status),
        assumptions=(),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )


@pytest.mark.parametrize(
    ("status", "variance_status"),
    [
        (CupedStatus.COMPLETED, VarianceReductionStatus.POSITIVE_REDUCTION),
        (CupedStatus.NO_IMPROVEMENT, VarianceReductionStatus.NO_REDUCTION),
        (CupedStatus.DEGRADED_PRECISION, VarianceReductionStatus.NEGATIVE_REDUCTION),
        (CupedStatus.INCONCLUSIVE, VarianceReductionStatus.UNAVAILABLE),
    ],
)
def test_numerical_status_requires_matching_variance_reduction(
    status: CupedStatus,
    variance_status: VarianceReductionStatus,
) -> None:
    result = _result(status=status, variance_status=variance_status)

    assert result.status is status
    assert result.variance_reduction.status is variance_status
    assert result.adjusted_result is not None
    assert result.adjusted_result.estimand == result.analysis_request.estimand
    assert result.comparable_unadjusted_result is not None
    assert result.comparable_unadjusted_result.estimand == result.analysis_request.estimand
    assert result.baseline_status is ComputationStatus.COMPLETED


def test_mismatched_status_and_variance_shape_is_rejected() -> None:
    with pytest.raises(ValidationError, match="variance-reduction status"):
        _result(
            status=CupedStatus.COMPLETED,
            variance_status=VarianceReductionStatus.NEGATIVE_REDUCTION,
        )


def test_unavailable_variance_does_not_serialize_undefined_values_as_zero() -> None:
    variance = _variance(VarianceReductionStatus.UNAVAILABLE)

    assert variance.unadjusted_estimator_variance is None
    assert variance.adjusted_estimator_variance is None
    assert variance.fraction is None
    assert variance.percentage is None


def test_abstained_cuped_preserves_valid_baseline_without_adjusted_result() -> None:
    request = _request()
    baseline = _randomized_result()
    result = CupedAnalysisResult(
        request_id="request-093",
        analysis_request=request,
        status=CupedStatus.ABSTAINED,
        baseline_status=baseline.status,
        covariate=request.covariates[0],
        retention=_retention(),
        coefficient=None,
        balance=_balance(),
        adjusted_result=None,
        comparable_unadjusted_result=baseline,
        full_sample_unadjusted_result=baseline,
        variance_reduction=_variance(VarianceReductionStatus.UNAVAILABLE),
        assumptions=(),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
        abstention_reason=CupedAbstentionReason(
            code="constant_covariate",
            message="CUPED requires covariate variation.",
            missing_or_invalid_information=("covariate_variance",),
        ),
    )

    assert result.status is CupedStatus.ABSTAINED
    assert result.baseline_status is ComputationStatus.COMPLETED
    assert result.full_sample_unadjusted_result.status is ComputationStatus.COMPLETED
    assert result.adjusted_result is None


def test_cuped_result_is_frozen_canonical_and_contains_no_row_values() -> None:
    first = RandomizedDiagnostic(
        code="z-last",
        category=RandomizedDiagnosticCategory.RESULT,
        severity="warning",
        status=RandomizedDiagnosticStatus.FAILED,
        message="Last diagnostic.",
    )
    second = RandomizedDiagnostic(
        code="a-first",
        category=RandomizedDiagnosticCategory.INPUT,
        severity="info",
        status=RandomizedDiagnosticStatus.PASSED,
        message="First diagnostic.",
    )
    result = _result().model_copy(update={"diagnostics": (first, second)})
    validated = CupedAnalysisResult.model_validate(result.model_dump(mode="python"))
    payload = json.loads(validated.model_dump_json())

    assert tuple(diagnostic.code for diagnostic in validated.diagnostics) == (
        "a-first",
        "z-last",
    )
    assert "rows" not in json.dumps(payload).lower()
    assert "adjusted_outcomes" not in json.dumps(payload).lower()
    with pytest.raises(ValidationError):
        CupedAnalysisResult.model_validate(
            {**validated.model_dump(mode="python"), "unexpected_rows": [1.0, 2.0]}
        )


def test_nonfinite_coefficient_and_inconsistent_retention_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CupedCoefficient(
            theta=float("nan"),
            covariance=4.0,
            covariate_variance=1.0,
            covariate_mean=1.0,
            outcome_variance=1.0,
            correlation=0.5,
            sample_size=4,
        )
    with pytest.raises(ValidationError, match="removed_count"):
        RetainedArmSummary(
            original_count=4,
            retained_count=3,
            removed_count=0,
            missing_covariate_count=1,
            retained_proportion=0.75,
            missing_covariate_rate=0.25,
        )
