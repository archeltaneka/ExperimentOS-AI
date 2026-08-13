"""Cumulative sequential execution, integrity, and stopping tests."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    AnalysisTable,
    MetricType,
    RandomizedAnalysisMethod,
    SampleCounts,
)
from packages.experiments.analysis.randomized import ComputationStatus
from packages.experiments.analysis.randomized.sequential import (
    PlanIntegrityStatus,
    SequentialAnalysisHistory,
    SequentialAnalysisService,
    SequentialLookExecution,
    SequentialStoppingStatus,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    OutcomeDataBinding,
    ValidationPolicy,
)
from tests.analysis_contract_fixtures import source
from tests.sequential_fixtures import sequential_plan


def _binding() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit_id",
        randomization_unit_column="unit_id",
    )


def _table(treatment: Sequence[object], control: Sequence[object]) -> AnalysisTable:
    return AnalysisTable(
        columns=("unit_id", "arm", "outcome"),
        rows=tuple(
            (f"treatment-{index}", "treatment", value)
            for index, value in enumerate(treatment)
        )
        + tuple(
            (f"control-{index}", "control", value) for index, value in enumerate(control)
        ),
    )


def _look(
    plan,
    index: int,
    treatment: Sequence[object],
    control: Sequence[object],
    **updates: object,
) -> SequentialLookExecution:
    values: dict[str, object] = {
        "look_index": index,
        "information_time": plan.planned_looks[index - 1].information_time,
        "plan_fingerprint": plan.plan_fingerprint,
        "analysis_request": plan.analysis_request,
        "table": _table(treatment, control),
        "binding": _binding(),
        "executed_at": datetime(2026, 7, 2, tzinfo=UTC) + timedelta(days=index),
    }
    values.update(updates)
    return SequentialLookExecution(**values)  # type: ignore[arg-type]


def _service(*, minimum_per_arm: int = 10) -> SequentialAnalysisService:
    return SequentialAnalysisService(
        validation_policy=ValidationPolicy(
            minimum_total=minimum_per_arm * 2,
            minimum_per_arm=minimum_per_arm,
            weak_total=100,
            weak_per_arm=30,
        )
    )


def _codes(history) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in history.deviations)


def test_null_sequence_completes_without_efficacy_and_retains_audit_history() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    first = tuple(float(value) for value in range(15))
    final = tuple(float(value) for value in range(30))

    history = _service().analyze(
        plan,
        (
            _look(plan, 1, first, first),
            _look(plan, 2, final, final),
        ),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.CONTINUE
    assert history.plan_integrity is PlanIntegrityStatus.VALID
    assert tuple(item.look_index for item in history.looks) == (1, 2)
    assert history.current_look == history.looks[-1]
    assert history.alpha_summary.cumulative_alpha_spent == plan.total_alpha
    assert "NaN" not in history.model_dump_json()
    assert "Infinity" not in history.model_dump_json()
    assert "outcome_values" not in history.model_dump_json()
    assert {assumption.code for assumption in history.current_look.assumptions} >= {
        "sequential.plan_preregistered",
        "sequential.cumulative_eligible_data",
        "sequential.information_time_prespecified",
    }


def test_early_effect_crosses_registered_boundary_not_fixed_alpha_rule() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    control = tuple(float(value) for value in range(15))
    treatment = tuple(value + 6.0 for value in control)

    history = _service().analyze(
        plan,
        (_look(plan, 1, treatment, control),),
        provenance=(source(),),
    )

    look = history.current_look
    assert look is not None
    assert look.look_level_analysis is not None
    assert look.look_level_analysis.status is ComputationStatus.COMPLETED
    assert look.standardized_statistic is not None
    assert abs(look.standardized_statistic) >= look.sequential_boundary
    assert look.boundary_crossed is True
    assert history.current_status is SequentialStoppingStatus.EFFICACY


def test_ordinary_p_below_total_alpha_does_not_override_stricter_early_boundary() -> None:
    plan = sequential_plan(information_times=(0.25, 1.0))
    control = tuple(float(value) for value in range(15))
    treatment = tuple(value + 3.5 for value in control)

    history = _service().analyze(
        plan,
        (_look(plan, 1, treatment, control),),
        provenance=(source(),),
    )

    look = history.current_look
    assert look is not None and look.look_level_analysis is not None
    assert look.look_level_analysis.test_result is not None
    assert look.look_level_analysis.test_result.p_value < plan.total_alpha
    assert look.boundary_crossed is False
    assert history.current_status is SequentialStoppingStatus.CONTINUE


def test_zero_nominal_alpha_look_cannot_cross_from_underflowed_p_value() -> None:
    plan = sequential_plan(information_times=(0.0026, 1.0))
    control = tuple(float(value) for value in range(100))
    treatment = tuple(value + 1e150 for value in control)

    history = _service().analyze(
        plan,
        (_look(plan, 1, treatment, control),),
        provenance=(source(),),
    )

    look = history.current_look
    assert look is not None and look.look_level_analysis is not None
    assert look.look_level_analysis.test_result is not None
    assert look.look_level_analysis.test_result.p_value <= math.nextafter(0.0, 1.0)
    assert look.nominal_alpha == 0.0
    assert look.boundary_crossed is False
    assert history.current_status is SequentialStoppingStatus.CONTINUE


def test_underlying_randomized_abstention_produces_sequential_abstention() -> None:
    plan = sequential_plan(information_times=(1.0,))

    history = _service(minimum_per_arm=1).analyze(
        plan,
        (_look(plan, 1, (1.0,), (0.0,)),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.ABSTAIN
    assert history.plan_integrity is PlanIntegrityStatus.VALID
    assert history.current_look is not None
    assert history.current_look.look_level_analysis is not None
    assert history.current_look.look_level_analysis.status is ComputationStatus.ABSTAINED


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda plan, look: look.__class__(**{**look.__dict__, "look_index": 3}),
            "SEQUENTIAL_UNPLANNED_LOOK",
        ),
        (
            lambda plan, look: look.__class__(
                **{**look.__dict__, "information_time": 0.75}
            ),
            "SEQUENTIAL_INFORMATION_TIME_MISMATCH",
        ),
        (
            lambda plan, look: look.__class__(
                **{**look.__dict__, "plan_fingerprint": "0" * 64}
            ),
            "SEQUENTIAL_PLAN_FINGERPRINT_CHANGED",
        ),
        (
            lambda plan, look: look.__class__(
                **{
                    **look.__dict__,
                    "analysis_request": look.analysis_request.model_copy(
                        update={
                            "outcome": look.analysis_request.outcome.model_copy(
                                update={
                                    "metric": look.analysis_request.outcome.metric.model_copy(
                                        update={"metric_id": "changed-outcome"}
                                    )
                                }
                            )
                        }
                    ),
                }
            ),
            "SEQUENTIAL_OUTCOME_CHANGED",
        ),
        (
            lambda plan, look: look.__class__(
                **{
                    **look.__dict__,
                    "analysis_request": look.analysis_request.model_copy(
                        update={
                            "treatment": look.analysis_request.treatment.model_copy(
                                update={"label": "Changed treatment"}
                            )
                        }
                    ),
                }
            ),
            "SEQUENTIAL_TREATMENT_CHANGED",
        ),
        (
            lambda plan, look: look.__class__(
                **{
                    **look.__dict__,
                    "analysis_request": look.analysis_request.model_copy(
                        update={
                            "control": look.analysis_request.control.model_copy(
                                update={"label": "Changed control"}
                            )
                        }
                    ),
                }
            ),
            "SEQUENTIAL_CONTROL_CHANGED",
        ),
    ],
)
def test_single_look_plan_deviations_are_invalid(mutator, expected_code: str) -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    values = tuple(float(value) for value in range(15))
    execution = mutator(plan, _look(plan, 1, values, values))

    history = _service().analyze(plan, (execution,), provenance=(source(),))

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert history.plan_integrity is PlanIntegrityStatus.INVALID
    assert expected_code in _codes(history)
    assert history.alpha_summary.cumulative_alpha_spent == 0.0


def test_skipped_and_duplicate_looks_are_invalid_without_double_spending() -> None:
    plan = sequential_plan(information_times=(0.25, 0.5, 1.0))
    values = tuple(float(value) for value in range(15))

    skipped = _service().analyze(
        plan,
        (_look(plan, 2, values, values),),
        provenance=(source(),),
    )
    duplicate = _service().analyze(
        plan,
        (_look(plan, 1, values, values), _look(plan, 1, values, values)),
        provenance=(source(),),
    )

    assert "SEQUENTIAL_SKIPPED_LOOK" in _codes(skipped)
    assert "SEQUENTIAL_DUPLICATE_LOOK" in _codes(duplicate)
    assert (
        duplicate.alpha_summary.cumulative_alpha_spent
        == duplicate.boundaries[0].cumulative_alpha_spent
    )
    assert tuple(item.look_index for item in duplicate.looks) == (1,)


@pytest.mark.parametrize(
    ("second_table", "expected_code"),
    [
        (_table(tuple(range(14)), tuple(range(15))), "SEQUENTIAL_SAMPLE_COUNT_DECREASED"),
        (_table(tuple(range(14)), tuple(range(16))), "SEQUENTIAL_TREATMENT_COUNT_DECREASED"),
        (_table(tuple(range(16)), tuple(range(14))), "SEQUENTIAL_CONTROL_COUNT_DECREASED"),
    ],
)
def test_nonmonotonic_cumulative_counts_are_invalid(
    second_table: AnalysisTable,
    expected_code: str,
) -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    first_values = tuple(float(value) for value in range(15))
    first = _look(plan, 1, first_values, first_values)
    second = _look(plan, 2, tuple(range(16)), tuple(range(16)), table=second_table)

    history = _service().analyze(plan, (first, second), provenance=(source(),))

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert expected_code in _codes(history)


def test_declared_cumulative_sample_count_must_match_registered_look() -> None:
    plan = sequential_plan(
        information_times=(0.5, 1.0),
        expected_cumulative_sample_counts=(
            SampleCounts(total=40, treatment=20, control=20),
            SampleCounts(total=60, treatment=30, control=30),
        ),
    )
    values = tuple(float(value) for value in range(15))

    history = _service().analyze(
        plan,
        (_look(plan, 1, values, values),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert history.plan_integrity is PlanIntegrityStatus.INVALID
    assert "SEQUENTIAL_PLANNED_SAMPLE_COUNT_MISMATCH" in _codes(history)
    assert history.looks == ()


def test_treatment_assignment_switch_is_invalid() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    values = tuple(float(value) for value in range(15))
    first = _look(plan, 1, values, values)
    rows = list(_table(tuple(range(16)), tuple(range(16))).rows)
    rows[0] = ("treatment-0", "control", 0.0)
    switched = AnalysisTable(columns=("unit_id", "arm", "outcome"), rows=tuple(rows))
    second = _look(plan, 2, tuple(range(16)), tuple(range(16)), table=switched)

    history = _service().analyze(plan, (first, second), provenance=(source(),))

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_TREATMENT_ASSIGNMENT_CHANGED" in _codes(history)


def test_execution_before_registration_is_invalid() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    look = _look(
        plan,
        1,
        values,
        values,
        executed_at=datetime(2026, 6, 30, tzinfo=UTC),
    )

    history = _service().analyze(plan, (look,), provenance=(source(),))

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_PLAN_NOT_PREREGISTERED" in _codes(history)


def test_sequential_service_rejects_nonsequential_method_mutation() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    request = plan.analysis_request.model_copy(
        update={
            "study_design": plan.analysis_request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.FIXED_HORIZON_AB}
            )
        }
    )

    history = _service().analyze(
        plan,
        (_look(plan, 1, values, values, analysis_request=request),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_ESTIMATOR_CONFIGURATION_CHANGED" in _codes(history)


def test_execution_times_must_remain_monotone() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    first_values = tuple(float(value) for value in range(15))
    final_values = tuple(float(value) for value in range(30))
    first = _look(
        plan,
        1,
        first_values,
        first_values,
        executed_at=datetime(2026, 7, 10, tzinfo=UTC),
    )
    second = _look(
        plan,
        2,
        final_values,
        final_values,
        executed_at=datetime(2026, 7, 9, tzinfo=UTC),
    )

    history = _service().analyze(plan, (first, second), provenance=(source(),))

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_EXECUTION_TIME_DECREASED" in _codes(history)


def test_analysis_binding_cannot_change_between_cumulative_looks() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    first_values = tuple(float(value) for value in range(15))
    final_values = tuple(float(value) for value in range(30))
    changed_binding = _binding().model_copy(update={"observation_unit_column": "account_id"})
    changed_table = AnalysisTable(
        columns=("account_id", "arm", "outcome"),
        rows=tuple(
            (f"treatment-{index}", "treatment", value)
            for index, value in enumerate(final_values)
        )
        + tuple(
            (f"control-{index}", "control", value)
            for index, value in enumerate(final_values)
        ),
    )

    history = _service().analyze(
        plan,
        (
            _look(plan, 1, first_values, first_values),
            _look(
                plan,
                2,
                final_values,
                final_values,
                binding=changed_binding,
                table=changed_table,
            ),
        ),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_ANALYSIS_BINDING_CHANGED" in _codes(history)


def test_metric_type_change_has_explicit_plan_deviation_code() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    request = plan.analysis_request.model_copy(
        update={
            "outcome": plan.analysis_request.outcome.model_copy(
                update={
                    "metric": plan.analysis_request.outcome.metric.model_copy(
                        update={"metric_type": MetricType.BINARY}
                    )
                }
            )
        }
    )

    history = _service().analyze(
        plan,
        (_look(plan, 1, values, values, analysis_request=request),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_METRIC_TYPE_CHANGED" in _codes(history)


def test_previously_observed_outcome_cannot_change_in_cumulative_snapshot() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    first_values = tuple(float(value) for value in range(15))
    final_values = tuple(float(value) for value in range(30))
    first = _look(plan, 1, first_values, first_values)
    changed_rows = list(_table(final_values, final_values).rows)
    changed_rows[0] = ("treatment-0", "treatment", 999.0)
    changed = AnalysisTable(
        columns=("unit_id", "arm", "outcome"),
        rows=tuple(changed_rows),
    )

    history = _service().analyze(
        plan,
        (
            first,
            _look(plan, 2, final_values, final_values, table=changed),
        ),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_CUMULATIVE_OUTCOME_CHANGED" in _codes(history)


def test_in_memory_plan_mutation_is_detected_before_boundary_evaluation() -> None:
    registered = sequential_plan(information_times=(1.0,))
    mutated = registered.model_copy(update={"total_alpha": 0.10})
    values = tuple(float(value) for value in range(15))

    history = _service().analyze(
        mutated,
        (_look(registered, 1, values, values),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert history.plan_integrity is PlanIntegrityStatus.INVALID
    assert "SEQUENTIAL_PLAN_FINGERPRINT_CHANGED" in _codes(history)
    assert history.looks == ()
    assert history.alpha_summary.cumulative_alpha_spent == 0.0


def test_missing_treatment_arm_abstains_and_preserves_zero_count() -> None:
    plan = sequential_plan(information_times=(1.0,))
    control = tuple(float(value) for value in range(15))

    history = _service().analyze(
        plan,
        (_look(plan, 1, (), control),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.ABSTAIN
    assert history.current_look is not None
    assert history.current_look.treatment_count == 0
    assert history.current_look.control_count == 15


def test_zero_look_index_is_structured_as_unplanned() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    execution = _look(plan, 1, values, values)
    execution = execution.__class__(**{**execution.__dict__, "look_index": 0})

    history = _service().analyze(plan, (execution,), provenance=(source(),))

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_UNPLANNED_LOOK" in _codes(history)


def test_naive_execution_timestamp_is_structured_as_invalid() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    execution = _look(plan, 1, values, values, executed_at=datetime(2026, 7, 3))

    history = _service().analyze(plan, (execution,), provenance=(source(),))

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_EXECUTION_TIME_INVALID" in _codes(history)


def test_missing_bound_column_returns_structured_binding_deviation() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    bad_binding = _binding().model_copy(update={"observation_unit_column": "missing_unit"})

    history = _service().analyze(
        plan,
        (_look(plan, 1, values, values, binding=bad_binding),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_ANALYSIS_BINDING_INVALID" in _codes(history)


def test_execution_request_residual_configuration_drift_is_invalid() -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    changed_request = plan.analysis_request.model_copy(
        update={"sample_counts": SampleCounts(total=62, treatment=31, control=31)}
    )

    history = _service().analyze(
        plan,
        (_look(plan, 1, values, values, analysis_request=changed_request),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.INVALID
    assert "SEQUENTIAL_ESTIMATOR_CONFIGURATION_CHANGED" in _codes(history)


def _tamper_with_boundary_schedule(payload: dict[str, object]) -> None:
    boundaries = payload["boundaries"]
    looks = payload["looks"]
    current = payload["current_look"]
    assert isinstance(boundaries, list)
    assert isinstance(looks, list)
    assert isinstance(boundaries[0], dict)
    assert isinstance(looks[0], dict)
    assert isinstance(current, dict)
    boundaries[0]["critical_boundary"] = 0.1
    looks[0]["sequential_boundary"] = 0.1
    current["sequential_boundary"] = 0.1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["looks"][0].__setitem__("plan_id", "different-plan"),
        lambda payload: payload["alpha_summary"].__setitem__("evaluated_look_count", 0),
        lambda payload: payload["alpha_summary"].__setitem__(
            "cumulative_alpha_spent", 0.0
        ),
        lambda payload: payload.__setitem__("current_status", "efficacy"),
        _tamper_with_boundary_schedule,
    ],
)
def test_history_deserialization_rejects_contradictory_audit_state(mutate) -> None:
    plan = sequential_plan(information_times=(1.0,))
    values = tuple(float(value) for value in range(15))
    history = _service().analyze(
        plan,
        (_look(plan, 1, values, values),),
        provenance=(source(),),
    )
    payload = history.model_dump(mode="json")
    mutate(payload)

    with pytest.raises(ValidationError):
        SequentialAnalysisHistory.model_validate(payload)
