from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from packages.agents.state import (
    AgentState,
    AgentStateUpdate,
    Citation,
    DecisionConfidence,
    ExecutiveSummary,
    ExecutiveSummaryStatus,
    create_error_entry,
    create_trace_entry,
)

EXECUTIVE_SUMMARY_NODE = "executive_summary"


@dataclass
class ExecutiveSummaryAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        trace = [create_trace_entry(node=EXECUTIVE_SUMMARY_NODE, event="started")]
        try:
            executive_summary = _build_executive_summary(state)
        except Exception as exc:
            return {
                "errors": [
                    create_error_entry(
                        code="executive_summary_failed",
                        message=f"Executive summary generation failed: {exc}",
                        node=EXECUTIVE_SUMMARY_NODE,
                        details={"error_type": type(exc).__name__},
                    )
                ],
                "trace": [
                    *trace,
                    create_trace_entry(
                        node=EXECUTIVE_SUMMARY_NODE,
                        event="failed",
                        details={"error_type": type(exc).__name__},
                    ),
                ],
                "metrics": {
                    **state["metrics"],
                    "executive_summary": {
                        "status": "failed",
                        "recommendation": "",
                        "confidence": "unknown",
                        "latency_ms": (perf_counter() - started_at) * 1000.0,
                        "citation_count": 0,
                        "key_finding_count": 0,
                        "limitation_count": 0,
                    },
                },
            }

        return {
            "executive_summary": executive_summary,
            "errors": [],
            "trace": [
                *trace,
                create_trace_entry(
                    node=EXECUTIVE_SUMMARY_NODE,
                    event="completed",
                    details={
                        "status": executive_summary["summary_status"],
                        "recommendation": executive_summary["recommendation"],
                    },
                ),
            ],
            "metrics": {
                **state["metrics"],
                "executive_summary": {
                    "status": executive_summary["summary_status"],
                    "recommendation": executive_summary["recommendation"],
                    "confidence": executive_summary["confidence"],
                    "latency_ms": (perf_counter() - started_at) * 1000.0,
                    "citation_count": len(executive_summary["evidence_citations"]),
                    "key_finding_count": len(executive_summary["key_findings"]),
                    "limitation_count": len(executive_summary["limitations"]),
                },
            },
        }


def _build_executive_summary(state: AgentState) -> ExecutiveSummary:
    analysis = state["experiment_analysis"]
    decision = state["decision"]
    approval = state["human_approval"]
    citations = _summary_citations(state)
    limitations = _limitations(state)
    summary_status = _summary_status(state, citations)

    if summary_status == "insufficient_data":
        headline = "Insufficient evidence to prepare an executive summary."
        recommendation = "needs_more_data"
        business_impact_summary = (
            "Business impact could not be grounded from the available evidence."
        )
        risk_summary = "Risk could not be assessed from the available evidence."
        decision_rationale = (
            "A decision-ready summary cannot be produced until the missing evidence is resolved."
        )
        recommended_next_actions = _unique(
            [
                (
                    "Resolve the target experiment, analysis, and decision artifacts "
                    "before briefing executives."
                ),
                "Re-run the workflow with grounded evidence and citations.",
            ]
        )
        confidence: DecisionConfidence = "unknown"
        key_findings: list[str] = []
    else:
        recommendation = str(decision["recommendation"])
        business_impact_summary = _business_impact_summary(state)
        risk_summary = _risk_summary(state)
        decision_rationale = (
            decision["rationale"] or "No decision rationale was recorded in shared state."
        )
        recommended_next_actions = _recommended_next_actions(state, summary_status)
        confidence = _summary_confidence(decision["confidence"])
        key_findings = _key_findings(
            analysis_summary=analysis["summary"],
            analysis_findings=analysis["findings"],
            business_impact_summary=business_impact_summary,
            risk_summary=risk_summary,
            decision_status=decision["decision_status"],
            blocking_issues=decision["blocking_issues"],
        )
        headline = _headline(
            summary_status=summary_status,
            decision_status=str(decision["decision_status"]),
            recommendation=recommendation,
            approval_status=str(approval["status"]),
        )
    approval_summary = _approval_summary(state)

    summary = _summary_text(
        headline=headline,
        recommendation=recommendation,
        business_impact_summary=business_impact_summary,
        risk_summary=risk_summary,
        decision_rationale=decision_rationale,
        approval_summary=approval_summary,
        approval_feedback=str(approval["feedback"]),
        recommended_next_actions=recommended_next_actions,
    )

    return {
        **state["executive_summary"],
        "summary_status": summary_status,
        "headline": headline,
        "recommendation": recommendation,
        "key_findings": key_findings,
        "business_impact_summary": business_impact_summary,
        "risk_summary": risk_summary,
        "decision_rationale": decision_rationale,
        "recommended_next_actions": recommended_next_actions,
        "confidence": confidence,
        "evidence_citations": citations,
        "limitations": limitations,
        "summary": summary,
    }


