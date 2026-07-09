from __future__ import annotations

import os
from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

from fastapi.testclient import TestClient

from apps.api.main import (
    app,
    get_agent_workflow_service,
    get_experiment_exists_dependency,
    get_question_answering_service,
)
from packages.agents.state import AgentState, create_initial_state
from packages.llm.client import LLMMetrics
from packages.qa.question_answering_service import Citation, QAResponse
from packages.retrieval.service import RetrievalMetrics, RetrievalResult

AgentE2EMode = Literal["agent_workflow", "legacy_rag"]
AgentE2EScenario = Literal[
    "decision_support",
    "executive_summary",
    "experiment_lookup",
    "risk_assessment",
    "business_impact",
    "agent_failure",
    "legacy_fallback",
]

FULL_AGENT_TRACE_NODES = (
    "planner",
    "retrieval",
    "experiment_analysis",
    "business_impact",
    "risk_assessment",
    "decision",
    "human_approval",
    "executive_summary",
)
LOOKUP_TRACE_NODES = (
    "planner",
    "retrieval",
    "experiment_analysis",
    "business_impact",
    "risk_assessment",
    "decision",
    "human_approval",
    "executive_summary",
)
EXPERIMENT_ID = "00000000-0000-0000-0000-000000000123"


@dataclass(frozen=True)
class AgentE2ECase:
    id: str
    question: str
    scenario: AgentE2EScenario
    ask_mode: AgentE2EMode = "agent_workflow"
    experiment_id: str = EXPERIMENT_ID
    top_k: int = 3
    expected_status_code: int = 200
    expected_intent: str | None = None
    expected_required_agents: tuple[str, ...] = ()
    expected_min_citations: int = 0
    expect_decision: bool = False
    expect_executive_summary: bool = False
    expected_approval_status: str | None = None
    expect_agent_trace: bool = False
    expected_trace_nodes: tuple[str, ...] = ()
    expect_agent_metrics: bool = False
    expected_error_detail: str | None = None


@dataclass(frozen=True)
class AgentE2ESampleResult:
    case: AgentE2ECase
    status_code: int
    response_json: dict[str, object]
    latency_ms: float
    used_agent_workflow: bool
    used_legacy_fallback: bool
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class AgentE2ESummary:
    sample_count: int
    pass_count: int
    fail_count: int
    default_agent_workflow_coverage: float
    legacy_fallback_coverage: float
    intent_accuracy: float
    routing_accuracy: float
    citation_coverage: float
    decision_coverage: float
    executive_summary_coverage: float
    approval_status_coverage: float
    average_latency_ms: float
    failure_cases: tuple[str, ...]

    @classmethod
    def from_samples(cls, samples: list[AgentE2ESampleResult]) -> AgentE2ESummary:
        if not samples:
            return cls(
                sample_count=0,
                pass_count=0,
                fail_count=0,
                default_agent_workflow_coverage=0.0,
                legacy_fallback_coverage=0.0,
                intent_accuracy=0.0,
                routing_accuracy=0.0,
                citation_coverage=0.0,
                decision_coverage=0.0,
                executive_summary_coverage=0.0,
                approval_status_coverage=0.0,
                average_latency_ms=0.0,
                failure_cases=(),
            )

        pass_count = sum(1 for sample in samples if sample.passed)
        fail_count = len(samples) - pass_count
        agent_samples = [sample for sample in samples if sample.case.ask_mode == "agent_workflow"]
        legacy_samples = [sample for sample in samples if sample.case.ask_mode == "legacy_rag"]
        success_samples = [sample for sample in samples if sample.status_code == 200]

        return cls(
            sample_count=len(samples),
            pass_count=pass_count,
            fail_count=fail_count,
            default_agent_workflow_coverage=_average(
                float(sample.used_agent_workflow) for sample in agent_samples
            ),
            legacy_fallback_coverage=_average(
                float(sample.used_legacy_fallback) for sample in legacy_samples
            ),
            intent_accuracy=_average(
                _intent_match(sample) for sample in success_samples
            ),
            routing_accuracy=_average(
                _routing_match(sample) for sample in success_samples
            ),
            citation_coverage=_average(
                _citation_score(sample) for sample in success_samples
            ),
            decision_coverage=_average(
                _decision_score(sample)
                for sample in success_samples
                if sample.case.expect_decision
            ),
            executive_summary_coverage=_average(
                _executive_summary_score(sample)
                for sample in success_samples
                if sample.case.expect_executive_summary
            ),
            approval_status_coverage=_average(
                _approval_status_score(sample)
                for sample in success_samples
                if sample.case.expected_approval_status is not None
            ),
            average_latency_ms=_average(sample.latency_ms for sample in samples),
            failure_cases=tuple(sample.case.id for sample in samples if not sample.passed),
        )


