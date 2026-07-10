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
from packages.observability.base import BaseObservabilityProvider


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


def build_default_agent_workflow_service(
    observability_provider: BaseObservabilityProvider | None = None,
) -> AgentWorkflowService:
    return AgentWorkflowService(
        retrieval_agent=_EvaluationRetrievalAgent(),
        experiment_analysis_agent=_EvaluationExperimentAnalysisAgent(),
        business_impact_agent=BusinessImpactAgent(),
        risk_assessment_agent=RiskAssessmentAgent(),
        decision_agent=DecisionAgent(),
        human_approval_agent=_EvaluationHumanApprovalAgent(),
        executive_summary_agent=ExecutiveSummaryAgent(),
        observability_provider=observability_provider,
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
        approval_required = bool(state["decision"].get("approval_required"))
        if not approval_required:
            approval = {
                "status": "not_requested",
                "required": False,
                "feedback": "",
                "actor": None,
                "timestamp": None,
            }
        elif "revision" in question or "revise" in question:
            approval = {
                "status": "revision_requested",
                "required": True,
                "feedback": "Clarify the rollout guardrails and supporting evidence.",
                "actor": "director@example.com",
                "timestamp": "2026-07-09T00:00:00Z",
            }
        elif "pricing" in question:
            approval = {
                "status": "rejected",
                "required": True,
                "feedback": "Margin dilution is not acceptable for rollout.",
                "actor": "director@example.com",
                "timestamp": "2026-07-09T00:00:00Z",
            }
        elif "executive" in question:
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
    profile = _evaluation_profile(normalized)
    experiment_id = str(profile["experiment_id"])
    experiment_name = str(profile["experiment_name"])
    primary_metric = str(profile["primary_metric"])
    baseline = profile["baseline"]
    treatment = profile["treatment"]
    annualized_amount = profile["annualized_amount"]
    affected_segment = str(profile["affected_segment"])
    findings = list(profile["findings"])
    limitations = list(profile["limitations"])
    imperfections = list(profile["imperfections"])
    business_decision = str(profile["business_decision"])
    analysis_confidence = str(profile["analysis_confidence"])
    citations = list(profile["citations"])

    relative_lift = None
    absolute_delta = None
    if isinstance(baseline, float) and isinstance(treatment, float) and baseline != 0:
        relative_lift = round((treatment - baseline) / baseline, 6)
        absolute_delta = round(treatment - baseline, 6)

    annualized_metadata = None
    if isinstance(annualized_amount, float):
        annualized_metadata = {
            "amount": annualized_amount,
            "currency": "USD",
            "period": "annual",
        }

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
            "summary": str(profile["analysis_summary"]),
            "findings": findings,
            "status": str(profile["analysis_status"]),
            "experiment_id": experiment_id,
            "experiment_name": experiment_name,
            "hypothesis": str(profile["hypothesis"]),
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
                "absolute_delta": absolute_delta,
                "relative_lift": relative_lift,
                "p_value": profile["p_value"],
            },
            "observed_lift": {
                "metric_name": primary_metric,
                "relative_lift": relative_lift,
                "p_value": profile["p_value"],
            },
            "statistical_significance": dict(profile["statistical_significance"]),
            "confidence_level": {"confidence_level": profile["confidence_score"]},
            "guardrail_metrics": list(profile["guardrail_metrics"]),
            "limitations": limitations,
            "analysis_confidence": analysis_confidence,
        },
        "experiment_metadata": {
            "experiment_id": experiment_id,
            "name": experiment_name,
            "hypothesis": str(profile["hypothesis"]),
            "primary_metric": primary_metric,
            "business_decision": business_decision,
            "affected_segment": affected_segment,
            "estimated_annualized_impact": annualized_metadata,
            "imperfections": imperfections,
        },
        "experiment_metrics": _experiment_metrics(
            primary_metric=primary_metric,
            baseline=baseline,
            treatment=treatment,
        ),
    }


