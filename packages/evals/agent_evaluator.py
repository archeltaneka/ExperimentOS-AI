from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from packages.agents.business_impact_agent import BusinessImpactAgent
from packages.agents.decision_agent import DecisionAgent
from packages.agents.executive_summary_agent import ExecutiveSummaryAgent
from packages.agents.human_approval_agent import HUMAN_APPROVAL_NODE
from packages.agents.observability import extract_workflow_observation
from packages.agents.risk_assessment_agent import RiskAssessmentAgent
from packages.agents.service import AgentWorkflowService
from packages.agents.state import AgentState, AgentStateUpdate, create_trace_entry
from packages.evals.agent_dataset import AgentEvaluationCase
from packages.evals.agent_metrics import (
    AgentEvaluationSummary,
    AgentSampleMetrics,
    calculate_agent_sample_metrics,
)


class AgentWorkflowServiceLike(Protocol):
    def run(self, question: str) -> AgentState:
        pass


@dataclass(frozen=True)
class AgentEvaluationSampleResult:
    case: AgentEvaluationCase
    state: AgentState | None
    observation: object | None
    metrics: AgentSampleMetrics | None
    error: str | None


@dataclass(frozen=True)
class AgentEvaluationRun:
    samples: list[AgentEvaluationSampleResult]
    summary: AgentEvaluationSummary


