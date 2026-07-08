from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from packages.agents.state import (
    AgentState,
    AgentStateUpdate,
    Citation,
    RiskAssessment,
    RiskFactor,
    RiskRecord,
    create_error_entry,
    create_trace_entry,
)

RISK_ASSESSMENT_NODE = "risk_assessment"
_SEVERITY_POINTS = {"low": 1, "medium": 2, "high": 3}
_NEGATIVE_GUARDRAIL_TERMS = (
    "retry",
    "error",
    "unsubscribe",
    "complaint",
    "support",
    "refund",
    "zero_result",
    "latency",
    "load",
    "time",
    "p95",
    "seconds",
)
_POSITIVE_GUARDRAIL_TERMS = (
    "completion",
    "success",
    "conversion",
    "intent",
    "click",
    "save",
    "margin",
    "revenue",
    "order",
    "purchase",
    "reactivation",
    "cart",
    "trial",
    "qualified",
)
_DATA_QUALITY_TERMS = (
    "sample ratio mismatch",
    "tracking",
    "telemetry",
    "under-count",
    "undercount",
    "lag",
    "allocation",
)
_ROLLOUT_TERMS = ("hold", "pending", "monitor", "fix", "telemetry", "tracking")


@dataclass
class RiskAssessmentAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        trace = [create_trace_entry(node=RISK_ASSESSMENT_NODE, event="started")]
        try:
            risk_assessment, risks = _build_risk_assessment(state)
        except Exception as exc:
            return {
                "errors": [
                    create_error_entry(
                        code="risk_assessment_failed",
                        message=f"Risk assessment failed: {exc}",
                        node=RISK_ASSESSMENT_NODE,
                        details={"error_type": type(exc).__name__},
                    )
                ],
                "trace": [
                    *trace,
                    create_trace_entry(
                        node=RISK_ASSESSMENT_NODE,
                        event="failed",
                        details={"error_type": type(exc).__name__},
                    ),
                ],
                "metrics": {
                    **state["metrics"],
                    "risk_assessment": {
                        "status": "failed",
                        "latency_ms": (perf_counter() - started_at) * 1000.0,
                        "citation_count": 0,
                        "risk_factor_count": 0,
                    },
                },
            }

        return {
            "risk_assessment": risk_assessment,
            "risks": risks,
            "errors": [],
            "trace": [
                *trace,
                create_trace_entry(
                    node=RISK_ASSESSMENT_NODE,
                    event="completed",
                    details={
                        "status": risk_assessment["risk_status"],
                        "overall_risk_level": risk_assessment["overall_risk_level"],
                    },
                ),
            ],
            "metrics": {
                **state["metrics"],
                "risk_assessment": {
                    "status": risk_assessment["risk_status"],
                    "latency_ms": (perf_counter() - started_at) * 1000.0,
                    "citation_count": len(risk_assessment["evidence_citations"]),
                    "risk_factor_count": len(risk_assessment["risk_factors"]),
                    "overall_risk_level": risk_assessment["overall_risk_level"],
                    "risk_score": risk_assessment["risk_score"],
                },
            },
        }