@dataclass(frozen=True)
class AgentE2ERun:
    samples: list[AgentE2ESampleResult]
    summary: AgentE2ESummary


@dataclass
class StubWorkflowService:
    state: AgentState | None = None
    failure_message: str | None = None
    calls: list[tuple[str, str | None, int]] = field(default_factory=list)

    def run(self, question: str, experiment_id: str | None = None, top_k: int = 5) -> AgentState:
        self.calls.append((question, experiment_id, top_k))
        if self.failure_message is not None:
            raise RuntimeError(self.failure_message)
        if self.state is None:
            raise RuntimeError("workflow state is required")
        return self.state


@dataclass
class StubQuestionAnsweringService:
    response: QAResponse
    calls: list[tuple[str, str, int]] = field(default_factory=list)

    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int = 5,
    ) -> QAResponse:
        self.calls.append((question, experiment_id, top_k))
        return self.response


class ExplodingQuestionAnsweringService:
    async def answer_question(
        self,
        *,
        question: str,
        experiment_id: str,
        top_k: int = 5,
    ) -> QAResponse:
        raise AssertionError("legacy QA path should not be selected")


async def always_true(_: str) -> bool:
    return True


class AgentE2EEvaluator:
    def __init__(self, *, cases: list[AgentE2ECase]) -> None:
        self.cases = list(cases)

    def evaluate(self) -> AgentE2ERun:
        samples = [self._evaluate_case(case) for case in self.cases]
        return AgentE2ERun(samples=samples, summary=AgentE2ESummary.from_samples(samples))

    def _evaluate_case(self, case: AgentE2ECase) -> AgentE2ESampleResult:
        previous_ask_mode = os.environ.get("ASK_MODE")
        workflow_service: StubWorkflowService | None = None
        qa_service: StubQuestionAnsweringService | None = None

        try:
            app.dependency_overrides.clear()
            if case.ask_mode == "legacy_rag":
                os.environ["ASK_MODE"] = "legacy_rag"
                qa_service = StubQuestionAnsweringService(_build_legacy_qa_response())
                app.dependency_overrides[get_question_answering_service] = (
                    lambda qa_service=qa_service: qa_service
                )
                app.dependency_overrides[get_agent_workflow_service] = (
                    lambda: StubWorkflowService(failure_message="agent workflow should not run")
                )
            else:
                os.environ.pop("ASK_MODE", None)
                workflow_service = _build_workflow_service(case)
                app.dependency_overrides[get_agent_workflow_service] = (
                    lambda workflow_service=workflow_service: workflow_service
                )
                app.dependency_overrides[get_experiment_exists_dependency] = lambda: always_true
                app.dependency_overrides[get_question_answering_service] = (
                    ExplodingQuestionAnsweringService
                )

            with TestClient(app) as client:
                started_at = perf_counter()
                response = client.post(
                    "/ask",
                    json={
                        "question": case.question,
                        "experiment_id": case.experiment_id,
                        "top_k": case.top_k,
                    },
                )
                latency_ms = (perf_counter() - started_at) * 1000.0

            response_json = response.json()
            if not isinstance(response_json, dict):
                response_json = {"detail": response_json}

            used_agent_workflow = _used_agent_workflow(case, response.status_code, response_json)
            used_legacy_fallback = _used_legacy_fallback(
                case,
                response.status_code,
                response_json,
            )
            failure_reasons = _validate_sample(
                case=case,
                status_code=response.status_code,
                response_json=response_json,
                used_agent_workflow=used_agent_workflow,
                used_legacy_fallback=used_legacy_fallback,
            )
            return AgentE2ESampleResult(
                case=case,
                status_code=response.status_code,
                response_json=response_json,
                latency_ms=latency_ms,
                used_agent_workflow=used_agent_workflow,
                used_legacy_fallback=used_legacy_fallback,
                passed=not failure_reasons,
                failure_reasons=tuple(failure_reasons),
            )
        finally:
            app.dependency_overrides.clear()
            if previous_ask_mode is None:
                os.environ.pop("ASK_MODE", None)
            else:
                os.environ["ASK_MODE"] = previous_ask_mode


