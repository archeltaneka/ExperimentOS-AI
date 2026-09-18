"""Negative controls proving that conformance gates reject malformed public evidence."""

import pytest

from packages.evals.statistical.advanced.fixtures import prepare_case, reference_cases, run_case
from packages.evals.statistical.advanced.result_checks import result_checks
from packages.evals.statistical.telemetry import _RecordingProvider


def case_for(capability="repository_dml", scenario="success"):
    return next(c for c in reference_cases() if c.case_id == f"advanced-{capability}-{scenario}")


@pytest.mark.parametrize(
    "mutation,dimension",
    [
        ("uncertainty", "uncertainty"),
        ("raw_object", "interface_leakage"),
        ("nonfinite", "interface_leakage"),
        ("folds", "data_leakage"),
        ("invalid_contract", "identification"),
        ("wrong_population", "estimand"),
    ],
)
def test_success_mutations_are_blocking(mutation, dimension):
    case = case_for()
    result = run_case(case, _RecordingProvider()).result
    if mutation == "uncertainty":
        result = result.model_copy(update={"test_result": None})
    elif mutation == "raw_object":
        result = result.model_copy(update={"hidden": object()})
    elif mutation == "nonfinite":
        result = result.model_copy(update={"point_estimate": float("nan")})
    elif mutation == "folds":
        result = result.model_copy(
            update={
                "fold_plan": result.fold_plan.model_copy(
                    update={"assignments": result.fold_plan.assignments[:-1]}
                )
            }
        )
    elif mutation == "invalid_contract":
        from packages.experiments.analysis.causal import CausalAssumptionStatus

        request = result.analysis_request
        assumptions = tuple(
            a.model_copy(update={"status": CausalAssumptionStatus.VIOLATED})
            for a in request.identification.assumptions
        )
        result = result.model_copy(
            update={
                "analysis_request": request.model_copy(
                    update={
                        "identification": request.identification.model_copy(
                            update={"assumptions": assumptions}
                        )
                    }
                )
            }
        )
    elif mutation == "wrong_population":
        from packages.experiments.analysis.causal import TargetPopulationKind

        result = result.model_copy(
            update={
                "target_population": result.target_population.model_copy(
                    update={"kind": TargetPopulationKind.TREATED}
                )
            }
        )
    checks = result_checks(case, result)
    assert any(c.status.value == "fail" and c.dimension == dimension for c in checks), checks


def test_nuisance_hyperparameters_change_recorded_configuration():
    from packages.experiments.analysis.causal.dml import DoubleMachineLearningEstimator
    from packages.experiments.analysis.causal.dml.adapter import SklearnRidgeOutcomeAdapter
    from tests.causal_identification_fixtures import provenance

    case = case_for()
    execution, table, _ = prepare_case(case)
    results = [
        DoubleMachineLearningEstimator(
            outcome_adapter=SklearnRidgeOutcomeAdapter(
                feature_order=("prior_orders",), seed=812, alpha=alpha
            )
        ).analyze(execution, table, provenance=provenance())
        for alpha in (1.0, 2.0)
    ]
    assert (
        results[0].configuration_fingerprint_sha256 != results[1].configuration_fingerprint_sha256
    )


def test_schema_cannot_bypass_advanced_harness_by_omitting_details():
    from pydantic import ValidationError

    from packages.evals.statistical.models import StatisticalReferenceCase

    payload = case_for().model_dump()
    payload["advanced"] = None
    with pytest.raises(ValidationError):
        StatisticalReferenceCase.model_validate(payload)


def test_wrong_abstention_reason_does_not_satisfy_expected_refusal():
    case = case_for(scenario="degenerate")
    result = run_case(case, _RecordingProvider()).result
    result = result.model_copy(
        update={
            "abstention_reason": result.abstention_reason.model_copy(
                update={"code": "unrelated_failure"}
            )
        }
    )
    checks = result_checks(case, result)
    assert any(c.dimension == "abstention" and c.status.value == "fail" for c in checks)


@pytest.mark.parametrize(
    "capability,scenario", [("repository_dml", "invalid"), ("repository_hte", "invalid_modifier")]
)
def test_invalid_request_with_nonfinite_configuration_stays_normalized(capability, scenario):
    from packages.experiments.analysis.causal.dml import DoubleMachineLearningEstimator
    from packages.experiments.analysis.causal.hte import HeterogeneousEffectEstimator
    from tests.causal_identification_fixtures import provenance

    request, table, _ = prepare_case(case_for(capability, scenario))
    request = request.model_copy(
        update={
            "configuration": request.configuration.model_copy(
                update={"treatment_residual_tolerance": float("nan")}
            )
        }
    )
    estimator = (
        DoubleMachineLearningEstimator()
        if capability == "repository_dml"
        else HeterogeneousEffectEstimator()
    )
    result = estimator.analyze(request, table, provenance=provenance())
    assert result.status.value == "invalid"
    assert result.abstention_reason