def _build_risk_assessment(state: AgentState) -> tuple[RiskAssessment, list[RiskRecord]]:
    analysis = state["experiment_analysis"]
    business_impact = state["business_impact"]
    citations = list(analysis["evidence_citations"]) or list(state["citations"])
    retrieved_chunks = state["retrieved_chunks"]
    experiment_ids = state["experiment_context"]["experiment_ids"]
    experiment_hints = _experiment_hints(state)

    limitations = _unique(
        [
            *analysis["limitations"],
            *business_impact["limitations"],
        ]
    )
    assumptions = _unique(
        [
            *business_impact["assumptions"],
            "Risk score is the deterministic sum of structured severity points.",
        ]
    )

    if not _has_minimum_context(
        analysis=analysis,
        citations=citations,
        retrieved_chunks=retrieved_chunks,
        experiment_ids=experiment_ids,
        experiment_hints=experiment_hints,
    ):
        limitations.append(
            "Insufficient evidence: no resolved experiment, analysis, or retrieval support was "
            "available for risk assessment."
        )
        risk_assessment = _build_result(
            state=state,
            citations=citations,
            risk_status="insufficient_data",
            overall_risk_level="unknown",
            risk_score=None,
            risk_factors=[],
            guardrail_concerns=[],
            data_quality_concerns=[],
            statistical_concerns=[],
            rollout_concerns=[],
            user_or_business_concerns=[],
            mitigation_actions=[
                "Resolve the target experiment and gather evidence before rollout."
            ],
            assumptions=assumptions,
            limitations=limitations,
            confidence_level="low",
        )
        return risk_assessment, []

    risk_factors: list[RiskFactor] = []
    guardrail_concerns: list[str] = []
    data_quality_concerns: list[str] = []
    statistical_concerns: list[str] = []
    rollout_concerns: list[str] = []
    user_or_business_concerns: list[str] = []
    mitigation_actions: list[str] = []

    def add_factor(
        *,
        code: str,
        title: str,
        severity: str,
        category: str,
        detail: str,
        mitigation: str,
    ) -> None:
        risk_factors.append(
            {
                "code": code,
                "title": title,
                "severity": severity,
                "category": category,
                "detail": detail,
                "mitigation": mitigation,
            }
        )
        mitigation_actions.append(mitigation)
        if category == "guardrail":
            guardrail_concerns.append(detail)
        elif category == "data_quality":
            data_quality_concerns.append(detail)
        elif category == "statistical":
            statistical_concerns.append(detail)
        elif category == "rollout":
            rollout_concerns.append(detail)
        elif category == "user_or_business":
            user_or_business_concerns.append(detail)

    experiment_id = analysis["experiment_id"] or (experiment_ids[0] if experiment_ids else "")
    if not experiment_id:
        if len(experiment_hints) > 1:
            add_factor(
                code="ambiguous_experiment_request",
                title="Experiment scope is ambiguous",
                severity="medium",
                category="data_quality",
                detail="Multiple experiment hints were present without a resolved experiment id.",
                mitigation="Specify a single experiment identifier before acting on the risk read.",
            )
        else:
            add_factor(
                code="missing_experiment_identifier",
                title="Experiment identifier is missing",
                severity="medium",
                category="data_quality",
                detail="Risk assessment did not receive a stable experiment identifier.",
                mitigation="Resolve the experiment id before making rollout-sensitive judgments.",
            )

    primary_metric = analysis["primary_metric"]
    if not primary_metric:
        add_factor(
            code="missing_primary_metric",
            title="Primary metric is missing",
            severity="high",
            category="statistical",
            detail="The experiment analysis did not identify a primary metric for risk evaluation.",
            mitigation="Confirm the primary metric before interpreting rollout risk.",
        )

    control_value = _metric_value(analysis.get("control"), "value")
    treatment_value = _metric_value(analysis.get("treatment"), "value")
    if control_value is None or treatment_value is None:
        add_factor(
            code="missing_baseline_or_treatment_values",
            title="Baseline or treatment values are missing",
            severity="high",
            category="statistical",
            detail=(
                "Control/treatment values were incomplete, so lift quality "
                "cannot be checked fully."
            ),
            mitigation="Recover control and treatment metric values before rollout review.",
        )

    if not analysis["statistical_significance"]:
        add_factor(
            code="missing_statistical_significance",
            title="Statistical significance is missing",
            severity="medium",
            category="statistical",
            detail=(
                "No stored statistical significance signal was available for "
                "the primary metric."
            ),
            mitigation="Treat the observed lift as directional until significance is established.",
        )

    if _is_low_confidence(
        analysis_confidence=analysis["analysis_confidence"],
        business_confidence=business_impact["confidence_level"],
    ):
        add_factor(
            code="low_or_unknown_confidence",
            title="Confidence is low or unknown",
            severity="medium",
            category="statistical",
            detail="At least one upstream artifact reported low or unknown confidence.",
            mitigation="Increase evidence quality before treating the result as rollout-ready.",
        )

    lift_signal = _lift_signal(analysis, business_impact)
    if lift_signal == "negative":
        add_factor(
            code="negative_or_unclear_lift",
            title="Primary metric moved in the wrong direction",
            severity="high",
            category="user_or_business",
            detail="Observed lift is negative, which increases rollout risk materially.",
            mitigation="Do not expand rollout until the negative lift is understood or reversed.",
        )
    elif lift_signal == "unclear":
        add_factor(
            code="negative_or_unclear_lift",
            title="Primary metric lift is unclear",
            severity="high",
            category="user_or_business",
            detail="Primary metric lift could not be established from the available state.",
            mitigation="Clarify the lift signal before making rollout-sensitive decisions.",
        )

    for guardrail_metric in analysis["guardrail_metrics"]:
        if _guardrail_deteriorated(guardrail_metric):
            metric_name = str(guardrail_metric.get("metric_name", "guardrail metric"))
            add_factor(
                code="guardrail_metric_deterioration",
                title=f"{metric_name} deteriorated",
                severity="medium",
                category="guardrail",
                detail=f"Guardrail metric {metric_name} moved in a riskier direction.",
                mitigation=(
                    f"Monitor and mitigate guardrail movement for {metric_name} "
                    "before ramping."
                ),
            )

    if not citations or not retrieved_chunks:
        add_factor(
            code="insufficient_retrieved_evidence",
            title="Retrieved evidence is limited",
            severity="medium",
            category="data_quality",
            detail="Citations or retrieved chunks were missing, reducing evidence traceability.",
            mitigation=(
                "Retrieve supporting evidence and citations before relying on "
                "this assessment."
            ),
        )

    if business_impact["impact_status"] == "partial_estimate":
        add_factor(
            code="business_impact_partial",
            title="Business impact estimate is partial",
            severity="medium",
            category="user_or_business",
            detail=(
                "Business impact is only partially estimated, so "
                "downside/upside tradeoffs remain fuzzy."
            ),
            mitigation=(
                "Ground the business impact with baseline, treatment, or "
                "explicit annualized values."
            ),
        )
    elif business_impact["impact_status"] == "insufficient_data":
        add_factor(
            code="business_impact_insufficient",
            title="Business impact estimate is insufficient",
            severity="medium",
            category="user_or_business",
            detail="Business impact could not be estimated cleanly from the available evidence.",
            mitigation="Resolve business impact before treating the rollout risk as complete.",
        )

    for note in _data_quality_notes(state, limitations):
        add_factor(
            code="data_quality_concern",
            title="Data quality concern present",
            severity="medium",
            category="data_quality",
            detail=note,
            mitigation=(
                "Address the data quality caveat or carry it explicitly into "
                "rollout monitoring."
            ),
        )

    rollout_note = _rollout_note(state)
    if rollout_note:
        add_factor(
            code="rollout_constraint",
            title="Rollout constraint is already documented",
            severity="medium",
            category="rollout",
            detail=rollout_note,
            mitigation="Honor the documented rollout constraint during ramp planning.",
        )

    risk_score = sum(_SEVERITY_POINTS[factor["severity"]] for factor in risk_factors)
    risk_status = _risk_status(
        analysis_status=analysis["status"],
        impact_status=business_impact["impact_status"],
    )
    overall_risk_level = _overall_risk_level(risk_score)
    confidence_level = _confidence_level(
        risk_status=risk_status,
        risk_score=risk_score,
        analysis_confidence=analysis["analysis_confidence"],
        business_confidence=business_impact["confidence_level"],
        has_statistical_support=bool(analysis["statistical_significance"]),
        has_citations=bool(citations),
    )

    risk_assessment = _build_result(
        state=state,
        citations=citations,
        risk_status=risk_status,
        overall_risk_level=overall_risk_level,
        risk_score=risk_score,
        risk_factors=risk_factors,
        guardrail_concerns=_unique(guardrail_concerns),
        data_quality_concerns=_unique(data_quality_concerns),
        statistical_concerns=_unique(statistical_concerns),
        rollout_concerns=_unique(rollout_concerns),
        user_or_business_concerns=_unique(user_or_business_concerns),
        mitigation_actions=_unique(mitigation_actions),
        assumptions=assumptions,
        limitations=_unique(limitations),
        confidence_level=confidence_level,
    )
    return risk_assessment, [_risk_record(factor) for factor in risk_factors]


