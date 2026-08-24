"""Public contract tests for the bounded two-period DiD estimator."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

import packages.experiments.analysis.causal as causal
from packages.experiments.analysis import (
    AnalysisWarning,
    ConfidenceInterval,
    DiagnosticSeverity,
)
from packages.experiments.analysis.causal.did import (
    DidAbstentionReason,
    DidCellMeans,
    DidDiagnostic,
    DidDiagnosticCategory,
    DidDiagnosticStatus,
    DidPanelPolicy,
    DidPretrendAvailability,
    DidPretrendDiagnostic,
    DidSampleCounts,
    DidStatus,
    DidTestResult,
    DidVarianceEstimator,
    DifferenceInDifferencesConfig,
    DifferenceInDifferencesDataBinding,
    DifferenceInDifferencesExecutionRequest,
    DifferenceInDifferencesResult,
)
from tests.causal_identification_fixtures import provenance
from tests.did_fixtures import did_request


def _binding() -> DifferenceInDifferencesDataBinding:
    return DifferenceInDifferencesDataBinding(
        unit_column="unit_id",
        time_column="observed_at",
        group_column="group",
        treatment_column="exposed",
        treatment_start_column="treatment_start",
        outcome_column="outcome",
        treated_group_value="treated",
        control_group_value="control",
    )


def test_binding_requires_distinct_explicit_columns_and_group_values() -> None:
    binding = _binding()

    assert binding.model_dump(mode="json") == {
        "unit_column": "unit_id",
        "time_column": "observed_at",
        "group_column": "group",
        "treatment_column": "exposed",
        "treatment_start_column": "treatment_start",
        "outcome_column": "outcome",
        "treated_group_value": "treated",
        "control_group_value": "control",
    }

    with pytest.raises(ValidationError, match="binding columns must be unique"):
        binding.model_copy(update={"outcome_column": "unit_id"}).__class__.model_validate(
            {**binding.model_dump(), "outcome_column": "unit_id"}
        )
    with pytest.raises(ValidationError, match="treated and control group values must differ"):
        DifferenceInDifferencesDataBinding.model_validate(
            {**binding.model_dump(), "control_group_value": "treated"}
        )


def test_configuration_centralizes_balanced_panel_and_cluster_policy() -> None:
    config = DifferenceInDifferencesConfig()

    assert config.panel_policy is DidPanelPolicy.REQUIRE_BALANCED
    assert config.variance_estimator is DidVarianceEstimator.CLUSTER_ROBUST_CR1
    assert config.confidence_level == 0.95
    assert config.minimum_cluster_count == 8
    assert config.minimum_cluster_count_per_group == 4
    assert config.few_cluster_warning_threshold == 30


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"minimum_cluster_count": 1}, "minimum_cluster_count must be at least two"),
        (
            {"minimum_cluster_count": 8, "few_cluster_warning_threshold": 8},
            "few-cluster warning threshold must exceed the minimum cluster count",
        ),
        (
            {"minimum_cluster_count": 6, "minimum_cluster_count_per_group": 4},
            "total minimum clusters must cover both group minima",
        ),
    ),
)
def test_configuration_rejects_incoherent_cluster_thresholds(
    updates: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        DifferenceInDifferencesConfig(**updates)


def test_public_contract_enums_are_stable_json_values() -> None:
    payload = {
        "statuses": [item.value for item in DidStatus],
        "panel_policy": DidPanelPolicy.REQUIRE_BALANCED,
        "variance": DidVarianceEstimator.CLUSTER_ROBUST_CR1,
    }
    assert json.loads(json.dumps(payload)) == {
        "statuses": ["completed", "abstained", "invalid", "unsupported"],
        "panel_policy": "require_balanced",
        "variance": "cluster_robust_cr1",
    }


def test_did_contracts_are_exported_from_causal_boundary() -> None:
    assert causal.DifferenceInDifferencesConfig is DifferenceInDifferencesConfig
    assert causal.DifferenceInDifferencesExecutionRequest is DifferenceInDifferencesExecutionRequest
    assert causal.DifferenceInDifferencesResult is DifferenceInDifferencesResult


def test_execution_request_requires_issue_97_identification_envelope() -> None:
    execution = DifferenceInDifferencesExecutionRequest(
        analysis_request=did_request(),
        binding=_binding(),
    )

    assert execution.request_id == "causal-request-001"
    assert execution.analysis_request.identification.estimand is not None
    assert execution.analysis_request.identification.estimand.estimand_type.value == "did_att"
    assert execution.extra_pre_periods == ()


def test_completed_result_contains_owned_finite_inference_and_serializes_deterministically(
) -> None:
    execution = DifferenceInDifferencesExecutionRequest(
        analysis_request=did_request(),
        binding=_binding(),
    )
    identification = execution.analysis_request.identification
    estimand = identification.estimand
    treatment = identification.treatment
    outcome = identification.outcome
    units = identification.units
    assert estimand is not None
    assert treatment is not None
    assert outcome is not None
    assert units is not None
    counts = DidSampleCounts(
        rows=40,
        total_units=20,
        treated_units=10,
        control_units=10,
        units_with_both_periods=20,
        units_missing_pre=0,
        units_missing_post=0,
        retained_units=20,
        incomplete_units=0,
        excluded_units=0,
        treated_retained_units=10,
        control_retained_units=10,
        treated_pre_rows=10,
        treated_post_rows=10,
        control_pre_rows=10,
        control_post_rows=10,
        treated_missing_pre_outcomes=0,
        treated_missing_post_outcomes=0,
        control_missing_pre_outcomes=0,
        control_missing_post_outcomes=0,
        retention_rate=1.0,
        treated_retention_rate=1.0,
        control_retention_rate=1.0,
    )
    cells = DidCellMeans(
        treated_pre_mean=10.0,
        treated_post_mean=15.0,
        control_pre_mean=8.0,
        control_post_mean=10.0,
        treated_change=5.0,
        control_change=2.0,
        did_estimate=3.0,
        treated_pre_count=10,
        treated_post_count=10,
        control_pre_count=10,
        control_post_count=10,
    )
    test_result = DidTestResult(
        variance_estimator=DidVarianceEstimator.CLUSTER_ROBUST_CR1,
        cluster_unit=units.analysis_unit,
        cluster_count=20,
        standard_error=0.5,
        statistic=6.0,
        degrees_of_freedom=19,
        p_value=0.00001,
        null_hypothesis="ATT_DiD = 0",
        alternative="two_sided",
        confidence_interval=ConfidenceInterval(
            lower=1.953,
            upper=4.047,
            confidence_level=0.95,
        ),
    )
    result = DifferenceInDifferencesResult(
        request_id=execution.request_id,
        analysis_request=execution.analysis_request,
        binding=execution.binding,
        configuration=execution.configuration,
        status=DidStatus.COMPLETED,
        estimand=estimand,
        design=identification.design,
        treatment=treatment,
        outcome=outcome,
        population=identification.population,
        units=units,
        time=identification.time,
        sample_counts=counts,
        cell_means=cells,
        test_result=test_result,
        assumptions=identification.assumptions,
        evidence_limitations=(),
        pretrend=DidPretrendDiagnostic(
            availability=DidPretrendAvailability.NOT_REQUESTED,
            message="No extra pre-treatment periods were requested.",
        ),
        diagnostics=(
            DidDiagnostic(
                code="did.few_clusters",
                category=DidDiagnosticCategory.INFERENCE,
                severity=DiagnosticSeverity.WARNING,
                status=DidDiagnosticStatus.FAILED,
                message="Cluster-robust inference uses fewer than 30 clusters.",
                context={"cluster_count": 20},
            ),
        ),
        warnings=(
            AnalysisWarning(
                code="did.few_clusters",
                message="Cluster-robust inference uses fewer than 30 clusters.",
                scope="difference_in_differences",
            ),
        ),
        provenance=provenance("did-result"),
    )

    first = result.model_dump_json()
    second = DifferenceInDifferencesResult.model_validate_json(first).model_dump_json()
    assert first == second
    assert result.method == "did"
    assert result.estimand.estimand_type.value == "did_att"
    assert result.estimand.target_population.kind.value == "treated"
    assert "statsmodels" not in first


def test_abstained_result_rejects_numerical_findings() -> None:
    execution = DifferenceInDifferencesExecutionRequest(
        analysis_request=did_request(),
        binding=_binding(),
    )
    identification = execution.analysis_request.identification
    estimand = identification.estimand
    treatment = identification.treatment
    outcome = identification.outcome
    units = identification.units
    assert estimand is not None
    assert treatment is not None
    assert outcome is not None
    assert units is not None
    payload = {
        "request_id": execution.request_id,
        "analysis_request": execution.analysis_request,
        "binding": execution.binding,
        "configuration": execution.configuration,
        "status": DidStatus.ABSTAINED,
        "estimand": estimand,
        "design": identification.design,
        "treatment": treatment,
        "outcome": outcome,
        "population": identification.population,
        "units": units,
        "time": identification.time,
        "sample_counts": DidSampleCounts(),
        "cell_means": DidCellMeans(
            treated_pre_mean=10.0,
            treated_post_mean=15.0,
            control_pre_mean=8.0,
            control_post_mean=10.0,
            treated_change=5.0,
            control_change=2.0,
            did_estimate=3.0,
            treated_pre_count=10,
            treated_post_count=10,
            control_pre_count=10,
            control_post_count=10,
        ),
        "assumptions": identification.assumptions,
        "evidence_limitations": (),
        "pretrend": DidPretrendDiagnostic(
            availability=DidPretrendAvailability.NOT_REQUESTED,
            message="No extra pre-treatment periods were requested.",
        ),
        "diagnostics": (),
        "warnings": (),
        "provenance": provenance("did-result"),
        "abstention_reason": DidAbstentionReason(
            code="did.insufficient_clusters",
            message="Cluster count is below policy minimum.",
            missing_or_invalid_information=("cluster_count",),
        ),
    }

    with pytest.raises(ValidationError, match="non-completed results must not contain estimates"):
        DifferenceInDifferencesResult.model_validate(payload)
