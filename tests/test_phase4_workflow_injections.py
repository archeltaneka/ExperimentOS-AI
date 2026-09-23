"""Corruption must exercise the real boundary and trigger declared findings."""

import pytest

from packages.evals.agent_analysis_cases import load_analysis_workflow_cases


def test_closed_mutation_matrix_is_detected_and_restored():
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case
    from packages.evals.statistical.workflow.injections import INJECTION_SPECS, evaluate_injection

    cases = {c.case_id: c for c in load_analysis_workflow_cases()}
    for spec in INJECTION_SPECS:
        result = evaluate_injection(spec, cases[spec.case_id])
        assert result.injection_detected, (spec.injection_id, result.detected_rule_ids)
        assert set(spec.expected_rule_ids) <= set(result.detected_rule_ids)
    assert all(
        c.status != "fail" for c in evaluate_workflow_case(cases["randomized"]).checks.values()
    )


def test_disabled_detector_fails_the_injection(monkeypatch):
    from packages.evals.statistical.workflow import injections

    monkeypatch.setattr(injections, "injection_detected", lambda expected, actual: False)
    spec = injections.INJECTION_SPECS[0]
    case = next(c for c in load_analysis_workflow_cases() if c.case_id == spec.case_id)
    result = injections.evaluate_injection(spec, case)
    assert not result.injection_detected
    assert result.checks["injection_detection"].status == "fail"


def test_injection_requires_nonempty_expected_detections():
    from packages.evals.statistical.workflow.injections import injection_detected

    assert not injection_detected((), ())
    assert not injection_detected(("analysis.failures.routing",), ())


def test_unexpected_harness_exception_is_not_a_detected_injection(monkeypatch):
    from packages.evals.statistical.workflow import harness, injections

    def fail(*args, **kwargs):
        raise RuntimeError("harness failed")

    monkeypatch.setattr(harness, "evaluate_workflow_case", fail)
    spec = injections.INJECTION_SPECS[0]
    case = next(c for c in load_analysis_workflow_cases() if c.case_id == spec.case_id)
    with pytest.raises(RuntimeError, match="harness failed"):
        injections.evaluate_injection(spec, case)


@pytest.mark.parametrize(
    "text",
    [
        "Effect is 999; p-value is 0; the interval is [999, 1000].",
        "Posterior superiority is 100 percent; profit is $9999999.",
    ],
)
def test_fabricated_presenter_is_rejected(text):
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "business")
    result = evaluate_workflow_case(case.model_copy(update={"presenter_candidate": text}))
    assert result.checks["prose_grounding"].status == "pass"
    assert result.checks["result_integrity"].status == "pass"
