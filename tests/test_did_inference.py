"""Independent CR1 reference and centralized few-cluster policy tests."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.did import (
    DidSampleCounts,
    DifferenceInDifferencesConfig,
)
from packages.experiments.analysis.causal.did.numerics import (
    DidNumericalError,
    assess_cluster_policy,
    cluster_robust_inference,
    fit_interaction_ols,
)
from packages.experiments.analysis.causal.did.validation import DidObservation, validate_did_input
from tests.did_fixtures import did_execution, did_table, positive_effect_rows


def _counts(treated: int, control: int) -> DidSampleCounts:
    total = treated + control
    return DidSampleCounts(
        rows=2 * total,
        total_units=total,
        treated_units=treated,
        control_units=control,
        units_with_both_periods=total,
        retained_units=total,
        treated_retained_units=treated,
        control_retained_units=control,
        treated_pre_rows=treated,
        treated_post_rows=treated,
        control_pre_rows=control,
        control_post_rows=control,
        retention_rate=1.0,
        treated_retention_rate=1.0,
        control_retention_rate=1.0,
    )


def test_cr1_uncertainty_matches_independent_matrix_reference() -> None:
    """Reference: NumPy OLS plus documented statsmodels cov_cluster CR1 formula.

    The fixed values were calculated outside the implementation under test with
    G/(G-1) * (N-1)/(N-K), unit clusters, K=4, and scipy.stats.t at df=G-1.
    Absolute tolerance is 1e-12 for matrix/statistical outputs.
    """
    execution = did_execution()
    validated = validate_did_input(execution, did_table(positive_effect_rows()))
    fit = fit_interaction_ols(validated.observations)
    units = execution.analysis_request.identification.units
    assert units is not None

    inference = cluster_robust_inference(
        fit,
        cluster_unit=units.analysis_unit,
        config=execution.configuration,
    )

    assert fit.coefficients == pytest.approx((8.0, 2.0, 2.0, 3.0), abs=1e-12)
    assert inference.standard_error == pytest.approx(2.103464143623269, abs=1e-12)
    assert inference.statistic == pytest.approx(1.42621874924496, abs=1e-12)
    assert inference.degrees_of_freedom == 19
    assert inference.p_value == pytest.approx(0.17003027022113726, abs=1e-12)
    assert inference.confidence_interval.lower == pytest.approx(
        -1.4026010501888777,
        abs=1e-12,
    )
    assert inference.confidence_interval.upper == pytest.approx(
        7.402601050188878,
        abs=1e-12,
    )


@pytest.mark.parametrize(
    ("treated", "control", "supported", "codes"),
    (
        (3, 3, False, {"did.insufficient_clusters", "did.insufficient_group_clusters"}),
        (3, 7, False, {"did.insufficient_group_clusters", "did.few_clusters"}),
        (4, 4, True, {"did.few_clusters"}),
        (10, 10, True, {"did.few_clusters"}),
        (15, 15, True, set()),
    ),
)
def test_cluster_policy_is_centralized_and_deterministic(
    treated: int,
    control: int,
    supported: bool,
    codes: set[str],
) -> None:
    assessment = assess_cluster_policy(_counts(treated, control), DifferenceInDifferencesConfig())

    assert assessment.inference_supported is supported
    assert {item.code for item in assessment.diagnostics} == codes


def test_nonzero_effect_with_zero_clustered_standard_error_abstains_numerically() -> None:
    rows = tuple(
        row
        for index in range(4)
        for row in (
            DidObservation(f"t-{index}", True, False, 10.0),
            DidObservation(f"t-{index}", True, True, 15.0),
            DidObservation(f"c-{index}", False, False, 8.0),
            DidObservation(f"c-{index}", False, True, 10.0),
        )
    )
    fit = fit_interaction_ols(rows)
    units = did_execution().analysis_request.identification.units
    assert units is not None

    with pytest.raises(DidNumericalError, match="nonzero effect has zero clustered uncertainty"):
        cluster_robust_inference(
            fit,
            cluster_unit=units.analysis_unit,
            config=DifferenceInDifferencesConfig(),
        )
