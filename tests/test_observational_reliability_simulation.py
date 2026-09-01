"""Versioned deterministic observational coverage simulation reliability."""

from __future__ import annotations

from packages.evals.statistical.did_fixtures import run_did_coverage_simulation
from packages.evals.statistical.evaluator import check_observational_coverage
from packages.evals.statistical.models import (
    CheckStatus,
    ObservationalSimulationSpecification,
    StatisticalCapability,
    StatisticalCaseCategory,
    StatisticalReferenceCase,
)


def _spec() -> ObservationalSimulationSpecification:
    return ObservationalSimulationSpecification(
        dgp_name="did_parallel_trends_gaussian",
        dgp_version="1.0.0",
        seed=101004,
        sample_size=80,
        treatment_assignment="40 treated and 40 comparison units; treatment fixed before draws",
        confounders=("unit_baseline", "group_baseline"),
        outcome_formula="8 + 2*treated_group + unit_baseline + 2*post + 3*treated_post + error",
        true_causal_effect=3.0,
        estimand="did_att",
        repetitions=40,
        model_configuration={
            "method": "two_group_two_period_did",
            "variance": "cluster_robust_cr1",
            "confidence_level": 0.95,
        },
        coverage_lower=0.80,
        coverage_upper=1.0,
        tolerance=0.15,
    )


def test_did_coverage_simulation_is_reproducible_and_records_complete_dgp() -> None:
    spec = _spec()

    first = run_did_coverage_simulation(spec)
    repeated = run_did_coverage_simulation(spec)

    assert first.model_dump(mode="json") == repeated.model_dump(mode="json")
    assert first.status == "completed"
    assert first.simulation == spec
    assert first.repetitions == 40
    assert first.true_effect == 3.0
    assert first.intervals_containing <= first.repetitions
    assert 0.0 <= first.interval_coverage <= 1.0
    assert first.coverage_status in {"within_aspirational_range", "outside_aspirational_range"}


def test_out_of_range_observational_coverage_is_advisory() -> None:
    case = StatisticalReferenceCase(
        case_id="observational-coverage-advisory",
        capability=StatisticalCapability.OBSERVATIONAL_COVERAGE,
        category=StatisticalCaseCategory.SUCCESSFUL_INFERENCE,
        method="did",
        analysis_design="two_group_two_period_did_simulation",
        estimand="did_att",
        target_population="treated",
        metric_type="continuous",
        fixture_id="observational_coverage_did_v1",
        expected_status="completed",
        expected_diagnostic_codes=(),
        expected_advisory_codes=(),
        expected_abstention=False,
        expected_abstention_reason=None,
        expected_values=(),
        simulation=_spec(),
        notes="Coverage is aspirational in v1.",
        fixture_provenance="phase4-statistical-fixtures-v1",
    )

    check = check_observational_coverage(case, {"interval_coverage": 0.5})[0]

    assert check.status is CheckStatus.ADVISORY
    assert check.rule_id == "statistics.performance.observational_interval_coverage"
