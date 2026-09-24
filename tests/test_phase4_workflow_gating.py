"""Actual estimator/calculator spies prove blocked work never runs."""

import pytest

from packages.evals.agent_analysis_cases import load_analysis_workflow_cases


@pytest.mark.parametrize(
    "case_id,boundary,expected",
    [
        ("dml-post-treatment", "dml", 0),
        ("dml-success", "dml", 1),
        ("ipw-ate-no-overlap", "ipw", 0),
        ("ipw-ate-success", "ipw", 1),
        ("missing-business-provenance", "business", 0),
        ("business", "business", 1),
    ],
)
def test_forbidden_call_and_positive_control(case_id, boundary, expected):
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == case_id)
    result = evaluate_workflow_case(case)
    assert result.call_counts[boundary] == expected
    assert result.checks["downstream_gating"].status == "pass"
