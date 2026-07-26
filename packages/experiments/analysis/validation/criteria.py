"""Shared typed evaluation for population and segment selection criteria."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..populations import CriterionOperator, SelectionCriterion


def evaluate_criteria(
    values: Mapping[str, object],
    criteria: Sequence[SelectionCriterion],
) -> bool:
    """Return whether one immutable row view satisfies every declared criterion."""
    return all(
        _evaluate_criterion(values[criterion.attribute], criterion) for criterion in criteria
    )


def _evaluate_criterion(value: object, criterion: SelectionCriterion) -> bool:
    expected = criterion.value
    operator = criterion.operator

    if operator is CriterionOperator.EQUAL:
        return _typed_equal(value, expected)
    if operator is CriterionOperator.NOT_EQUAL:
        return not _typed_equal(value, expected)

    if operator in {CriterionOperator.IN, CriterionOperator.NOT_IN}:
        if not isinstance(expected, tuple):
            raise RuntimeError("validated set criterion is missing tuple values")
        contained = any(_typed_equal(value, candidate) for candidate in expected)
        return contained if operator is CriterionOperator.IN else not contained

    if isinstance(expected, tuple):
        raise RuntimeError("validated scalar criterion contains tuple values")
    if type(value) is not type(expected):
        return False

    if operator is CriterionOperator.GREATER_THAN:
        return value > expected  # type: ignore[operator]
    if operator is CriterionOperator.GREATER_THAN_OR_EQUAL:
        return value >= expected  # type: ignore[operator]
    if operator is CriterionOperator.LESS_THAN:
        return value < expected  # type: ignore[operator]
    if operator is CriterionOperator.LESS_THAN_OR_EQUAL:
        return value <= expected  # type: ignore[operator]
    raise RuntimeError(f"unsupported validated criterion operator: {operator.value}")


def _typed_equal(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right
