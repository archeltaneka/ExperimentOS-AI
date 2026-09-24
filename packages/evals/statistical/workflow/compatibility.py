"""Small executed old-surface controls, with honest external-check skips."""

from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter

SURFACES = (
    "legacy_rag_api",
    "agent_workflow",
    "old_ask_api",
    "prompts",
    "phase3_policy",
    "factuality",
    "internal_traces",
    "database",
    "langsmith",
    "phoenix",
    "otel_sdk",
)
EXTERNAL_SURFACES = frozenset({"database", "langsmith", "phoenix", "otel_sdk"})


@dataclass(frozen=True)
class CompatibilityResult:
    surface: str
    status: str
    reason: str
    evidence_ids: tuple[str, ...]
    duration_ms: float = 0


def evaluate_compatibility():
    from packages.evals.agent_dataset import load_agent_evaluation_dataset
    from packages.evals.agent_e2e import AgentE2EEvaluator, build_default_agent_e2e_cases
    from packages.evals.agent_evaluator import (
        AgentWorkflowEvaluator,
        build_default_agent_workflow_service,
    )
    from packages.evals.ci_quality_gate import validate_policy_invariants
    from packages.evals.factuality.deterministic import evaluate_case
    from packages.evals.factuality.models import FactualityCase
    from packages.evals.policy.config import load_quality_policy
    from packages.llm.client import MockLLMClient
    from packages.llm.prompt_registry import get_prompt_registry
    from packages.qa.question_answering_service import QuestionAnsweringService
    from packages.retrieval.service import RetrievalMetrics, RetrievalResult

    results = []
    started = perf_counter()

    def record(surface, passed, *evidence):
        nonlocal started
        finished = perf_counter()
        results.append(
            CompatibilityResult(
                surface,
                "pass" if passed else "fail",
                "executed_offline",
                tuple(evidence),
                (finished - started) * 1000,
            )
        )
        started = finished

    class Retrieval:
        calls = 0
        last_metrics = RetrievalMetrics(
            embedding_time_ms=0, vector_search_time_ms=0, retrieved_chunks=1, average_similarity=1
        )

        async def search_by_experiment(self, experiment_id, query, *, top_k=5):
            self.calls += 1
            return [
                RetrievalResult(
                    experiment_id=str(experiment_id),
                    experiment_name="Reference",
                    document_id="reference-document",
                    document_name="Reference",
                    chunk_text="The experiment requires more evidence.",
                    similarity=1,
                    metadata={},
                )
            ]

    async def exists(_):
        return True

    retrieval = Retrieval()
    qa = QuestionAnsweringService(
        retrieval_service=retrieval,
        llm_client=MockLLMClient(answer="The experiment requires more evidence."),
        experiment_exists=exists,
    )
    legacy = next(c for c in build_default_agent_e2e_cases() if c.id == "legacy-fallback")
    sample = (
        AgentE2EEvaluator(cases=[legacy], qa_service_factory=lambda _: qa).evaluate().samples[0]
    )
    record(
        "legacy_rag_api",
        sample.passed and retrieval.calls == 1 and sample.response_json.get("analysis") is None,
        "real_qa",
        "real_ask",
        "mock_llm",
        "fixture_retrieval",
    )

    cases = [c for c in load_agent_evaluation_dataset() if c.analysis_case is None]
    run = AgentWorkflowEvaluator(
        workflow_service=build_default_agent_workflow_service(), cases=cases
    ).evaluate()
    record(
        "agent_workflow", bool(run.samples) and run.summary.fail_count == 0, "real_agent_evaluator"
    )
    old = next(c for c in build_default_agent_e2e_cases() if c.id == "decision-loyalty-default")
    # The existing evaluation human-approval fixture approves this grounded case.
    old = replace(old, expected_approval_status="approved")
    sample = (
        AgentE2EEvaluator(
            cases=[old], service_factory=lambda _: build_default_agent_workflow_service()
        )
        .evaluate()
        .samples[0]
    )
    record(
        "old_ask_api",
        sample.passed and sample.response_json.get("analysis") is None,
        "real_agent_ask",
    )
    record(
        "internal_traces",
        bool(sample.response_json.get("agent_trace"))
        and bool(sample.response_json.get("agent_metrics")),
        "real_agent_trace",
    )
    get_prompt_registry().validate()
    record("prompts", True, "registry_validation")
    validate_policy_invariants(load_quality_policy(Path("config/evaluation/quality_policy.yaml")))
    record("phase3_policy", True, "unchanged_zero_tolerance_guards")
    bad = evaluate_case(
        FactualityCase(
            case_id="compatibility-factuality",
            dataset_identifier="phase4",
            question="What is the impact?",
            category="business",
            surface="agent_workflow",
            answer="This created USD 2,000,000 in revenue lift.",
            business_impact={
                "impact_status": "insufficient_data",
                "estimated_annualized_impact": None,
            },
        )
    )
    record(
        "factuality",
        any(f.category == "fabricated_revenue_or_roi" for f in bad.failed_findings),
        "deterministic_financial_fabrication_detection",
    )
    results.extend(
        CompatibilityResult(surface, "skipped", "external_integration_not_executed", ())
        for surface in sorted(EXTERNAL_SURFACES)
    )
    return tuple(results)


def workflow_compatibility_results():
    from .models import AnalysisCheck, WorkflowCaseResult

    return tuple(
        WorkflowCaseResult(
            case_id="compatibility-" + r.surface,
            case_version="1",
            family="compatibility",
            method=None,
            design="not_applicable",
            estimand="not_applicable",
            execution_status="not_executed" if r.status == "skipped" else "completed",
            duration_ms=r.duration_ms,
            execution_kind="external" if r.status == "skipped" else "real",
            checks={
                "compatibility": AnalysisCheck(
                    code="compatibility",
                    status=r.status,
                    method=None,
                    execution_status="not_executed" if r.status == "skipped" else "completed",
                    applicable=r.status != "skipped",
                    rule_id="analysis.failures.compatibility",
                    case_id="compatibility-" + r.surface,
                    diagnostic_evidence=(r.reason, *r.evidence_ids),
                )
            },
        )
        for r in evaluate_compatibility()
    )
