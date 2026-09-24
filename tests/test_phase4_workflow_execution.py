"""Real API execution must preserve owned evidence and caller state."""

from copy import deepcopy

import pytest

from apps.api.main import app, get_question_answering_service
from packages.evals.agent_analysis_cases import load_analysis_workflow_cases
from packages.evals.agent_e2e import AgentE2EEvaluator, build_default_agent_e2e_cases


def test_evaluator_restores_caller_overrides():
    previous = dict(app.dependency_overrides)

    def sentinel():
        return "caller-owned"

    app.dependency_overrides[get_question_answering_service] = sentinel
    try:
        case = next(c for c in build_default_agent_e2e_cases() if c.id == "analysis-randomized")
        AgentE2EEvaluator(cases=[case]).evaluate()
        assert app.dependency_overrides[get_question_answering_service] is sentinel
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("case", load_analysis_workflow_cases(), ids=lambda c: c.case_id)
def test_real_workflow_case_preserves_state_and_references(case):
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    result = evaluate_workflow_case(case)
    assert result.execution_status == (
        "unavailable" if result.dependency_state == "unavailable" else case.expected_status
    )
    assert not [c for c in result.checks.values() if c.status == "fail"]
    assert result.checks["state_preserved"].status == "pass"
    assert "ask_payload" not in result.model_dump_json()


def test_bayesian_uncertainty_loss_is_not_skipped():
    from packages.evals.agent_analysis_cases import run_direct_reference
    from packages.evals.statistical.workflow.checks import evidence_checks

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "bayesian-success")
    payload = deepcopy(run_direct_reference(case).model_dump(mode="json"))
    payload["effect"]["credible_interval"] = None
    checks = evidence_checks(case, payload)
    assert checks["uncertainty_preserved"].status == "fail"


def test_valid_negative_business_impact_is_not_a_quality_failure():
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "business-negative")
    result = evaluate_workflow_case(case)
    assert result.business_evidence["net_monetary_impact"]["central"] == pytest.approx(-10000)
    assert not [c for c in result.checks.values() if c.status == "fail"]


def test_evaluator_restores_overrides_and_environment_on_exception(monkeypatch):
    import os

    previous = dict(app.dependency_overrides)
    sentinel = object()
    app.dependency_overrides[get_question_answering_service] = sentinel
    monkeypatch.setenv("ASK_MODE", "caller-mode")

    def fail(_):
        raise RuntimeError("controlled harness failure")

    try:
        with pytest.raises(RuntimeError, match="controlled harness failure"):
            AgentE2EEvaluator(
                cases=build_default_agent_e2e_cases()[:1], service_factory=fail
            ).evaluate()
        assert os.environ["ASK_MODE"] == "caller-mode"
        assert app.dependency_overrides[get_question_answering_service] is sentinel
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_lost_assumptions_fail_and_repeated_evidence_is_deterministic():
    from packages.evals.statistical.workflow.checks import evidence_checks
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "dml-success")
    first, second = evaluate_workflow_case(case), evaluate_workflow_case(case)
    assert first.evidence == second.evidence
    changed = deepcopy(first.evidence)
    changed["assumptions"] = []
    assert evidence_checks(case, changed)["assumptions_preserved"].status == "fail"
