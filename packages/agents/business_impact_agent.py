from __future__ import annotations

import re
from dataclasses import dataclass
from time import perf_counter

from packages.agents.state import (
    AgentState,
    AgentStateUpdate,
    BusinessImpact,
    Citation,
    ExperimentMetricRecord,
    RetrievedChunk,
    create_error_entry,
    create_trace_entry,
)

BUSINESS_IMPACT_NODE = "business_impact"
_ANNUALIZED_TEXT_PATTERN = re.compile(
    r"annualized (?:impact|savings)[^\dA-Z$]*"
    r"(?:(USD|AUD|GBP|EUR|JPY|SGD)\s*)?\$?([0-9][0-9,]*(?:\.\d+)?)",
    re.IGNORECASE,
)


@dataclass
class BusinessImpactAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        trace = [create_trace_entry(node=BUSINESS_IMPACT_NODE, event="started")]
        try:
            business_impact = _build_business_impact(state)
        except Exception as exc:
            return {
                "errors": [
                    create_error_entry(
                        code="business_impact_failed",
                        message=f"Business impact analysis failed: {exc}",
                        node=BUSINESS_IMPACT_NODE,
                        details={"error_type": type(exc).__name__},
                    )
                ],
                "trace": [
                    *trace,
                    create_trace_entry(
                        node=BUSINESS_IMPACT_NODE,
                        event="failed",
                        details={"error_type": type(exc).__name__},
                    ),
                ],
                "metrics": {
                    **state["metrics"],
                    "business_impact": {
                        "status": "failed",
                        "latency_ms": (perf_counter() - started_at) * 1000.0,
                        "citation_count": 0,
                        "has_annualized_impact": False,
                    },
                },
            }

        return {
            "business_impact": business_impact,
            "errors": [],
            "trace": [
                *trace,
                create_trace_entry(
                    node=BUSINESS_IMPACT_NODE,
                    event="completed",
                    details={"status": business_impact["impact_status"]},
                ),
            ],
            "metrics": {
                **state["metrics"],
                "business_impact": {
                    "status": business_impact["impact_status"],
                    "latency_ms": (perf_counter() - started_at) * 1000.0,
                    "citation_count": len(business_impact["evidence_citations"]),
                    "has_annualized_impact": business_impact["estimated_annualized_impact"]
                    is not None,
                    "has_operational_savings": business_impact["operational_savings"] is not None,
                },
            },
        }


def _build_business_impact(state: AgentState) -> BusinessImpact:
    analysis = state["experiment_analysis"]
    citations = list(analysis["evidence_citations"]) or list(state["citations"])
    primary_metric = analysis["primary_metric"] or str(
        state["experiment_metadata"].get("primary_metric", "")
    )
    confidence = analysis["analysis_confidence"] or "low"

    assumptions: list[str] = []
    limitations = list(analysis["limitations"])

    baseline = _metric_value(analysis.get("control"), "value")
    treatment = _metric_value(analysis.get("treatment"), "value")
    if baseline is None or treatment is None:
        baseline, treatment = _metric_values_from_state_metrics(
            state["experiment_metrics"],
            primary_metric,
        )

    absolute_lift: float | None = None
    relative_lift: float | None = None
    impact_status = "insufficient_data"

    if baseline is not None and treatment is not None:
        absolute_lift = round(treatment - baseline, 6)
        assumptions.append("Absolute lift computed as treatment_value - baseline_value.")
        if baseline != 0:
            relative_lift = round(absolute_lift / baseline, 6)
            assumptions.append("Relative lift computed as absolute_lift / baseline_value.")
        else:
            limitations.append("Baseline value was zero, so relative lift was not computed.")
        impact_status = "estimated"
    else:
        relative_lift = _metric_value(analysis.get("observed_lift"), "relative_lift")
        if relative_lift is not None:
            assumptions.append(
                "Observed lift was carried forward because baseline and treatment values "
                "were unavailable."
            )
            limitations.append(
                "Baseline and treatment values were unavailable, so only observed lift "
                "could be reported."
            )
            impact_status = "partial_estimate"
        else:
            limitations.append(
                "Business impact could not be estimated because baseline, treatment, "
                "and observed lift data were unavailable."
            )

    annualized_impact = _explicit_value_from_sources(
        citations=citations,
        retrieved_chunks=state["retrieved_chunks"],
        experiment_metadata=state["experiment_metadata"],
        keys=("estimated_annualized_impact", "annualized_impact", "annualized_impact_value"),
    )
    operational_savings = _explicit_value_from_sources(
        citations=citations,
        retrieved_chunks=state["retrieved_chunks"],
        experiment_metadata=state["experiment_metadata"],
        keys=("operational_savings", "annualized_operational_savings"),
    )
    affected_segment = _explicit_segment_from_sources(
        citations=citations,
        retrieved_chunks=state["retrieved_chunks"],
        experiment_metadata=state["experiment_metadata"],
    )

    if impact_status == "insufficient_data" and any(
        value not in (None, "")
        for value in (annualized_impact, operational_savings, affected_segment)
    ):
        impact_status = "partial_estimate"

    if annualized_impact is not None:
        assumptions.append(
            "Estimated annualized impact was carried forward from explicit source data."
        )
    else:
        limitations.append("No explicit annualized impact was available in shared state evidence.")

    if operational_savings is not None:
        assumptions.append("Operational savings were carried forward from explicit source data.")

    summary = _build_summary(
        impact_status=impact_status,
        primary_metric=primary_metric,
        baseline=baseline,
        treatment=treatment,
        absolute_lift=absolute_lift,
        relative_lift=relative_lift,
        annualized_impact=annualized_impact,
    )

    return {
        "summary": summary,
        "impact_status": impact_status,
        "primary_business_metric": primary_metric,
        "baseline_value": baseline,
        "treatment_value": treatment,
        "absolute_lift": absolute_lift,
        "relative_lift": relative_lift,
        "estimated_annualized_impact": annualized_impact,
        "affected_segment": affected_segment,
        "operational_savings": operational_savings,
        "confidence_level": confidence,
        "assumptions": assumptions,
        "limitations": limitations,
        "evidence_citations": citations,
    }


