from __future__ import annotations

from functools import partial

from packages.evals.agent_e2e import AgentE2ECase
from packages.evals.dataset import EvaluationQuestion
from packages.evals.evaluator import EvaluationRun, OfflineEvaluator
from packages.evals.factuality.runner import build_factuality_report
from packages.evals.prompt_experiments.models import (
    PromptExperimentDefinition,
    PromptExperimentRecommendation,
    PromptExperimentReport,
    PromptExperimentVariantResult,
)
from packages.evals.prompt_experiments.validation import validate_prompt_experiment_definition
from packages.evals.prompt_regression import (
    PromptRegressionReport,
    PromptRegressionRunner,
    _RecordedRetrieval,
    _RecordingRetrievalService,
    _ReplayRetrievalService,
    build_prompt_regression_mock_llm,
)
from packages.llm.prompts import build_grounded_prompt
from packages.qa.question_answering_service import QuestionAnsweringService


class PromptExperimentRunner:
    def __init__(
        self,
        *,
        definition: PromptExperimentDefinition,
        qa_questions: list[EvaluationQuestion],
        ask_cases: tuple[AgentE2ECase, ...] | list[AgentE2ECase],
        retrieval_service,
        llm_client_factory=None,
        prompt_registry=None,
        dataset_label: str | None = None,
        top_k: int = 5,
        judge_mode: bool = False,
        deepeval_judge_provider: str | None = None,
        deepeval_judge_model: str | None = None,
    ) -> None:
        validate_prompt_experiment_definition(definition, registry=prompt_registry)
        self.definition = definition
        self.qa_questions = list(qa_questions)
        self.ask_cases = list(ask_cases)
        self.retrieval_service = retrieval_service
        self.llm_client_factory = llm_client_factory or build_prompt_regression_mock_llm
        self.prompt_registry = prompt_registry
        self.dataset_label = dataset_label or definition.dataset_id
        self.top_k = top_k
        self.judge_mode = judge_mode
        self.deepeval_judge_provider = deepeval_judge_provider
        self.deepeval_judge_model = deepeval_judge_model

    async def run(self) -> PromptExperimentReport:
        control_run, recorded = await self._evaluate_qa(self.definition.control_version)
        control_factuality = build_factuality_report(
            target="legacy_rag",
            mode="offline",
            legacy_run=control_run,
            agent_run=None,
            dataset_identifier=self.definition.dataset_id,
            agent_dataset_identifier="",
        )

        variants = {
            "control": self._build_variant_result(
                variant="control",
                prompt_version=self.definition.control_version,
                qa_run=control_run,
                factuality_report=control_factuality,
                regression_report=None,
            )
        }
        metric_deltas: dict[str, dict[str, float]] = {}
        recommendations: list[PromptExperimentRecommendation] = []

        for version in self.definition.treatment_versions:
            variant = f"treatment_{version}"
            treatment_run, _ = await self._evaluate_qa(version, recorded=recorded)
            treatment_factuality = build_factuality_report(
                target="legacy_rag",
                mode="offline",
                legacy_run=treatment_run,
                agent_run=None,
                dataset_identifier=self.definition.dataset_id,
                agent_dataset_identifier="",
            )
            regression_report = await PromptRegressionRunner(
                prompt_registry=self.prompt_registry,
                prompt_id=self.definition.prompt_id,
                baseline_version=self.definition.control_version,
                candidate_version=version,
                qa_questions=self.qa_questions,
                ask_cases=self.ask_cases,
                retrieval_service=self.retrieval_service,
                llm_client_factory=lambda _surface: self.llm_client_factory(),
                dataset_label=self.dataset_label,
                judge_mode=self.judge_mode,
                deepeval_judge_provider=self.deepeval_judge_provider,
                deepeval_judge_model=self.deepeval_judge_model,
            ).evaluate()
            variants[variant] = self._build_variant_result(
                variant=variant,
                prompt_version=version,
                qa_run=treatment_run,
                factuality_report=treatment_factuality,
                regression_report=regression_report,
            )
            metric_deltas[variant] = self._metric_delta(
                control=variants["control"],
                treatment=variants[variant],
            )
            recommendations.append(
                self._recommend_variant(
                    treatment_variant=variant,
                    control=variants["control"],
                    treatment=variants[variant],
                )
            )

        recommendation = self._select_recommendation(recommendations)
        return PromptExperimentReport(
            experiment_id=self.definition.experiment_id,
            name=self.definition.name,
            description=self.definition.description,
            prompt_id=self.definition.prompt_id,
            control_version=self.definition.control_version,
            treatment_versions=self.definition.treatment_versions,
            dataset_id=self.definition.dataset_id,
            hypothesis=self.definition.hypothesis,
            primary_metric=self.definition.primary_metric,
            secondary_metrics=self.definition.secondary_metrics,
            guardrail_metrics=self.definition.guardrail_metrics,
            assignment_strategy=self.definition.assignment_strategy,
            variants=variants,
            metric_deltas=metric_deltas,
            recommendation=recommendation,
            limitations=(
                "Offline evaluation results do not establish production causal impact.",
                "Runtime assignment remains disabled by default.",
                "Judge metrics are supplementary and optional.",
            ),
            validity_status="valid",
            config_fingerprint={
                "dataset_id": self.definition.dataset_id,
                "dataset_label": self.dataset_label,
                "top_k": self.top_k,
                "retrieval_reused": True,
                "embedding_provider": "fake",
                "llm_provider": "mock",
                "judge_mode": self.judge_mode,
            },
            production_traffic_involved=False,
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
            llm_client=self.llm_client_factory(),
            prompt_builder=partial(
                build_grounded_prompt,
                registry=self.prompt_registry,
                prompt_id=self.definition.prompt_id,
                version=version,
            ),
        )
        evaluator = OfflineEvaluator(
            qa_service=service,
            questions=self.qa_questions,
            top_k=self.top_k,
            embedding_provider="fake",
            embedding_model="fake",
            llm_provider="mock",
            llm_model="mock-prompt-experiment",
        )
        return await evaluator.evaluate(), captured

    def _resolve_retrieval_service(
        self,
        recorded: dict[tuple[str, str, int], _RecordedRetrieval] | None,
    ) -> tuple[object, dict[tuple[str, str, int], _RecordedRetrieval]]:
        if recorded is None:
            wrapper = _RecordingRetrievalService(self.retrieval_service)
            return wrapper, wrapper.recorded
        return _ReplayRetrievalService(recorded), recorded

    def _build_variant_result(
        self,
        *,
        variant: str,
        prompt_version: str,
        qa_run: EvaluationRun,
        factuality_report,
        regression_report: PromptRegressionReport | None,
    ) -> PromptExperimentVariantResult:
        sample_size = len(qa_run.samples)
        prompt_rendering_success = (
            sum(1 for sample in qa_run.samples if sample.error is None) / sample_size
            if sample_size
            else 0.0
        )
        factuality_pass_rate = (
            factuality_report.case_status_counts.get("pass", 0) / sample_size
            if sample_size
            else 0.0
        )
        response_availability = (
            sum(1 for sample in qa_run.samples if sample.answer.strip()) / sample_size
            if sample_size
            else 0.0
        )
        metrics = {
            "citation_coverage": qa_run.summary.average_citation_coverage,
            "factuality_pass_rate": factuality_pass_rate,
            "latency_ms": (
                qa_run.summary.average_retrieval_latency_ms + qa_run.summary.average_llm_latency_ms
            ),
            "prompt_rendering_success": prompt_rendering_success,
            "regression_pass_rate": self._regression_pass_rate(regression_report),
            "response_availability": response_availability,
        }
        findings_by_category = dict(factuality_report.findings_by_category)
        findings_by_category["critical_factuality_violations"] = (
            factuality_report.findings_by_severity.get("critical", 0)
        )
        findings_by_category["fabricated_significance"] = findings_by_category.get(
            "fabricated_statistical_significance",
            0,
        )
        regression_findings = (
            {
                "regressions": regression_report.summary.regressions,
                "improvements": regression_report.summary.improvements,
                "failures": regression_report.summary.failures,
            }
            if regression_report is not None
            else {"regressions": 0, "improvements": 0, "failures": 0}
        )
        return PromptExperimentVariantResult(
            variant=variant,
            prompt_version=prompt_version,
            sample_size=sample_size,
            metrics=metrics,
            factuality_findings=findings_by_category,
            regression_findings=regression_findings,
            latency_ms=metrics["latency_ms"],
            passed=factuality_report.policy_result.status == "pass",
        )

    def _regression_pass_rate(self, report: PromptRegressionReport | None) -> float:
        if report is None or report.summary.cases_run == 0:
            return 1.0
        passed_cases = (
            report.summary.cases_run - report.summary.regressions - report.summary.failures
        )
        return max(passed_cases / report.summary.cases_run, 0.0)

    def _metric_delta(
        self,
        *,
        control: PromptExperimentVariantResult,
        treatment: PromptExperimentVariantResult,
    ) -> dict[str, float]:
        metric_names = set(control.metrics) | set(treatment.metrics)
        return {
            metric_name: (
                treatment.metrics.get(metric_name, 0.0) - control.metrics.get(metric_name, 0.0)
            )
            for metric_name in sorted(metric_names)
        }

    def _recommend_variant(
        self,
        *,
        treatment_variant: str,
        control: PromptExperimentVariantResult,
        treatment: PromptExperimentVariantResult,
    ) -> PromptExperimentRecommendation:
        guardrail_reasons = self._guardrail_failures(control=control, treatment=treatment)
        if guardrail_reasons:
            return PromptExperimentRecommendation(
                outcome="retain_control",
                variant=None,
                reasons=tuple(guardrail_reasons),
            )

        control_metric = control.metrics.get(self.definition.primary_metric, 0.0)
        treatment_metric = treatment.metrics.get(self.definition.primary_metric, 0.0)
        delta = treatment_metric - control_metric
        if treatment.sample_size < 1 or control.sample_size < 1:
            return PromptExperimentRecommendation(
                outcome="invalid_experiment",
                variant=None,
                reasons=("At least one variant had no evaluated samples.",),
            )
        if delta > 0.0:
            return PromptExperimentRecommendation(
                outcome="recommend_treatment",
                variant=treatment_variant,
                reasons=(
                    (
                        f"{treatment_variant} performed better on the evaluation dataset for "
                        f"{self.definition.primary_metric}."
                    ),
                ),
            )
        if delta < 0.0:
            return PromptExperimentRecommendation(
                outcome="retain_control",
                variant=None,
                reasons=(
                    (
                        f"{treatment_variant} performed worse on the evaluation dataset for "
                        f"{self.definition.primary_metric}."
                    ),
                ),
            )
        return PromptExperimentRecommendation(
            outcome="inconclusive",
            variant=None,
            reasons=("The primary metric was unchanged on the evaluation dataset.",),
        )

    def _guardrail_failures(
        self,
        *,
        control: PromptExperimentVariantResult,
        treatment: PromptExperimentVariantResult,
    ) -> list[str]:
        reasons: list[str] = []
        if treatment.factuality_findings.get("critical_factuality_violations", 0) > 0:
            reasons.append("Critical factuality violations were detected for the treatment.")
        if treatment.factuality_findings.get("fabricated_revenue_or_roi", 0) > 0:
            reasons.append("Fabricated revenue or ROI claims were detected for the treatment.")
        if treatment.factuality_findings.get("fabricated_significance", 0) > 0:
            reasons.append("Fabricated significance claims were detected for the treatment.")
        if treatment.metrics["citation_coverage"] < control.metrics["citation_coverage"]:
            reasons.append("Citation coverage regressed relative to control.")
        if treatment.metrics["response_availability"] < control.metrics["response_availability"]:
            reasons.append("Response availability regressed relative to control.")
        return reasons

    def _select_recommendation(
        self,
        recommendations: list[PromptExperimentRecommendation],
    ) -> PromptExperimentRecommendation:
        if not recommendations:
            return PromptExperimentRecommendation(
                outcome="invalid_experiment",
                variant=None,
                reasons=("No treatment variants were evaluated.",),
            )
        recommend = next(
            (
                recommendation
                for recommendation in recommendations
                if recommendation.outcome == "recommend_treatment"
            ),
            None,
        )
        if recommend is not None:
            return recommend
        retain = next(
            (
                recommendation
                for recommendation in recommendations
                if recommendation.outcome == "retain_control"
            ),
            None,
        )
        if retain is not None:
            return retain
        return recommendations[0]