def _summary_status(
    state: AgentState,
    citations: list[Citation],
) -> ExecutiveSummaryStatus:
    analysis = state["experiment_analysis"]
    business_impact = state["business_impact"]
    risk_assessment = state["risk_assessment"]
    decision = state["decision"]

    if (
        analysis["status"] in {"", "not_applicable", "insufficient_data"}
        and business_impact["impact_status"] in {"", "not_required", "insufficient_data"}
        and risk_assessment["risk_status"] in {"", "not_required", "insufficient_data"}
        and decision["decision_status"] in {"", "not_required", "insufficient_data"}
        and not citations
    ):
        return "insufficient_data"

    if (
        business_impact["impact_status"]
        in {"partial_estimate", "insufficient_data", "not_required"}
        or risk_assessment["risk_status"]
        in {"partial_assessment", "insufficient_data", "not_required"}
        or decision["decision_status"] in {"needs_more_data", "blocked", "insufficient_data"}
        or analysis["status"] != "completed"
        or bool(state["errors"])
    ):
        return "partial_summary"

    return "generated"


def _headline(
    *,
    summary_status: ExecutiveSummaryStatus,
    decision_status: str,
    recommendation: str,
    approval_status: str,
) -> str:
    if summary_status == "insufficient_data":
        return "Insufficient evidence to prepare an executive summary."
    if approval_status == "rejected":
        return "The recommendation was not approved."
    if approval_status == "revision_requested":
        return "Revision was requested before approval."
    if approval_status == "pending":
        return "Recommendation is awaiting human approval."
    if approval_status == "approved" and recommendation == "rollout":
        return "Rollout is supported and approved."
    if decision_status in {"needs_more_data", "blocked", "insufficient_data"} or recommendation in {
        "continue_experiment",
        "needs_more_data",
    }:
        return "Rollout is not ready; more evidence is required."
    if recommendation == "do_not_rollout":
        return "Do not roll out based on the current evidence."
    if recommendation == "rollback":
        return "Rollback is recommended based on the current evidence."
    if recommendation == "rollout":
        return "Rollout is supported by the current evidence."
    return "Executive summary generated from the current workflow evidence."


def _business_impact_summary(state: AgentState) -> str:
    business_impact = state["business_impact"]
    summary = business_impact["summary"]
    if summary:
        return summary
    if business_impact["impact_status"] == "partial_estimate":
        return "Business impact is only partially estimated from the available evidence."
    return "Business impact could not be grounded from the available evidence."


def _risk_summary(state: AgentState) -> str:
    risk_assessment = state["risk_assessment"]
    risk_status = risk_assessment["risk_status"]
    overall_risk_level = risk_assessment["overall_risk_level"]
    factor_count = len(risk_assessment["risk_factors"])

    if risk_status == "assessed":
        if factor_count == 0:
            return (
                f"Risk is currently assessed as {overall_risk_level} with no material "
                "blocking factors recorded."
            )
        noun = "factor" if factor_count == 1 else "factors"
        return (
            f"Risk is currently assessed as {overall_risk_level} with {factor_count} material "
            f"{noun} recorded."
        )
    if risk_status == "partial_assessment":
        return "Risk review is incomplete and should not be treated as final."
    return "Risk could not be assessed from the available evidence."


def _recommended_next_actions(
    state: AgentState,
    summary_status: ExecutiveSummaryStatus,
) -> list[str]:
    decision_actions = list(state["decision"]["recommended_next_actions"])
    if decision_actions:
        return _unique(decision_actions)

    actions: list[str] = []
    if summary_status != "generated":
        actions.append(
            "Resolve the missing evidence before making a rollout-sensitive executive call."
        )
    actions.extend(state["risk_assessment"]["mitigation_actions"])
    if not actions:
        actions.append("Review the supporting analysis before taking the next rollout step.")
    return _unique(actions)


