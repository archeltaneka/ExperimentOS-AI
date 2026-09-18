"""Cross-input dimensional, target, and horizon validation before computation."""

from __future__ import annotations

from dataclasses import dataclass

from ..metrics import MetricUnit, UnitDimension, ValueScale
from ..provenance import Diagnostic, DiagnosticOutcome, DiagnosticSeverity
from .inputs import BusinessImpactRequest
from .source_models import SourceEffect
from .units import TimeBasis


def diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(
        code=f"impact.{code}",
        message=message,
        severity=DiagnosticSeverity.ERROR,
        outcome=DiagnosticOutcome.FAILED,
    )


def same_unit(left: MetricUnit, right: MetricUnit) -> bool:
    """Compare semantic dimensions/scale; symbol is display text, not a conversion."""
    return left.model_dump(exclude={"symbol"}) == right.model_dump(exclude={"symbol"})


def count_unit() -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.COUNT,
        value_scale=ValueScale.RAW,
        symbol="events",
        scale_to_base_unit=1.0,
    )


def money_unit(currency: str) -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.CURRENCY,
        value_scale=ValueScale.RAW,
        symbol=currency,
        scale_to_base_unit=1.0,
        currency_code=currency,
    )


def repetitions(part: TimeBasis, whole: TimeBasis) -> int | None:
    """Only exact declared calendar subdivisions or day durations are compatible."""
    calendar = {"months": 1, "quarters": 3, "years": 12}
    if part.unit == "days" or whole.unit == "days":
        if part.unit != whole.unit:
            return None
        a, b = part.count, whole.count
    else:
        a, b = part.count * calendar[part.unit], whole.count * calendar[whole.unit]
    return b // a if b % a == 0 else None


@dataclass(frozen=True)
class Alignment:
    diagnostics: tuple[Diagnostic, ...]
    multiplier: int
    extrapolated: bool
    outcome_unit: MetricUnit
    currency: str | None


