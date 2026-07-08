from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

from packages.agents.tools.schemas import ToolSpec


class AbsoluteLiftInput(BaseModel):
    baseline_value: float
    treatment_value: float


class AbsoluteLiftOutput(BaseModel):
    absolute_lift: float


def calculate_absolute_lift(input_model: AbsoluteLiftInput) -> AbsoluteLiftOutput:
    return AbsoluteLiftOutput(
        absolute_lift=round(input_model.treatment_value - input_model.baseline_value, 6)
    )


class RelativeLiftInput(BaseModel):
    baseline_value: float
    treatment_value: float | None = None
    absolute_lift: float | None = None

    @model_validator(mode="after")
    def validate_input(self) -> RelativeLiftInput:
        if self.treatment_value is None and self.absolute_lift is None:
            raise ValueError("Either treatment_value or absolute_lift must be provided.")
        return self


class RelativeLiftOutput(BaseModel):
    relative_lift: float | None
    status: Literal["computed", "undefined_zero_baseline"]


def calculate_relative_lift(input_model: RelativeLiftInput) -> RelativeLiftOutput:
    absolute_lift = input_model.absolute_lift
    if absolute_lift is None and input_model.treatment_value is not None:
        absolute_lift = input_model.treatment_value - input_model.baseline_value
    if input_model.baseline_value == 0:
        return RelativeLiftOutput(
            relative_lift=None,
            status="undefined_zero_baseline",
        )
    return RelativeLiftOutput(
        relative_lift=round(float(absolute_lift) / input_model.baseline_value, 6),
        status="computed",
    )


ABSOLUTE_LIFT_TOOL = ToolSpec(
    name="calculate_absolute_lift",
    input_model=AbsoluteLiftInput,
    output_model=AbsoluteLiftOutput,
    handler=calculate_absolute_lift,
)

RELATIVE_LIFT_TOOL = ToolSpec(
    name="calculate_relative_lift",
    input_model=RelativeLiftInput,
    output_model=RelativeLiftOutput,
    handler=calculate_relative_lift,
)
