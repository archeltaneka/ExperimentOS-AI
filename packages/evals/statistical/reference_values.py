"""Independent reference values shared by native and workflow evaluation."""

import math
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictBool,
    StrictInt,
    model_validator,
)

type NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
type ExpectedScalar = StrictBool | StrictInt | FiniteFloat | NonEmptyStr | None


class StatisticalCaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class StatisticalTolerance(StatisticalCaseModel):
    """One independently justified absolute/relative tolerance."""

    absolute: Annotated[FiniteFloat, Field(ge=0)]
    relative: Annotated[FiniteFloat, Field(ge=0)] = 0.0
    rationale: NonEmptyStr
    provenance: NonEmptyStr

    def accepts(self, actual: float, reference: float) -> bool:
        return (
            math.isfinite(actual)
            and math.isfinite(reference)
            and abs(actual - reference) <= self.absolute + self.relative * abs(reference)
        )


class StatisticalExpectedValue(StatisticalCaseModel):
    path: NonEmptyStr
    value: ExpectedScalar
    tolerance: StatisticalTolerance | None = None

    @model_validator(mode="after")
    def require_float_tolerance(self) -> Self:
        if isinstance(self.value, float) and self.tolerance is None:
            raise ValueError("floating expected values require a tolerance")
        return self
