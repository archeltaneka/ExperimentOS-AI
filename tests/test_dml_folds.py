"""Deterministic, stratified DML fold-plan contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.causal.dml.folds import (
    FoldObservation,
    build_fold_plan,
)
from packages.experiments.analysis.causal.dml.models import DMLConfig, DMLFoldPlan


def observations() -> tuple[FoldObservation, ...]:
    return (
        FoldObservation(observation_id="c-0", treated=False),
        FoldObservation(observation_id="c-1", treated=False),
        FoldObservation(observation_id="c-2", treated=False),
        FoldObservation(observation_id="c-3", treated=False),
        FoldObservation(observation_id="t-0", treated=True),
        FoldObservation(observation_id="t-1", treated=True),
        FoldObservation(observation_id="t-2", treated=True),
        FoldObservation(observation_id="t-3", treated=True),
    )


def config(*, seed: int = 17) -> DMLConfig:
    return DMLConfig(fold_count=2, random_seed=seed)


def assignment_map(plan: DMLFoldPlan) -> dict[object, int]:
    return {item.observation_id: item.fold_index for item in plan.assignments}


def test_fold_assignment_matches_hand_checked_seeded_reference() -> None:
    plan = build_fold_plan(observations(), config())

    assert assignment_map(plan) == {
        "c-0": 0,
        "c-1": 1,
        "c-2": 0,
        "c-3": 1,
        "t-0": 1,
        "t-1": 0,
        "t-2": 1,
        "t-3": 0,
    }
    assert plan.split_method == "deterministic_stratified_sha256_round_robin"
    assert plan.split_version == "dml-stratified-sha256-v1"
    assert plan.stratification_policy == "binary_treatment"


def test_fold_assignment_is_row_order_invariant_and_repeatable() -> None:
    first = build_fold_plan(observations(), config())
    repeated = build_fold_plan(observations(), config())
    reversed_rows = build_fold_plan(tuple(reversed(observations())), config())

    assert first == repeated
    assert first == reversed_rows
    assert len(first.fingerprint_sha256) == 64


def test_different_seed_changes_fold_fingerprint() -> None:
    first = build_fold_plan(observations(), config(seed=17))
    second = build_fold_plan(observations(), config(seed=18))

    assert first.fingerprint_sha256 != second.fingerprint_sha256


def test_every_fold_is_stratified_and_train_score_sets_are_exact_complements() -> None:
    plan = build_fold_plan(observations(), config())
    all_ids = {item.observation_id for item in observations()}

    assert len(plan.summaries) == 2
    for summary in plan.summaries:
        score_ids = {
            assignment.observation_id
            for assignment in plan.assignments
            if assignment.fold_index == summary.fold_index
        }
        train_ids = all_ids - score_ids

        assert score_ids.isdisjoint(train_ids)
        assert score_ids | train_ids == all_ids
        assert summary.score_count == 4
        assert summary.score_treated_count == 2
        assert summary.score_control_count == 2
        assert summary.train_count == 4
        assert summary.train_treated_count == 2
        assert summary.train_control_count == 2


def test_fold_configuration_requires_at_least_two_folds() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 2"):
        DMLConfig(fold_count=1, random_seed=17)


def test_fold_plan_rejects_duplicate_stable_observation_ids() -> None:
    duplicate = (*observations(), FoldObservation(observation_id="c-0", treated=False))

    with pytest.raises(ValueError, match="observation IDs must be unique"):
        build_fold_plan(duplicate, config())


def test_fold_plan_rejects_configuration_without_each_class_in_each_fold() -> None:
    inadequate = (
        FoldObservation(observation_id="c-0", treated=False),
        FoldObservation(observation_id="t-0", treated=True),
        FoldObservation(observation_id="t-1", treated=True),
        FoldObservation(observation_id="t-2", treated=True),
    )

    with pytest.raises(ValueError, match="each scoring fold requires both treatment classes"):
        build_fold_plan(inadequate, config())
