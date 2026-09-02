"""Strict contracts for issue #101 observational reliability references."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.models import (
    ObservationalSimulationSpecification,
    StatisticalCapability,
    StatisticalCaseCategory,
    StatisticalReferenceCase,
)


def _case_payload() -> dict[str, object]:
    return {
        "case_id": "observational-coverage-known-effect",
        "capability": "observational_coverage",
        "category": "successful_inference",
        "method": "ipw_ate",
        "analysis_design": "observational_cross_sectional",
        "estimand": "ate",
        "target_population": "eligible_population",
        "metric_type": "continuous",
        "fixture_id": "observational_coverage_known_effect",
        "expected_status": "advisory",
        "expected_diagnostic_codes": [],
        "expected_advisory_codes": ["coverage.outside_aspirational_range"],
        "expected_abstention": False,
        "expected_abstention_reason": None,
        "expected_values": [],
        "expected_assumption_codes": ["conditional_exchangeability", "positivity"],
        "deterministic_configuration": {"execution_mode": "offline_seeded"},
        "simulation": {
            "dgp_name": "confounded_linear_ipw_ate",
            "dgp_version": "1.0.0",
            "seed": 10101,
            "sample_size": 200,
            "treatment_assignment": "logit(-0.2 + 0.6 * x1 - 0.4 * x2)",
            "confounders": ["x1", "x2"],
            "outcome_formula": "1.0 + 2.0 * treatment + 0.8 * x1 - 0.5 * x2 + error",
            "true_causal_effect": 2.0,
            "estimand": "ate",
            "repetitions": 40,
            "model_configuration": {
                "propensity_model": "binary_logistic_newton_v1",
                "variance_method": "robust_sandwich",
            },
            "coverage_lower": 0.80,
            "coverage_upper": 1.0,
            "tolerance": 0.05,
        },
        "reference_provenance": "issue-101-independent-reference-v1",
        "notes": "Explicit deterministic coverage simulation.",
        "fixture_provenance": "phase4-statistical-fixtures-v2",
    }


def test_observational_capabilities_have_distinct_stable_ids() -> None:
    assert StatisticalCapability.CAUSAL_IDENTIFICATION.value == "causal_identification"
    assert StatisticalCapability.PROPENSITY_SCORE.value == "propensity_score"
    assert StatisticalCapability.IPW_ATE.value == "ipw_ate"
    assert StatisticalCapability.IPW_ATT.value == "ipw_att"
    assert StatisticalCapability.OBSERVATIONAL_COVERAGE.value == "observational_coverage"


def test_observational_reference_inventory_covers_issue_101_case_classes() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    case_ids = {case.case_id for case in dataset.cases}

    assert {
        "identification-contradictory-timing",
        "identification-insufficient-evidence",
        "propensity-raw-imbalance",
        "propensity-weighted-balance-improved",
        "ipw-ate-extreme-scores-advisory",
        "ipw-att-extreme-control-weights-advisory",
        "ipw-att-failed-overlap-abstention",
        "ipw-att-low-ess-abstention",
    } <= case_ids


def test_successful_did_references_declare_did_att_target() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    successful_did = tuple(
        case
        for case in dataset.cases
        if case.capability is StatisticalCapability.DIFFERENCE_IN_DIFFERENCES
        and case.category is StatisticalCaseCategory.SUCCESSFUL_INFERENCE
    )

    assert successful_did
    assert {(case.estimand, case.target_population) for case in successful_did} == {
        ("did_att", "treated")
    }


def test_observational_reference_records_estimand_population_and_explicit_dgp() -> None:
    case = StatisticalReferenceCase.model_validate(_case_payload())

    assert case.category is StatisticalCaseCategory.SUCCESSFUL_INFERENCE
    assert case.estimand == "ate"
    assert case.target_population == "eligible_population"
    assert case.simulation == ObservationalSimulationSpecification(
        dgp_name="confounded_linear_ipw_ate",
        dgp_version="1.0.0",
        seed=10101,
        sample_size=200,
        treatment_assignment="logit(-0.2 + 0.6 * x1 - 0.4 * x2)",
        confounders=("x1", "x2"),
        outcome_formula="1.0 + 2.0 * treatment + 0.8 * x1 - 0.5 * x2 + error",
        true_causal_effect=2.0,
        estimand="ate",
        repetitions=40,
        model_configuration={
            "propensity_model": "binary_logistic_newton_v1",
            "variance_method": "robust_sandwich",
        },
        coverage_lower=0.80,
        coverage_upper=1.0,
        tolerance=0.05,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("treatment_assignment", ""),
        ("confounders", []),
        ("repetitions", 0),
        ("coverage_lower", 1.01),
        ("coverage_upper", -0.01),
    ],
)
def test_simulation_spec_rejects_hidden_or_invalid_configuration(
    field: str,
    value: object,
) -> None:
    payload = _case_payload()
    simulation = dict(payload["simulation"])  # type: ignore[arg-type]
    simulation[field] = value
    payload["simulation"] = simulation

    with pytest.raises(ValidationError):
        StatisticalReferenceCase.model_validate(payload)


def test_simulation_capability_requires_simulation_metadata() -> None:
    payload = _case_payload()
    payload["simulation"] = None

    with pytest.raises(ValidationError, match="observational coverage cases require simulation"):
        StatisticalReferenceCase.model_validate(payload)


def test_non_simulation_capability_rejects_simulation_metadata() -> None:
    payload = _case_payload()
    payload["capability"] = "ipw_ate"

    with pytest.raises(ValidationError, match="only observational coverage cases may declare"):
        StatisticalReferenceCase.model_validate(payload)
