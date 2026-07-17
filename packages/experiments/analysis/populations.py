"""Typed selection criteria, populations, segments, and their scalar aliases."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from .base import ContractModel, NonEmptyStr, ScalarValue


class CriterionOperator(StrEnum):
    """Comparison operators supported by structured selection criteria."""

    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"


class SelectionCriterion(ContractModel):
    """A typed predicate over one population or segment attribute."""

    attribute: NonEmptyStr
    operator: CriterionOperator
    value: ScalarValue | tuple[ScalarValue, ...]

    @model_validator(mode="after")
    def validate_value_shape(self) -> Self:
        set_operators = {CriterionOperator.IN, CriterionOperator.NOT_IN}
        if self.operator in set_operators:
            if not isinstance(self.value, tuple):
                raise ValueError("in and not_in operators require a tuple scalar value")
            if not self.value:
                raise ValueError("in and not_in operators require a non-empty tuple value")
        elif isinstance(self.value, tuple):
            raise ValueError("scalar operators do not accept a tuple value")
        return self


class PopulationDefinition(ContractModel):
    """A named analysis population and its structured selection criteria."""

    population_id: NonEmptyStr
    label: NonEmptyStr
    criteria: tuple[SelectionCriterion, ...]


class SegmentDefinition(ContractModel):
    """A named population subset and its structured selection criteria."""

    segment_id: NonEmptyStr
    label: NonEmptyStr
    criteria: tuple[SelectionCriterion, ...]