class AgentWorkflowEvaluator:
    def __init__(
        self,
        *,
        workflow_service: AgentWorkflowServiceLike,
        cases: list[AgentEvaluationCase],
    ) -> None:
        self.workflow_service = workflow_service
        self.cases = list(cases)

    def evaluate(self) -> AgentEvaluationRun:
        samples: list[AgentEvaluationSampleResult] = []
        for case in self.cases:
            try:
                state = self.workflow_service.run(case.question)
                observation = extract_workflow_observation(state)
                metrics = calculate_agent_sample_metrics(case=case, observation=observation)
                samples.append(
                    AgentEvaluationSampleResult(
                        case=case,
                        state=state,
                        observation=observation,
                        metrics=metrics,
                        error=None,
                    )
                )
            except Exception as exc:
                samples.append(
                    AgentEvaluationSampleResult(
                        case=case,
                        state=None,
                        observation=None,
                        metrics=None,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        return AgentEvaluationRun(
            samples=samples,
            summary=AgentEvaluationSummary.from_samples(samples),
        )


def build_default_agent_workflow_service() -> AgentWorkflowService:
    return AgentWorkflowService(
        retrieval_agent=_EvaluationRetrievalAgent(),
        experiment_analysis_agent=_EvaluationExperimentAnalysisAgent(),
        business_impact_agent=BusinessImpactAgent(),
        risk_assessment_agent=RiskAssessmentAgent(),
        decision_agent=DecisionAgent(),
        human_approval_agent=_EvaluationHumanApprovalAgent(),
        executive_summary_agent=ExecutiveSummaryAgent(),
    )


@dataclass
class _EvaluationRetrievalAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        bundle = _evaluation_bundle(state["question"])
        return {
            "retrieved_chunks": bundle["retrieved_chunks"],
            "citations": bundle["citations"],
            "metrics": {
                **state["metrics"],
                "retrieval": {
                    "embedding_time_ms": 10.0,
                    "vector_search_time_ms": 8.0,
                    "retrieved_chunks": len(bundle["retrieved_chunks"]),
                    "average_similarity": 0.91,
                },
            },
            "errors": [],
            "trace": [
                create_trace_entry(node="retrieval", event="started"),
                create_trace_entry(
                    node="retrieval",
                    event="completed",
                    details={"retrieved_chunks": len(bundle["retrieved_chunks"])},
                ),
            ],
        }


@dataclass
class _EvaluationExperimentAnalysisAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        bundle = _evaluation_bundle(state["question"])
        analysis = bundle["analysis"]
        return {
            "experiment_analysis": {
                **state["experiment_analysis"],
                **analysis,
                "evidence_citations": list(state["citations"]),
            },
            "experiment_metadata": dict(bundle["experiment_metadata"]),
            "experiment_metrics": list(bundle["experiment_metrics"]),
            "errors": [],
            "trace": [
                create_trace_entry(node="experiment_analysis", event="started"),
                create_trace_entry(
                    node="experiment_analysis",
                    event="completed",
                    details={"status": analysis["status"]},
                ),
            ],
            "metrics": {
                **state["metrics"],
                "experiment_analysis": {
                    "status": analysis["status"],
                    "latency_ms": max((perf_counter() - started_at) * 1000.0, 0.0),
                    "citation_count": len(state["citations"]),
                },
            },
        }


@dataclass
class _EvaluationHumanApprovalAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        question = state["question"].lower()
        if "executive" in question:
            approval = {
                "status": "pending",
                "required": True,
                "feedback": "",
                "actor": None,
                "timestamp": None,
            }
        else:
            approval = {
                "status": "approved",
                "required": True,
                "feedback": "Approved for a monitored rollout.",
                "actor": "director@example.com",
                "timestamp": "2026-07-09T00:00:00Z",
            }
        return {
            "human_approval": approval,
            "errors": [],
            "trace": [
                create_trace_entry(node=HUMAN_APPROVAL_NODE, event="started"),
                create_trace_entry(
                    node=HUMAN_APPROVAL_NODE,
                    event="completed",
                    details={"status": approval["status"]},
                ),
            ],
            "metrics": {
                **state["metrics"],
                "human_approval": {
                    "status": approval["status"],
                    "latency_ms": max((perf_counter() - started_at) * 1000.0, 0.0),
                    "approval_required": approval["required"],
                    "input_present": bool(state["human_approval_input"]),
                },
            },
        }


def _evaluation_bundle(question: str) -> dict[str, object]:
    normalized = question.lower()
    if "checkout" in normalized:
        experiment_id = "exp-004-checkout-ux"
        experiment_name = "Checkout UX Streamlining"
        primary_metric = "checkout_completion_rate"
        baseline = 0.41
        treatment = 0.46
        annualized_amount = 640000.0
        affected_segment = "mobile checkout"
    else:
        experiment_id = "exp-001-payment-recommendation"
        experiment_name = "Adaptive Payment Method Recommendation"
        primary_metric = "payment_success_rate"
        baseline = 0.67
        treatment = 0.73
        annualized_amount = 910000.0
        affected_segment = "wallet users"

    relative_lift = round((treatment - baseline) / baseline, 6)
    citations = [
        {
            "document_id": f"{experiment_id}-doc-1",
            "experiment_id": experiment_id,
            "quote": "Primary metric improved in treatment.",
            "section": "Results",
            "metadata": {
                "section": "Results",
                "affected_segment": affected_segment,
            },
        },
        {
            "document_id": f"{experiment_id}-doc-2",
            "experiment_id": experiment_id,
            "quote": f"Annualized impact was USD {annualized_amount:,.0f}.",
            "section": "Recommendation",
            "metadata": {
                "section": "Recommendation",
                "affected_segment": affected_segment,
                "estimated_annualized_impact": {
                    "amount": annualized_amount,
                    "currency": "USD",
                    "period": "annual",
                },
            },
        },
    ]
    return {
        "retrieved_chunks": [
            {
                "document_id": citation["document_id"],
                "experiment_id": experiment_id,
                "content": str(citation["quote"]),
                "score": 0.91,
                "metadata": dict(citation["metadata"]),
            }
            for citation in citations
        ],
        "citations": citations,
        "analysis": {
            "summary": f"{experiment_name} improved {primary_metric} in treatment.",
            "findings": [
                f"Primary metric {primary_metric} improved from {baseline:.2f} to {treatment:.2f}.",
                "Statistical significance cleared the threshold.",
            ],
            "status": "completed",
            "experiment_id": experiment_id,
            "experiment_name": experiment_name,
            "hypothesis": "Reducing friction should improve the primary conversion metric.",
            "primary_metric": primary_metric,
            "control": {
                "metric_name": primary_metric,
                "variant": "control",
                "value": baseline,
            },
            "treatment": {
                "metric_name": primary_metric,
                "variant": "treatment",
                "value": treatment,
            },
            "treatment_control_comparison": {
                "metric_name": primary_metric,
                "control_value": baseline,
                "treatment_value": treatment,
                "absolute_delta": round(treatment - baseline, 6),
                "relative_lift": relative_lift,
                "p_value": 0.02,
            },
            "observed_lift": {
                "metric_name": primary_metric,
                "relative_lift": relative_lift,
                "p_value": 0.02,
            },
            "statistical_significance": {"p_value": 0.02, "is_significant": True},
            "confidence_level": {"confidence_level": 0.95},
            "guardrail_metrics": [
                {
                    "metric_name": "completion_rate",
                    "control_value": 0.32,
                    "treatment_value": 0.35,
                    "absolute_delta": 0.03,
                    "relative_lift": 0.09375,
                }
            ],
            "limitations": [],
            "analysis_confidence": "high",
        },
        "experiment_metadata": {
            "experiment_id": experiment_id,
            "name": experiment_name,
            "hypothesis": "Reducing friction should improve the primary conversion metric.",
            "primary_metric": primary_metric,
            "business_decision": "Roll out gradually after approval.",
            "affected_segment": affected_segment,
            "estimated_annualized_impact": {
                "amount": annualized_amount,
                "currency": "USD",
                "period": "annual",
            },
        },
        "experiment_metrics": [
            {"metric_name": primary_metric, "variant": "control", "value": baseline},
            {"metric_name": primary_metric, "variant": "treatment", "value": treatment},
        ],
    }
