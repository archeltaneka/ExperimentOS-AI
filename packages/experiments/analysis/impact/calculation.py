"""Shared-factor scenario formulas evaluated over deterministic input bounds."""

from __future__ import annotations

from typing import Literal

from .arithmetic import Bounds, add, multiply, subtract
from .inputs import BusinessImpactRequest, InputRange
from .source_models import SourceEffect
from .validation import Alignment, repetitions

Mode = Literal["central", "statistical", "business", "combined"]
MaybeBounds = Bounds | None


def product(a: MaybeBounds, b: MaybeBounds) -> MaybeBounds:
    return None if a is None or b is None else multiply(a, b)


def plus(a: MaybeBounds, b: MaybeBounds) -> MaybeBounds:
    return None if a is None or b is None else add(a, b)


def minus(a: MaybeBounds, b: MaybeBounds) -> MaybeBounds:
    return None if a is None or b is None else subtract(a, b)


def evaluate(
    source: SourceEffect, req: BusinessImpactRequest, alignment: Alignment, mode: Mode
) -> dict[str, MaybeBounds]:
    def value(v: InputRange) -> MaybeBounds:
        if mode in {"central", "statistical"}:
            return None if v.central is None else Bounds(v.central, v.central)
        return Bounds(v.lower, v.upper)

    assert source.point is not None and source.interval is not None
    e = (
        Bounds(source.interval.lower, source.interval.upper)
        if mode in {"statistical", "combined"}
        else Bounds(source.point, source.point)
    )
    a = product(value(req.population.value), value(req.exposure.value))
    a = product(a, Bounds(alignment.multiplier, alignment.multiplier))
    if req.exposure_conversion is not None:
        a = product(a, value(req.exposure_conversion.value))
    effect: MaybeBounds = e
    if source.effect_scale == "absolute_binary":
        scale = req.binding.outcome_unit.scale_to_base_unit
        effect = product(effect, Bounds(scale, scale))
    if req.baseline is not None:
        effect = product(effect, value(req.baseline.value))
    q = product(a, effect)
    outputs = {"exposed_population": a, "gross_incremental_outcome": q}
    if req.output == "outcome" or alignment.currency is None:
        return outputs
    if req.conversion is not None:
        sign = 1 if req.conversion.orientation == "added" else -1
        v = product(value(req.conversion.value), Bounds(sign, sign))
    else:
        scale = req.binding.outcome_unit.scale_to_base_unit
        v = Bounds(scale, scale)
    outputs["gross_monetary_impact"] = product(q, v)
    if req.output != "net" or req.costs is None:
        return outputs
    fixed: MaybeBounds = Bounds(0, 0)
    exposure_cost: MaybeBounds = Bounds(0, 0)
    event_cost: MaybeBounds = Bounds(0, 0)
    for cost in req.costs.items:
        c = value(cost.value)
        if cost.basis == "per_exposure":
            exposure_cost = plus(exposure_cost, c)
            amount = product(a, c)
        elif cost.basis == "per_incremental_outcome":
            event_cost = plus(event_cost, c)
            amount = product(q, c)
        else:
            times = repetitions(cost.horizon, req.horizon.basis) if cost.basis == "recurring" else 1
            assert times is not None
            amount = product(c, Bounds(times, times))
            fixed = plus(fixed, amount)
        outputs[f"costs.{cost.cost_id}"] = amount
    # Keep each shared exposure/effect once: tighter than independent subtraction.
    outputs["declared_costs"] = plus(
        fixed, product(a, plus(exposure_cost, product(effect, event_cost)))
    )
    outputs["net_monetary_impact"] = minus(
        product(a, minus(product(effect, minus(v, event_cost)), exposure_cost)), fixed
    )
    return outputs