def test_comparison_is_part_of_the_existing_report():
    from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
    from packages.evals.statistical.models import StatisticalReferenceDataset

    dataset = StatisticalReferenceDataset(
        baseline_id="advanced",
        version="1",
        fixture_provenance="phase4-statistical-fixtures-v1",
        cases=tuple(sorted((case_for(), case_for("econml_dml")), key=lambda c: c.case_id)),
    )
    report = StatisticalBaselineEvaluator().evaluate(dataset)
    assert any(
        check.check_id == "comparison" for case in report.case_results for check in case.checks
    )


def test_sensitive_diagnostic_is_blocked_and_not_serialized(monkeypatch):
    from packages.evals.statistical.advanced import harness

    original = harness.run_case
    secret = "private-array-canary patient Alice Smith"

    def corrupt(*args):
        execution = original(*args)
        result = execution.result
        execution.result = result.model_copy(
            update={
                "diagnostics": (
                    *result.diagnostics,
                    result.diagnostics[0].model_copy(update={"code": secret}),
                )
            }
        )
        return execution

    monkeypatch.setattr(harness, "run_case", corrupt)
    report = harness.evaluate_advanced_case(case_for(scenario="invalid"))
    assert not report.passed
    assert secret not in report.model_dump_json()


def test_observed_same_fold_training_leakage_blocks_even_with_plausible_reports(monkeypatch):
    from packages.evals.statistical.advanced.harness import evaluate_advanced_case
    from packages.experiments.analysis.causal.dml import crossfit
    from packages.experiments.analysis.causal.dml.validation import validate_dml_input

    case = case_for()
    request, table, _ = prepare_case(case)
    rows = validate_dml_input(request, table).rows
    original = crossfit._fit

    def leaking(adapter, batch, target, **kwargs):
        if kwargs["role"].value != "outcome":
            return original(adapter, batch, target, **kwargs)
        full = crossfit._batch(rows, tuple(range(len(rows))), batch.feature_names)
        all_targets = tuple(r.outcome for r in rows)
        return original(adapter, full, all_targets, **kwargs).model_copy(
            update={"training_count": len(batch.rows)}
        )

    monkeypatch.setattr(crossfit, "_fit", leaking)
    report = evaluate_advanced_case(case)
    assert report.actual_status == "completed", report
    assert any(c.dimension == "data_leakage" and c.status.value == "fail" for c in report.checks)


def test_missing_dependency_cannot_mask_malformed_success(monkeypatch):
    from packages.evals.statistical.advanced import harness
    from packages.experiments.analysis.causal.econml import dependency

    monkeypatch.setattr(harness, "dependency_state", lambda _: ("unavailable", None))

    def missing():
        raise dependency.AdapterError("OPTIONAL_DEPENDENCY_UNAVAILABLE", "absent")

    monkeypatch.setattr(dependency, "load_econml", missing)
    original = harness.run_case

    def corrupt(*args):
        execution = original(*args)
        result = execution.result
        execution.result = result.model_copy(update={"status": type(result.status)("completed")})
        return execution

    monkeypatch.setattr(harness, "run_case", corrupt)
    report = harness.evaluate_advanced_case(case_for("econml_dml"))
    assert not report.passed


def test_self_consistent_wrong_target_is_rejected_against_executed_request(monkeypatch):
    from packages.evals.statistical.advanced import harness
    from packages.experiments.analysis.causal import TargetPopulationKind

    original = harness.run_case

    def corrupt(*args):
        execution = original(*args)
        result = execution.result
        population = result.target_population.model_copy(
            update={"kind": TargetPopulationKind.TREATED}
        )
        execution.result = result.model_copy(
            update={
                "target_population": population,
                "estimand": result.estimand.model_copy(update={"target_population": population}),
            }
        )
        return execution

    monkeypatch.setattr(harness, "run_case", corrupt)
    report = harness.evaluate_advanced_case(case_for())
    assert any(c.dimension == "estimand" and c.status.value == "fail" for c in report.checks)