def _evaluation_profile(normalized_question: str) -> dict[str, object]:
    if "pricing" in normalized_question:
        return {
            "experiment_id": "exp-005-pricing",
            "experiment_name": "Transparent Discount Price Framing",
            "primary_metric": "gross_margin_per_visitor",
            "baseline": 4.86,
            "treatment": 4.71,
            "annualized_amount": None,
            "affected_segment": "discount-sensitive shoppers",
            "analysis_status": "completed",
            "analysis_summary": (
                "Transparent Discount Price Framing reduced gross_margin_per_visitor in treatment."
            ),
            "hypothesis": (
                "Showing the final discounted price earlier will improve conversion while "
                "preserving gross margin."
            ),
            "findings": [
                "Primary metric gross_margin_per_visitor declined from 4.86 to 4.71.",
                "Conversion gains did not offset margin dilution.",
            ],
            "limitations": [
                (
                    "Seasonality from end-of-quarter promotions inflated baseline "
                    "discount sensitivity."
                ),
            ],
            "imperfections": [
                (
                    "Seasonality from end-of-quarter promotions inflated baseline "
                    "discount sensitivity."
                ),
                "Country-specific behaviour: Germany showed margin loss despite flat conversion.",
            ],
            "business_decision": (
                "Do not roll out; conversion gain did not offset margin dilution."
            ),
            "analysis_confidence": "high",
            "confidence_score": 0.95,
            "p_value": 0.02,
            "statistical_significance": {"p_value": 0.02, "is_significant": True},
            "guardrail_metrics": [],
            "citations": [
                {
                    "document_id": "exp-005-pricing-doc-1",
                    "experiment_id": "exp-005-pricing",
                    "quote": (
                        "Control recorded 4.8600 on gross_margin_per_visitor, while "
                        "treatment recorded 4.7100."
                    ),
                    "section": "Results",
                    "metadata": {
                        "section": "Results",
                        "affected_segment": "discount-sensitive shoppers",
                    },
                },
                {
                    "document_id": "exp-005-pricing-doc-2",
                    "experiment_id": "exp-005-pricing",
                    "quote": "Do not roll out; conversion gain did not offset margin dilution.",
                    "section": "Recommendation",
                    "metadata": {
                        "section": "Recommendation",
                        "affected_segment": "discount-sensitive shoppers",
                    },
                },
            ],
        }
    if "premium subscription" in normalized_question:
        return {
            "experiment_id": "exp-010-premium-subscriptions",
            "experiment_name": "Premium Subscription Trial Offer",
            "primary_metric": "trial_start_rate",
            "baseline": None,
            "treatment": None,
            "annualized_amount": None,
            "affected_segment": "eligible non-subscribers",
            "analysis_status": "completed",
            "analysis_summary": (
                "Premium Subscription Trial Offer showed directional trial-start movement, but "
                "the grounded business read remains incomplete."
            ),
            "hypothesis": (
                "A contextual premium trial offer should increase trial starts without "
                "cannibalizing annual plans."
            ),
            "findings": [
                "Trial-start tracking lagged for Apple in-app subscriptions.",
                "Annual-plan cannibalization guardrails still need validation.",
            ],
            "limitations": [
                (
                    "Business impact could not be estimated because baseline, "
                    "treatment, and observed lift data were unavailable."
                ),
                "No explicit annualized impact was available in shared state evidence.",
            ],
            "imperfections": [
                "Trial-start tracking lagged for Apple in-app subscriptions.",
                "July holiday planning lifted interest in AU and US.",
            ],
            "business_decision": (
                "Roll out to eligible non-subscribers with annual-plan exclusion logic."
            ),
            "analysis_confidence": "medium",
            "confidence_score": 0.7,
            "p_value": None,
            "statistical_significance": {},
            "guardrail_metrics": [],
            "citations": [
                {
                    "document_id": "exp-010-premium-subscriptions-doc-1",
                    "experiment_id": "exp-010-premium-subscriptions",
                    "quote": "Trial-start tracking lagged for Apple in-app subscriptions.",
                    "section": "Limitations",
                    "metadata": {
                        "section": "Limitations",
                        "affected_segment": "eligible non-subscribers",
                    },
                }
            ],
        }
    if "search ranking" in normalized_question:
        return {
            "experiment_id": "exp-003-search-ranking",
            "experiment_name": "Intent-Aware Search Ranking",
            "primary_metric": "search_to_order_rate",
            "baseline": 0.183,
            "treatment": 0.211,
            "annualized_amount": 520000.0,
            "affected_segment": "long-tail search sessions",
            "analysis_status": "completed",
            "analysis_summary": (
                "Intent-Aware Search Ranking improved search_to_order_rate in treatment."
            ),
            "hypothesis": "Intent-aware ranking should raise search-to-order conversion.",
            "findings": [
                "Primary metric search_to_order_rate improved from 0.1830 to 0.2110.",
                "Long-tail query diversity still requires monitoring before broader rollout.",
            ],
            "limitations": [
                "Supplier diversity fell for some long-tail searches in Germany.",
            ],
            "imperfections": [
                "Supplier diversity fell for some long-tail searches in Germany.",
            ],
            "business_decision": (
                "Continue monitoring for long-tail query diversity before broader rollout."
            ),
            "analysis_confidence": "high",
            "confidence_score": 0.95,
            "p_value": 0.02,
            "statistical_significance": {"p_value": 0.02, "is_significant": True},
            "guardrail_metrics": [],
            "citations": [
                {
                    "document_id": "exp-003-search-ranking-doc-1",
                    "experiment_id": "exp-003-search-ranking",
                    "quote": (
                        "Control recorded 0.1830 on search_to_order_rate, while "
                        "treatment recorded 0.2110."
                    ),
                    "section": "Results",
                    "metadata": {
                        "section": "Results",
                        "affected_segment": "long-tail search sessions",
                        "estimated_annualized_impact": {
                            "amount": 520000.0,
                            "currency": "USD",
                            "period": "annual",
                        },
                    },
                },
                {
                    "document_id": "exp-003-search-ranking-doc-2",
                    "experiment_id": "exp-003-search-ranking",
                    "quote": (
                        "Continue monitoring for long-tail query diversity before "
                        "broader rollout."
                    ),
                    "section": "Recommendation",
                    "metadata": {
                        "section": "Recommendation",
                        "affected_segment": "long-tail search sessions",
                    },
                },
            ],
        }
    if "search filters" in normalized_question:
        return {
            "experiment_id": "exp-009-search-filters",
            "experiment_name": "Dynamic Search Filter Shortcuts",
            "primary_metric": "qualified_result_click_rate",
            "baseline": 0.316,
            "treatment": 0.369,
            "annualized_amount": 430000.0,
            "affected_segment": "high-volume mobile web categories",
            "analysis_status": "completed",
            "analysis_summary": (
                "Dynamic Search Filter Shortcuts improved qualified_result_click_rate while "
                "keeping rollout risk concentrated in tracking quality."
            ),
            "hypothesis": "Dynamic filter shortcuts should increase qualified result clicks.",
            "findings": [
                "Primary metric qualified_result_click_rate improved from 0.3160 to 0.3690.",
                "Mobile web scroll tracking dropped some shortcut impressions.",
            ],
            "limitations": [
                "Mobile web scroll tracking dropped some shortcut impressions.",
            ],
            "imperfections": [
                "Mobile web scroll tracking dropped some shortcut impressions.",
            ],
            "business_decision": (
                "Roll out to high-volume categories after fixing mobile web scroll tracking."
            ),
            "analysis_confidence": "high",
            "confidence_score": 0.95,
            "p_value": 0.02,
            "statistical_significance": {"p_value": 0.02, "is_significant": True},
            "guardrail_metrics": [
                {
                    "metric_name": "zero_result_rate",
                    "control_value": 0.05,
                    "treatment_value": 0.07,
                    "absolute_delta": 0.02,
                    "relative_lift": 0.4,
                }
            ],
            "citations": [
                {
                    "document_id": "exp-009-search-filters-doc-1",
                    "experiment_id": "exp-009-search-filters",
                    "quote": (
                        "Control recorded 0.3160 on qualified_result_click_rate, "
                        "while treatment recorded 0.3690."
                    ),
                    "section": "Results",
                    "metadata": {
                        "section": "Results",
                        "affected_segment": "high-volume mobile web categories",
                        "estimated_annualized_impact": {
                            "amount": 430000.0,
                            "currency": "USD",
                            "period": "annual",
                        },
                    },
                },
                {
                    "document_id": "exp-009-search-filters-doc-2",
                    "experiment_id": "exp-009-search-filters",
                    "quote": "Mobile web scroll tracking dropped some shortcut impressions.",
                    "section": "Limitations",
                    "metadata": {
                        "section": "Limitations",
                        "affected_segment": "high-volume mobile web categories",
                    },
                },
            ],
        }
    if "loyalty" in normalized_question:
        return {
            "experiment_id": "exp-006-loyalty",
            "experiment_name": "Loyalty Tier Progress Nudges",
            "primary_metric": "repeat_session_rate_14d",
            "baseline": 0.274,
            "treatment": 0.329,
            "annualized_amount": 380000.0,
            "affected_segment": "silver and gold members",
            "analysis_status": "completed",
            "analysis_summary": (
                "Loyalty Tier Progress Nudges improved repeat_session_rate_14d in "
                "treatment."
            ),
            "hypothesis": "Progress nudges should increase short-term repeat sessions.",
            "findings": [
                "Primary metric repeat_session_rate_14d improved from 0.2740 to 0.3290.",
                "Sample ratio mismatch and novelty effects lowered confidence in early clicks.",
            ],
            "limitations": [
                "Sample ratio mismatch from delayed exclusion of dormant loyalty accounts.",
            ],
            "imperfections": [
                "Sample ratio mismatch from delayed exclusion of dormant loyalty accounts.",
                "Novelty effect in the first three days increased progress-panel clicks.",
            ],
            "business_decision": "Roll out to silver and gold members with a frequency cap.",
            "analysis_confidence": "high",
            "confidence_score": 0.95,
            "p_value": 0.02,
            "statistical_significance": {"p_value": 0.02, "is_significant": True},
            "guardrail_metrics": [],
            "citations": [
                {
                    "document_id": "exp-006-loyalty-doc-1",
                    "experiment_id": "exp-006-loyalty",
                    "quote": (
                        "Control recorded 0.2740 on repeat_session_rate_14d, while "
                        "treatment recorded 0.3290."
                    ),
                    "section": "Results",
                    "metadata": {
                        "section": "Results",
                        "affected_segment": "silver and gold members",
                        "estimated_annualized_impact": {
                            "amount": 380000.0,
                            "currency": "USD",
                            "period": "annual",
                        },
                    },
                },
                {
                    "document_id": "exp-006-loyalty-doc-2",
                    "experiment_id": "exp-006-loyalty",
                    "quote": "Roll out to silver and gold members with a frequency cap.",
                    "section": "Recommendation",
                    "metadata": {
                        "section": "Recommendation",
                        "affected_segment": "silver and gold members",
                    },
                },
            ],
        }
    if "checkout" in normalized_question:
        return {
            "experiment_id": "exp-004-checkout-ux",
            "experiment_name": "One-Page Checkout UX",
            "primary_metric": "checkout_completion_rate",
            "baseline": 0.584,
            "treatment": 0.638,
            "annualized_amount": 640000.0,
            "affected_segment": "returning checkout users",
            "analysis_status": "completed",
            "analysis_summary": (
                "One-Page Checkout UX improved checkout_completion_rate in treatment."
            ),
            "hypothesis": "Reducing checkout friction should improve completion.",
            "findings": [
                "Primary metric checkout_completion_rate improved from 0.5840 to 0.6380.",
                "First-time users should remain on guided checkout.",
            ],
            "limitations": [
                "Address autocomplete telemetry missed apartment-unit edits on mobile Safari.",
            ],
            "imperfections": [
                "Novelty effects: repeat visitors completed faster during week one than week two.",
                "Address autocomplete telemetry missed apartment-unit edits on mobile Safari.",
            ],
            "business_decision": (
                "Roll out to returning users; keep first-time users on guided checkout."
            ),
            "analysis_confidence": "high",
            "confidence_score": 0.95,
            "p_value": 0.02,
            "statistical_significance": {"p_value": 0.02, "is_significant": True},
            "guardrail_metrics": [],
            "citations": [
                {
                    "document_id": "exp-004-checkout-ux-doc-1",
                    "experiment_id": "exp-004-checkout-ux",
                    "quote": (
                        "Control recorded 0.5840 on checkout_completion_rate, while "
                        "treatment recorded 0.6380."
                    ),
                    "section": "Results",
                    "metadata": {
                        "section": "Results",
                        "affected_segment": "returning checkout users",
                        "estimated_annualized_impact": {
                            "amount": 640000.0,
                            "currency": "USD",
                            "period": "annual",
                        },
                    },
                },
                {
                    "document_id": "exp-004-checkout-ux-doc-2",
                    "experiment_id": "exp-004-checkout-ux",
                    "quote": (
                        "Roll out to returning users; keep first-time users on "
                        "guided checkout."
                    ),
                    "section": "Recommendation",
                    "metadata": {
                        "section": "Recommendation",
                        "affected_segment": "returning checkout users",
                    },
                },
            ],
        }
    return {
        "experiment_id": "exp-001-payment-recommendation",
        "experiment_name": "Adaptive Payment Method Recommendation",
        "primary_metric": "payment_success_rate",
        "baseline": 0.67,
        "treatment": 0.73,
        "annualized_amount": 910000.0,
        "affected_segment": "wallet users",
        "analysis_status": "completed",
        "analysis_summary": (
            "Adaptive Payment Method Recommendation improved payment_success_rate in treatment."
        ),
        "hypothesis": "Reducing hesitation should improve successful payment completion.",
        "findings": [
            "Primary metric payment_success_rate improved from 0.67 to 0.73.",
            "Japan wallet success events were under-counted during the early run.",
        ],
        "limitations": [
            "Japan wallet success events were under-counted for the first 18 hours.",
        ],
        "imperfections": [
            "Sample ratio mismatch from late allocation rule change in mobile web.",
            "Japan wallet success events were under-counted for the first 18 hours.",
        ],
        "business_decision": "Roll out to AU, SG, and GB; hold JP pending wallet tracking fix.",
        "analysis_confidence": "high",
        "confidence_score": 0.95,
        "p_value": 0.02,
        "statistical_significance": {"p_value": 0.02, "is_significant": True},
        "guardrail_metrics": [],
        "citations": [
            {
                "document_id": "exp-001-payment-recommendation-doc-1",
                "experiment_id": "exp-001-payment-recommendation",
                "quote": "Primary metric improved in treatment.",
                "section": "Results",
                "metadata": {
                    "section": "Results",
                    "affected_segment": "wallet users",
                },
            },
            {
                "document_id": "exp-001-payment-recommendation-doc-2",
                "experiment_id": "exp-001-payment-recommendation",
                "quote": "Annualized impact was USD 910,000.",
                "section": "Recommendation",
                "metadata": {
                    "section": "Recommendation",
                    "affected_segment": "wallet users",
                    "estimated_annualized_impact": {
                        "amount": 910000.0,
                        "currency": "USD",
                        "period": "annual",
                    },
                },
            },
        ],
    }


def _experiment_metrics(
    *,
    primary_metric: str,
    baseline: float | None,
    treatment: float | None,
) -> list[dict[str, object]]:
    metrics: list[dict[str, object]] = []
    if baseline is not None:
        metrics.append({"metric_name": primary_metric, "variant": "control", "value": baseline})
    if treatment is not None:
        metrics.append({"metric_name": primary_metric, "variant": "treatment", "value": treatment})
    return metrics