def _build_summary(
    *,
    impact_status: str,
    primary_metric: str,
    baseline: float | None,
    treatment: float | None,
    absolute_lift: float | None,
    relative_lift: float | None,
    annualized_impact: dict[str, object] | None,
) -> str:
    if impact_status == "estimated" and baseline is not None and treatment is not None:
        summary = (
            f"Estimated business impact for {primary_metric}: baseline={baseline:.4f}, "
            f"treatment={treatment:.4f}, absolute_lift={absolute_lift:.6f}."
        )
        if relative_lift is not None:
            summary += f" Relative lift={relative_lift:.6f}."
        if annualized_impact is not None:
            summary += " Annualized impact was carried from source evidence."
        return summary
    if impact_status == "partial_estimate" and relative_lift is not None:
        return (
            f"Partial business impact estimate for {primary_metric}: observed relative lift "
            f"was {relative_lift:.4f}, but the underlying baseline/treatment values "
            "were incomplete."
        )
    return "Insufficient data to estimate grounded business impact."


def _metric_value(record: dict[str, object] | None, key: str) -> float | None:
    if not record:
        return None
    value = record.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_values_from_state_metrics(
    metrics: list[ExperimentMetricRecord],
    primary_metric: str,
) -> tuple[float | None, float | None]:
    baseline: float | None = None
    treatment: float | None = None
    for metric in metrics:
        if metric.get("metric_name") != primary_metric:
            continue
        if metric.get("variant") == "control":
            baseline = _metric_value(metric, "value")
        if metric.get("variant") == "treatment":
            treatment = _metric_value(metric, "value")
    return baseline, treatment


def _explicit_value_from_sources(
    *,
    citations: list[Citation],
    retrieved_chunks: list[RetrievedChunk],
    experiment_metadata: dict[str, object],
    keys: tuple[str, ...],
) -> dict[str, object] | None:
    for citation in citations:
        metadata = citation.get("metadata", {})
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, dict):
                return value
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, dict):
                return value
    for key in keys:
        value = experiment_metadata.get(key)
        if isinstance(value, dict):
            return value
    for citation in citations:
        parsed = _parse_annualized_text(citation.get("quote", ""))
        if parsed is not None:
            return parsed
    for chunk in retrieved_chunks:
        parsed = _parse_annualized_text(chunk.get("content", ""))
        if parsed is not None:
            return parsed
    return None


def _explicit_segment_from_sources(
    *,
    citations: list[Citation],
    retrieved_chunks: list[RetrievedChunk],
    experiment_metadata: dict[str, object],
) -> str:
    for citation in citations:
        metadata = citation.get("metadata", {})
        value = metadata.get("affected_segment")
        if value:
            return str(value)
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        value = metadata.get("affected_segment")
        if value:
            return str(value)
    value = experiment_metadata.get("affected_segment")
    return str(value) if value else ""


def _parse_annualized_text(text: str) -> dict[str, object] | None:
    match = _ANNUALIZED_TEXT_PATTERN.search(text)
    if match is None:
        return None
    currency = (match.group(1) or "USD").upper()
    amount = float(match.group(2).replace(",", ""))
    return {
        "amount": amount,
        "currency": currency,
        "period": "annual",
    }
