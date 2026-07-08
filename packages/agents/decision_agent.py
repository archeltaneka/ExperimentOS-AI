from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from packages.agents.state import (
    AgentState,
    AgentStateUpdate,
    Citation,
    DecisionConfidence,
    DecisionRecommendation,
    DecisionRecord,
    DecisionStatus,
    create_error_entry,
    create_trace_entry,
)

DECISION_NODE = "decision"
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


@dataclass
class DecisionAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        trace = [create_trace_entry(node=DECISION_NODE, event="started")]
        try:
            decision = _build_decision(state)
        except Exception as exc:
            return {
                "errors": [
                    create_error_entry(
                        code="decision_failed",
                        message=f"Decision synthesis failed: {exc}",
                        node=DECISION_NODE,
                        details={"error_type": type(exc).__name__},
                    )
                ],
                "trace": [
                    *trace,
                    create_trace_entry(
                        node=DECISION_NODE,
                        event="failed",
                        details={"error_type": type(exc).__name__},
                    ),
                ],
                "metrics": {
                    **state["metrics"],
                    "decision": {
                        "status": "failed",
                        "recommendation": "unknown",
                        "latency_ms": (perf_counter() - started_at) * 1000.0,
                        "citation_count": 0,
                        "blocking_issue_count": 0,
                    },
                },
            }

        return {
            "decision": decision,
            "errors": [],
            "trace": [
                *trace,
                create_trace_entry(
                    node=DECISION_NODE,
                    event="completed",
                    details={
                        "status": decision["decision_status"],
                        "recommendation": decision["recommendation"],
                    },
                ),
            ],
            "metrics": {
                **state["metrics"],
                "decision": {
                    "status": decision["decision_status"],
                    "recommendation": decision["recommendation"],
                    "confidence": decision["confidence"],
                    "latency_ms": (perf_counter() - started_at) * 1000.0,
                    "citation_count": len(decision["evidence_citations"]),
                    "blocking_issue_count": len(decision["blocking_issues"]),
                    "supporting_evidence_count": len(decision["supporting_evidence"]),
                    "approval_required": decision["approval_required"],
                },
            },
        }


