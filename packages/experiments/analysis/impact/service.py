"""Offline deterministic composition of owned causal evidence and sourced inputs."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from ..base import AnalysisStatus
from ..provenance import AnalysisWarning, Diagnostic
from ..results import AbstentionReason
from ..uncertainty import ConfidenceInterval, CredibleInterval
from .calculation import Mode, evaluate
from .inputs import BusinessImpactRequest, input_evidence
from .results import (
    BusinessImpactResult,
    CostBreakdown,
    Derivation,
    DerivedQuantity,
    ScenarioBand,
)
from .source_models import SourceEffect
from .sources import adapt_source
from .validation import count_unit, diagnostic, money_unit, validate


class BusinessImpactService:
    """Compute a scenario or return an auditable refusal with no numeric impact."""

    def analyze(
        self, source: object, request: BusinessImpactRequest | Mapping[str, object]
    ) -> BusinessImpactResult:
        parsed: BusinessImpactRequest | None = None
        invalid: list[Diagnostic] = []
        try:
            parsed = BusinessImpactRequest.model_validate(
                request.model_dump() if isinstance(request, BusinessImpactRequest) else request
            )
        except ValidationError as exc:
            # Never echo rejected values, arbitrary exception text, or source documents.
            invalid = [
                diagnostic(
                    "invalid_input",
                    "Invalid or missing input: " + ".".join(str(x) for x in e["loc"]),
                )
                for e in exc.errors(include_input=False)
            ]
        effect = adapt_source(source, subgroup_id=parsed.subgroup_id if parsed else None)
        errors = tuple(invalid) + effect.blocking_diagnostics
        if errors or parsed is None:
            return _abstain(
                effect, parsed, errors or (diagnostic("invalid_input", "Invalid request"),)
            )
        alignment = validate(effect, parsed)
        if alignment.diagnostics:
            return _abstain(effect, parsed, alignment.diagnostics)
        if effect.point is None or effect.interval is None:
            return _abstain(
                effect, parsed, (diagnostic("uncertainty_missing", "Source inference missing"),)
            )
        try:
            modes: tuple[Mode, ...] = ("central", "statistical", "business", "combined")
            values = {mode: evaluate(effect, parsed, alignment, mode) for mode in modes}
            quantities: dict[str, DerivedQuantity] = {}
            for field, bounds in values["combined"].items():
                assert bounds is not None
                business = values["business"][field]
                assert business is not None
                central, statistical = values["central"][field], values["statistical"][field]
                dependent = field not in {"exposed_population", "declared_costs"}
                if field == "declared_costs":
                    dependent = parsed.costs is not None and any(
                        c.basis == "per_incremental_outcome" for c in parsed.costs.items
                    )
                if field.startswith("costs."):
                    assert parsed.costs is not None
                    dependent = any(
                        c.cost_id == field.removeprefix("costs.")
                        and c.basis == "per_incremental_outcome"
                        for c in parsed.costs.items
                    )
                if not dependent:
                    statistical = None
                interval: ConfidenceInterval | CredibleInterval | None = None
                if statistical is not None:
                    if isinstance(effect.interval, ConfidenceInterval):
                        interval = ConfidenceInterval(
                            lower=statistical.lower,
                            upper=statistical.upper,
                            confidence_level=effect.interval.confidence_level,
                        )
                    else:
                        interval = CredibleInterval(
                            lower=statistical.lower,
                            upper=statistical.upper,
                            credible_level=effect.interval.credible_level,
                        )
                entity = None
                if field == "exposed_population":
                    unit, entity = count_unit(), parsed.binding.entity
                elif field == "gross_incremental_outcome":
                    unit, entity = alignment.outcome_unit, parsed.binding.event
                else:
                    assert alignment.currency is not None
                    unit = money_unit(alignment.currency)
                quantities[field] = DerivedQuantity(
                    central=central.lower if central else None,
                    unit=unit,
                    entity=entity,
                    horizon=parsed.horizon.basis,
                    statistical=interval,
                    statistical_unavailable_reason=(
                        (
                            "Quantity is independent of treatment-effect uncertainty."
                            if not dependent
                            else "Business inputs have no explicitly supplied central values."
                        )
                        if statistical is None
                        else None
                    ),
                    business_inputs=ScenarioBand(lower=business.lower, upper=business.upper),
                    combined=ScenarioBand(lower=bounds.lower, upper=bounds.upper),
                )
        except (ValueError, OverflowError, ArithmeticError):
            return _abstain(
                effect,
                parsed,
                (diagnostic("nonfinite_arithmetic", "Finite impact bounds unavailable"),),
            )
        conditional = (
            effect.conditional
            or alignment.extrapolated
            or any(e.status == "assumed" for e in input_evidence(parsed))
        )
        warnings: list[AnalysisWarning] = []
        if conditional:
            warnings.append(
                AnalysisWarning(
                    code="impact.conditional",
                    scope="scenario",
                    message=(
                        "Scenario is conditional on retained source limitations "
                        "and declared business assumptions."
                    ),
                )
            )
        if any(q.combined.lower < 0 < q.combined.upper for q in quantities.values()):
            warnings.append(
                AnalysisWarning(
                    code="impact.crosses_zero",
                    scope="scenario",
                    message="The scenario band includes both negative and positive outcomes.",
                )
            )
        output_names = (
            "exposed_population",
            "gross_incremental_outcome",
            "gross_monetary_impact",
            "declared_costs",
            "net_monetary_impact",
        )
        return BusinessImpactResult(
            request_id=parsed.request_id,
            source=effect,
            inputs=parsed,
            status=AnalysisStatus.INCONCLUSIVE if conditional else AnalysisStatus.COMPLETED,
            horizon_kind="extrapolated" if alignment.extrapolated else "observed",
            population_multiplier=alignment.multiplier,
            exposed_population=quantities["exposed_population"],
            gross_incremental_outcome=quantities["gross_incremental_outcome"],
            gross_monetary_impact=quantities.get("gross_monetary_impact"),
            declared_costs=quantities.get("declared_costs"),
            net_monetary_impact=quantities.get("net_monetary_impact"),
            cost_breakdown=tuple(
                CostBreakdown(cost_id=c.cost_id, amount=quantities[f"costs.{c.cost_id}"])
                for c in parsed.costs.items
            )
            if parsed.costs and parsed.output == "net"
            else (),
            derivations=tuple(
                _derivation(name, q, parsed)
                for name, q in quantities.items()
                if name in output_names or name.startswith("costs.")
            ),
            warnings=tuple(warnings),
        )


def _abstain(
    source: SourceEffect, request: BusinessImpactRequest | None, diagnostics: tuple[Diagnostic, ...]
) -> BusinessImpactResult:
    return BusinessImpactResult(
        request_id=request.request_id if request else None,
        status=AnalysisStatus.ABSTAINED,
        source=source,
        inputs=request,
        diagnostics=diagnostics,
        abstention_reason=AbstentionReason(
            code=diagnostics[0].code,
            message=(
                "No business-impact scenario was computed; required evidence or inputs are invalid."
            ),
            missing_or_invalid_information=tuple(d.code for d in diagnostics),
        ),
    )


def _derivation(field: str, result: DerivedQuantity, request: BusinessImpactRequest) -> Derivation:
    refs = [
        "source.point",
        "source.interval",
        "inputs.population",
        "inputs.exposure",
        "inputs.horizon",
        "inputs.binding",
    ]
    refs.extend(
        "inputs." + name
        for name in (
            "baseline",
            "exposure_conversion",
            "conversion",
            "costs",
            "persistence",
            "repetition",
        )
        if getattr(request, name) is not None
    )
    formulas = {
        "exposed_population": "A = population * repetition * exposure * exposure_conversion",
        "gross_incremental_outcome": "Q = A * effect * scale * baseline_if_relative",
        "gross_monetary_impact": "G = Q * signed_value_per_outcome",
        "declared_costs": (
            "C = fixed + A * (cost_per_exposure + "
            "effect * scale * baseline_if_relative * cost_per_outcome)"
        ),
        "net_monetary_impact": (
            "net = A * (effect * scale * baseline_if_relative * "
            "(signed_value_per_outcome - cost_per_outcome) "
            "- cost_per_exposure) - fixed"
        ),
    }
    formula = formulas.get(field)
    if formula is None:
        cost_id = field.removeprefix("costs.")
        assert request.costs is not None
        cost = next(c for c in request.costs.items if c.cost_id == cost_id)
        formula = {
            "implementation": "cost = declared_amount (once)",
            "recurring": "cost = declared_amount * explicit_calendar_occurrences",
            "per_exposure": "cost = A * declared_rate",
            "per_incremental_outcome": "cost = Q * declared_rate",
        }[cost.basis]
        refs.append(f"inputs.costs.items[{cost.cost_id}]")
    return Derivation(
        field=field,
        formula_id=f"impact.v1.{field}",
        formula=formula,
        input_references=tuple(refs),
        result=result,
    )
