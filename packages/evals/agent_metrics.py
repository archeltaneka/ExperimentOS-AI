from __future__ import annotations

from dataclasses import dataclass

from packages.agents.observability import PHASE2_WORKFLOW_NODES, WorkflowObservation
from packages.evals.agent_dataset import AgentEvaluationCase


@dataclass(frozen=True)
class AgentSampleMetrics:
    workflow_latency_ms: float
    trace_completeness: float
    planner_intent_accuracy: float
    routing_accuracy: float
    citation_coverage: float
    recommendation_coverage: float | None
    workflow_success: bool
    tool_call_count: int
    tool_failure_count: int
    decision_status: str
    approval_status: str
    passed: bool
    failure_reasons: tuple[str, ...]
    per_agent_latency_ms: dict[str, float]


@dataclass(frozen=True)
class AgentEvaluationSummary:
    sample_count: int
    pass_count: int
    fail_count: int
    workflow_success_rate: float
    average_workflow_latency_ms: float
    average_trace_completeness: float
    planner_intent_accuracy: float
    routing_accuracy: float
    citation_coverage: float
    recommendation_coverage: float
    total_tool_calls: int
    total_tool_failures: int
    average_tool_calls: float
    decision_status_distribution: dict[str, int]
    approval_status_distribution: dict[str, int]
    per_agent_latency_ms: dict[str, float]
    failure_cases: tuple[str, ...]

    @classmethod
    def from_samples(cls, samples: list[object]) -> AgentEvaluationSummary:
        if not samples:
            return cls(
                sample_count=0,
                pass_count=0,
                fail_count=0,
                workflow_success_rate=0.0,
                average_workflow_latency_ms=0.0,
                average_trace_completeness=0.0,
                planner_intent_accuracy=0.0,
                routing_accuracy=0.0,
                citation_coverage=0.0,
                recommendation_coverage=0.0,
                total_tool_calls=0,
                total_tool_failures=0,
                average_tool_calls=0.0,
                decision_status_distribution={},
                approval_status_distribution={},
                per_agent_latency_ms={node: 0.0 for node in PHASE2_WORKFLOW_NODES},
                failure_cases=(),
            )

        metric_samples = [
            sample.metrics
            for sample in samples
            if getattr(sample, "metrics", None) is not None
        ]
        if not metric_samples:
            return cls.from_samples([])

        recommendation_samples = [
            metric.recommendation_coverage
            for metric in metric_samples
            if metric.recommendation_coverage is not None
        ]
        decision_status_distribution: dict[str, int] = {}
        approval_status_distribution: dict[str, int] = {}
        per_agent_latency_ms: dict[str, float] = {}
        for node in PHASE2_WORKFLOW_NODES:
            per_agent_latency_ms[node] = sum(
                metric.per_agent_latency_ms.get(node, 0.0) for metric in metric_samples
            ) / len(metric_samples)

        for sample in samples:
            observation = getattr(sample, "observation", None)
            if observation is None:
                continue
            decision_status_distribution[observation.decision_status] = (
                decision_status_distribution.get(observation.decision_status, 0) + 1
            )
            approval_status_distribution[observation.approval_status] = (
                approval_status_distribution.get(observation.approval_status, 0) + 1
            )

        pass_count = sum(1 for metric in metric_samples if metric.passed)
        sample_count = len(samples)
        fail_count = sample_count - pass_count
        return cls(
            sample_count=sample_count,
            pass_count=pass_count,
            fail_count=fail_count,
            workflow_success_rate=sum(1 for metric in metric_samples if metric.workflow_success)
            / len(metric_samples),
            average_workflow_latency_ms=sum(metric.workflow_latency_ms for metric in metric_samples)
            / len(metric_samples),
            average_trace_completeness=sum(metric.trace_completeness for metric in metric_samples)
            / len(metric_samples),
            planner_intent_accuracy=sum(
                metric.planner_intent_accuracy for metric in metric_samples
            )
            / len(metric_samples),
            routing_accuracy=sum(metric.routing_accuracy for metric in metric_samples)
            / len(metric_samples),
            citation_coverage=sum(metric.citation_coverage for metric in metric_samples)
            / len(metric_samples),
            recommendation_coverage=(
                sum(recommendation_samples) / len(recommendation_samples)
                if recommendation_samples
                else 0.0
            ),
            total_tool_calls=sum(metric.tool_call_count for metric in metric_samples),
            total_tool_failures=sum(metric.tool_failure_count for metric in metric_samples),
            average_tool_calls=sum(metric.tool_call_count for metric in metric_samples)
            / len(metric_samples),
            decision_status_distribution=decision_status_distribution,
            approval_status_distribution=approval_status_distribution,
            per_agent_latency_ms=per_agent_latency_ms,
            failure_cases=tuple(
                sample.case.id
                for sample in samples
                if getattr(sample, "metrics", None) is None or not sample.metrics.passed
            ),
        )


