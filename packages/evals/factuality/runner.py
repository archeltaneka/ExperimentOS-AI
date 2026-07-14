from __future__ import annotations

from datetime import UTC, datetime

from packages.evals.agent_evaluator import AgentEvaluationRun
from packages.evals.deepeval_adapter import (
    DeepEvalBindings,
    DeepEvalPreparedCase,
    build_llm_test_case,
    import_deepeval_bindings,
)
from packages.evals.evaluator import EvaluationRun
from packages.evals.factuality.deterministic import evaluate_case
from packages.evals.factuality.models import (
    CitationRecord,
    EvidenceRecord,
    FactualityCase,
    FactualityCaseResult,
    FactualityPolicy,
    FactualityPolicyResult,
    FactualityReport,
    JudgeMetricResult,
)

_DEFAULT_JUDGE_METRICS = (
    "faithfulness",
    "hallucination",
    "contextual_relevancy",
    "answer_relevancy",
)
_DEFAULT_JUDGE_THRESHOLDS = {
    "faithfulness": 0.5,
    "hallucination": 0.5,
    "contextual_relevancy": 0.5,
    "answer_relevancy": 0.5,
}


def build_legacy_rag_cases(
    run: EvaluationRun,
    *,
    dataset_identifier: str,
) -> list[FactualityCase]:
    cases: list[FactualityCase] = []
    for sample in run.samples:
        if sample.error is not None:
            continue
        evidence = tuple(
            EvidenceRecord(
                source_id=(
                    sample.retrieved_documents[min(index, len(sample.retrieved_documents) - 1)]
                    if sample.retrieved_documents
                    else f"context-{index + 1}"
                ),
                source_type="document",
                text=context,
                metadata={},
            )
            for index, context in enumerate(sample.retrieved_contexts)
        )
        citations = tuple(
            CitationRecord(
                source_id=str(citation.get("document", citation.get("source_id", ""))).strip()
                or f"citation-{index + 1}",
                source_type="document",
                text=None,
                metadata=dict(citation),
            )
            for index, citation in enumerate(sample.citations)
            if isinstance(citation, dict)
        )
        cases.append(
            FactualityCase(
                case_id=sample.question.id,
                dataset_identifier=dataset_identifier,
                question=sample.question.question,
                category=sample.question.category,
                surface="legacy_rag",
                answer=sample.answer,
                citations=citations,
                evidence=evidence,
                expected_min_citations=1 if sample.question.expected_citation_required else 0,
                expected_failure_mode=sample.question.expected_failure_mode,
                prompt_id=sample.prompt_id,
                prompt_version=sample.prompt_version,
                metadata={"reference_answer": sample.question.reference_answer},
            )
        )
    return cases


def build_agent_workflow_cases(
    run: AgentEvaluationRun,
    *,
    dataset_identifier: str,
) -> list[FactualityCase]:
    cases: list[FactualityCase] = []
    for sample in run.samples:
        if sample.error is not None or sample.state is None:
            continue
        state = sample.state
        evidence = tuple(
            EvidenceRecord(
                source_id=str(
                    chunk.get("document_id") or chunk.get("chunk_id") or f"chunk-{index + 1}"
                ),
                source_type="document",
                text=str(chunk.get("content", "")).strip(),
                metadata=dict(chunk.get("metadata", {}))
                if isinstance(chunk.get("metadata", {}), dict)
                else {},
            )
            for index, chunk in enumerate(state["retrieved_chunks"])
        )
        citations = tuple(
            CitationRecord(
                source_id=str(
                    citation.get("document_id")
                    or citation.get("chunk_id")
                    or f"citation-{index + 1}"
                ),
                source_type="document",
                text=str(citation.get("quote", "")).strip() or None,
                metadata=dict(citation.get("metadata", {}))
                if isinstance(citation.get("metadata", {}), dict)
                else {},
            )
            for index, citation in enumerate(state["citations"])
        )
        answer = (
            str(state["executive_summary"].get("summary", "")).strip()
            or str(state["decision"].get("rationale", "")).strip()
            or str(state["experiment_analysis"].get("summary", "")).strip()
        )
        cases.append(
            FactualityCase(
                case_id=sample.case.id,
                dataset_identifier=dataset_identifier,
                question=sample.case.question,
                category=sample.case.category,
                surface="agent_workflow",
                answer=answer,
                citations=citations,
                evidence=evidence,
                experiment_analysis=dict(state["experiment_analysis"]),
                business_impact=dict(state["business_impact"]),
                risk_assessment=dict(state["risk_assessment"]),
                decision=dict(state["decision"]),
                executive_summary=dict(state["executive_summary"]),
                approval_status=state["human_approval"].get("status"),
                expected_min_citations=sample.case.expected_min_citations or 0,
                expected_failure_mode=sample.case.expected_failure_mode,
                expected_decision_status=sample.case.expected_decision_status,
                expected_recommendation=sample.case.expected_recommendation,
                expected_summary_status=sample.case.expected_summary_status,
                expected_approval_status=sample.case.expected_approval_status,
                metadata={
                    "expected_intent": sample.case.expected_intent,
                    "expected_required_agents": list(sample.case.expected_required_agents),
                },
            )
        )
    return cases