def build_default_agent_e2e_cases() -> list[AgentE2ECase]:
    return [
        AgentE2ECase(
            id="decision-loyalty-default",
            question="Should we roll out the loyalty tier progress nudges experiment?",
            scenario="decision_support",
            expected_intent="decision_support",
            expected_required_agents=(
                "retrieval",
                "experiment_analysis",
                "business_impact",
                "risk_assessment",
                "decision",
                "human_approval",
                "executive_summary",
            ),
            expected_min_citations=1,
            expect_decision=True,
            expect_executive_summary=True,
            expected_approval_status="pending",
            expect_agent_trace=True,
            expected_trace_nodes=FULL_AGENT_TRACE_NODES,
            expect_agent_metrics=True,
        ),
        AgentE2ECase(
            id="summary-payment-default",
            question="Summarize the payment recommendation experiment for executives.",
            scenario="executive_summary",
            expected_intent="executive_summary",
            expected_required_agents=(
                "retrieval",
                "experiment_analysis",
                "business_impact",
                "risk_assessment",
                "decision",
                "human_approval",
                "executive_summary",
            ),
            expected_min_citations=1,
            expect_decision=True,
            expect_executive_summary=True,
            expected_approval_status="pending",
            expect_agent_trace=True,
        ),
        AgentE2ECase(
            id="lookup-hotel-default",
            question="What happened in the hotel image quality experiment?",
            scenario="experiment_lookup",
            expected_intent="experiment_lookup",
            expected_required_agents=("retrieval",),
            expected_min_citations=1,
            expected_approval_status="not_requested",
            expect_agent_trace=True,
            expected_trace_nodes=LOOKUP_TRACE_NODES,
        ),
        AgentE2ECase(
            id="risk-checkout-default",
            question="What are the risks of launching the checkout UX experiment?",
            scenario="risk_assessment",
            expected_intent="risk_assessment",
            expected_required_agents=("retrieval", "experiment_analysis", "risk_assessment"),
            expected_min_citations=1,
            expected_approval_status="not_requested",
            expect_agent_trace=True,
        ),
        AgentE2ECase(
            id="impact-search-default",
            question="What is the business impact of the search ranking experiment?",
            scenario="business_impact",
            expected_intent="business_impact",
            expected_required_agents=("retrieval", "experiment_analysis", "business_impact"),
            expected_min_citations=1,
            expected_approval_status="not_requested",
            expect_agent_trace=True,
        ),
        AgentE2ECase(
            id="legacy-fallback",
            question="What happened in the payment recommendation experiment?",
            scenario="legacy_fallback",
            ask_mode="legacy_rag",
            expected_min_citations=1,
        ),
        AgentE2ECase(
            id="failure-default",
            question="Should we roll out the loyalty tier progress nudges experiment?",
            scenario="agent_failure",
            expected_status_code=502,
            expected_error_detail="workflow exploded",
        ),
    ]


def _build_workflow_service(case: AgentE2ECase) -> StubWorkflowService:
    if case.scenario == "agent_failure":
        return StubWorkflowService(failure_message="workflow exploded")
    return StubWorkflowService(state=_build_state_for_case(case))


def _build_state_for_case(case: AgentE2ECase) -> AgentState:
    if case.scenario == "executive_summary":
        return _build_executive_summary_state(case.question, case.experiment_id, case.top_k)
    if case.scenario == "experiment_lookup":
        return _build_lookup_state(case.question, case.experiment_id, case.top_k)
    if case.scenario == "risk_assessment":
        return _build_risk_state(case.question, case.experiment_id, case.top_k)
    if case.scenario == "business_impact":
        return _build_business_impact_state(case.question, case.experiment_id, case.top_k)
    return _build_decision_support_state(case.question, case.experiment_id, case.top_k)