def _build_result(
    *,
    state: AgentState,
    citations: list[Citation],
    risk_status: str,
    overall_risk_level: str,
    risk_score: int | None,
    risk_factors: list[RiskFactor],
    guardrail_concerns: list[str],
    data_quality_concerns: list[str],
    statistical_concerns: list[str],
    rollout_concerns: list[str],
    user_or_business_concerns: list[str],
    mitigation_actions: list[str],
    assumptions: list[str],
    limitations: list[str],
    confidence_level: str,
) -> RiskAssessment:
    return {
        **state["risk_assessment"],
        "risk_status": risk_status,
        "overall_risk_level": overall_risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "guardrail_concerns": guardrail_concerns,
        "data_quality_concerns": data_quality_concerns,
        "statistical_concerns": statistical_concerns,
        "rollout_concerns": rollout_concerns,
        "user_or_business_concerns": user_or_business_concerns,
        "mitigation_actions": mitigation_actions,
        "assumptions": assumptions,
        "limitations": limitations,
        "evidence_citations": citations,
        "confidence_level": confidence_level,
    }


def _has_minimum_context(
    *,
    analysis: dict[str, object],
    citations: list[Citation],
    retrieved_chunks: list[dict[str, object]],
    experiment_ids: list[str],
    experiment_hints: list[str],
) -> bool:
    return any(
        (
            analysis.get("experiment_id"),
            analysis.get("primary_metric"),
            citations,
            retrieved_chunks,
            experiment_ids,
            experiment_hints,
        )
    )