def validate(source: SourceEffect, request: BusinessImpactRequest) -> Alignment:
    errors: list[Diagnostic] = []
    p, b, h = request.population, request.binding, request.horizon

    def reject(code: str, message: str) -> None:
        errors.append(diagnostic(code, message))

    if source.population is None or source.population != p.definition:
        reject(
            "population_mismatch", "population.definition must match the source target population"
        )
    if source.target_kind != p.target_kind:
        reject("target_mismatch", "population.target_kind must match the source estimand target")
    if source.subgroup_id != p.subgroup_id or source.subgroup_rule != p.subgroup_rule:
        reject(
            "subgroup_mismatch", "population subgroup identity/rule must match the selected effect"
        )
    if source.analysis_unit is None or source.analysis_unit != b.analysis_unit:
        reject(
            "analysis_unit_mismatch", "binding.analysis_unit must match the source analysis unit"
        )
    metric = source.metric.metric if source.metric is not None else None
    if (
        metric is None
        or metric.metric_id != b.metric_id
        or not same_unit(metric.unit, b.outcome_unit)
    ):
        reject("metric_mismatch", "binding metric and outcome_unit must match the source metric")
    binary = source.effect_scale in {"absolute_binary", "relative_binary"}
    out_unit = count_unit() if binary else b.outcome_unit
    if (binary or b.outcome_unit.dimension is UnitDimension.COUNT) and b.event is None:
        reject("event_missing", "binary/count effects require an explicit event in binding")
    if not binary and b.event is not None and b.outcome_unit.dimension is not UnitDimension.COUNT:
        reject("event_incompatible", "only binary/count outcomes can declare an event entity")
    if source.effect_scale == "absolute_binary" and (
        b.outcome_unit.dimension is not UnitDimension.PROPORTION
    ):
        reject("effect_scale_mismatch", "absolute binary effects require a proportion unit")
    if source.effect_scale == "relative_binary":
        baseline = request.baseline
        if baseline is None:
            reject("baseline_missing", "relative binary effect requires explicit baseline")
        elif baseline.event != b.event or baseline.per_entity != b.entity:
            reject("baseline_unit_mismatch", "baseline event/entity must match the effect binding")
    elif request.baseline is not None:
        reject("unused_baseline", "baseline is only applicable to relative effects")

    if p.entity != b.entity:
        conversion = request.exposure_conversion
        if (
            conversion is None
            or conversion.from_entity != p.entity
            or conversion.to_entity != b.entity
        ):
            reject(
                "exposure_unit_mismatch",
                "population entity needs explicit compatible exposure conversion",
            )
    elif request.exposure_conversion is not None:
        reject("duplicate_exposure_conversion", "matching entities must not be converted again")
    if p.exposure_basis == "already_exposed":
        rate = request.exposure.value
        if (
            request.exposure.meaning != "already_exposed"
            or rate.lower != 1
            or rate.upper != 1
            or rate.central != 1
        ):
            reject(
                "double_exposure",
                "already-exposed population requires explicit already_exposed rate 1",
            )
    elif request.exposure.meaning == "already_exposed":
        reject(
            "exposure_basis_mismatch", "eligible population cannot claim already-exposed meaning"
        )

    multiplier = 1
    if p.time_basis != h.basis:
        rep = request.repetition
        expected = repetitions(p.time_basis, h.basis)
        if (
            p.basis != "per_period"
            or rep is None
            or expected is None
            or expected < 1
            or rep.source_basis != p.time_basis
            or rep.target_basis != h.basis
            or rep.repetitions != expected
        ):
            reject(
                "population_horizon_mismatch",
                "population period requires explicit compatible repetition",
            )
        else:
            multiplier = expected
    elif request.repetition is not None:
        reject(
            "duplicate_annualization",
            "population already covers horizon; repetition is not applicable",
        )

    for name in ("exposure", "baseline", "conversion", "exposure_conversion"):
        value = getattr(request, name)
        if value is not None and value.horizon != h.basis:
            reject("horizon_mismatch", f"{name}.horizon must equal the scenario horizon")
    observed = source.observed_period
    if b.observed_period is not None:
        if observed is not None and observed != b.observed_period:
            reject("observed_period_conflict", "binding observed period contradicts the source")
        elif observed is None:
            if b.evidence.status != "measured":
                reject(
                    "observed_period_unmeasured",
                    "missing source observed period needs measured evidence",
                )
            observed = b.observed_period
    extrapolated = observed is None or not (
        observed.start <= h.period.start and h.period.end <= observed.end
    )
    if observed is None:
        reject("observed_period_missing", "source observation period requires explicit evidence")
    if extrapolated:
        persistence = request.persistence
        if (
            persistence is None
            or persistence.period.start > h.period.start
            or persistence.period.end < h.period.end
        ):
            reject(
                "persistence_missing", "extrapolated horizon requires explicit effect persistence"
            )

    currency = b.outcome_unit.currency_code if not binary else None
    if request.conversion is not None:
        conv = request.conversion
        if currency is not None:
            reject(
                "double_monetization", "monetary source outcomes cannot be monetized a second time"
            )
        if (
            conv.metric_id != b.metric_id
            or not same_unit(conv.per_unit, out_unit)
            or conv.event != b.event
        ):
            reject(
                "conversion_unit_mismatch",
                "monetary conversion must match the incremental outcome unit",
            )
        currency = conv.currency
    if request.output != "outcome" and currency is None:
        reject(
            "conversion_missing", "monetary output requires explicit compatible monetary conversion"
        )
    if request.output == "net" and request.costs is None:
        reject("costs_missing", "net output requires an explicit complete declared-cost set")
    if request.costs is not None:
        if currency is None:
            reject("costs_without_money", "declared monetary costs require monetary gross impact")
        for cost in request.costs.items:
            if cost.currency != currency:
                reject(
                    "currency_mismatch",
                    f"costs.{cost.cost_id} currency differs from gross currency",
                )
            if cost.basis == "recurring":
                if repetitions(cost.horizon, h.basis) is None:
                    reject(
                        "cost_horizon_mismatch",
                        f"costs.{cost.cost_id} recurring basis is incompatible",
                    )
            elif cost.horizon != h.basis:
                reject("cost_horizon_mismatch", f"costs.{cost.cost_id} horizon must match scenario")
            if cost.basis == "per_exposure" and cost.entity != b.entity:
                reject(
                    "cost_unit_mismatch",
                    f"costs.{cost.cost_id} exposure entity must match effect exposure",
                )
            if cost.basis == "per_incremental_outcome" and (
                cost.metric_id != b.metric_id
                or cost.outcome_unit is None
                or not same_unit(cost.outcome_unit, out_unit)
                or cost.event != b.event
            ):
                reject(
                    "cost_unit_mismatch",
                    f"costs.{cost.cost_id} must match incremental outcome unit",
                )
    return Alignment(tuple(errors), multiplier, extrapolated, out_unit, currency)
