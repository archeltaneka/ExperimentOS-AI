"""Exercise actual public services through the Phase 4 advanced harness."""

import pytest


def test_every_reference_case_satisfies_its_declared_contract():
    from packages.evals.statistical.advanced.fixtures import reference_cases
    from packages.evals.statistical.advanced.harness import evaluate_advanced_case

    results = [evaluate_advanced_case(c) for c in reference_cases()]
    assert all(r.passed for r in results), [
        (r.case_id, r.blocking_findings) for r in results if not r.passed
    ]


def test_fold_and_group_audits_validate_source_evidence():
    from packages.evals.statistical.advanced.fixtures import reference_cases
    from packages.evals.statistical.advanced.harness import evaluate_advanced_case

    case = next(c for c in reference_cases() if c.case_id == "advanced-repository_hte-success")
    result = evaluate_advanced_case(case)
    checks = {c.check_id: c for c in result.checks}
    assert checks["fold_audit"].status.value == "pass"
    assert checks["group_audit"].status.value == "pass"


@pytest.mark.parametrize("capability", ["repository_dml", "repository_hte"])
def test_owned_capabilities_run_successfully_with_uncertainty_and_replay(capability):
    from packages.evals.statistical.advanced.fixtures import reference_cases
    from packages.evals.statistical.advanced.harness import evaluate_advanced_case

    case = next(c for c in reference_cases() if c.case_id == f"advanced-{capability}-success")
    result = evaluate_advanced_case(case)
    assert result.passed, result.checks
    assert result.actual_status == "completed"
    assert result.determinism_passed
    assert result.advanced.configuration_fingerprint
    assert {"uncertainty", "interface", "repeatability", "privacy"} <= {
        c.check_id for c in result.checks
    }


def test_installed_broken_adapter_is_not_optional_absence(monkeypatch):
    from packages.evals.statistical.advanced import harness
    from packages.evals.statistical.advanced.fixtures import reference_cases
    from packages.experiments.analysis.causal.econml import dependency

    monkeypatch.setattr(harness, "dependency_state", lambda package: ("installed", "0.17.0"))

    def broken():
        raise dependency.AdapterError("INCOMPATIBLE_DEPENDENCY_RUNTIME", "safe")

    monkeypatch.setattr(dependency, "load_econml", broken)
    case = next(c for c in reference_cases() if c.case_id == "advanced-econml_dml-success")
    result = harness.evaluate_advanced_case(case)
    assert not result.passed
    assert result.advanced.dependency_state != "unavailable"


def test_escaped_exception_is_blocking_and_redacted(monkeypatch):
    from packages.evals.statistical.advanced import harness
    from packages.evals.statistical.advanced.fixtures import reference_cases

    def broken(*args, **kwargs):
        raise RuntimeError("private_feature=[1,2,3]")

    monkeypatch.setattr(harness, "run_case", broken)
    result = harness.evaluate_advanced_case(reference_cases()[0])
    assert not result.passed
    assert "private_feature" not in result.model_dump_json()
    assert any(
        c.dimension == "exception_normalization" and c.status.value == "fail" for c in result.checks
    )
