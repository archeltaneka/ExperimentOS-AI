from __future__ import annotations

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)

REQUIRED_CASE_IDS = {
    "cuped-positive-variance-reduction",
    "cuped-zero-variance-reduction",
    "cuped-negative-variance-reduction",
    "cuped-constant-covariate-abstention",
    "cuped-post-treatment-covariate-abstention",
    "cuped-missing-covariate-retention",
    "cuped-excessive-missingness-abstention",
    "cuped-arm-imbalance-advisory",
    "sequential-null-sequence",
    "sequential-early-efficacy-crossing",
    "sequential-late-efficacy-crossing",
    "sequential-no-stop-sequence",
    "sequential-skipped-look-invalid",
    "sequential-duplicate-look-invalid",
    "sequential-decreasing-sample-invalid",
    "sequential-plan-mutation-invalid",
    "sequential-changed-outcome-invalid",
    "sequential-changed-treatment-invalid",
    "sequential-insufficient-sample-abstention",
    "sequential-invalid-fingerprint-invalid",
    "bayesian-binary-conjugate",
    "bayesian-continuous-conjugate",
    "bayesian-weak-prior",
    "bayesian-informative-prior-advisory",
    "bayesian-null-effect",
    "bayesian-positive-effect",
    "bayesian-negative-effect",
    "bayesian-sparse-events",
    "bayesian-zero-events",
    "bayesian-invalid-prior",
    "bayesian-unsupported-likelihood",
    "bayesian-rope-supplied",
    "bayesian-rope-absent",
    "bayesian-seeded-approximation-skipped",
    "bayesian-inadequate-data-abstention",
}


def test_reference_inventory_covers_randomized_inference_methods() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    cases = {case.case_id: case for case in dataset.cases}

    assert REQUIRED_CASE_IDS <= cases.keys()
    assert {case.capability.value for case in dataset.cases} >= {
        "cuped",
        "sequential",
        "bayesian_binary",
        "bayesian_continuous",
    }


def test_every_reference_declares_reliability_contract_metadata() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)

    for case in dataset.cases:
        assert case.method
        assert isinstance(case.expected_assumption_codes, tuple)
        assert isinstance(case.expected_uncertainty_fields, tuple)
        assert case.reference_provenance
        assert case.deterministic_configuration
        for expected in case.expected_values:
            if isinstance(expected.value, float):
                assert expected.tolerance is not None
                assert expected.tolerance.absolute >= 0.0
                assert expected.tolerance.rationale
                assert expected.tolerance.provenance


def test_seeded_sampling_is_honestly_skipped_when_no_sampling_path_exists() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    case = next(
        item for item in dataset.cases if item.case_id == "bayesian-seeded-approximation-skipped"
    )

    assert case.category.value == "skipped"
    assert case.expected_status == "skipped"
    assert case.deterministic_configuration["reason"] == "no_seeded_sampling_path"


def test_core_method_references_cover_required_numerical_outputs() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    cases = {case.case_id: case for case in dataset.cases}

    required_paths = {
        "cuped-positive-variance-reduction": {
            "coefficient.theta",
            "coefficient.covariance",
            "coefficient.covariate_variance",
            "coefficient.correlation",
            "retention.treatment.retained_count",
            "retention.control.retained_count",
            "adjusted_result.point_effect.absolute_effect.value",
            "adjusted_result.test_result.standard_error",
            "adjusted_result.test_result.confidence_interval.lower",
            "adjusted_result.test_result.confidence_interval.upper",
            "variance_reduction.fraction",
            "status",
        },
        "sequential-null-sequence": {
            "plan.plan_fingerprint",
            "plan.planned_looks.0.information_time",
            "plan.planned_looks.1.information_time",
            "boundaries.0.critical_boundary",
            "boundaries.0.cumulative_alpha_spent",
            "boundaries.0.nominal_alpha",
            "boundaries.1.critical_boundary",
            "boundaries.1.cumulative_alpha_spent",
            "boundaries.1.nominal_alpha",
            "current_look.standardized_statistic",
            "current_status",
            "plan_integrity",
        },
        "bayesian-binary-conjugate": {
            "treatment_posterior.prior.alpha",
            "treatment_posterior.prior.beta",
            "treatment_posterior.posterior_alpha",
            "treatment_posterior.posterior_beta",
            "treatment_posterior.posterior_mean",
            "treatment_posterior.posterior_variance",
            "control_posterior.posterior_alpha",
            "control_posterior.posterior_beta",
            "effect.posterior_mean",
            "effect.posterior_standard_deviation",
            "effect.credible_interval.lower",
            "effect.credible_interval.upper",
            "effect.probability_of_superiority.probability",
        },
        "bayesian-continuous-conjugate": {
            "treatment_posterior.prior.mu_0",
            "treatment_posterior.posterior_mu",
            "treatment_posterior.posterior_kappa",
            "treatment_posterior.posterior_alpha",
            "treatment_posterior.posterior_beta",
            "treatment_posterior.marginal_mean_variance",
            "control_posterior.posterior_mu",
            "effect.posterior_mean",
            "effect.posterior_standard_deviation",
            "effect.credible_interval.lower",
            "effect.credible_interval.upper",
            "effect.probability_of_superiority.probability",
        },
    }

    for case_id, expected_paths in required_paths.items():
        actual_paths = {expected.path for expected in cases[case_id].expected_values}
        assert expected_paths <= actual_paths
