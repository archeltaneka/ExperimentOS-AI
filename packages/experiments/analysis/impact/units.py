"""Bounded entity and time semantics; display labels never determine arithmetic."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from typing import Literal

from ..base import ContractModel, PositiveInt
from ..metrics import MetricUnit

Entity = Literal["users", "sessions", "orders", "conversions", "events"]


class TimeBasis(ContractModel):
    """Positive calendar-period or day-duration count used for alignment."""

    count: PositiveInt
    unit: Literal["days", "months", "quarters", "years"]

    def end_from(self, start: datetime) -> datetime:
        if self.unit == "days":
            return start + timedelta(days=self.count)
        months = self.count * {"months": 1, "quarters": 3, "years": 12}[self.unit]
        year, month = divmod(start.year * 12 + start.month - 1 + months, 12)
        # Clamping is explicit calendar arithmetic, never a 30-day approximation.
        return start.replace(
            year=year, month=month + 1, day=min(start.day, monthrange(year, month + 1)[1])
        )


class OutcomeUnit(ContractModel):
    """Metric identity and optional event semantics for an aggregate outcome."""

    metric_id: str
    unit: MetricUnit
    event: Entity | None = None
