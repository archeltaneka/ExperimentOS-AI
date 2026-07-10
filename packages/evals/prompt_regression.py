from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import partial
from typing import Any

from apps.api.ask_service import AskRequest, LegacyRagAskService
from packages.evals import run_deepeval, run_ragas
from packages.evals.agent_e2e import (
    AgentE2ECase,
    AgentE2ERun,
    AgentE2ESampleResult,
    AgentE2ESummary,
)
from packages.evals.agent_evaluator import AgentEvaluationRun
from packages.evals.agent_metrics import AgentEvaluationSummary
from packages.evals.dataset import EvaluationQuestion
from packages.evals.evaluator import EvaluationRun, OfflineEvaluator
from packages.llm.client import MockLLMClient
from packages.llm.prompt_registry import PromptRegistry, get_prompt_registry
from packages.llm.prompts import build_grounded_prompt
from packages.qa.question_answering_service import QuestionAnsweringService

FORBIDDEN_HALLUCINATION_MARKERS = (
    "annualized",
    "revenue lift",
    "usd ",
    "statistically significant",
    "roi",
)


@dataclass(frozen=True)
class PromptRegressionMetricComparison:
    name: str
    baseline: float | None
    candidate: float | None
    delta: float | None
    regressions: int
    improvements: int


@dataclass(frozen=True)
class PromptRegressionFrameworkComparison:
    framework: str
    metrics: tuple[PromptRegressionMetricComparison, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PromptRegressionCaseResult:
    case_id: str
    surface: str
    baseline_output: str
    candidate_output: str
    metric_scores: dict[str, dict[str, float | bool | None]]
    regression_detected: bool
    improvement_detected: bool
    failed: bool
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PromptRegressionSummary:
    cases_run: int
    regressions: int
    improvements: int
    unchanged: int
    failures: int
    skipped: int
    passed: bool


@dataclass(frozen=True)
class PromptRegressionReport:
    prompt_id: str
    baseline_version: str
    candidate_version: str
    dataset: str
    case_results: tuple[PromptRegressionCaseResult, ...]
    metrics: tuple[PromptRegressionMetricComparison, ...]
    ragas_comparison: PromptRegressionFrameworkComparison | None
    deepeval_comparison: PromptRegressionFrameworkComparison | None
    summary: PromptRegressionSummary


@dataclass(frozen=True)
class _RecordedRetrieval:
    response: list[Any]
    metrics: Any


class _RecordingRetrievalService:
    def __init__(self, base_service: Any) -> None:
        self.base_service = base_service
        self.last_metrics = getattr(base_service, "last_metrics", None)
        self.recorded: dict[tuple[str, str, int], _RecordedRetrieval] = {}

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[Any]:
        response = await self.base_service.search_by_experiment(
            experiment_id,
            query,
            top_k=top_k,
        )
        self.last_metrics = getattr(self.base_service, "last_metrics", None)
        self.recorded[(str(experiment_id), query.strip(), top_k)] = _RecordedRetrieval(
            response=list(response),
            metrics=self.last_metrics,
        )
        return response


class _ReplayRetrievalService:
    def __init__(self, recorded: dict[tuple[str, str, int], _RecordedRetrieval]) -> None:
        self.recorded = dict(recorded)
        self.last_metrics = None

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[Any]:
        key = (str(experiment_id), query.strip(), top_k)
        try:
            recorded = self.recorded[key]
        except KeyError as exc:
            raise KeyError(f"missing recorded retrieval for {key}") from exc
        self.last_metrics = recorded.metrics
        return list(recorded.response)


class PromptRegressionRunner:
    def __init__(
        self,
        *,
        prompt_registry: PromptRegistry | None = None,
        prompt_id: str,
        baseline_version: str,
        candidate_version: str,
        qa_questions: list[EvaluationQuestion],
        ask_cases: list[AgentE2ECase],
        retrieval_service: Any,
        llm_client_factory: Any | None = None,
        dataset_label: str = "data/eval/qa_dataset.json",
        judge_mode: bool = False,
        deepeval_judge_provider: str | None = None,
        deepeval_judge_model: str | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry or get_prompt_registry()
        self.prompt_id = prompt_id
        self.baseline_version = baseline_version
        self.candidate_version = candidate_version
        self.qa_questions = list(qa_questions)
        self.ask_cases = list(ask_cases)
        self.retrieval_service = retrieval_service
        self.llm_client_factory = llm_client_factory or (
            lambda _surface: build_prompt_regression_mock_llm()
        )
        self.dataset_label = dataset_label
        self.judge_mode = judge_mode
        self.deepeval_judge_provider = deepeval_judge_provider
        self.deepeval_judge_model = deepeval_judge_model

        self.prompt_registry.get(prompt_id, baseline_version)
        self.prompt_registry.get(prompt_id, candidate_version)

    async def evaluate(self) -> PromptRegressionReport:
        baseline_qa_run, recorded_qa = await self._evaluate_qa(self.baseline_version)
        candidate_qa_run, _ = await self._evaluate_qa(
            self.candidate_version,
            recorded=recorded_qa,
        )
        baseline_ask_run, recorded_ask = await self._evaluate_ask(self.baseline_version)
        candidate_ask_run, _ = await self._evaluate_ask(
            self.candidate_version,
            recorded=recorded_ask,
        )

        case_results = tuple(
            [
                *self._compare_qa_cases(baseline_qa_run, candidate_qa_run),
                *self._compare_ask_cases(baseline_ask_run, candidate_ask_run),
            ]
        )
        metrics = _summarize_case_metrics(case_results)
        ragas_comparison = self._build_ragas_comparison(baseline_qa_run, candidate_qa_run)
        deepeval_comparison = self._build_deepeval_comparison(
            baseline_qa_run,
            candidate_qa_run,
            baseline_ask_run,
            candidate_ask_run,
        )
        summary = PromptRegressionSummary(
            cases_run=len(case_results),
            regressions=sum(1 for case in case_results if case.regression_detected),
            improvements=sum(1 for case in case_results if case.improvement_detected),
            unchanged=sum(
                1
                for case in case_results
                if (
                    not case.regression_detected
                    and not case.improvement_detected
                    and not case.failed
                )
            ),
            failures=sum(1 for case in case_results if case.failed),
            skipped=0,
            passed=not any(case.regression_detected or case.failed for case in case_results),
        )
        return PromptRegressionReport(
            prompt_id=self.prompt_id,
            baseline_version=self.baseline_version,
            candidate_version=self.candidate_version,
            dataset=self.dataset_label,
            case_results=case_results,
            metrics=metrics,
            ragas_comparison=ragas_comparison,
            deepeval_comparison=deepeval_comparison,
            summary=summary,
        )

    async def _evaluate_qa(
        self,
        version: str,
        *,
        recorded: dict[tuple[str, str, int], _RecordedRetrieval] | None = None,
    ) -> tuple[EvaluationRun, dict[tuple[str, str, int], _RecordedRetrieval]]:
        retrieval_service, captured = self._resolve_retrieval_service(recorded)
        service = QuestionAnsweringService(
            retrieval_service=retrieval_service,
            llm_client=self.llm_client_factory("legacy_rag.qa"),
            prompt_builder=partial(
                build_grounded_prompt,
                registry=self.prompt_registry,
                prompt_id=self.prompt_id,
                version=version,
            ),
        )
        evaluator = OfflineEvaluator(
            qa_service=service,
            questions=self.qa_questions,
            top_k=5,
            embedding_provider="fake",
            embedding_model="fake",
            llm_provider="mock",
            llm_model="mock-prompt-regression",
        )
        return await evaluator.evaluate(), captured

    async def _evaluate_ask(
        self,
        version: str,
        *,
        recorded: dict[tuple[str, str, int], _RecordedRetrieval] | None = None,
    ) -> tuple[AgentE2ERun, dict[tuple[str, str, int], _RecordedRetrieval]]:
        if not self.ask_cases:
            return AgentE2ERun(samples=[], summary=AgentE2ESummary.from_samples([])), {}

        retrieval_service, captured = self._resolve_retrieval_service(recorded)
        qa_service = QuestionAnsweringService(
            retrieval_service=retrieval_service,
            llm_client=self.llm_client_factory("legacy_rag.ask"),
            prompt_builder=partial(
                build_grounded_prompt,
                registry=self.prompt_registry,
                prompt_id=self.prompt_id,
                version=version,
            ),
        )
        ask_service = LegacyRagAskService(qa_service)
        samples: list[AgentE2ESampleResult] = []
        for case in self.ask_cases:
            try:
                response = await ask_service.answer(
                    AskRequest(
                        question=case.question,
                        experiment_id=case.experiment_id,
                        top_k=case.top_k,
                    )
                )
                samples.append(
                    AgentE2ESampleResult(
                        case=case,
                        status_code=200,
                        response_json=response.model_dump(),
                        latency_ms=0.0,
                        used_agent_workflow=False,
                        used_legacy_fallback=True,
                        passed=True,
                        failure_reasons=(),
                    )
                )
            except Exception as exc:
                samples.append(
                    AgentE2ESampleResult(
                        case=case,
                        status_code=500,
                        response_json={"detail": f"{type(exc).__name__}: {exc}"},
                        latency_ms=0.0,
                        used_agent_workflow=False,
                        used_legacy_fallback=False,
                        passed=False,
                        failure_reasons=(f"{type(exc).__name__}: {exc}",),
                    )
                )
        return AgentE2ERun(samples=samples, summary=AgentE2ESummary.from_samples(samples)), captured

    def _resolve_retrieval_service(
        self,
        recorded: dict[tuple[str, str, int], _RecordedRetrieval] | None,
    ) -> tuple[Any, dict[tuple[str, str, int], _RecordedRetrieval]]:
        if recorded is None:
            wrapper = _RecordingRetrievalService(self.retrieval_service)
            return wrapper, wrapper.recorded
        return _ReplayRetrievalService(recorded), recorded

    def _compare_qa_cases(
        self,
        baseline_run: EvaluationRun,
        candidate_run: EvaluationRun,
    ) -> list[PromptRegressionCaseResult]:
        baseline_map = {sample.question.id: sample for sample in baseline_run.samples}
        candidate_map = {sample.question.id: sample for sample in candidate_run.samples}
        results: list[PromptRegressionCaseResult] = []
        for question in self.qa_questions:
            baseline = baseline_map[question.id]
            candidate = candidate_map[question.id]
            baseline_scores = {
                "prompt_rendering_success": 0.0 if baseline.error else 1.0,
                "answer_generated": _binary_score(bool(baseline.answer.strip())),
                "keyword_coverage": _keyword_coverage(baseline.answer, question.expected_keywords),
                "document_reference_coverage": _document_reference_coverage(
                    baseline.answer,
                    question.expected_documents,
                ),
                "citation_coverage": (
                    baseline.metrics.citation_coverage if baseline.metrics is not None else 0.0
                ),
                "retrieval_consistency": _binary_score(
                    baseline.retrieved_documents == candidate.retrieved_documents
                    and baseline.retrieved_contexts == candidate.retrieved_contexts
                ),
                "forbidden_hallucination_markers": _hallucination_score(baseline.answer),
            }
            candidate_scores = {
                "prompt_rendering_success": 0.0 if candidate.error else 1.0,
                "answer_generated": _binary_score(bool(candidate.answer.strip())),
                "keyword_coverage": _keyword_coverage(
                    candidate.answer,
                    question.expected_keywords,
                ),
                "document_reference_coverage": _document_reference_coverage(
                    candidate.answer,
                    question.expected_documents,
                ),
                "citation_coverage": (
                    candidate.metrics.citation_coverage if candidate.metrics is not None else 0.0
                ),
                "retrieval_consistency": _binary_score(
                    baseline.retrieved_documents == candidate.retrieved_documents
                    and baseline.retrieved_contexts == candidate.retrieved_contexts
                ),
                "forbidden_hallucination_markers": _hallucination_score(candidate.answer),
            }
            metric_scores, regression, improvement = _compare_scores(
                baseline_scores,
                candidate_scores,
            )
            notes: list[str] = []
            if baseline.error:
                notes.append(baseline.error)
            if candidate.error:
                notes.append(candidate.error)
            results.append(
                PromptRegressionCaseResult(
                    case_id=question.id,
                    surface="legacy_rag",
                    baseline_output=baseline.answer,
                    candidate_output=candidate.answer,
                    metric_scores=metric_scores,
                    regression_detected=regression,
                    improvement_detected=improvement,
                    failed=baseline.error is not None or candidate.error is not None,
                    notes=tuple(notes),
                )
            )
        return results

    def _compare_ask_cases(
        self,
        baseline_run: AgentE2ERun,
        candidate_run: AgentE2ERun,
    ) -> list[PromptRegressionCaseResult]:
        baseline_map = {sample.case.id: sample for sample in baseline_run.samples}
        candidate_map = {sample.case.id: sample for sample in candidate_run.samples}
        results: list[PromptRegressionCaseResult] = []
        for case in self.ask_cases:
            baseline = baseline_map[case.id]
            candidate = candidate_map[case.id]
            baseline_response = baseline.response_json
            candidate_response = candidate.response_json
            baseline_scores = {
                "prompt_rendering_success": _binary_score(baseline.status_code == 200),
                "answer_generated": _binary_score(
                    bool(str(baseline_response.get("answer", "")).strip())
                ),
                "legacy_fallback_compatibility": _binary_score(
                    _legacy_ask_is_compatible(baseline_response)
                ),
                "structured_output_validity": _binary_score(
                    _legacy_ask_is_structurally_valid(baseline_response)
                ),
                "document_reference_coverage": _document_reference_coverage(
                    str(baseline_response.get("answer", "")),
                    tuple(_citation_documents(baseline_response)),
                ),
                "forbidden_hallucination_markers": _hallucination_score(
                    str(baseline_response.get("answer", ""))
                ),
            }
            candidate_scores = {
                "prompt_rendering_success": _binary_score(candidate.status_code == 200),
                "answer_generated": _binary_score(
                    bool(str(candidate_response.get("answer", "")).strip())
                ),
                "legacy_fallback_compatibility": _binary_score(
                    _legacy_ask_is_compatible(candidate_response)
                ),
                "structured_output_validity": _binary_score(
                    _legacy_ask_is_structurally_valid(candidate_response)
                ),
                "document_reference_coverage": _document_reference_coverage(
                    str(candidate_response.get("answer", "")),
                    tuple(_citation_documents(candidate_response)),
                ),
                "forbidden_hallucination_markers": _hallucination_score(
                    str(candidate_response.get("answer", ""))
                ),
            }
            metric_scores, regression, improvement = _compare_scores(
                baseline_scores,
                candidate_scores,
            )
            notes: list[str] = []
            if baseline.status_code != 200:
                notes.extend(baseline.failure_reasons)
            if candidate.status_code != 200:
                notes.extend(candidate.failure_reasons)
            results.append(
                PromptRegressionCaseResult(
                    case_id=case.id,
                    surface="legacy_rag.ask",
                    baseline_output=str(baseline_response.get("answer", "")),
                    candidate_output=str(candidate_response.get("answer", "")),
                    metric_scores=metric_scores,
                    regression_detected=regression,
                    improvement_detected=improvement,
                    failed=baseline.status_code != 200 or candidate.status_code != 200,
                    notes=tuple(notes),
                )
            )
        return results

    def _build_ragas_comparison(
        self,
        baseline_run: EvaluationRun,
        candidate_run: EvaluationRun,
    ) -> PromptRegressionFrameworkComparison | None:
        baseline_report = _build_ragas_report_for_run(baseline_run, self.dataset_label)
        candidate_report = _build_ragas_report_for_run(candidate_run, self.dataset_label)
        return _compare_framework_reports(
            framework="ragas",
            baseline_metrics={
                metric.name: metric.average_score
                for metric in baseline_report.metric_results
                if metric.average_score is not None
            },
            candidate_metrics={
                metric.name: metric.average_score
                for metric in candidate_report.metric_results
                if metric.average_score is not None
            },
            notes=tuple(
                dict.fromkeys([*baseline_report.limitations, *candidate_report.limitations])
            ),
        )

    def _build_deepeval_comparison(
        self,
        baseline_qa_run: EvaluationRun,
        candidate_qa_run: EvaluationRun,
        baseline_ask_run: AgentE2ERun,
        candidate_ask_run: AgentE2ERun,
    ) -> PromptRegressionFrameworkComparison | None:
        baseline_report = _build_deepeval_report_for_runs(
            baseline_qa_run,
            baseline_ask_run,
            self.dataset_label,
            judge_mode=self.judge_mode,
            judge_provider=self.deepeval_judge_provider,
            judge_model=self.deepeval_judge_model,
        )
        candidate_report = _build_deepeval_report_for_runs(
            candidate_qa_run,
            candidate_ask_run,
            self.dataset_label,
            judge_mode=self.judge_mode,
            judge_provider=self.deepeval_judge_provider,
            judge_model=self.deepeval_judge_model,
        )
        return _compare_framework_reports(
            framework="deepeval",
            baseline_metrics=_average_deepeval_scores(baseline_report),
            candidate_metrics=_average_deepeval_scores(candidate_report),
            notes=tuple(
                dict.fromkeys([*baseline_report.limitations, *candidate_report.limitations])
            ),
        )


def build_prompt_regression_mock_llm() -> MockLLMClient:
    return MockLLMClient(
        model="mock-prompt-regression",
        response_builder=_build_prompt_sensitive_answer,
    )


def render_prompt_regression_report(report: PromptRegressionReport) -> str:
    lines = [
        "# Prompt Regression Report",
        "",
        f"- Prompt ID: {report.prompt_id}",
        f"- Baseline version: {report.baseline_version}",
        f"- Candidate version: {report.candidate_version}",
        f"- Dataset: {report.dataset}",
        f"- Cases run: {report.summary.cases_run}",
        f"- Regressions: {report.summary.regressions}",
        f"- Improvements: {report.summary.improvements}",
        f"- Unchanged: {report.summary.unchanged}",
        f"- Failures: {report.summary.failures}",
        f"- Pass/fail: {'pass' if report.summary.passed else 'fail'}",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Baseline | Candidate | Delta | Regressions | Improvements |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for metric in report.metrics:
        lines.append(
            f"| {metric.name} | {_format_score(metric.baseline)} | "
            f"{_format_score(metric.candidate)} | {_format_score(metric.delta)} | "
            f"{metric.regressions} | {metric.improvements} |"
        )

    lines.extend(["", "## Case Results", ""])
    for case in report.case_results:
        status = "unchanged"
        if case.regression_detected:
            status = "regression"
        elif case.improvement_detected:
            status = "improvement"
        lines.append(f"- `{case.case_id}` ({case.surface}): {status}")
        if case.notes:
            lines.append(f"  Notes: {' | '.join(case.notes)}")

    for framework in (report.ragas_comparison, report.deepeval_comparison):
        if framework is None:
            continue
        lines.extend(
            [
                "",
                f"## {framework.framework.upper()} Comparison",
                "",
                "| Metric | Baseline | Candidate | Delta |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for metric in framework.metrics:
            lines.append(
                f"| {metric.name} | {_format_score(metric.baseline)} | "
                f"{_format_score(metric.candidate)} | {_format_score(metric.delta)} |"
            )
        if framework.notes:
            lines.extend(["", "Notes:"])
            for note in framework.notes:
                lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def prompt_regression_to_json(report: PromptRegressionReport) -> str:
    return json.dumps(asdict(report), indent=2)


def _build_prompt_sensitive_answer(prompt: str, system_instruction: str) -> str:
    combined = f"{system_instruction}\n{prompt}".lower()
    question = _extract_block(prompt, "User Question:")
    if not question:
        question = _extract_block(prompt, "Question:")
    context = _extract_context(prompt)
    document_names = _extract_document_names(prompt)
    if "answer quickly" in combined:
        return "Quick answer."

    if (
        any(fragment in question.lower() for fragment in ("roi", "revenue", "annualized"))
        and "insufficient evidence" in combined
        and "under-counted" in context.lower()
    ):
        answer = "Insufficient evidence exists to answer the question."
    else:
        answer = _best_context_sentence(context)

    if "cite the supporting documents" in combined and document_names:
        answer = f"{answer} Source: {', '.join(document_names)}."
    return answer.strip()


def _extract_block(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.split(prefix, maxsplit=1)[1].strip()
    return ""


def _extract_context(prompt: str) -> str:
    chunks: list[str] = []
    collecting = False
    for line in prompt.splitlines():
        if line.startswith("Retrieved Context:") or line.startswith("Context:"):
            collecting = True
            continue
        if collecting and line.startswith("Answer using"):
            break
        if collecting:
            chunks.append(line)
    return "\n".join(chunks).strip()


def _extract_document_names(prompt: str) -> list[str]:
    names: list[str] = []
    for line in prompt.splitlines():
        if line.startswith("Document:"):
            name = line.split("Document:", maxsplit=1)[1].strip()
            if name and name not in names:
                names.append(name)
    return names


def _best_context_sentence(context: str) -> str:
    cleaned = " ".join(part.strip() for part in context.splitlines() if part.strip())
    if not cleaned:
        return "Insufficient evidence exists to answer the question."
    for sentence in cleaned.split("."):
        candidate = sentence.strip()
        if any(token in candidate.lower() for token in ("roll out", "monitoring", "wallet")):
            return f"{candidate}."
    first = cleaned.split(".")[0].strip()
    return f"{first}." if first else "Insufficient evidence exists to answer the question."


def _binary_score(value: bool) -> float:
    return 1.0 if value else 0.0


def _keyword_coverage(answer: str, expected_keywords: tuple[str, ...]) -> float:
    if not expected_keywords:
        return 1.0
    normalized = answer.lower()
    hits = sum(1 for keyword in expected_keywords if keyword.lower() in normalized)
    return hits / len(expected_keywords)


def _document_reference_coverage(answer: str, expected_documents: tuple[str, ...]) -> float:
    if not expected_documents:
        return 1.0
    normalized = answer.lower()
    hits = sum(1 for document in expected_documents if document.lower() in normalized)
    return hits / len(expected_documents)


def _hallucination_score(answer: str) -> float:
    normalized = answer.lower()
    return 0.0 if any(marker in normalized for marker in FORBIDDEN_HALLUCINATION_MARKERS) else 1.0


def _legacy_ask_is_compatible(response: dict[str, object]) -> bool:
    return (
        response.get("intent") is None
        and response.get("decision") is None
        and response.get("executive_summary") is None
        and response.get("agent_trace") in ([], None)
        and response.get("agent_metrics") in ({}, None)
    )


def _legacy_ask_is_structurally_valid(response: dict[str, object]) -> bool:
    prompt_metadata = response.get("prompt_metadata")
    citations = response.get("citations")
    return isinstance(prompt_metadata, dict) and isinstance(citations, list)


def _citation_documents(response: dict[str, object]) -> list[str]:
    documents: list[str] = []
    for citation in response.get("citations", []):
        if not isinstance(citation, dict):
            continue
        document = str(citation.get("document", "")).strip()
        if document and document not in documents:
            documents.append(document)
    return documents


def _compare_scores(
    baseline_scores: dict[str, float],
    candidate_scores: dict[str, float],
) -> tuple[dict[str, dict[str, float | bool | None]], bool, bool]:
    metric_scores: dict[str, dict[str, float | bool | None]] = {}
    regression = False
    improvement = False
    for name, baseline in baseline_scores.items():
        candidate = candidate_scores[name]
        delta = candidate - baseline
        metric_regression = candidate < baseline
        metric_improvement = candidate > baseline
        regression = regression or metric_regression
        improvement = improvement or metric_improvement
        metric_scores[name] = {
            "baseline": baseline,
            "candidate": candidate,
            "delta": delta,
            "regression": metric_regression,
            "improvement": metric_improvement,
        }
    return metric_scores, regression, improvement


def _summarize_case_metrics(
    case_results: tuple[PromptRegressionCaseResult, ...],
) -> tuple[PromptRegressionMetricComparison, ...]:
    if not case_results:
        return ()
    metric_names = sorted({name for case in case_results for name in case.metric_scores})
    comparisons: list[PromptRegressionMetricComparison] = []
    for metric_name in metric_names:
        baseline_values = [
            float(case.metric_scores[metric_name]["baseline"])
            for case in case_results
            if metric_name in case.metric_scores
            and case.metric_scores[metric_name]["baseline"] is not None
        ]
        candidate_values = [
            float(case.metric_scores[metric_name]["candidate"])
            for case in case_results
            if metric_name in case.metric_scores
            and case.metric_scores[metric_name]["candidate"] is not None
        ]
        baseline_average = sum(baseline_values) / len(baseline_values) if baseline_values else None
        candidate_average = (
            sum(candidate_values) / len(candidate_values) if candidate_values else None
        )
        delta = None
        if baseline_average is not None and candidate_average is not None:
            delta = candidate_average - baseline_average
        comparisons.append(
            PromptRegressionMetricComparison(
                name=metric_name,
                baseline=baseline_average,
                candidate=candidate_average,
                delta=delta,
                regressions=sum(
                    1
                    for case in case_results
                    if metric_name in case.metric_scores
                    and case.metric_scores[metric_name]["regression"]
                ),
                improvements=sum(
                    1
                    for case in case_results
                    if metric_name in case.metric_scores
                    and case.metric_scores[metric_name]["improvement"]
                ),
            )
        )
    return tuple(comparisons)


def _compare_framework_reports(
    *,
    framework: str,
    baseline_metrics: dict[str, float | None],
    candidate_metrics: dict[str, float | None],
    notes: tuple[str, ...],
) -> PromptRegressionFrameworkComparison:
    metric_names = sorted(set(baseline_metrics) | set(candidate_metrics))
    metrics: list[PromptRegressionMetricComparison] = []
    for name in metric_names:
        baseline = baseline_metrics.get(name)
        candidate = candidate_metrics.get(name)
        delta = None if baseline is None or candidate is None else candidate - baseline
        metrics.append(
            PromptRegressionMetricComparison(
                name=name,
                baseline=baseline,
                candidate=candidate,
                delta=delta,
                regressions=int(delta is not None and delta < 0.0),
                improvements=int(delta is not None and delta > 0.0),
            )
        )
    return PromptRegressionFrameworkComparison(
        framework=framework,
        metrics=tuple(metrics),
        notes=notes,
    )


def _average_deepeval_scores(report: Any) -> dict[str, float | None]:
    grouped: dict[str, list[float]] = {}
    for metric in report.metric_results:
        if metric.skipped or metric.error is not None or metric.score is None:
            continue
        grouped.setdefault(metric.metric_name, []).append(float(metric.score))
    return {
        name: (sum(values) / len(values) if values else None) for name, values in grouped.items()
    }


def _build_ragas_report_for_run(run: EvaluationRun, dataset_label: str) -> Any:
    args = run_ragas.parse_args(
        [
            "--dataset",
            dataset_label,
            "--embedding-provider",
            "fake",
            "--llm-provider",
            "mock",
        ]
    )
    with _patched_attributes(
        run_ragas,
        build_qa_evaluation_run=lambda _args: run,
        run_async=lambda value: value,
    ):
        return run_ragas.build_ragas_report(args)


def _build_deepeval_report_for_runs(
    qa_run: EvaluationRun,
    ask_run: AgentE2ERun,
    dataset_label: str,
    *,
    judge_mode: bool,
    judge_provider: str | None,
    judge_model: str | None,
) -> Any:
    argv = [
        "--mode",
        "judge" if judge_mode else "offline",
        "--dataset",
        dataset_label,
        "--agent-dataset",
        "data/eval/agent_dataset.json",
        "--embedding-provider",
        "fake",
        "--llm-provider",
        "mock",
    ]
    if judge_provider:
        argv.extend(["--judge-provider", judge_provider])
    if judge_model:
        argv.extend(["--judge-model", judge_model])
    args = run_deepeval.parse_args(argv)
    empty_agent_run = AgentEvaluationRun(
        samples=[],
        summary=AgentEvaluationSummary.from_samples([]),
    )
    with _patched_attributes(
        run_deepeval,
        build_qa_evaluation_run=lambda _args: qa_run,
        build_agent_e2e_evaluation_run=lambda _args: ask_run,
        build_agent_evaluation_run=lambda _args: empty_agent_run,
        run_async=lambda value: value,
    ):
        return run_deepeval.build_deepeval_report(args)


@contextmanager
def _patched_attributes(module: Any, **replacements: Any):
    originals = {name: getattr(module, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(module, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(module, name, value)


def _format_score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"