def calculate_agent_sample_metrics(
    *,
    case: AgentEvaluationCase,
    observation: WorkflowObservation,
) -> AgentSampleMetrics:
    planner_intent_accuracy = 1.0 if observation.intent == case.expected_intent else 0.0
    routing_accuracy = calculate_routing_accuracy(
        expected_agents=case.expected_required_agents,
        actual_agents=observation.required_agents,
    )
    citation_coverage = calculate_citation_coverage(
        expected_min_citations=case.expected_min_citations,
        actual_citations=observation.citation_count,
    )
    recommendation_coverage = calculate_recommendation_coverage(
        expected_recommendation=case.expected_recommendation,
        actual_recommendation=observation.final_recommendation,
    )

    failure_reasons: list[str] = []
    if planner_intent_accuracy < 1.0:
        failure_reasons.append(
            f"intent mismatch: expected {case.expected_intent}, got {observation.intent}"
        )
    if routing_accuracy < 1.0:
        failure_reasons.append(
            "routing mismatch: expected "
            f"{list(case.expected_required_agents)}, got {list(observation.required_agents)}"
        )
    if citation_coverage < 1.0:
        failure_reasons.append(
            f"citation coverage below expectation: {observation.citation_count} citations"
        )
    if (
        case.expected_decision_status is not None
        and observation.decision_status != case.expected_decision_status
    ):
        failure_reasons.append(
            "decision status mismatch: expected "
            f"{case.expected_decision_status}, got {observation.decision_status}"
        )
    if recommendation_coverage == 0.0:
        failure_reasons.append(
            "recommendation mismatch: expected "
            f"{case.expected_recommendation}, got {observation.final_recommendation}"
        )
    if (
        case.expected_summary_status is not None
        and observation.summary_status != case.expected_summary_status
    ):
        failure_reasons.append(
            "summary status mismatch: expected "
            f"{case.expected_summary_status}, got {observation.summary_status}"
        )
    if not observation.workflow_success:
        failure_reasons.append("workflow reported failure")

    passed = not failure_reasons
    return AgentSampleMetrics(
        workflow_latency_ms=observation.workflow_latency_ms,
        trace_completeness=observation.trace_completeness,
        planner_intent_accuracy=planner_intent_accuracy,
        routing_accuracy=routing_accuracy,
        citation_coverage=citation_coverage,
        recommendation_coverage=recommendation_coverage,
        workflow_success=observation.workflow_success,
        tool_call_count=observation.total_tool_calls,
        tool_failure_count=observation.total_tool_failures,
        decision_status=observation.decision_status,
        approval_status=observation.approval_status,
        passed=passed,
        failure_reasons=tuple(failure_reasons),
        per_agent_latency_ms={
            node: observation.nodes[node].latency_ms for node in PHASE2_WORKFLOW_NODES
        },
    )


def calculate_routing_accuracy(
    *,
    expected_agents: tuple[str, ...],
    actual_agents: tuple[str, ...],
) -> float:
    expected = set(expected_agents)
    actual = set(actual_agents)
    if not expected and not actual:
        return 1.0
    union = expected | actual
    if not union:
        return 1.0
    return len(expected & actual) / len(union)


def calculate_citation_coverage(
    *,
    expected_min_citations: int | None,
    actual_citations: int,
) -> float:
    if expected_min_citations is None or expected_min_citations == 0:
        return 1.0
    return min(actual_citations / expected_min_citations, 1.0)


def calculate_recommendation_coverage(
    *,
    expected_recommendation: str | None,
    actual_recommendation: str,
) -> float | None:
    if expected_recommendation is None:
        return None
    return 1.0 if actual_recommendation == expected_recommendation else 0.0