def _risk_status(*, analysis_status: str, impact_status: str) -> str:
    if analysis_status == "insufficient_data":
        return "partial_assessment"
    if impact_status in {"partial_estimate", "insufficient_data"}:
        return "partial_assessment"
    return "assessed"


def _overall_risk_level(risk_score: int) -> str:
    if risk_score >= 3:
        return "high"
    if risk_score >= 1:
        return "medium"
    return "low"


def _confidence_level(
    *,
    risk_status: str,
    risk_score: int,
    analysis_confidence: str,
    business_confidence: str,
    has_statistical_support: bool,
    has_citations: bool,
) -> str:
    if risk_status == "insufficient_data":
        return "low"
    if (
        risk_score == 0
        and analysis_confidence == "high"
        and business_confidence == "high"
        and has_statistical_support
        and has_citations
    ):
        return "high"
    if risk_status == "partial_assessment":
        return "low"
    return "medium"


def _risk_record(factor: RiskFactor) -> RiskRecord:
    return {
        "title": str(factor["title"]),
        "severity": str(factor["severity"]),
        "detail": str(factor["detail"]),
        "mitigation": str(factor["mitigation"]),
    }


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


def _lift_signal(analysis: dict[str, object], business_impact: dict[str, object]) -> str:
    relative_lift = _metric_value(analysis.get("observed_lift"), "relative_lift")
    if relative_lift is None:
        relative_lift = _metric_value(analysis.get("treatment_control_comparison"), "relative_lift")
    if relative_lift is None:
        relative_lift = _metric_value(business_impact, "relative_lift")
    if relative_lift is not None:
        return "negative" if relative_lift < 0 else "positive"

    absolute_lift = _metric_value(analysis.get("treatment_control_comparison"), "absolute_delta")
    if absolute_lift is None:
        absolute_lift = _metric_value(business_impact, "absolute_lift")
    if absolute_lift is not None:
        return "negative" if absolute_lift < 0 else "positive"
    return "unclear"


def _is_low_confidence(*, analysis_confidence: str, business_confidence: str) -> bool:
    normalized_analysis = (analysis_confidence or "").strip().lower()
    normalized_business = (business_confidence or "").strip().lower()
    if normalized_analysis in {"", "low", "unknown"}:
        return True
    return normalized_analysis != "high" and normalized_business in {"", "low", "unknown"}


def _guardrail_deteriorated(metric: dict[str, object]) -> bool:
    metric_name = str(metric.get("metric_name", "")).lower()
    control = _metric_value(metric, "control_value")
    treatment = _metric_value(metric, "treatment_value")
    if control is None or treatment is None:
        return False
    if any(term in metric_name for term in _NEGATIVE_GUARDRAIL_TERMS):
        return treatment > control
    if any(term in metric_name for term in _POSITIVE_GUARDRAIL_TERMS):
        return treatment < control
    return False


def _data_quality_notes(state: AgentState, limitations: list[str]) -> list[str]:
    notes: list[str] = []
    imperfections = state["experiment_metadata"].get("imperfections", [])
    for note in [*limitations, *[str(value) for value in imperfections if value]]:
        normalized = note.lower()
        if any(term in normalized for term in _DATA_QUALITY_TERMS):
            notes.append(note)
    return _unique(notes)


def _rollout_note(state: AgentState) -> str:
    value = str(state["experiment_metadata"].get("business_decision", ""))
    normalized = value.lower()
    if value and any(term in normalized for term in _ROLLOUT_TERMS):
        return value
    return ""


def _experiment_hints(state: AgentState) -> list[str]:
    hints = state["experiment_context"]["filters"].get("experiment_hints", [])
    if isinstance(hints, list):
        return [str(hint) for hint in hints if str(hint).strip()]
    return []


def _unique(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
