"""Execute real request/state/API boundaries through the existing E2E evaluator."""

from copy import deepcopy
from time import perf_counter

from .checks import check, evidence_checks, merge_checks
from .models import WorkflowCaseResult


class CapturedWorkflow:
    def __init__(self, delegate):
        self.delegate = delegate
        self.analysis = None

    def run(self, *args, **kwargs):
        state = self.delegate.run(*args, **kwargs)
        result = state.get("analysis_result")
        self.analysis = result.model_dump(mode="json") if result is not None else None
        return state


def evaluate_workflow_case(case, *, observability_provider=None):
    from packages.evals.agent_analysis_cases import analysis_case_plan, build_analysis_case_service
    from packages.evals.agent_e2e import FULL_AGENT_TRACE_NODES, AgentE2ECase, AgentE2EEvaluator

    started = perf_counter()
    workflow = CapturedWorkflow(
        build_analysis_case_service(case, observability_provider=observability_provider)
    )
    plan = analysis_case_plan(case)
    api_case = AgentE2ECase(
        id="analysis-" + case.case_id,
        question=str(case.ask_payload["question"]),
        experiment_id=str(case.ask_payload["experiment_id"]),
        scenario="analysis",
        analysis_case=case,
        expected_intent=plan.intent,
        expected_required_agents=tuple(plan.required_agents),
        expect_agent_trace=True,
        expected_trace_nodes=FULL_AGENT_TRACE_NODES,
        expect_executive_summary=True,
        expected_min_citations=1,
    )
    sample = (
        AgentE2EEvaluator(
            cases=[api_case],
            service_factory=lambda _: workflow,
            observability_provider=observability_provider,
        )
        .evaluate()
        .samples[0]
    )
    public = sample.response_json.get("analysis")
    if not isinstance(public, dict):
        public = {}
    evidence = public.get("evidence")
    checks = merge_checks(sample.analysis_checks, evidence_checks(case, evidence))
    checks["state_preserved"] = check(case, "state_preserved", workflow.analysis == public)
    checks["api_contract"] = check(
        case, "api_contract", sample.status_code == 200 and not sample.failure_reasons
    )
    checks = {
        code: value.model_copy(
            update={"case_id": case.case_id, "rule_id": "analysis.failures." + code}
        )
        for code, value in checks.items()
    }
    return WorkflowCaseResult(
        case_id=case.case_id,
        case_version=case.case_version,
        family=case.family,
        method=public.get("method"),
        design=case.design,
        estimand=case.estimand,
        execution_status=public.get("status", "failed"),
        native_status=evidence.get("status", evidence.get("current_status")) if evidence else None,
        checks=checks,
        evidence=deepcopy(evidence),
        business_evidence=deepcopy(public.get("business_impact")),
        duration_ms=(perf_counter() - started) * 1000,
        dependency_state="controlled" if case.optional_unavailable else "not_required",
        execution_kind="controlled" if case.optional_unavailable else "real",
    )
