"""Optional identity, genuine absence, and installed breakage are distinct."""

import pytest

from packages.evals.agent_analysis_cases import load_analysis_workflow_cases


@pytest.mark.parametrize("method", ["econml_dml", "econml_hte", "dowhy"])
def test_optional_identity_and_controlled_absence(method):
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    case = next(
        c
        for c in load_analysis_workflow_cases()
        if c.expected_method == method and c.optional_unavailable
    )
    result = evaluate_workflow_case(case)
    assert result.method == method
    assert result.execution_status == "unavailable"
    assert result.dependency_state == "controlled"
    assert all(c.status != "fail" for c in result.checks.values())


@pytest.mark.parametrize("method", ["econml_dml", "econml_hte", "dowhy"])
def test_installed_broken_is_not_reported_as_absent(method, monkeypatch):
    from packages.evals.statistical.workflow import optional
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == method + "-real")
    monkeypatch.setattr(optional, "dependency_state", lambda package: ("installed", "test"))
    with optional.dependency_override(method, "absent"):
        result = evaluate_workflow_case(case)
    assert result.checks["dependency"].status == "fail"
    assert result.dependency_state == "broken"


def test_real_optional_cases_are_explicitly_recorded():
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    for case in load_analysis_workflow_cases():
        if case.case_id.endswith("-real"):
            result = evaluate_workflow_case(case)
            assert result.dependency_state in {"installed", "unavailable", "broken"}
            assert result.execution_kind == "real"
            assert not [c for c in result.checks.values() if c.status == "fail"]