def _build_decision_support_state(question: str, experiment_id: str, top_k: int) -> AgentState:
    state = create_initial_state(question, experiment_id=experiment_id, top_k=top_k)
    state["intent"] = "decision_support"
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-1",
            "experiment_id": experiment_id,
            "content": "Primary metric improved by 8.9% in treatment.",
            "score": 0.91,
            "metadata": {"section": "Results", "document_name": "Launch Report"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": experiment_id,
            "quote": "Primary metric improved by 8.9% in treatment.",
            "section": "Results",
            "metadata": {"section": "Results", "document_name": "Launch Report"},
        }
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "summary": "Treatment beat control on the primary metric.",
        "status": "completed",
        "experiment_id": experiment_id,
        "experiment_name": "Adaptive Payment Method Recommendation",
        "primary_metric": "payment_success_rate",
        "evidence_citations": list(state["citations"]),
        "analysis_confidence": "high",
    }
    state["business_impact"] = {
        **state["business_impact"],
        "summary": "Projected incremental payment success is material.",
        "impact_status": "estimated",
        "relative_lift": 0.089,
        "evidence_citations": list(state["citations"]),
        "confidence_level": "high",
    }
    state["risk_assessment"] = {
        **state["risk_assessment"],
        "risk_status": "assessed",
        "overall_risk_level": "medium",
        "risk_score": 2,
        "risk_factors": [
            {
                "code": "monitor_rollout",
                "title": "Monitor ramp",
                "severity": "medium",
                "category": "rollout",
                "detail": "Monitor telemetry during ramp.",
                "mitigation": "Ramp gradually.",
            }
        ],
        "mitigation_actions": ["Ramp gradually."],
        "evidence_citations": list(state["citations"]),
        "confidence_level": "high",
    }
    state["decision"] = {
        **state["decision"],
        "decision_status": "decided",
        "recommendation": "rollout",
        "confidence": "high",
        "rationale": "Positive lift outweighed manageable rollout risk.",
        "supporting_evidence": ["Primary metric improved."],
        "recommended_next_actions": ["Roll out gradually."],
        "approval_required": True,
        "evidence_citations": list(state["citations"]),
    }
    state["executive_summary"] = {
        **state["executive_summary"],
        "summary_status": "generated",
        "headline": "Rollout is supported by the current evidence.",
        "recommendation": "rollout",
        "summary": "Rollout is supported by the current evidence.",
        "evidence_citations": list(state["citations"]),
    }
    state["human_approval"] = {
        **state["human_approval"],
        "status": "pending",
        "required": True,
    }
    state["metrics"] = {
        "planner_rule_version": "deterministic_v1",
        "planner": {"status": "planned", "latency_ms": 1.0},
        "retrieval": {
            "embedding_time_ms": 10.0,
            "vector_search_time_ms": 8.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.91,
        },
        "experiment_analysis": {"status": "completed", "latency_ms": 11.0},
        "business_impact": {"status": "estimated", "latency_ms": 12.0},
        "risk_assessment": {"status": "assessed", "latency_ms": 13.0},
        "decision": {"status": "decided", "latency_ms": 14.0},
        "human_approval": {"status": "pending", "latency_ms": 15.0},
        "executive_summary": {"status": "generated", "latency_ms": 16.0},
    }
    state["trace"] = _full_trace()
    return state


def _build_executive_summary_state(question: str, experiment_id: str, top_k: int) -> AgentState:
    state = _build_decision_support_state(question, experiment_id, top_k)
    state["intent"] = "executive_summary"
    state["executive_summary"] = {
        **state["executive_summary"],
        "summary": "Executives should proceed with a monitored rollout.",
    }
    return state


def _build_lookup_state(question: str, experiment_id: str, top_k: int) -> AgentState:
    state = create_initial_state(question, experiment_id=experiment_id, top_k=top_k)
    state["intent"] = "experiment_lookup"
    state["required_agents"] = ["retrieval"]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-lookup-1",
            "experiment_id": experiment_id,
            "content": "Hotel image quality treatment improved booking conversion.",
            "score": 0.88,
            "metadata": {"section": "Results", "document_name": "Hotel Report"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-lookup-1",
            "experiment_id": experiment_id,
            "quote": "Hotel image quality treatment improved booking conversion.",
            "section": "Results",
            "metadata": {"section": "Results", "document_name": "Hotel Report"},
        }
    ]
    state["metrics"] = {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {
            "embedding_time_ms": 6.0,
            "vector_search_time_ms": 5.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.88,
        },
    }
    state["trace"] = _lookup_trace()
    return state


