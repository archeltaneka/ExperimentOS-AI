"""Stable-ID deterministic stratified fold planning for DML."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Literal

from ...base import ScalarValue
from .models import DMLConfig, DMLFoldAssignment, DMLFoldPlan, DMLFoldSummary

_SPLIT_METHOD: Literal["deterministic_stratified_sha256_round_robin"] = (
    "deterministic_stratified_sha256_round_robin"
)
_SPLIT_VERSION: Literal["dml-stratified-sha256-v1"] = "dml-stratified-sha256-v1"


@dataclass(frozen=True, slots=True)
class FoldObservation:
    """Only the stable identity and treatment stratum needed for fold planning."""

    observation_id: ScalarValue
    treated: bool


def build_fold_plan(
    observations: tuple[FoldObservation, ...],
    config: DMLConfig,
) -> DMLFoldPlan:
    """Build a row-order-invariant stratified plan without mutable RNG state."""
    if not observations:
        raise ValueError("fold planning requires retained observations")
    identity_keys = tuple(canonical_observation_key(item.observation_id) for item in observations)
    if len(identity_keys) != len(set(identity_keys)):
        raise ValueError("observation IDs must be unique by type and value")

    by_treatment = {
        treated: tuple(item for item in observations if item.treated is treated)
        for treated in (False, True)
    }
    if any(len(items) < config.fold_count for items in by_treatment.values()):
        raise ValueError("each scoring fold requires both treatment classes")

    assigned: list[tuple[FoldObservation, int]] = []
    for treated, items in by_treatment.items():
        ranked = sorted(
            items,
            key=lambda item: (
                _rank_digest(item.observation_id, treated=treated, config=config),
                _identity_digest(item.observation_id),
            ),
        )
        assigned.extend((item, index % config.fold_count) for index, item in enumerate(ranked))

    assigned.sort(key=lambda pair: canonical_observation_key(pair[0].observation_id))
    total_treated = sum(item.treated for item, _fold in assigned)
    summaries: list[DMLFoldSummary] = []
    for fold_index in range(config.fold_count):
        scored = tuple(item for item, fold in assigned if fold == fold_index)
        score_treated = sum(item.treated for item in scored)
        score_control = len(scored) - score_treated
        train_count = len(assigned) - len(scored)
        train_treated = total_treated - score_treated
        train_control = train_count - train_treated
        if len(scored) < config.minimum_scoring_rows:
            raise ValueError("scoring fold is smaller than the configured minimum")
        if train_count < config.minimum_training_rows:
            raise ValueError("training fold is smaller than the configured minimum")
        if not score_treated or not score_control:
            raise ValueError("each scoring fold requires both treatment classes")
        if not train_treated or not train_control:
            raise ValueError("each training fold requires both treatment classes")
        summaries.append(
            DMLFoldSummary(
                fold_index=fold_index,
                score_count=len(scored),
                score_treated_count=score_treated,
                score_control_count=score_control,
                train_count=train_count,
                train_treated_count=train_treated,
                train_control_count=train_control,
            )
        )

    assignments = tuple(
        DMLFoldAssignment(observation_id=item.observation_id, fold_index=fold)
        for item, fold in assigned
    )
    fingerprint = _fingerprint(
        assignments,
        fold_count=config.fold_count,
        random_seed=config.random_seed,
    )
    return DMLFoldPlan(
        fold_count=config.fold_count,
        random_seed=config.random_seed,
        split_method=_SPLIT_METHOD,
        split_version=_SPLIT_VERSION,
        stratification_policy="binary_treatment",
        assignments=assignments,
        summaries=tuple(summaries),
        fingerprint_sha256=fingerprint,
    )


def canonical_observation_key(value: ScalarValue) -> str:
    """Return a stable type-aware key for an owned scalar observation identity."""
    if isinstance(value, bool):
        kind = "bool"
    elif isinstance(value, int):
        kind = "int"
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("observation IDs must be finite")
        kind = "float"
    elif isinstance(value, str):
        kind = "str"
    else:
        raise ValueError("observation IDs must be supported scalar values")
    return json.dumps(
        {"type": kind, "value": value},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def validate_fold_plan_integrity(
    observations: tuple[FoldObservation, ...],
    plan: DMLFoldPlan,
) -> None:
    """Reject mutation of assignments, summaries, or their recorded fingerprint."""
    observation_by_key = {
        canonical_observation_key(item.observation_id): item for item in observations
    }
    assignment_by_key = {
        canonical_observation_key(item.observation_id): item for item in plan.assignments
    }
    if (
        len(observation_by_key) != len(observations)
        or len(assignment_by_key) != len(plan.assignments)
        or set(observation_by_key) != set(assignment_by_key)
        or any(item.fold_index >= plan.fold_count for item in plan.assignments)
    ):
        raise ValueError("fold assignments must exactly cover retained observations")
    canonical_assignments = tuple(
        sorted(
            plan.assignments,
            key=lambda item: canonical_observation_key(item.observation_id),
        )
    )
    if plan.assignments != canonical_assignments:
        raise ValueError("fold assignments must retain canonical identity ordering")
    expected_fingerprint = _fingerprint(
        canonical_assignments,
        fold_count=plan.fold_count,
        random_seed=plan.random_seed,
    )
    if plan.fingerprint_sha256 != expected_fingerprint:
        raise ValueError("fold fingerprint does not match assignments and split configuration")

    total_treated = sum(item.treated for item in observations)
    expected_summaries: list[DMLFoldSummary] = []
    for fold_index in range(plan.fold_count):
        scored = tuple(
            observation_by_key[key]
            for key, assignment in assignment_by_key.items()
            if assignment.fold_index == fold_index
        )
        score_treated = sum(item.treated for item in scored)
        score_control = len(scored) - score_treated
        train_count = len(observations) - len(scored)
        train_treated = total_treated - score_treated
        expected_summaries.append(
            DMLFoldSummary(
                fold_index=fold_index,
                score_count=len(scored),
                score_treated_count=score_treated,
                score_control_count=score_control,
                train_count=train_count,
                train_treated_count=train_treated,
                train_control_count=train_count - train_treated,
            )
        )
    if plan.summaries != tuple(expected_summaries):
        raise ValueError("fold summaries do not match retained observations and assignments")


def _identity_digest(value: ScalarValue) -> str:
    return hashlib.sha256(canonical_observation_key(value).encode("utf-8")).hexdigest()


def _rank_digest(value: ScalarValue, *, treated: bool, config: DMLConfig) -> str:
    payload = {
        "id_digest": _identity_digest(value),
        "seed": config.random_seed,
        "split_version": _SPLIT_VERSION,
        "stratum": "treated" if treated else "control",
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fingerprint(
    assignments: tuple[DMLFoldAssignment, ...],
    *,
    fold_count: int,
    random_seed: int,
) -> str:
    payload = {
        "assignments": tuple(
            {
                "fold_index": item.fold_index,
                "id_digest": _identity_digest(item.observation_id),
            }
            for item in assignments
        ),
        "fold_count": fold_count,
        "random_seed": random_seed,
        "split_method": _SPLIT_METHOD,
        "split_version": _SPLIT_VERSION,
        "stratification_policy": "binary_treatment",
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = [
    "FoldObservation",
    "build_fold_plan",
    "canonical_observation_key",
    "validate_fold_plan_integrity",
]