def _build_decision(state: AgentState) -> DecisionRecord:
    analysis = state["experiment_analysis"]
    business_impact = state["business_impact"]
    risk_assessment = state["risk_assessment"]
    citations = _decision_citations(state)
    supporting_evidence = _supporting_evidence(state)
    assumptions = _unique(
        [
            *business_impact["assumptions"],
            *risk_assessment["assumptions"],
            "Decision recommendation uses deterministic state-based rules only.",
        ]
    )
    limitations = _unique(
        [
            *analysis["limitations"],
            *business_impact["limitations"],
            *risk_assessment["limitations"],
        ]
    )

    if state["errors"]:
        blocking_issues = [
            f"{error['code']}: {error['message']}"
            for error in state["errors"]
            if error.get("code") and error.get("message")
        ]
        return _build_result(
            state=state,
            decision_status="blocked",
            recommendation="needs_more_data",
            confidence="low",
            rationale=(
                "Decision synthesis was blocked because upstream workflow errors were "
                "recorded in shared state."
            ),
            supporting_evidence=supporting_evidence,
            blocking_issues=blocking_issues,
            recommended_next_actions=[
                "Resolve upstream agent errors before making a rollout decision.",
                "Re-run the workflow after the blocking failures are fixed.",
            ],
            approval_required=False,
            evidence_citations=citations,
            assumptions=assumptions,
            limitations=limitations,
        )

    if _insufficient_data(analysis=analysis, business_impact=business_impact, citations=citations):
        return _build_result(
            state=state,
            decision_status="insufficient_data",
            recommendation="needs_more_data",
            confidence="unknown",
            rationale=(
                "Shared state does not contain enough grounded analysis, business impact, "
                "or evidence to support a rollout recommendation."
            ),
            supporting_evidence=supporting_evidence,
            blocking_issues=[
                "Experiment analysis is insufficient or missing.",
                "Grounded evidence citations are missing or incomplete.",
            ],
            recommended_next_actions=[
                "Resolve the target experiment and retrieval evidence.",
                "Re-run analysis, business impact, and risk assessment with complete inputs.",
            ],
            approval_required=False,
            evidence_citations=citations,
            assumptions=assumptions,
            limitations=limitations,
        )

    harmful_guardrails = _harmful_guardrail_issues(state)
    if harmful_guardrails:
        return _build_result(
            state=state,
            decision_status="decided",
            recommendation="rollback",
            confidence=_decision_confidence(
                analysis_confidence=analysis["analysis_confidence"],
                business_confidence=business_impact["confidence_level"],
                risk_confidence=risk_assessment["confidence_level"],
                overall_risk_level=risk_assessment["overall_risk_level"],
                has_statistical_support=bool(analysis["statistical_significance"]),
                has_citations=bool(citations),
            ),
            rationale=(
                "Evidence indicates harmful guardrail deterioration, so rollback is safer "
                "than expanding or sustaining the rollout."
            ),
            supporting_evidence=supporting_evidence,
            blocking_issues=harmful_guardrails,
            recommended_next_actions=_unique(
                [
                    (
                        "Rollback or keep the feature disabled until the harmful "
                        "guardrail change is understood."
                    ),
                    *risk_assessment["mitigation_actions"],
                ]
            ),
            approval_required=True,
            evidence_citations=citations,
            assumptions=assumptions,
            limitations=limitations,
        )

    positive_lift = _lift_direction(analysis, business_impact) == "positive"
    negative_lift = _lift_direction(analysis, business_impact) == "negative"
    primary_metric_worsened = _primary_metric_worsened(analysis)
    business_positive = _business_positive(business_impact)
    overall_risk_level = risk_assessment["overall_risk_level"]
    statistical_significance = analysis["statistical_significance"]

    if negative_lift or primary_metric_worsened:
        return _build_result(
            state=state,
            decision_status="decided",
            recommendation="do_not_rollout",
            confidence=_decision_confidence(
                analysis_confidence=analysis["analysis_confidence"],
                business_confidence=business_impact["confidence_level"],
                risk_confidence=risk_assessment["confidence_level"],
                overall_risk_level=overall_risk_level,
                has_statistical_support=bool(statistical_significance),
                has_citations=bool(citations),
            ),
            rationale=(
                "The primary metric moved in the wrong direction, so the evidence does not "
                "support rollout."
            ),
            supporting_evidence=supporting_evidence,
            blocking_issues=_decision_gaps(state),
            recommended_next_actions=_unique(
                [
                    "Do not roll out the treatment beyond the current exposure.",
                    "Investigate the negative metric movement before running a follow-up test.",
                    *risk_assessment["mitigation_actions"],
                ]
            ),
            approval_required=True,
            evidence_citations=citations,
            assumptions=assumptions,
            limitations=limitations,
        )

    if _needs_more_data(state, positive_lift=positive_lift, business_positive=business_positive):
        recommendation: DecisionRecommendation = (
            "continue_experiment" if positive_lift and business_positive else "needs_more_data"
        )
        rationale = (
            "Evidence is directionally positive but still incomplete, so the experiment "
            "should continue before a rollout call is made."
            if recommendation == "continue_experiment"
            else (
                "Evidence is incomplete or uncertain, so a rollout recommendation "
                "is not supported."
            )
        )
        return _build_result(
            state=state,
            decision_status="needs_more_data",
            recommendation=recommendation,
            confidence="low",
            rationale=rationale,
            supporting_evidence=supporting_evidence,
            blocking_issues=_decision_gaps(state),
            recommended_next_actions=_needs_more_data_actions(state),
            approval_required=False,
            evidence_citations=citations,
            assumptions=assumptions,
            limitations=limitations,
        )

    if positive_lift and business_positive and overall_risk_level in {"low", "medium"}:
        return _build_result(
            state=state,
            decision_status="decided",
            recommendation="rollout",
            confidence=_decision_confidence(
                analysis_confidence=analysis["analysis_confidence"],
                business_confidence=business_impact["confidence_level"],
                risk_confidence=risk_assessment["confidence_level"],
                overall_risk_level=overall_risk_level,
                has_statistical_support=bool(statistical_significance),
                has_citations=bool(citations),
            ),
            rationale=(
                "The primary metric improved, business impact is positive, and risk is "
                "within a manageable range for rollout."
            ),
            supporting_evidence=supporting_evidence,
            blocking_issues=[],
            recommended_next_actions=_unique(
                [
                    "Roll out gradually and monitor primary and guardrail metrics during the ramp.",
                    *risk_assessment["mitigation_actions"],
                ]
            ),
            approval_required=True,
            evidence_citations=citations,
            assumptions=assumptions,
            limitations=limitations,
        )

    return _build_result(
        state=state,
        decision_status="needs_more_data",
        recommendation="needs_more_data",
        confidence="low",
        rationale="Available evidence does not support a confident rollout recommendation yet.",
        supporting_evidence=supporting_evidence,
        blocking_issues=_decision_gaps(state),
        recommended_next_actions=_needs_more_data_actions(state),
        approval_required=False,
        evidence_citations=citations,
        assumptions=assumptions,
        limitations=limitations,
    )


