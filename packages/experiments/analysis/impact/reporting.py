"""Plain deterministic scenario reporting from the owned result, never an LLM."""

from __future__ import annotations

from ..base import AnalysisStatus
from .inputs import input_evidence
from .results import BusinessImpactResult


def render_scenario(result: BusinessImpactResult) -> str:
    """Render evidence and all uncertainty layers without reducing them to one claim."""
    src = result.source
    lines = [
        f"Business-impact scenario: {result.status.value}",
        f"Source estimator: {src.estimator}; estimand: {src.estimand}; "
        f"native status: {src.native_status}",
    ]
    lines.append(f"Source request: {src.request_id}; fingerprint: {src.fingerprint}")
    for provenance in src.provenance:
        lines.append(f"Source provenance: {provenance.model_dump_json()}")
    for source_record in (
        *src.source_diagnostics,
        *src.source_warnings,
        *src.source_assumptions,
        *src.evidence_limitations,
        *src.source_metadata,
    ):
        lines.append(f"Source evidence ({source_record.scope}): {source_record.model_dump_json()}")
    if result.status is AnalysisStatus.ABSTAINED:
        lines.extend(f"{d.code}: {d.message}" for d in result.diagnostics)
        return "\n".join(lines)
    assert result.inputs is not None
    if src.interval is not None:
        lines.append(
            f"Causal estimate: {src.point}; {src.interval.kind} {src.interval.model_dump_json()}"
        )
    lines.append(
        f"Horizon: {result.horizon_kind}; "
        f"{result.inputs.horizon.basis.count} {result.inputs.horizon.basis.unit}"
    )
    if src.metric is not None:
        lines.append(
            f"Metric: {src.metric.metric.metric_id}; "
            f"improvement direction: {src.metric.direction.value}"
        )
    lines.append("Operational inputs (values, units and evidence):")
    # These are explicit report inputs, never standard telemetry.
    for name in (
        "horizon",
        "population",
        "exposure",
        "binding",
        "conversion",
        "costs",
        "baseline",
        "exposure_conversion",
        "persistence",
        "repetition",
    ):
        item = getattr(result.inputs, name)
        if item is not None:
            lines.append(f"{name}: {item.model_dump_json()}")
    lines.append(
        "Evidence origins: "
        + ", ".join(sorted({f"{e.origin}/{e.status}" for e in input_evidence(result.inputs)}))
    )
    for record in result.derivations:
        q = record.result
        unit = q.unit.currency_code or q.entity or q.unit.symbol
        lines.append(f"{record.field} ({unit} per scenario horizon):")
        lines.append(
            f"  Central plug-in value: {q.central if q.central is not None else 'unavailable'}"
        )
        if q.statistical is not None:
            lines.append(
                f"  Statistical uncertainty ({q.statistical.kind}): "
                f"{q.statistical.model_dump_json()}"
            )
        else:
            lines.append(f"  Statistical uncertainty: {q.statistical_unavailable_reason}")
        lines.append(
            f"  Business-input band: [{q.business_inputs.lower}, {q.business_inputs.upper}]"
        )
        lines.append(f"  Combined scenario band: [{q.combined.lower}, {q.combined.upper}]")
        if q.combined.lower < 0 < q.combined.upper:
            lines.append("  Includes both negative and positive outcomes.")
        lines.append(f"  Derivation: {record.formula_id}; {record.formula}")
        lines.append(f"  Input references: {', '.join(record.input_references)}")
    for warning in result.warnings:
        lines.append(f"{warning.code}: {warning.message}")
    return "\n".join(lines)
