"""Shared LangGraph state contract for the internal Phase 2 agent workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, TypeAdapter
from typing_extensions import TypedDict

AgentIntent = Literal[
    "general_question",
    "experiment_lookup",
    "decision_support",
    "risk_assessment",
    "business_impact",
    "executive_summary",
    "unknown",
]
RequiredAgent = Literal[
    "planner",
    "retrieval",
    "experiment_analysis",
    "business_impact",
    "risk_assessment",
    "decision",
    "executive_summary",
    "human_approval",
]
HumanApprovalStatus = Literal[
    "not_requested",
    "skipped",
    "pending",
    "approved",
    "rejected",
    "revision_requested",
]
ToolCallStatus = Literal["pending", "completed", "failed"]
BusinessImpactStatus = Literal[
    "estimated",
    "partial_estimate",
    "insufficient_data",
    "not_required",
]
RiskAssessmentStatus = Literal[
    "assessed",
    "partial_assessment",
    "insufficient_data",
    "not_required",
]
OverallRiskLevel = Literal["low", "medium", "high", "unknown"]
DecisionStatus = Literal[
    "decided",
    "needs_more_data",
    "blocked",
    "not_required",
    "insufficient_data",
]
DecisionRecommendation = Literal[
    "rollout",
    "do_not_rollout",
    "continue_experiment",
    "rollback",
    "needs_more_data",
    "unknown",
]
DecisionConfidence = Literal["high", "medium", "low", "unknown"]
ExecutiveSummaryStatus = Literal[
    "generated",
    "partial_summary",
    "insufficient_data",
    "not_required",
]


class AgentInputState(BaseModel):
    question: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentRequest(TypedDict):
    question: str
    normalized_question: str


class ExperimentContext(TypedDict):
    experiment_ids: list[str]
    filters: dict[str, object]


class RetrievedChunk(TypedDict, total=False):
    chunk_id: str
    document_id: str
    experiment_id: str
    content: str
    score: float
    metadata: dict[str, object]


class Citation(TypedDict, total=False):
    chunk_id: str
    document_id: str
    experiment_id: str
    quote: str
    section: str
    metadata: dict[str, object]


class MetricVariantRecord(TypedDict, total=False):
    metric_name: str
    variant: str
    value: float
    unit: str
    numerator: float
    denominator: float
    notes: str


class MetricComparisonRecord(TypedDict, total=False):
    metric_name: str
    control_value: float
    treatment_value: float
    absolute_delta: float
    relative_lift: float
    unit: str
    p_value: float


class ExperimentAnalysis(TypedDict):
    summary: str
    findings: list[str]
    status: str
    experiment_id: str
    experiment_name: str
    hypothesis: str
    primary_metric: str
    control: MetricVariantRecord
    treatment: MetricVariantRecord
    treatment_control_comparison: MetricComparisonRecord
    observed_lift: MetricComparisonRecord
    statistical_significance: dict[str, object]
    confidence_level: dict[str, object]
    guardrail_metrics: list[MetricComparisonRecord]
    limitations: list[str]
    evidence_citations: list[Citation]
    analysis_confidence: str


class ExperimentMetadata(TypedDict, total=False):
    experiment_id: str
    name: str
    area: str
    hypothesis: str
    owner: dict[str, object]
    status: str
    start_date: str
    end_date: str
    primary_metric: str
    secondary_metrics: list[str]
    imperfections: list[str]
    business_decision: str


class ExperimentMetricRecord(TypedDict, total=False):
    metric_name: str
    variant: str
    value: float
    unit: str
    numerator: float
    denominator: float
    notes: str
    lift_vs_control: float
    p_value: float


class BusinessImpact(TypedDict):
    summary: str
    impact_status: BusinessImpactStatus
    primary_business_metric: str
    baseline_value: float | None
    treatment_value: float | None
    absolute_lift: float | None
    relative_lift: float | None
    estimated_annualized_impact: dict[str, object] | None
    affected_segment: str
    operational_savings: dict[str, object] | None
    confidence_level: str
    assumptions: list[str]
    limitations: list[str]
    evidence_citations: list[Citation]


class RiskFactor(TypedDict, total=False):
    code: str
    title: str
    severity: str
    category: str
    detail: str
    mitigation: str


class RiskAssessment(TypedDict):
    risk_status: RiskAssessmentStatus
    overall_risk_level: OverallRiskLevel
    risk_score: int | None
    risk_factors: list[RiskFactor]
    guardrail_concerns: list[str]
    data_quality_concerns: list[str]
    statistical_concerns: list[str]
    rollout_concerns: list[str]
    user_or_business_concerns: list[str]
    mitigation_actions: list[str]
    assumptions: list[str]
    limitations: list[str]
    evidence_citations: list[Citation]
    confidence_level: str


class RiskRecord(TypedDict, total=False):
    title: str
    severity: str
    detail: str
    mitigation: str


class DecisionRecord(TypedDict):
    decision_status: DecisionStatus
    recommendation: DecisionRecommendation
    confidence: DecisionConfidence
    rationale: str
    supporting_evidence: list[str]
    blocking_issues: list[str]
    recommended_next_actions: list[str]
    approval_required: bool
    evidence_citations: list[Citation]
    assumptions: list[str]
    limitations: list[str]


class ExecutiveSummary(TypedDict):
    summary_status: ExecutiveSummaryStatus
    headline: str
    recommendation: str
    key_findings: list[str]
    business_impact_summary: str
    risk_summary: str
    decision_rationale: str
    recommended_next_actions: list[str]
    confidence: DecisionConfidence
    evidence_citations: list[Citation]
    limitations: list[str]
    summary: str


class HumanApprovalInputRecord(TypedDict, total=False):
    status: str
    feedback: object
    actor: object
    timestamp: object


class HumanApprovalRecord(TypedDict):
    status: HumanApprovalStatus
    required: bool
    feedback: str
    actor: str | None
    timestamp: str | None


class ToolCallRecord(TypedDict, total=False):
    tool_name: str
    status: ToolCallStatus
    arguments: dict[str, object]
    result: dict[str, object]
    error: str
    at: str


class ErrorRecord(TypedDict, total=False):
    code: str
    message: str
    node: str
    details: dict[str, object]
    at: str


class TraceEntry(TypedDict, total=False):
    node: str
    event: str
    details: dict[str, object]
    at: str


class StateTimestamps(TypedDict):
    created_at: str
    updated_at: str


class RunMetadata(TypedDict):
    run_id: str
    workflow: str
    state_version: int


def append_str_list(current: list[str], update: list[str] | None) -> list[str]:
    if update is None:
        return current
    return [*current, *update]


def append_dict_list[T](
    current: list[T],
    update: list[T] | None,
) -> list[T]:
    if update is None:
        return current
    return [*current, *update]


class AgentState(TypedDict):
    question: str
    request: AgentRequest
    intent: AgentIntent
    required_agents: list[RequiredAgent]
    planner_notes: str
    experiment_context: ExperimentContext
    retrieved_chunks: list[RetrievedChunk]
    citations: list[Citation]
    experiment_analysis: ExperimentAnalysis
    experiment_metadata: ExperimentMetadata
    experiment_metrics: list[ExperimentMetricRecord]
    business_impact: BusinessImpact
    risk_assessment: RiskAssessment
    risks: list[RiskRecord]
    decision: DecisionRecord
    executive_summary: ExecutiveSummary
    human_approval_input: HumanApprovalInputRecord
    human_approval: HumanApprovalRecord
    tool_calls: Annotated[list[ToolCallRecord], append_dict_list]
    metrics: dict[str, object]
    errors: Annotated[list[ErrorRecord], append_dict_list]
    trace: Annotated[list[TraceEntry], append_dict_list]
    timestamps: StateTimestamps
    run_metadata: RunMetadata


class AgentStateUpdate(TypedDict, total=False):
    request: AgentRequest
    intent: AgentIntent
    required_agents: list[RequiredAgent]
    planner_notes: str
    experiment_context: ExperimentContext
    retrieved_chunks: list[RetrievedChunk]
    citations: list[Citation]
    experiment_analysis: ExperimentAnalysis
    experiment_metadata: ExperimentMetadata
    experiment_metrics: list[ExperimentMetricRecord]
    business_impact: BusinessImpact
    risk_assessment: RiskAssessment
    risks: list[RiskRecord]
    decision: DecisionRecord
    executive_summary: ExecutiveSummary
    human_approval_input: HumanApprovalInputRecord
    human_approval: HumanApprovalRecord
    tool_calls: list[ToolCallRecord]
    metrics: dict[str, object]
    errors: list[ErrorRecord]
    trace: list[TraceEntry]
    timestamps: StateTimestamps
    run_metadata: RunMetadata


AGENT_STATE_ADAPTER = TypeAdapter(AgentState)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _updated_timestamps(timestamps: StateTimestamps) -> StateTimestamps:
    return {
        "created_at": timestamps["created_at"],
        "updated_at": _utc_now_iso(),
    }


def create_trace_entry(
    *,
    node: str,
    event: str,
    details: dict[str, object] | None = None,
    at: str | None = None,
) -> TraceEntry:
    entry: TraceEntry = {
        "node": node,
        "event": event,
        "at": at or _utc_now_iso(),
    }
    if details:
        entry["details"] = details
    return entry


def create_error_entry(
    *,
    code: str,
    message: str,
    node: str | None = None,
    details: dict[str, object] | None = None,
    at: str | None = None,
) -> ErrorRecord:
    entry: ErrorRecord = {
        "code": code,
        "message": message,
        "at": at or _utc_now_iso(),
    }
    if node is not None:
        entry["node"] = node
    if details:
        entry["details"] = details
    return entry


def create_initial_state(question: str) -> AgentState:
    normalized_question = question.strip()
    now = _utc_now_iso()
    return {
        "question": question,
        "request": {
            "question": question,
            "normalized_question": normalized_question,
        },
        "intent": "unknown",
        "required_agents": [],
        "planner_notes": "",
        "experiment_context": {
            "experiment_ids": [],
            "filters": {},
        },
        "retrieved_chunks": [],
        "citations": [],
        "experiment_analysis": {
            "summary": "",
            "findings": [],
            "status": "not_applicable",
            "experiment_id": "",
            "experiment_name": "",
            "hypothesis": "",
            "primary_metric": "",
            "control": {},
            "treatment": {},
            "treatment_control_comparison": {},
            "observed_lift": {},
            "statistical_significance": {},
            "confidence_level": {},
            "guardrail_metrics": [],
            "limitations": [],
            "evidence_citations": [],
            "analysis_confidence": "low",
        },
        "experiment_metadata": {},
        "experiment_metrics": [],
        "business_impact": {
            "summary": "",
            "impact_status": "not_required",
            "primary_business_metric": "",
            "baseline_value": None,
            "treatment_value": None,
            "absolute_lift": None,
            "relative_lift": None,
            "estimated_annualized_impact": None,
            "affected_segment": "",
            "operational_savings": None,
            "confidence_level": "low",
            "assumptions": [],
            "limitations": [],
            "evidence_citations": [],
        },
        "risk_assessment": {
            "risk_status": "not_required",
            "overall_risk_level": "unknown",
            "risk_score": None,
            "risk_factors": [],
            "guardrail_concerns": [],
            "data_quality_concerns": [],
            "statistical_concerns": [],
            "rollout_concerns": [],
            "user_or_business_concerns": [],
            "mitigation_actions": [],
            "assumptions": [],
            "limitations": [],
            "evidence_citations": [],
            "confidence_level": "low",
        },
        "risks": [],
        "decision": {
            "decision_status": "not_required",
            "recommendation": "unknown",
            "confidence": "unknown",
            "rationale": "",
            "supporting_evidence": [],
            "blocking_issues": [],
            "recommended_next_actions": [],
            "approval_required": False,
            "evidence_citations": [],
            "assumptions": [],
            "limitations": [],
        },
        "executive_summary": {
            "summary_status": "not_required",
            "headline": "",
            "recommendation": "",
            "key_findings": [],
            "business_impact_summary": "",
            "risk_summary": "",
            "decision_rationale": "",
            "recommended_next_actions": [],
            "confidence": "unknown",
            "evidence_citations": [],
            "limitations": [],
            "summary": "",
        },
        "human_approval_input": {},
        "human_approval": {
            "status": "not_requested",
            "required": False,
            "feedback": "",
            "actor": None,
            "timestamp": None,
        },
        "tool_calls": [],
        "metrics": {},
        "errors": [],
        "trace": [],
        "timestamps": {
            "created_at": now,
            "updated_at": now,
        },
        "run_metadata": {
            "run_id": str(uuid4()),
            "workflow": "phase2_shared_state",
            "state_version": 9,
        },
    }


def build_initial_state(question: str) -> AgentState:
    return create_initial_state(question)


def append_trace(
    state: AgentState,
    *,
    node: str,
    event: str,
    details: dict[str, object] | None = None,
) -> AgentState:
    updated = {
        **state,
        "trace": [
            *state["trace"],
            create_trace_entry(node=node, event=event, details=details),
        ],
        "timestamps": _updated_timestamps(state["timestamps"]),
    }
    return validate_state_shape(updated)


def append_error(
    state: AgentState,
    *,
    code: str,
    message: str,
    node: str | None = None,
    details: dict[str, object] | None = None,
) -> AgentState:
    updated = {
        **state,
        "errors": [
            *state["errors"],
            create_error_entry(
                code=code,
                message=message,
                node=node,
                details=details,
            ),
        ],
        "timestamps": _updated_timestamps(state["timestamps"]),
    }
    return validate_state_shape(updated)


def record_metric(state: AgentState, name: str, value: object) -> AgentState:
    updated = {
        **state,
        "metrics": {
            **state["metrics"],
            name: value,
        },
        "timestamps": _updated_timestamps(state["timestamps"]),
    }
    return validate_state_shape(updated)


def validate_state_shape(state: object) -> AgentState:
    return AGENT_STATE_ADAPTER.validate_python(state)
