"""Role-scoped graph publication against a request-local authoritative store."""

from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.agents.state import AgentState, AgentStateUpdate, Citation

    from .service import AnalysisService

from .results import AnalysisResultEnvelope


def artifact_citations(result: AnalysisResultEnvelope, experiment_id: str) -> list["Citation"]:
    return [
        {
            "artifact_id": artifact.artifact_id,
            "schema_version": "1",
            "experiment_id": experiment_id,
            "section": "Structured analysis",
            "metadata": {
                "source_type": "analysis_artifact",
                "artifact_kind": artifact.kind,
                "version": artifact.version,
                "evidence_fingerprint": artifact.evidence_fingerprint,
            },
        }
        for artifact in result.artifacts
    ]


def protect_update(
    *,
    node: str,
    current: "AgentState",
    proposed: "AgentStateUpdate",
    analysis_service: "AnalysisService",
) -> "AgentStateUpdate":
    from packages.agents.decision_agent import DecisionAgent
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent
    from packages.agents.human_approval_agent import HumanApprovalAgent
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent
    from packages.agents.state import create_trace_entry

    prior = current.get("analysis_result")
    candidate = proposed.get("analysis_result")
    reference = prior or candidate
    if reference is None:
        return proposed
    canonical = analysis_service.authoritative_result(reference.analysis_id)
    trusted = deepcopy(current)
    trusted["analysis_result"] = canonical
    request = trusted.get("analysis_request")
    citations = artifact_citations(canonical, request.experiment_id if request else "")
    trusted["citations"] = citations
    canonical_update: AgentStateUpdate = {}
    # Only required deterministic consumers can publish narratives. Injected
    # candidates are checked but cannot authorize additional state writes.
    if node in current["required_agents"]:
        if node == "risk_assessment":
            canonical_update = RiskAssessmentAgent().run(trusted)
        elif node == "decision":
            canonical_update = DecisionAgent().run(trusted)
        elif node == "human_approval":
            canonical_update = HumanApprovalAgent().run(trusted)
        elif node == "executive_summary":
            canonical_update = ExecutiveSummaryAgent().run(trusted)
    ignored = {"trace", "metrics", "errors", "tool_calls", "analysis_result"}
    conflict = "analysis_result" in proposed and candidate != canonical
    for key, value in proposed.items():
        if key not in ignored and value != canonical_update.get(key):
            conflict = True
    if conflict:
        canonical = analysis_service.record_integrity(
            canonical.analysis_id, node=node, code="analysis.integrity.rejected_update"
        )
    result: AgentStateUpdate = {
        **canonical_update,
        "analysis_result": canonical,
        "citations": citations,
        "trace": [
            create_trace_entry(node=node, event="started"),
            create_trace_entry(
                node=node,
                event="completed" if node in current["required_agents"] else "skipped",
                details={"status": canonical.status},
            ),
        ],
    }
    result["metrics"] = {
        **current["metrics"],
        node: {"status": canonical.status, "method": canonical.method},
    }
    return result


def protect_response(state: "AgentState", analysis_service: "AnalysisService") -> "AgentState":
    protected = deepcopy(state)
    result = protected.get("analysis_result")
    if result is None:
        return protected
    canonical = analysis_service.authoritative_result(result.analysis_id)
    if result != canonical:
        canonical = analysis_service.record_integrity(
            result.analysis_id, node="response", code="analysis.integrity.response_mismatch"
        )
    protected["analysis_result"] = canonical
    return protected