def _build_risk_state(question: str, experiment_id: str, top_k: int) -> AgentState:
    state = create_initial_state(question, experiment_id=experiment_id, top_k=top_k)
    state["intent"] = "risk_assessment"
    state["required_agents"] = ["retrieval", "experiment_analysis", "risk_assessment"]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-risk-1",
            "experiment_id": experiment_id,
            "content": "Checkout UX improved conversion but requires telemetry monitoring.",
            "score": 0.89,
            "metadata": {"section": "Risks", "document_name": "Checkout Report"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-risk-1",
            "experiment_id": experiment_id,
            "quote": "Checkout UX improved conversion but requires telemetry monitoring.",
            "section": "Risks",
            "metadata": {"section": "Risks", "document_name": "Checkout Report"},
        }
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "summary": "Checkout UX improved conversion in treatment.",
        "status": "completed",
        "experiment_id": experiment_id,
        "experiment_name": "Checkout UX Streamlining",
        "primary_metric": "checkout_completion_rate",
        "evidence_citations": list(state["citations"]),
        "analysis_confidence": "medium",
    }
    state["risk_assessment"] = {
        **state["risk_assessment"],
        "risk_status": "assessed",
        "overall_risk_level": "medium",
        "risk_score": 2,
        "risk_factors": [
            {
                "code": "telemetry_monitoring",
                "title": "Telemetry must be monitored",
                "severity": "medium",
                "category": "rollout",
                "detail": "Monitoring should stay in place during rollout.",
                "mitigation": "Ramp gradually.",
            }
        ],
        "mitigation_actions": ["Ramp gradually."],
        "evidence_citations": list(state["citations"]),
        "confidence_level": "medium",
    }
    state["human_approval"] = {
        **state["human_approval"],
        "status": "not_requested",
        "required": False,
    }
    state["metrics"] = {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {
            "embedding_time_ms": 9.0,
            "vector_search_time_ms": 7.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.89,
        },
        "experiment_analysis": {"status": "completed", "latency_ms": 9.0},
        "risk_assessment": {"status": "assessed", "latency_ms": 10.0},
    }
    state["trace"] = [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "started", "at": "2026-07-09T00:00:01Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:02Z"},
        {"node": "experiment_analysis", "event": "started", "at": "2026-07-09T00:00:03Z"},
        {
            "node": "experiment_analysis",
            "event": "completed",
            "at": "2026-07-09T00:00:04Z",
        },
        {"node": "business_impact", "event": "skipped", "at": "2026-07-09T00:00:05Z"},
        {"node": "risk_assessment", "event": "started", "at": "2026-07-09T00:00:06Z"},
        {"node": "risk_assessment", "event": "completed", "at": "2026-07-09T00:00:07Z"},
        {"node": "decision", "event": "skipped", "at": "2026-07-09T00:00:08Z"},
        {"node": "human_approval", "event": "skipped", "at": "2026-07-09T00:00:09Z"},
        {"node": "executive_summary", "event": "skipped", "at": "2026-07-09T00:00:10Z"},
    ]
    return state


