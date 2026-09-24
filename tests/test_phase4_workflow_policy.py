"""Complete policy consumes actual cases and checks, never asserted totals."""

from copy import deepcopy

import pytest


@pytest.fixture(scope="module")
def golden_results():
    from packages.evals.agent_analysis_cases import load_analysis_workflow_cases
    from packages.evals.statistical.workflow.suite import evaluate_workflow_suite

    cases = {c.case_id: c for c in load_analysis_workflow_cases()}
    results, errors = evaluate_workflow_suite(tuple(cases.values()))
    assert not errors
    return [r.model_dump(mode="json") for r in results]


def test_complete_inventory_passes(golden_results):
    from packages.evals.statistical.workflow.policy import workflow_metrics

    metrics = workflow_metrics(golden_results, scope="complete")
    assert not {k: v for k, v in metrics.items() if k.startswith("analysis.failures.") and v}


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "missing-check", "forged-pass", "illegal-skip", "forged-status"],
)
def test_incomplete_or_forged_checks_fail_closed(golden_results, mutation):
    from packages.evals.statistical.workflow.policy import workflow_metrics

    results = deepcopy(golden_results)
    target = next(r for r in results if r["case_id"] == "randomized")
    if mutation == "missing":
        results.remove(target)
    elif mutation == "duplicate":
        results.append(target)
    elif mutation == "missing-check":
        del target["checks"]["uncertainty_preserved"]
    elif mutation == "forged-pass":
        target["checks"]["reference_accuracy"]["status"] = "fail"
    elif mutation == "forged-status":
        target["execution_status"] = "abstained"
    else:
        target["checks"]["routing"].update(status="skipped", applicable=False)
    metrics = workflow_metrics(results, scope="complete")
    assert any(v for k, v in metrics.items() if k.startswith("analysis.failures."))


def test_optional_scope_cannot_claim_complete(golden_results):
    from packages.evals.statistical.workflow.policy import workflow_metrics

    results = [r for r in golden_results if r["family"] == "adapter"]
    assert (
        workflow_metrics(results, scope="optional-adapters")["analysis.scope"]
        == "optional-adapters"
    )
    assert workflow_metrics(results, scope="complete")["analysis.failures.case_inventory"] > 0


@pytest.mark.parametrize("identity", ["randomized", "econml_dml-absent", "econml_dml-broken"])
def test_unavailable_cannot_bypass_core_or_controlled_evidence(golden_results, identity):
    from packages.evals.statistical.workflow.policy import workflow_metrics

    results = deepcopy(golden_results)
    target = next(r for r in results if r["case_id"] == identity)
    target["dependency_state"] = "unavailable"
    target["evidence"] = None
    target["checks"]["reference_accuracy"].update(status="skipped", applicable=False)
    metrics = workflow_metrics(results, scope="complete")
    assert metrics["analysis.failures.dependency"] > 0


def test_controlled_execution_cannot_claim_real(golden_results):
    from packages.evals.statistical.workflow.policy import workflow_metrics

    results = deepcopy(golden_results)
    target = next(r for r in results if r["case_id"] == "econml_dml-absent")
    target["execution_kind"] = "real"
    assert workflow_metrics(results, scope="complete")["analysis.failures.dependency"] > 0


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (("pass", "warning"), "warning"),
        (("pass", "fail"), "fail"),
        (("skipped",), "skipped"),
        (("pass", "skipped"), "pass"),
        ((), "skipped"),
    ],
)
def test_quality_status_is_separate_from_execution(statuses, expected):
    from packages.evals.statistical.workflow.policy import workflow_quality_status

    assert workflow_quality_status(statuses) == expected
