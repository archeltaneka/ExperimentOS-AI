"""Independent numerical references cover each actually supported core method."""

import pytest

from packages.evals.agent_analysis_cases import load_analysis_workflow_cases, run_direct_reference

CORE_METHODS = {
    "randomized_fixed_horizon",
    "cuped",
    "sequential",
    "bayesian_ab",
    "did",
    "propensity_diagnostics",
    "ipw_ate",
    "ipw_att",
    "dml",
    "hte",
}


def test_every_core_method_has_independent_reference():
    cases = load_analysis_workflow_cases()
    supported = {
        c.expected_method
        for c in cases
        if c.expected_status in {"completed", "inconclusive"} and c.expectations.numerical
    }
    assert CORE_METHODS <= supported


@pytest.mark.parametrize("method", sorted(CORE_METHODS))
def test_core_reference_values_match_declared_tolerances(method):
    from packages.evals.statistical.evaluator import check_expected_value

    candidates = [
        c
        for c in load_analysis_workflow_cases()
        if c.expected_method == method and c.expectations.numerical
    ]
    assert candidates, f"missing {method} reference"
    for case in candidates:
        evidence = run_direct_reference(case)
        assert evidence is not None
        payload = evidence.model_dump(mode="json")
        for expected in case.expectations.numerical:
            check = check_expected_value(payload, expected)
            assert check.status == "pass", (case.case_id, check)


def test_reference_uses_requested_dataset_not_first_dataset():
    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "randomized")
    expected = run_direct_reference(case)
    changed = case.model_copy(deep=True)
    decoy = dict(changed.ask_payload["analysis_datasets"][0])
    decoy.update(reference="decoy", rows=[])
    changed.ask_payload["analysis_datasets"].insert(0, decoy)
    assert run_direct_reference(changed) == expected