def _build_business_impact_state(question: str, experiment_id: str, top_k: int) -> AgentState:
    state = create_initial_state(question, experiment_id=experiment_id, top_k=top_k)
    state["intent"] = "business_impact"
    state["required_agents"] = ["retrieval", "experiment_analysis", "business_impact"]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-impact-1",
            "experiment_id": experiment_id,
            "content": "Search ranking treatment generated a positive revenue lift.",
            "score": 0.9,
            "metadata": {"section": "Business Impact", "document_name": "Search Report"},
        }
    ]
    state["citations"] = [
        {
            "document_id": "doc-impact-1",
            "experiment_id": experiment_id,
            "quote": "Search ranking treatment generated a positive revenue lift.",
            "section": "Business Impact",
            "metadata": {"section": "Business Impact", "document_name": "Search Report"},
        }
    ]
    state["experiment_analysis"] = {
        **state["experiment_analysis"],
        "summary": "Search ranking improved the primary metric in treatment.",
        "status": "completed",
        "experiment_id": experiment_id,
        "experiment_name": "Search Ranking Refresh",
        "primary_metric": "qualified_search_sessions",
        "evidence_citations": list(state["citations"]),
        "analysis_confidence": "high",
    }
    state["business_impact"] = {
        **state["business_impact"],
        "summary": "Projected annualized revenue lift is positive.",
        "impact_status": "estimated",
        "relative_lift": 0.052,
        "evidence_citations": list(state["citations"]),
        "confidence_level": "high",
    }
    state["human_approval"] = {
        **state["human_approval"],
        "status": "not_requested",
        "required": False,
    }
    state["metrics"] = {
        "planner_rule_version": "deterministic_v1",
        "retrieval": {
            "embedding_time_ms": 8.0,
            "vector_search_time_ms": 6.0,
            "retrieved_chunks": 1,
            "average_similarity": 0.9,
        },
        "experiment_analysis": {"status": "completed", "latency_ms": 8.0},
        "business_impact": {"status": "estimated", "latency_ms": 9.0},
    }
    state["trace"] = [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "started", "at": "2026-07-09T00:00:01Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:02Z"},
        {"node": "experiment_analysis", "event": "started", "at": "2026-07-09T00:00:03Z"},
        {
            "node": "experiment_analysis",
            "event": "completed",
            "at": "2026-07-09T00:00:04Z",
        },
        {"node": "business_impact", "event": "started", "at": "2026-07-09T00:00:05Z"},
        {"node": "business_impact", "event": "completed", "at": "2026-07-09T00:00:06Z"},
        {"node": "risk_assessment", "event": "skipped", "at": "2026-07-09T00:00:07Z"},
        {"node": "decision", "event": "skipped", "at": "2026-07-09T00:00:08Z"},
        {"node": "human_approval", "event": "skipped", "at": "2026-07-09T00:00:09Z"},
        {"node": "executive_summary", "event": "skipped", "at": "2026-07-09T00:00:10Z"},
    ]
    return state


def _build_legacy_qa_response() -> QAResponse:
    return QAResponse(
        answer="Legacy grounded answer.",
        citations=[
            Citation(
                experiment_id=EXPERIMENT_ID,
                document="Legacy Report",
                similarity=0.87,
            )
        ],
        retrieved_chunks=[
            RetrievalResult(
                experiment_id=EXPERIMENT_ID,
                experiment_name="Legacy Experiment",
                document_id="legacy-doc-1",
                document_name="Legacy Report",
                chunk_text="Legacy evidence chunk.",
                similarity=0.87,
                metadata={"section": "Results"},
            )
        ],
        retrieval_metrics=RetrievalMetrics(
            embedding_time_ms=1.0,
            vector_search_time_ms=2.0,
            retrieved_chunks=1,
            average_similarity=0.87,
        ),
        llm_metrics=LLMMetrics(
            model="mock",
            input_tokens=12,
            output_tokens=4,
            latency_ms=0.0,
        ),
    )