def apply_policy(
    case_results: list[FactualityCaseResult],
    *,
    policy: FactualityPolicy,
    judge_metrics: tuple[JudgeMetricResult, ...],
) -> FactualityPolicyResult:
    if not case_results:
        return FactualityPolicyResult(
            status="skipped",
            reasons=("No factuality cases were evaluated.",),
            finding_counts={},
            severity_counts={},
        )

    finding_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    reasons: list[str] = []
    citation_coverages = [result.citation_coverage for result in case_results]

    for result in case_results:
        for finding in result.failed_findings:
            finding_counts[finding.category] = finding_counts.get(finding.category, 0) + 1
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

    if severity_counts.get("critical", 0) > policy.critical_violations_allowed:
        reasons.append("Critical factuality violations exceeded the configured allowance.")
    if (
        finding_counts.get("unsupported_numerical_claim", 0)
        > policy.unsupported_numerical_claims_allowed
    ):
        reasons.append("Unsupported numerical claims exceeded the configured allowance.")
    if (
        finding_counts.get("fabricated_revenue_or_roi", 0)
        > policy.fabricated_financial_claims_allowed
    ):
        reasons.append("Fabricated financial claims exceeded the configured allowance.")
    if (
        finding_counts.get("fabricated_statistical_significance", 0)
        > policy.fabricated_statistical_claims_allowed
    ):
        reasons.append("Fabricated statistical claims exceeded the configured allowance.")
    if citation_coverages and min(citation_coverages) < policy.required_citation_coverage_minimum:
        reasons.append("Citation coverage fell below the configured minimum.")
    if severity_counts.get("medium", 0) > policy.max_unresolved_medium_severity_findings:
        reasons.append("Medium-severity findings exceeded the configured allowance.")

    for metric in judge_metrics:
        if metric.skipped or metric.score is None:
            continue
        threshold = policy.judge_metric_thresholds.get(metric.metric_name)
        if threshold is not None and metric.score < threshold:
            reasons.append(
                f"Judge metric `{metric.metric_name}` fell below the configured threshold."
            )

    status = "fail" if reasons else "pass"
    if status == "pass" and any(result.unparsed_claims for result in case_results):
        status = "warning"
        reasons.append("Some cases could not be parsed conservatively into explicit claims.")
    return FactualityPolicyResult(
        status=status,
        reasons=tuple(dict.fromkeys(reasons)),
        finding_counts=dict(sorted(finding_counts.items())),
        severity_counts=dict(sorted(severity_counts.items())),
    )


def run_deterministic_checks(cases: list[FactualityCase]) -> list[FactualityCaseResult]:
    return [evaluate_case(case) for case in cases]


def run_judge_checks(
    *,
    cases: list[FactualityCase],
    mode: str,
    judge_provider: str,
    judge_model: str | None = None,
    metrics: tuple[str, ...] = _DEFAULT_JUDGE_METRICS,
) -> tuple[JudgeMetricResult, ...]:
    if mode == "offline":
        return tuple(
            JudgeMetricResult(
                framework="deepeval",
                metric_name=metric_name,
                case_id=case.case_id,
                surface=case.surface,
                score=None,
                threshold=_DEFAULT_JUDGE_THRESHOLDS[metric_name],
                passed=None,
                skipped=True,
                reason="Judge metrics are disabled in offline mode.",
                provider=judge_provider,
                model=judge_model,
            )
            for case in cases
            for metric_name in metrics
        )
    if judge_provider == "none" or not judge_model:
        return tuple(
            JudgeMetricResult(
                framework="deepeval",
                metric_name=metric_name,
                case_id=case.case_id,
                surface=case.surface,
                score=None,
                threshold=_DEFAULT_JUDGE_THRESHOLDS[metric_name],
                passed=None,
                skipped=True,
                reason="Judge mode requires an explicit provider and model.",
                provider=judge_provider,
                model=judge_model,
            )
            for case in cases
            for metric_name in metrics
        )
    try:
        bindings = import_deepeval_bindings()
    except Exception as exc:
        return tuple(
            JudgeMetricResult(
                framework="deepeval",
                metric_name=metric_name,
                case_id=case.case_id,
                surface=case.surface,
                score=None,
                threshold=_DEFAULT_JUDGE_THRESHOLDS[metric_name],
                passed=None,
                skipped=True,
                reason=f"DeepEval bindings unavailable: {type(exc).__name__}: {exc}",
                provider=judge_provider,
                model=judge_model,
            )
            for case in cases
            for metric_name in metrics
        )
    return _run_deepeval_metrics(
        cases=cases,
        metrics=metrics,
        bindings=bindings,
        judge_provider=judge_provider,
        judge_model=judge_model,
    )