def _build_result(
    *,
    state: AgentState,
    decision_status: DecisionStatus,
    recommendation: DecisionRecommendation,
    confidence: DecisionConfidence,
    rationale: str,
    supporting_evidence: list[str],
    blocking_issues: list[str],
    recommended_next_actions: list[str],
    approval_required: bool,
    evidence_citations: list[Citation],
    assumptions: list[str],
    limitations: list[str],
) -> DecisionRecord:
    return {
        **state["decision"],
        "decision_status": decision_status,
        "recommendation": recommendation,
        "confidence": confidence,
        "rationale": rationale,
        "supporting_evidence": _unique(supporting_evidence),
        "blocking_issues": _unique(blocking_issues),
        "recommended_next_actions": _unique(recommended_next_actions),
        "approval_required": approval_required,
        "evidence_citations": evidence_citations,
        "assumptions": _unique(assumptions),
        "limitations": _unique(limitations),
    }


def _decision_citations(state: AgentState) -> list[Citation]:
    seen: set[tuple[str, str, str, str]] = set()
    citations: list[Citation] = []
    for citation in [
        *state["experiment_analysis"]["evidence_citations"],
        *state["business_impact"]["evidence_citations"],
        *state["risk_assessment"]["evidence_citations"],
        *state["citations"],
    ]:
        key = (
            str(citation.get("document_id", "")),
            str(citation.get("experiment_id", "")),
            str(citation.get("section", "")),
            str(citation.get("quote", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        citations.append(citation)
    return citations


def _supporting_evidence(state: AgentState) -> list[str]:
    analysis = state["experiment_analysis"]
    business_impact = state["business_impact"]
    risk_assessment = state["risk_assessment"]

    evidence = [
        analysis["summary"],
        *analysis["findings"],
        business_impact["summary"],
        (
            f"Business impact status: {business_impact['impact_status']} "
            f"with relative lift {business_impact['relative_lift']}."
        ),
        (
            f"Risk assessment status: {risk_assessment['risk_status']} "
            f"with overall risk {risk_assessment['overall_risk_level']}."
        ),
    ]
    return [item for item in _unique(evidence) if item]


def _insufficient_data(
    *,
    analysis: dict[str, object],
    business_impact: dict[str, object],
    citations: list[Citation],
) -> bool:
    analysis_status = str(analysis.get("status", ""))
    impact_status = str(business_impact.get("impact_status", ""))
    return (
        analysis_status in {"", "not_applicable", "insufficient_data"}
        and impact_status in {"", "not_required", "insufficient_data"}
        and not citations
    )


def _needs_more_data(
    state: AgentState,
    *,
    positive_lift: bool,
    business_positive: bool,
) -> bool:
    analysis = state["experiment_analysis"]
    business_impact = state["business_impact"]
    risk_assessment = state["risk_assessment"]
    if analysis["status"] != "completed":
        return True
    if business_impact["impact_status"] in {"partial_estimate", "insufficient_data"}:
        return True
    if risk_assessment["risk_status"] in {"partial_assessment", "insufficient_data"}:
        return True
    if risk_assessment["overall_risk_level"] == "unknown":
        return True
    if not analysis["statistical_significance"]:
        return True
    if (
        risk_assessment["overall_risk_level"] == "high"
        and not positive_lift
        and not business_positive
    ):
        return False
    return False


def _needs_more_data_actions(state: AgentState) -> list[str]:
    actions = [
        "Gather additional evidence before making a rollout-sensitive decision.",
        "Resolve missing statistical support, business impact, or risk evidence.",
    ]
    actions.extend(state["risk_assessment"]["mitigation_actions"])
    if state["business_impact"]["impact_status"] != "estimated":
        actions.append("Ground the business impact with baseline, treatment, or annualized values.")
    if not state["experiment_analysis"]["statistical_significance"]:
        actions.append("Establish statistical support for the primary metric before rollout.")
    return _unique(actions)


def _decision_gaps(state: AgentState) -> list[str]:
    analysis = state["experiment_analysis"]
    business_impact = state["business_impact"]
    risk_assessment = state["risk_assessment"]
    gaps: list[str] = []

    if analysis["status"] != "completed":
        gaps.append(f"Experiment analysis status is {analysis['status']}.")
    if not analysis["statistical_significance"]:
        gaps.append("Statistical significance is missing for the primary metric.")
    if business_impact["impact_status"] == "partial_estimate":
        gaps.append("Business impact is only partially estimated.")
    if business_impact["impact_status"] == "insufficient_data":
        gaps.append("Business impact is insufficient for a rollout decision.")
    if risk_assessment["risk_status"] == "partial_assessment":
        gaps.append("Risk assessment is only partially complete.")
    if risk_assessment["risk_status"] == "insufficient_data":
        gaps.append("Risk assessment is insufficient for a rollout decision.")
    if risk_assessment["overall_risk_level"] == "unknown":
        gaps.append("Overall risk level is unknown.")
    gaps.extend(risk_assessment["guardrail_concerns"])
    gaps.extend(risk_assessment["statistical_concerns"])
    gaps.extend(risk_assessment["data_quality_concerns"])
    gaps.extend(risk_assessment["rollout_concerns"])
    gaps.extend(risk_assessment["user_or_business_concerns"])
    return _unique(gaps)


def _harmful_guardrail_issues(state: AgentState) -> list[str]:
    issues = list(state["risk_assessment"]["guardrail_concerns"])
    for factor in state["risk_assessment"]["risk_factors"]:
        if (
            factor.get("category") == "guardrail"
            or factor.get("code") == "guardrail_metric_deterioration"
        ):
            detail = str(factor.get("detail", "")).strip()
            if detail:
                issues.append(detail)
    for metric in state["experiment_analysis"]["guardrail_metrics"]:
        if _guardrail_deteriorated(metric):
            metric_name = str(metric.get("metric_name", "guardrail metric"))
            issues.append(f"Guardrail metric {metric_name} moved in a riskier direction.")
    return _unique(issues)


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


def _lift_direction(analysis: dict[str, object], business_impact: dict[str, object]) -> str:
    relative_lift = _metric_value(analysis.get("observed_lift"), "relative_lift")
    if relative_lift is None:
        relative_lift = _metric_value(analysis.get("treatment_control_comparison"), "relative_lift")
    if relative_lift is None:
        relative_lift = _metric_value(business_impact, "relative_lift")
    if relative_lift is not None:
        return "positive" if relative_lift > 0 else "negative" if relative_lift < 0 else "flat"

    absolute_lift = _metric_value(analysis.get("treatment_control_comparison"), "absolute_delta")
    if absolute_lift is None:
        absolute_lift = _metric_value(business_impact, "absolute_lift")
    if absolute_lift is not None:
        return "positive" if absolute_lift > 0 else "negative" if absolute_lift < 0 else "flat"
    return "unknown"


def _primary_metric_worsened(analysis: dict[str, object]) -> bool:
    control = _metric_value(analysis.get("control"), "value")
    treatment = _metric_value(analysis.get("treatment"), "value")
    if control is None or treatment is None:
        return False
    return treatment < control


def _business_positive(business_impact: dict[str, object]) -> bool:
    if business_impact.get("impact_status") not in {"estimated", "partial_estimate"}:
        return False
    relative_lift = _metric_value(business_impact, "relative_lift")
    if relative_lift is not None:
        return relative_lift > 0
    absolute_lift = _metric_value(business_impact, "absolute_lift")
    if absolute_lift is not None:
        return absolute_lift > 0
    annualized = business_impact.get("estimated_annualized_impact")
    if isinstance(annualized, dict):
        amount = annualized.get("amount")
        try:
            return float(amount) > 0
        except (TypeError, ValueError):
            return False
    return False


def _decision_confidence(
    *,
    analysis_confidence: str,
    business_confidence: str,
    risk_confidence: str,
    overall_risk_level: str,
    has_statistical_support: bool,
    has_citations: bool,
) -> DecisionConfidence:
    normalized = {
        (analysis_confidence or "").strip().lower(),
        (business_confidence or "").strip().lower(),
        (risk_confidence or "").strip().lower(),
    }
    if (
        normalized == {"high"}
        and overall_risk_level == "low"
        and has_statistical_support
        and has_citations
    ):
        return "high"
    if "low" in normalized or "unknown" in normalized or overall_risk_level == "high":
        return "medium"
    return "medium"


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


def _unique(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
