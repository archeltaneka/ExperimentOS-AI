"""Supported estimand vocabulary and conditional-estimand contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from .base import ContractModel
from .populations import SegmentDefinition


class EstimandKind(StrEnum):
    """Stable identifiers for the effect quantities an analysis may target."""

    DIFFERENCE_IN_MEANS = "difference_in_means"
    DIFFERENCE_IN_PROPORTIONS = "difference_in_proportions"
    ABSOLUTE_LIFT = "absolute_lift"
    RELATIVE_LIFT = "relative_lift"
    AVERAGE_TREATMENT_EFFECT = "average_treatment_effect"
    AVERAGE_TREATMENT_EFFECT_ON_TREATED = "average_treatment_effect_on_treated"
    CONDITIONAL_AVERAGE_TREATMENT_EFFECT = "conditional_average_treatment_effect"
    INTENTION_TO_TREAT = "intention_to_treat"


class EstimandDefinition(ContractModel):
    """An estimand kind with optional conditioning used only for CATE."""

    kind: EstimandKind
    conditioning_segment: SegmentDefinition | None = None

    @model_validator(mode="after")
    def validate_conditioning_segment(self) -> Self:
        is_cate = self.kind is EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT
        if is_cate and self.conditioning_segment is None:
            raise ValueError("CATE requires a conditioning segment")
        if not is_cate and self.conditioning_segment is not None:
            raise ValueError("conditioning_segment is only valid for CATE")
        return self
