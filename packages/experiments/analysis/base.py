from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
)

SCHEMA_VERSION: Literal["1"] = "1"
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$", strict=True)]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
OpenProbability = Annotated[float, Field(strict=True, gt=0, lt=1, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
type ScalarValue = StrictBool | StrictInt | StrictFloat | NonEmptyStr


class AnalysisStatus(StrEnum):
    ELIGIBLE = "eligible"
    ELIGIBLE_WITH_WARNINGS = "eligible_with_warnings"
    INELIGIBLE = "ineligible"
    NEEDS_MORE_DATA = "needs_more_data"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    ABSTAINED = "abstained"
    FAILED = "failed"


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