def _validate_sample(
    *,
    case: AgentE2ECase,
    status_code: int,
    response_json: dict[str, object],
    used_agent_workflow: bool,
    used_legacy_fallback: bool,
) -> list[str]:
    failures: list[str] = []
    if status_code != case.expected_status_code:
        failures.append(
            f"status mismatch: expected {case.expected_status_code}, got {status_code}"
        )

    if case.ask_mode == "agent_workflow" and not used_agent_workflow:
        failures.append("default agent_workflow route was not selected")
    if case.ask_mode == "legacy_rag" and not used_legacy_fallback:
        failures.append("legacy_rag fallback route was not selected")

    if status_code != 200:
        if case.expected_error_detail is not None:
            actual_detail = str(response_json.get("detail", "")).strip()
            if actual_detail != case.expected_error_detail:
                failures.append(
                    f"error detail mismatch: expected {case.expected_error_detail}, "
                    f"got {actual_detail}"
                )
        return failures

    if case.ask_mode == "legacy_rag":
        if response_json.get("intent") is not None:
            failures.append("legacy response should not expose planner intent")
        if response_json.get("decision") is not None:
            failures.append("legacy response should not expose decision artifacts")
        if response_json.get("executive_summary") is not None:
            failures.append("legacy response should not expose executive summary artifacts")
        if response_json.get("agent_trace") not in ([], None):
            failures.append("legacy response should not expose agent trace")
        if response_json.get("agent_metrics") not in ({}, None):
            failures.append("legacy response should not expose agent metrics")
        return failures

    if case.expected_intent is not None and response_json.get("intent") != case.expected_intent:
        failures.append(
            f"intent mismatch: expected {case.expected_intent}, "
            f"got {response_json.get('intent')}"
        )

    actual_required_agents = tuple(response_json.get("required_agents", []))
    if (
        case.expected_required_agents
        and actual_required_agents != case.expected_required_agents
    ):
        failures.append(
            "routing mismatch: expected "
            f"{list(case.expected_required_agents)}, got {list(actual_required_agents)}"
        )

    citations = response_json.get("citations", [])
    if not isinstance(citations, list):
        failures.append("citations should be a list")
    elif len(citations) < case.expected_min_citations:
        failures.append(
            f"citation coverage below expectation: {len(citations)} citations returned"
        )

    decision = response_json.get("decision")
    if case.expect_decision:
        if not isinstance(decision, dict):
            failures.append("decision artifact was not returned")
        elif decision.get("decision_status") in {"", "not_required", "unknown"}:
            failures.append("decision artifact did not contain a real decision status")

    executive_summary = response_json.get("executive_summary")
    if case.expect_executive_summary:
        if not isinstance(executive_summary, dict):
            failures.append("executive summary artifact was not returned")
        elif executive_summary.get("summary_status") in {"", "not_required"}:
            failures.append("executive summary artifact was not generated")

    if (
        case.expected_approval_status is not None
        and response_json.get("approval_status") != case.expected_approval_status
    ):
        failures.append(
            "approval status mismatch: expected "
            f"{case.expected_approval_status}, got {response_json.get('approval_status')}"
        )

    if case.expect_agent_trace:
        trace = response_json.get("agent_trace", [])
        if not isinstance(trace, list) or not trace:
            failures.append("agent trace was not returned")
        elif case.expected_trace_nodes:
            actual_nodes = tuple(
                str(entry.get("node", ""))
                for entry in trace
                if entry.get("event") in {"planned", "completed", "skipped"}
            )
            if actual_nodes != case.expected_trace_nodes:
                failures.append(
                    f"trace order mismatch: expected {list(case.expected_trace_nodes)}, "
                    f"got {list(actual_nodes)}"
                )

    if case.expect_agent_metrics:
        metrics = response_json.get("agent_metrics", {})
        if not isinstance(metrics, dict) or not metrics:
            failures.append("agent metrics were not returned")
        else:
            for key in (
                "experiment_analysis",
                "business_impact",
                "risk_assessment",
                "decision",
                "human_approval",
                "executive_summary",
            ):
                value = metrics.get(key)
                if not isinstance(value, dict) or "status" not in value:
                    failures.append(f"agent metrics missing structured data for {key}")
            retrieval_metrics = metrics.get("retrieval")
            if (
                not isinstance(retrieval_metrics, dict)
                or "retrieved_chunks" not in retrieval_metrics
            ):
                failures.append("agent metrics missing retrieval metrics")

    return failures


def _intent_match(sample: AgentE2ESampleResult) -> float:
    if sample.case.expected_intent is None:
        return 1.0
    return float(sample.response_json.get("intent") == sample.case.expected_intent)


def _routing_match(sample: AgentE2ESampleResult) -> float:
    if not sample.case.expected_required_agents:
        return 1.0
    actual = tuple(sample.response_json.get("required_agents", []))
    return float(actual == sample.case.expected_required_agents)


def _citation_score(sample: AgentE2ESampleResult) -> float:
    if sample.case.expected_min_citations == 0:
        return 1.0
    citations = sample.response_json.get("citations", [])
    if not isinstance(citations, list):
        return 0.0
    return min(len(citations) / sample.case.expected_min_citations, 1.0)


