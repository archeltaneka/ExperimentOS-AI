"""Pre-registered sequential-plan contract and fingerprint tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import RandomizedAnalysisMethod
from packages.experiments.analysis.metrics import SampleCounts
from packages.experiments.analysis.randomized.sequential import (
    SequentialAnalysisPlan,
    SequentialBoundaryMethod,
    SequentialLookDefinition,
    SequentialSidedness,
)
from tests.analysis_contract_fixtures import randomized_request, source


def _plan(**updates: object) -> SequentialAnalysisPlan:
    request = randomized_request()
    request = request.model_copy(
        update={
            "study_design": request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.SEQUENTIAL_AB}
            )
        }
    )
    values: dict[str, object] = {
        "plan_id": "issue-94-primary",
        "experiment_id": "payment-ranking-2026-07",
        "analysis_request": request,
        "total_alpha": 0.05,
        "sidedness": SequentialSidedness.TWO_SIDED,
        "boundary_method": SequentialBoundaryMethod.OBRIEN_FLEMING_WEIGHTED_BONFERRONI,
        "planned_looks": tuple(
            SequentialLookDefinition(look_index=index, information_time=time)
            for index, time in enumerate((0.25, 0.5, 0.75, 1.0), start=1)
        ),
        "registration_marker": "registry-entry-94-v1",
        "registered_at": datetime(2026, 7, 1, tzinfo=UTC),
        "provenance": (source(),),
    }
    values.update(updates)
    return SequentialAnalysisPlan(**values)  # type: ignore[arg-type]


def test_valid_plan_is_frozen_canonical_and_fingerprinted() -> None:
    plan = _plan()

    assert tuple(look.look_index for look in plan.planned_looks) == (1, 2, 3, 4)
    assert len(plan.plan_fingerprint) == 64
    assert plan.plan_fingerprint == _plan().plan_fingerprint
    with pytest.raises(ValidationError):
        plan.total_alpha = 0.1  # type: ignore[misc]


@pytest.mark.parametrize(
    "times",
    [
        (0.5, 0.25, 1.0),
        (0.25, 0.25, 1.0),
        (0.0, 1.0),
        (-0.1, 1.0),
        (0.25, 1.1),
        (0.25, 0.9),
    ],
)
def test_plan_rejects_invalid_information_time_schedules(times: tuple[float, ...]) -> None:
    looks = tuple(
        {"look_index": index, "information_time": time}
        for index, time in enumerate(times, start=1)
    )

    with pytest.raises(ValidationError):
        _plan(planned_looks=looks)


def test_plan_rejects_noncanonical_look_indexes() -> None:
    looks = (
        SequentialLookDefinition(look_index=1, information_time=0.5),
        SequentialLookDefinition(look_index=3, information_time=1.0),
    )

    with pytest.raises(ValidationError, match="look indexes"):
        _plan(planned_looks=looks)


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.1])
def test_plan_rejects_invalid_total_alpha(alpha: float) -> None:
    with pytest.raises(ValidationError):
        _plan(total_alpha=alpha)


def test_plan_rejects_unsupported_literal_method_and_sidedness() -> None:
    payload = _plan().model_dump(mode="python")
    with pytest.raises(ValidationError):
        SequentialAnalysisPlan.model_validate({**payload, "sidedness": "one_sided"})
    with pytest.raises(ValidationError):
        SequentialAnalysisPlan.model_validate({**payload, "boundary_method": "pocock"})


def test_plan_requires_sequential_randomized_design() -> None:
    with pytest.raises(ValidationError, match="sequential_ab"):
        _plan(analysis_request=randomized_request())


@pytest.mark.parametrize(
    "mutation",
    ["alpha", "outcome", "treatment", "control", "information_times", "analysis_unit"],
)
def test_statistically_meaningful_mutation_changes_fingerprint(mutation: str) -> None:
    original = _plan()
    request = original.analysis_request
    updates: dict[str, object] = {}
    if mutation == "alpha":
        updates["total_alpha"] = 0.025
    elif mutation == "outcome":
        updates["analysis_request"] = request.model_copy(
            update={
                "outcome": request.outcome.model_copy(
                    update={
                        "metric": request.outcome.metric.model_copy(
                            update={"metric_id": "changed-primary"}
                        )
                    }
                )
            }
        )
    elif mutation == "treatment":
        updates["analysis_request"] = request.model_copy(
            update={
                "treatment": request.treatment.model_copy(update={"label": "Changed treatment"})
            }
        )
    elif mutation == "control":
        updates["analysis_request"] = request.model_copy(
            update={"control": request.control.model_copy(update={"label": "Changed control"})}
        )
    elif mutation == "information_times":
        updates["planned_looks"] = (
            SequentialLookDefinition(look_index=1, information_time=0.5),
            SequentialLookDefinition(look_index=2, information_time=1.0),
        )
    else:
        updates["analysis_request"] = request.model_copy(
            update={
                "unit_of_analysis": request.unit_of_analysis.model_copy(
                    update={"unit_id": "changed-unit"}
                )
            }
        )

    assert _plan(**updates).plan_fingerprint != original.plan_fingerprint


def test_registration_and_provenance_order_do_not_change_statistical_fingerprint() -> None:
    first = _plan()
    second_source = source().model_copy(update={"source_id": "another-source"})
    equivalent = _plan(
        plan_id="presentation-id",
        registration_marker="another-marker",
        registered_at=datetime(2026, 7, 2, tzinfo=UTC),
        provenance=(second_source, source()),
    )

    assert equivalent.plan_fingerprint == first.plan_fingerprint


def test_explicit_wrong_fingerprint_is_rejected() -> None:
    with pytest.raises(ValidationError, match="fingerprint"):
        _plan(plan_fingerprint="0" * 64)


def test_planned_cumulative_counts_must_be_all_or_none_and_monotone() -> None:
    partial = (
        SequentialLookDefinition(
            look_index=1,
            information_time=0.5,
            expected_cumulative_sample_counts=SampleCounts(total=20, treatment=10, control=10),
        ),
        SequentialLookDefinition(look_index=2, information_time=1.0),
    )
    decreasing = (
        SequentialLookDefinition(
            look_index=1,
            information_time=0.5,
            expected_cumulative_sample_counts=SampleCounts(total=20, treatment=10, control=10),
        ),
        SequentialLookDefinition(
            look_index=2,
            information_time=1.0,
            expected_cumulative_sample_counts=SampleCounts(total=20, treatment=9, control=11),
        ),
    )

    with pytest.raises(ValidationError, match="every look or none"):
        _plan(planned_looks=partial)
    with pytest.raises(ValidationError, match="increase monotonically"):
        _plan(planned_looks=decreasing)


def test_final_information_time_within_tolerance_is_accepted() -> None:
    plan = _plan(
        planned_looks=(
            SequentialLookDefinition(look_index=1, information_time=0.5),
            SequentialLookDefinition(look_index=2, information_time=0.9999999999995),
        )
    )

    assert plan.planned_looks[-1].information_time == 0.9999999999995