def _summary_confidence(confidence: str) -> DecisionConfidence:
    normalized = (confidence or "").strip().lower()
    if normalized in {"high", "medium", "low", "unknown"}:
        return normalized  # type: ignore[return-value]
    return "unknown"


def _key_findings(
    *,
    analysis_summary: str,
    analysis_findings: list[str],
    business_impact_summary: str,
    risk_summary: str,
    decision_status: str,
    blocking_issues: list[str],
) -> list[str]:
    findings = [analysis_summary, *analysis_findings[:2], business_impact_summary, risk_summary]
    if decision_status in {"needs_more_data", "blocked", "insufficient_data"}:
        findings.extend(blocking_issues[:2])
    return _unique([finding for finding in findings if finding])


def _summary_text(
    *,
    headline: str,
    recommendation: str,
    business_impact_summary: str,
    risk_summary: str,
    decision_rationale: str,
    approval_summary: str,
    approval_feedback: str,
    recommended_next_actions: list[str],
) -> str:
    sentences = [
        headline,
        f"Recommendation: {recommendation}.",
        business_impact_summary,
        risk_summary,
        decision_rationale,
        approval_summary,
    ]
    if approval_feedback:
        sentences.append(f"Approval feedback: {approval_feedback}")
    if recommended_next_actions:
        sentences.append(f"Next action: {recommended_next_actions[0]}")
    return " ".join(sentence for sentence in sentences if sentence)


def _approval_summary(state: AgentState) -> str:
    approval = state["human_approval"]
    if approval["status"] == "skipped":
        return "Approval was not required for this recommendation."
    if approval["status"] == "pending":
        return "The recommendation is awaiting human approval."
    if approval["status"] == "approved":
        return "The recommendation was approved."
    if approval["status"] == "rejected":
        return "The recommendation was not approved."
    if approval["status"] == "revision_requested":
        return "Revision was requested before approval."
    return ""


def _summary_citations(state: AgentState) -> list[Citation]:
    seen: set[tuple[str, str, str, str]] = set()
    citations: list[Citation] = []
    for citation in [
        *state["experiment_analysis"]["evidence_citations"],
        *state["business_impact"]["evidence_citations"],
        *state["risk_assessment"]["evidence_citations"],
        *state["decision"]["evidence_citations"],
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


def _limitations(state: AgentState) -> list[str]:
    analysis = state["experiment_analysis"]
    business_impact = state["business_impact"]
    risk_assessment = state["risk_assessment"]
    decision = state["decision"]
    limitations = [
        *analysis["limitations"],
        *business_impact["limitations"],
        *risk_assessment["limitations"],
        *decision["limitations"],
    ]
    if analysis["status"] != "completed":
        limitations.append(f"Experiment analysis status is {analysis['status']}.")
    if business_impact["impact_status"] == "partial_estimate":
        limitations.append("Business impact is incomplete and should be treated as directional.")
    elif business_impact["impact_status"] in {"insufficient_data", "not_required"}:
        limitations.append("Business impact evidence is missing or insufficient.")
    if risk_assessment["risk_status"] == "partial_assessment":
        limitations.append("Risk assessment is incomplete and should not be treated as final.")
    elif risk_assessment["risk_status"] in {"insufficient_data", "not_required"}:
        limitations.append("Risk evidence is missing or insufficient.")
    if decision["decision_status"] in {"needs_more_data", "blocked", "insufficient_data"}:
        limitations.extend(decision["blocking_issues"])
    approval = state["human_approval"]
    if approval["status"] == "pending":
        limitations.append("Human approval is still pending.")
    elif approval["status"] == "rejected":
        limitations.append("The recommendation was not approved.")
    elif approval["status"] == "revision_requested":
        limitations.append("Revision was requested before approval.")
    if approval["feedback"]:
        limitations.append(f"Approval feedback: {approval['feedback']}")
    for error in state["errors"]:
        code = str(error.get("code", "")).strip()
        message = str(error.get("message", "")).strip()
        if code and message:
            limitations.append(f"{code}: {message}")
    return _unique(limitations)


def _unique(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
