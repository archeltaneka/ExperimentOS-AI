"""Deterministic assignment for pre-declared heterogeneous-effect groups."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from ...base import ScalarValue
from ...validation.table import AnalysisTable
from ..dml.folds import canonical_observation_key
from .models import (
    CategoricalSubgroup,
    ContinuousBinSubgroup,
    HTEExecutionRequest,
    HTEModifierType,
)


class HTEAssignmentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AssignedObservation:
    observation_id: ScalarValue
    subgroup_id: str | None


@dataclass(frozen=True, slots=True)
class AssignedSubgroupSummary:
    subgroup_id: str
    label: str
    rule: str
    raw_count: int


@dataclass(frozen=True, slots=True)
class HTEAssignmentResult:
    assignments: tuple[AssignedObservation, ...]
    groups: tuple[AssignedSubgroupSummary, ...]
    unassigned_count: int
    fingerprint_sha256: str


def assign_subgroups(
    execution: HTEExecutionRequest,
    table: AnalysisTable,
) -> HTEAssignmentResult:
    """Apply one explicit modifier definition without inspecting outcomes."""
    binding = execution.binding
    required = (binding.observation_id_column, binding.modifier_column)
    if any(column not in table.columns for column in required):
        raise HTEAssignmentError(
            "hte.binding.missing_column",
            "Subgroup assignment requires the bound identity and modifier columns.",
        )
    identity_index = table.columns.index(binding.observation_id_column)
    modifier_index = table.columns.index(binding.modifier_column)
    assignments: list[AssignedObservation] = []
    seen: set[str] = set()
    for row in table.rows:
        observation_id = row[identity_index]
        try:
            key = canonical_observation_key(observation_id)  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise HTEAssignmentError(
                "hte.sample.invalid_observation_id",
                "Observation IDs must be finite supported scalar values.",
            ) from error
        if key in seen:
            raise HTEAssignmentError(
                "hte.sample.duplicate_observation_id",
                "Stable observation IDs must be unique by type and value.",
            )
        seen.add(key)
        value = row[modifier_index]
        subgroup_id = None if value is None else _assign_value(execution, value)
        assignments.append(
            AssignedObservation(
                observation_id=observation_id,  # type: ignore[arg-type]
                subgroup_id=subgroup_id,
            )
        )
    assignments.sort(key=lambda item: canonical_observation_key(item.observation_id))
    canonical_assignments = tuple(assignments)
    groups = tuple(
        AssignedSubgroupSummary(
            subgroup_id=subgroup.subgroup_id,
            label=subgroup.label,
            rule=subgroup_rule(execution, subgroup),
            raw_count=sum(
                item.subgroup_id == subgroup.subgroup_id for item in canonical_assignments
            ),
        )
        for subgroup in execution.modifier.subgroups
    )
    unassigned_count = sum(item.subgroup_id is None for item in canonical_assignments)
    return HTEAssignmentResult(
        assignments=canonical_assignments,
        groups=groups,
        unassigned_count=unassigned_count,
        fingerprint_sha256=_fingerprint(execution, canonical_assignments),
    )


def _assign_value(execution: HTEExecutionRequest, value: object) -> str:
    modifier = execution.modifier
    if modifier.modifier_type in {
        HTEModifierType.BINARY_CATEGORICAL,
        HTEModifierType.FINITE_CATEGORICAL,
    }:
        for subgroup in modifier.subgroups:
            assert isinstance(subgroup, CategoricalSubgroup)
            if type(value) is type(subgroup.value) and value == subgroup.value:
                return subgroup.subgroup_id
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTEAssignmentError(
                "hte.modifier.invalid_value",
                "Continuous effect modifiers require finite real values.",
            )
        converted = float(value)
        if not math.isfinite(converted):
            raise HTEAssignmentError(
                "hte.modifier.invalid_value",
                "Continuous effect modifiers require finite real values.",
            )
        for subgroup in modifier.subgroups:
            assert isinstance(subgroup, ContinuousBinSubgroup)
            lower_ok = subgroup.lower is None or converted >= subgroup.lower
            upper_ok = subgroup.upper is None or converted < subgroup.upper
            if lower_ok and upper_ok:
                return subgroup.subgroup_id
    raise HTEAssignmentError(
        "hte.modifier.unregistered_value",
        "Every non-missing modifier value must match a declared subgroup.",
    )


def subgroup_rule(
    execution: HTEExecutionRequest,
    subgroup: CategoricalSubgroup | ContinuousBinSubgroup,
) -> str:
    column = execution.binding.modifier_column
    if isinstance(subgroup, CategoricalSubgroup):
        rendered = json.dumps(subgroup.value, ensure_ascii=False, separators=(",", ":"))
        return f"{column} == {rendered}"
    lower = "-inf" if subgroup.lower is None else repr(subgroup.lower)
    upper = "inf" if subgroup.upper is None else repr(subgroup.upper)
    return f"{column} in [{lower}, {upper})"


def _fingerprint(
    execution: HTEExecutionRequest,
    assignments: tuple[AssignedObservation, ...],
) -> str:
    payload = {
        "analysis_version": execution.configuration.analysis_version,
        "modifier": execution.modifier.model_dump(mode="json"),
        "assignments": [
            {
                "identity_digest": hashlib.sha256(
                    canonical_observation_key(item.observation_id).encode("utf-8")
                ).hexdigest(),
                "subgroup_id": item.subgroup_id,
            }
            for item in assignments
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AssignedObservation",
    "AssignedSubgroupSummary",
    "HTEAssignmentError",
    "HTEAssignmentResult",
    "assign_subgroups",
    "subgroup_rule",
]
