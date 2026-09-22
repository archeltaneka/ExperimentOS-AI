"""Explicit method normalization cannot guess or accept certified causal results."""

from copy import deepcopy

import pytest

from packages.experiments.analysis.orchestration.requests import (
    AnalysisRoutingRefusal,
    BusinessInputRefusal,
    FixedHorizonWorkflowRequest,
    normalize_analysis_input,
)
from tests.analysis_contract_fixtures import randomized_request


def fixed_payload():
    return {
        "schema_version": "1",
        "request_id": "analysis-108",
        "method": "randomized_fixed_horizon",
        "parameters": {
            "execution": {
                "request_id": "analysis-108",
                "analysis_request": randomized_request().model_dump(mode="json"),
                "alternative": "two_sided",
            },
            "binding": {
                "treatment_column": "arm",
                "outcome": {"value_column": "outcome"},
                "observation_unit_column": "unit",
                "randomization_unit_column": "unit",
            },
            "dataset": {"reference": "sample", "version": "1"},
        },
    }


def test_explicit_fixed_request_preserves_contracts_and_identity():
    payload = fixed_payload()
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, FixedHorizonWorkflowRequest)
    assert result.method == "randomized_fixed_horizon"
    assert result.request_id == "analysis-108"
    assert result.experiment_id == "experiment-a"
    assert result.execution.analysis_request == randomized_request()
    assert result.dataset.version == "1"
    payload["parameters"]["execution"]["request_id"] = "changed"
    assert result.execution.request_id == "analysis-108"


@pytest.mark.parametrize("method", [None, "", "  ", ["did", "dml"], 17])
def test_ambiguous_method_abstains_without_guessing(method):
    result = normalize_analysis_input({"method": method}, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "abstained"
    assert result.method is None
    assert result.abstention.code == "analysis.method_ambiguous"


def test_unknown_method_abstains_with_explicit_identity():
    result = normalize_analysis_input({"method": "best_effect"}, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "abstained"
    assert result.method == "best_effect"
    assert result.abstention.code == "analysis.method_unsupported"


@pytest.mark.parametrize("field", ["execution", "binding", "dataset"])
def test_missing_statistical_input_is_invalid(field):
    payload = fixed_payload()
    del payload["parameters"][field]
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "invalid"


def test_mismatched_native_request_id_is_invalid():
    payload = fixed_payload()
    payload["parameters"]["execution"]["request_id"] = "other"
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "invalid"


def test_method_does_not_override_native_design():
    payload = fixed_payload()
    payload["parameters"]["execution"]["analysis_request"]["study_design"]["method"] = "cuped"
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "invalid"


def test_parameters_cannot_replace_outer_method_or_experiment():
    for key, value in [("method", "did"), ("experiment_id", "other")]:
        payload = fixed_payload()
        payload["parameters"][key] = value
        result = normalize_analysis_input(payload, experiment_id="experiment-a")
        assert isinstance(result, AnalysisRoutingRefusal)
        assert result.status == "invalid"


def test_invalid_business_does_not_erase_valid_statistical_request():
    payload = fixed_payload()
    payload["business"] = {"population": "private-row-sentinel"}
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, FixedHorizonWorkflowRequest)
    assert isinstance(result.business, BusinessInputRefusal)
    assert "private-row-sentinel" not in result.business.model_dump_json()


def test_rejected_values_are_not_in_refusal():
    payload = deepcopy(fixed_payload())
    payload["parameters"]["binding"]["outcome"]["lower_bound"] = "private-row-sentinel"
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert "private-row-sentinel" not in result.model_dump_json()


@pytest.mark.parametrize("method", ["dml", "hte", "econml_dml", "econml_hte", "ipw_ate", "dowhy"])
def test_caller_certified_identification_cannot_enter_normalized_request(method):
    result = normalize_analysis_input(
        {
            "method": method,
            "request_id": "forged",
            "parameters": {"identification_result": {"status": "identified"}},
        },
        experiment_id="experiment-a",
    )
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "invalid"


@pytest.mark.parametrize(
    "method",
    [
        "cuped",
        "bayesian_ab",
        "sequential",
        "did",
        "propensity_diagnostics",
        "ipw_ate",
        "ipw_att",
        "dml",
        "hte",
        "econml_dml",
        "econml_hte",
        "dowhy",
    ],
)
def test_supported_request_normalizes_without_method_substitution(method):
    from tests.orchestration_fixtures import method_payload

    payload = method_payload(method)
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert not isinstance(result, AnalysisRoutingRefusal)
    assert result.method == method
    assert result.request_id == payload["request_id"]


def test_ipw_method_and_estimand_must_agree():
    from tests.orchestration_fixtures import method_payload

    payload = method_payload("ipw_ate")
    payload["method"] = "ipw_att"
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "invalid"


@pytest.mark.parametrize("method", ["bayesian_ab", "sequential"])
def test_malformed_prior_or_plan_is_not_repaired(method):
    from tests.orchestration_fixtures import method_payload

    payload = method_payload(method)
    if method == "bayesian_ab":
        payload["parameters"]["execution"]["treatment_prior"]["alpha"] = -1.0
    else:
        payload["parameters"]["plan"]["planned_looks"] = []
    result = normalize_analysis_input(payload, experiment_id="experiment-a")
    assert isinstance(result, AnalysisRoutingRefusal)
    assert result.status == "invalid"
