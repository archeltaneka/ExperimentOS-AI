"""Deterministic null, early, late, and no-stop sequential references."""

from __future__ import annotations

from packages.experiments.analysis import MetricType, RandomizedAnalysisMethod
from packages.experiments.analysis.randomized import (
    AlternativeHypothesis,
    RandomizedAnalysisExecutionRequest,
    RandomizedAnalysisService,
)
from packages.experiments.analysis.randomized.sequential import SequentialStoppingStatus
from tests.analysis_contract_fixtures import source
from tests.sequential_fixtures import sequential_plan
from tests.test_sequential_service import _binding, _look, _service, _table


def test_late_effect_does_not_cross_early_but_crosses_final_boundary() -> None:
    plan = sequential_plan(information_times=(0.25, 0.5, 1.0))
    control_1 = tuple(float(value) for value in range(15))
    treatment_1 = control_1
    control_2 = tuple(float(value) for value in range(20))
    treatment_2 = treatment_1 + tuple(float(value + 4) for value in range(15, 20))
    control_3 = tuple(float(value) for value in range(30))
    treatment_3 = treatment_2 + tuple(float(value + 21) for value in range(20, 30))

    history = _service().analyze(
        plan,
        (
            _look(plan, 1, treatment_1, control_1),
            _look(plan, 2, treatment_2, control_2),
            _look(plan, 3, treatment_3, control_3),
        ),
        provenance=(source(),),
    )

    assert tuple(look.boundary_crossed for look in history.looks) == (False, False, True)
    assert history.current_status is SequentialStoppingStatus.EFFICACY


def test_weak_effect_finishes_with_no_rejection_not_no_effect() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0))
    control_1 = tuple(float(value) for value in range(15))
    treatment_1 = tuple(value + 0.25 for value in control_1)
    control_2 = tuple(float(value) for value in range(30))
    treatment_2 = tuple(value + 0.25 for value in control_2)

    history = _service().analyze(
        plan,
        (
            _look(plan, 1, treatment_1, control_1),
            _look(plan, 2, treatment_2, control_2),
        ),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.CONTINUE
    assert all(not look.boundary_crossed for look in history.looks)
    assert history.current_look is not None
    assert history.current_look.look_level_analysis is not None
    assert history.current_look.look_level_analysis.point_effect is not None
    assert history.current_look.look_level_analysis.point_effect.absolute_effect.value == 0.25


def test_binary_early_effect_uses_existing_two_proportion_estimator() -> None:
    plan = sequential_plan(information_times=(0.5, 1.0), metric_type=MetricType.BINARY)
    treatment = (1,) * 25 + (0,) * 5
    control = (1,) * 10 + (0,) * 20

    history = _service().analyze(
        plan,
        (_look(plan, 1, treatment, control),),
        provenance=(source(),),
    )

    assert history.current_status is SequentialStoppingStatus.EFFICACY
    assert history.current_look is not None
    assert history.current_look.estimator_method is not None
    assert history.current_look.estimator_method.value == "two_proportion_z"


def test_look_level_effect_and_uncertainty_equal_existing_randomized_analyzer() -> None:
    plan = sequential_plan(information_times=(1.0,))
    treatment = tuple(float(value + 1.5) for value in range(15))
    control = tuple(float(value) for value in range(15))
    table = _table(treatment, control)

    sequential = _service().analyze(
        plan,
        (_look(plan, 1, treatment, control),),
        provenance=(source(),),
    )
    fixed_request = plan.analysis_request.model_copy(
        update={
            "study_design": plan.analysis_request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.FIXED_HORIZON_AB}
            )
        }
    )
    fixed = RandomizedAnalysisService(validation_policy=_service()._policy).analyze(
        RandomizedAnalysisExecutionRequest(
            request_id="independent-fixed-comparison",
            analysis_request=fixed_request,
            alternative=AlternativeHypothesis.TWO_SIDED,
        ),
        table,
        _binding(),
        provenance=(source(),),
    )

    assert sequential.current_look is not None
    actual = sequential.current_look.look_level_analysis
    assert actual is not None
    assert actual.point_effect == fixed.point_effect
    assert actual.test_result == fixed.test_result