def build_factuality_report(
    *,
    target: str,
    mode: str,
    legacy_run: EvaluationRun | None,
    agent_run: AgentEvaluationRun | None,
    dataset_identifier: str,
    agent_dataset_identifier: str,
    judge_provider: str = "none",
    judge_model: str | None = None,
    policy: FactualityPolicy | None = None,
    case_id: str | None = None,
    category: str | None = None,
) -> FactualityReport:
    cases: list[FactualityCase] = []
    if target in {"legacy_rag", "all"} and legacy_run is not None:
        cases.extend(build_legacy_rag_cases(legacy_run, dataset_identifier=dataset_identifier))
    if target in {"agent_workflow", "all"} and agent_run is not None:
        cases.extend(
            build_agent_workflow_cases(agent_run, dataset_identifier=agent_dataset_identifier)
        )
    if case_id is not None:
        cases = [case for case in cases if case.case_id == case_id]
    if category is not None:
        cases = [case for case in cases if case.category == category]
    case_results = run_deterministic_checks(cases)
    judge_metrics = run_judge_checks(
        cases=cases,
        mode=mode,
        judge_provider=judge_provider,
        judge_model=judge_model,
    )
    policy_result = apply_policy(
        case_results,
        policy=policy or FactualityPolicy(judge_metric_thresholds=dict(_DEFAULT_JUDGE_THRESHOLDS)),
        judge_metrics=judge_metrics,
    )
    limitations = (
        "Deterministic checks are conservative and do not prove universal factual correctness.",
        "Numerical and workflow assertions remain deterministic; judge metrics are optional.",
        "Offline mode never invokes a live provider.",
    )
    return FactualityReport.build(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        target=target,
        mode=mode,
        dataset_identifiers=tuple(
            identifier
            for identifier in (dataset_identifier, agent_dataset_identifier)
            if identifier
        ),
        case_results=tuple(case_results),
        judge_metrics=judge_metrics,
        policy_result=policy_result,
        judge_provider=judge_provider,
        judge_model=judge_model,
        limitations=limitations,
    )


def _run_deepeval_metrics(
    *,
    cases: list[FactualityCase],
    metrics: tuple[str, ...],
    bindings: DeepEvalBindings,
    judge_provider: str,
    judge_model: str,
) -> tuple[JudgeMetricResult, ...]:
    metric_factories = {name: bindings.metric_factories[name] for name in metrics}
    prepared_cases = [_to_deepeval_case(case) for case in cases]
    results: list[JudgeMetricResult] = []
    for metric_name, factory in metric_factories.items():
        metric = factory(
            threshold=_DEFAULT_JUDGE_THRESHOLDS[metric_name],
            model=judge_model,
            async_mode=False,
        )
        evaluation = bindings.evaluate(
            test_cases=[
                build_llm_test_case(prepared_case, bindings=bindings)
                for prepared_case in prepared_cases
            ],
            metrics=[metric],
            async_config=bindings.AsyncConfig(run_async=False),
            display_config=bindings.DisplayConfig(
                show_indicator=False,
                print_results=False,
                inspect_after_run=False,
            ),
            cache_config=bindings.CacheConfig(write_cache=False, use_cache=False),
            error_config=bindings.ErrorConfig(ignore_errors=False, skip_on_missing_params=True),
        )
        for case, test_result in zip(cases, getattr(evaluation, "test_results", []), strict=True):
            metric_data = next(
                (
                    item
                    for item in getattr(test_result, "metrics_data", []) or []
                    if getattr(item, "name", None) == metric_name
                ),
                None,
            )
            if metric_data is None:
                results.append(
                    JudgeMetricResult(
                        framework="deepeval",
                        metric_name=metric_name,
                        case_id=case.case_id,
                        surface=case.surface,
                        score=None,
                        threshold=_DEFAULT_JUDGE_THRESHOLDS[metric_name],
                        passed=False,
                        skipped=False,
                        reason="DeepEval returned no metric payload for the case.",
                        provider=judge_provider,
                        model=judge_model,
                    )
                )
                continue
            results.append(
                JudgeMetricResult(
                    framework="deepeval",
                    metric_name=metric_name,
                    case_id=case.case_id,
                    surface=case.surface,
                    score=float(getattr(metric_data, "score", 0.0)),
                    threshold=float(
                        getattr(metric_data, "threshold", _DEFAULT_JUDGE_THRESHOLDS[metric_name])
                    ),
                    passed=bool(getattr(metric_data, "success", False)),
                    skipped=False,
                    reason=getattr(metric_data, "reason", None),
                    provider=judge_provider,
                    model=judge_model,
                )
            )
    return tuple(results)


def _to_deepeval_case(case: FactualityCase) -> DeepEvalPreparedCase:
    return DeepEvalPreparedCase(
        case_id=case.case_id,
        category=case.category,
        scope="response",
        surface=case.surface,
        dataset_identifier=case.dataset_identifier,
        input_text=case.question,
        actual_output=case.answer,
        expected_output=None,
        context=tuple(record.text for record in case.evidence),
        retrieval_context=tuple(record.text for record in case.evidence),
        metadata={
            "prompt_id": case.prompt_id,
            "prompt_version": case.prompt_version,
            "expected_min_citations": case.expected_min_citations,
        },
    )
