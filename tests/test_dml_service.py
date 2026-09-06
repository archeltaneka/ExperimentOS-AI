"""End-to-end tests for the bounded deterministic DML estimator."""

from __future__ import annotations

from packages.experiments.analysis.causal.dml.protocols import NuisanceRole
from packages.experiments.analysis.causal.dml.results import DMLStatus
from packages.experiments.analysis.causal.dml.service import DoubleMachineLearningEstimator
from packages.experiments.analysis.causal.variables import MeasurementTiming
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_identification, dml_table
from tests.test_dml_crossfit import (
    RecordingOutcomeAdapter,
    RecordingTreatmentAdapter,
    adapter_metadata,
)


def _linear_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    noise = (-0.4, 0.2, 0.5, -0.3, 0.1)
    for index in range(80):
        x = (index - 39.5) / 10.0
        treated = (index * 17 + 3) % 7 < 3
        rows.append(
            {
                "account_id": f"unit-{index:03d}",
                "treated": int(treated),
                "outcome": 2.0 * treated + 0.7 * x + noise[index % len(noise)],
                "prior_orders": x,
            }
        )
    return tuple(rows)


def test_dml_service_returns_owned_complete_deterministic_result() -> None:
    estimator = DoubleMachineLearningEstimator()
    execution = dml_execution(fold_count=4, seed=812)
    table = dml_table(_linear_rows())

    first = estimator.analyze(execution, table, provenance=provenance())
    second = estimator.analyze(execution, table, provenance=provenance())

    assert first.status is DMLStatus.COMPLETED
    assert first.point_estimate is not None
    assert abs(first.point_estimate - 2.0) < 0.25
    assert first.test_result is not None
    assert first.test_result.standard_error > 0.0
    assert first.fold_plan is not None
    assert len(first.fold_fits) == 4
    assert first.nuisance_diagnostics is not None
    assert "does not establish causal validity" in first.nuisance_diagnostics.interpretation
    assert first.model_dump_json() == second.model_dump_json()
    assert "sklearn" not in type(first).__module__


def test_dml_service_is_row_order_invariant_with_stable_ids() -> None:
    estimator = DoubleMachineLearningEstimator()
    execution = dml_execution(fold_count=4, seed=99)
    rows = _linear_rows()

    ordered = estimator.analyze(execution, dml_table(rows), provenance=provenance())
    reversed_result = estimator.analyze(
        execution,
        dml_table(tuple(reversed(rows))),
        provenance=provenance(),
    )

    assert ordered.model_dump(mode="json") == reversed_result.model_dump(mode="json")


def test_dml_service_normalizes_invalid_identification_without_fitting() -> None:
    execution = dml_execution(
        identification_result=dml_identification(adjustment_timing=MeasurementTiming.POST_TREATMENT)
    )

    result = DoubleMachineLearningEstimator().analyze(
        execution,
        dml_table(_linear_rows()),
        provenance=provenance(),
    )

    assert result.status is DMLStatus.INVALID
    assert result.point_estimate is None
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "dml.identification.invalid"


def test_dml_service_normalizes_failed_nuisance_fit_with_fold_and_role() -> None:
    estimator = DoubleMachineLearningEstimator(
        outcome_adapter=RecordingOutcomeAdapter(
            adapter_metadata(NuisanceRole.OUTCOME), [], fail_fit=True
        ),
        treatment_adapter=RecordingTreatmentAdapter(adapter_metadata(NuisanceRole.TREATMENT), []),
    )

    result = estimator.analyze(
        dml_execution(fold_count=4, seed=12),
        dml_table(_linear_rows()),
        provenance=provenance(),
    )

    assert result.status is DMLStatus.ABSTAINED
    assert result.point_estimate is None
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "dml.nuisance.fit_failure"
    assert result.abstention_reason.fold_index == 0
    assert result.abstention_reason.nuisance_role is NuisanceRole.OUTCOME


def test_dml_service_abstains_for_fatal_cross_fitted_overlap() -> None:
    rows = tuple(
        {
            "account_id": f"poor-{index:03d}",
            "treated": int(index >= 20),
            "outcome": float(index >= 20) + 0.2 * (index - 19.5),
            "prior_orders": float(index - 19.5),
        }
        for index in range(40)
    )
    estimator = DoubleMachineLearningEstimator(
        outcome_adapter=RecordingOutcomeAdapter(adapter_metadata(NuisanceRole.OUTCOME), []),
        treatment_adapter=RecordingTreatmentAdapter(
            adapter_metadata(NuisanceRole.TREATMENT), [], "extreme_by_feature"
        ),
    )

    result = estimator.analyze(
        dml_execution(fold_count=4, seed=27),
        dml_table(rows),
        provenance=provenance(),
    )

    assert result.status is DMLStatus.ABSTAINED
    assert result.point_estimate is None
    assert result.overlap is not None
    assert result.overlap.status.value == "severe"
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "dml.overlap.severe"


def test_dml_null_effect_fixture_has_finite_uncertainty_without_false_certainty() -> None:
    rows = tuple(
        {**row, "outcome": float(row["outcome"]) - 2.0 * int(row["treated"])}
        for row in _linear_rows()
    )
    result = DoubleMachineLearningEstimator().analyze(
        dml_execution(fold_count=4, seed=812),
        dml_table(rows),
        provenance=provenance(),
    )

    assert result.status is DMLStatus.COMPLETED
    assert result.point_estimate is not None
    assert abs(result.point_estimate) < 0.25
    assert result.test_result is not None
    assert result.test_result.standard_error > 0.0
    assert result.test_result.p_value > 0.05


def test_dml_nonlinear_nuisance_fixture_uses_supplied_owned_adapters() -> None:
    noise = (-0.3, 0.2, 0.4, -0.1)
    rows = tuple(
        {
            "account_id": f"nonlinear-{index:03d}",
            "treated": index % 2,
            "outcome": 1.5 * (index % 2) + ((index - 39.5) / 10.0) ** 2 + noise[index % 4],
            "prior_orders": (index - 39.5) / 10.0,
        }
        for index in range(80)
    )
    estimator = DoubleMachineLearningEstimator(
        outcome_adapter=RecordingOutcomeAdapter(
            adapter_metadata(NuisanceRole.OUTCOME), [], "square"
        ),
        treatment_adapter=RecordingTreatmentAdapter(adapter_metadata(NuisanceRole.TREATMENT), []),
    )

    result = estimator.analyze(
        dml_execution(fold_count=4, seed=31),
        dml_table(rows),
        provenance=provenance(),
    )

    assert result.status is DMLStatus.COMPLETED
    assert result.point_estimate is not None
    assert abs(result.point_estimate - 1.5) < 0.15
    assert {item.outcome_adapter.model_family for item in result.fold_fits} == {"test_constant"}