def _decision_score(sample: AgentE2ESampleResult) -> float:
    decision = sample.response_json.get("decision")
    if not isinstance(decision, dict):
        return 0.0
    return float(decision.get("decision_status") not in {"", "not_required", "unknown"})


def _executive_summary_score(sample: AgentE2ESampleResult) -> float:
    summary = sample.response_json.get("executive_summary")
    if not isinstance(summary, dict):
        return 0.0
    return float(summary.get("summary_status") not in {"", "not_required"})


def _approval_status_score(sample: AgentE2ESampleResult) -> float:
    if sample.case.expected_approval_status is None:
        return 1.0
    return float(
        sample.response_json.get("approval_status")
        == sample.case.expected_approval_status
    )


def _used_agent_workflow(
    case: AgentE2ECase,
    status_code: int,
    response_json: dict[str, object],
) -> bool:
    if case.ask_mode != "agent_workflow":
        return False
    if status_code == 200:
        llm_metrics = response_json.get("llm_metrics", {})
        if isinstance(llm_metrics, dict) and llm_metrics.get("model") == "agent-workflow":
            return response_json.get("intent") is not None
        return False
    return str(response_json.get("detail", "")).strip() == case.expected_error_detail


def _used_legacy_fallback(
    case: AgentE2ECase,
    status_code: int,
    response_json: dict[str, object],
) -> bool:
    if case.ask_mode != "legacy_rag" or status_code != 200:
        return False
    llm_metrics = response_json.get("llm_metrics", {})
    if not isinstance(llm_metrics, dict):
        return False
    return (
        llm_metrics.get("model") != "agent-workflow"
        and response_json.get("intent") is None
        and response_json.get("decision") is None
        and response_json.get("executive_summary") is None
    )


def _average(values: object) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return sum(collected) / len(collected)


def _full_trace() -> list[dict[str, object]]:
    return [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "started", "at": "2026-07-09T00:00:01Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:02Z"},
        {"node": "experiment_analysis", "event": "started", "at": "2026-07-09T00:00:03Z"},
        {
            "node": "experiment_analysis",
            "event": "completed",
            "at": "2026-07-09T00:00:04Z",
        },
        {"node": "business_impact", "event": "started", "at": "2026-07-09T00:00:05Z"},
        {"node": "business_impact", "event": "completed", "at": "2026-07-09T00:00:06Z"},
        {"node": "risk_assessment", "event": "started", "at": "2026-07-09T00:00:07Z"},
        {"node": "risk_assessment", "event": "completed", "at": "2026-07-09T00:00:08Z"},
        {"node": "decision", "event": "started", "at": "2026-07-09T00:00:09Z"},
        {"node": "decision", "event": "completed", "at": "2026-07-09T00:00:10Z"},
        {"node": "human_approval", "event": "started", "at": "2026-07-09T00:00:11Z"},
        {"node": "human_approval", "event": "completed", "at": "2026-07-09T00:00:12Z"},
        {"node": "executive_summary", "event": "started", "at": "2026-07-09T00:00:13Z"},
        {
            "node": "executive_summary",
            "event": "completed",
            "at": "2026-07-09T00:00:14Z",
        },
    ]


def _lookup_trace() -> list[dict[str, object]]:
    return [
        {"node": "planner", "event": "planned", "at": "2026-07-09T00:00:00Z"},
        {"node": "retrieval", "event": "started", "at": "2026-07-09T00:00:01Z"},
        {"node": "retrieval", "event": "completed", "at": "2026-07-09T00:00:02Z"},
        {"node": "experiment_analysis", "event": "skipped", "at": "2026-07-09T00:00:03Z"},
        {"node": "business_impact", "event": "skipped", "at": "2026-07-09T00:00:04Z"},
        {"node": "risk_assessment", "event": "skipped", "at": "2026-07-09T00:00:05Z"},
        {"node": "decision", "event": "skipped", "at": "2026-07-09T00:00:06Z"},
        {"node": "human_approval", "event": "skipped", "at": "2026-07-09T00:00:07Z"},
        {"node": "executive_summary", "event": "skipped", "at": "2026-07-09T00:00:08Z"},
    ]
