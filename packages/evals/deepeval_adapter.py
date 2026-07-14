from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from packages.evals.agent_e2e import AgentE2ERun
from packages.evals.agent_evaluator import AgentEvaluationRun
from packages.evals.evaluator import EvaluationRun

DeepEvalScope = Literal["response", "workflow"]
DeepEvalSurface = Literal["agent_workflow", "legacy_rag"]


@dataclass(frozen=True)
class DeepEvalPreparedCase:
    case_id: str
    category: str
    scope: DeepEvalScope
    surface: DeepEvalSurface
    dataset_identifier: str
    input_text: str
    actual_output: str | None
    expected_output: str | None
    context: tuple[str, ...]
    retrieval_context: tuple[str, ...]
    metadata: dict[str, object]
    source_error: str | None = None


@dataclass(frozen=True)
class DeepEvalBindings:
    version: str
    EvaluationDataset: type[Any]
    Golden: type[Any]
    LLMTestCase: type[Any]
    evaluate: Any
    assert_test: Any
    AsyncConfig: type[Any]
    CacheConfig: type[Any]
    DisplayConfig: type[Any]
    ErrorConfig: type[Any]
    metric_factories: dict[str, Any]


def prepare_qa_response_cases(
    run: EvaluationRun,
    *,
    dataset_identifier: str,
) -> list[DeepEvalPreparedCase]:
    cases: list[DeepEvalPreparedCase] = []
    for sample in run.samples:
        question = sample.question
        metadata = {
            "source_question_id": question.id,
            "expected_documents": list(question.expected_documents),
            "retrieved_documents": list(sample.retrieved_documents),
            "expected_citation_required": question.expected_citation_required,
            "citation_coverage": sample.metrics.citation_coverage if sample.metrics else 0.0,
            "retrieval_success": sample.metrics.retrieval_success if sample.metrics else False,
            "notes": question.notes,
        }
        cases.append(
            DeepEvalPreparedCase(
                case_id=f"legacy_rag::{question.id}",
                category=question.category,
                scope="response",
                surface="legacy_rag",
                dataset_identifier=dataset_identifier,
                input_text=question.question,
                actual_output=sample.answer or None,
                expected_output=question.reference_answer,
                context=tuple(sample.retrieved_contexts),
                retrieval_context=tuple(sample.retrieved_contexts),
                metadata=metadata,
                source_error=sample.error,
            )
        )
    return cases


def prepare_agent_response_cases(
    run: AgentE2ERun,
    *,
    dataset_identifier: str = "packages.evals.agent_e2e:default_cases",
) -> list[DeepEvalPreparedCase]:
    cases: list[DeepEvalPreparedCase] = []
    for sample in run.samples:
        response = sample.response_json
        citations = response.get("citations", [])
        retrieval_context = tuple(
            str(citation.get("quote", "")).strip()
            for citation in citations
            if isinstance(citation, dict) and str(citation.get("quote", "")).strip()
        )
        decision = response.get("decision", {})
        executive_summary = response.get("executive_summary", {})
        metadata = {
            "source_case_id": sample.case.id,
            "ask_mode": sample.case.ask_mode,
            "status_code": sample.status_code,
            "expected_status_code": sample.case.expected_status_code,
            "used_agent_workflow": sample.used_agent_workflow,
            "used_legacy_fallback": sample.used_legacy_fallback,
            "expected_min_citations": sample.case.expected_min_citations,
            "actual_citation_count": len(citations) if isinstance(citations, list) else 0,
            "expected_intent": sample.case.expected_intent,
            "actual_intent": response.get("intent"),
            "expected_required_agents": list(sample.case.expected_required_agents),
            "actual_required_agents": list(response.get("required_agents", [])),
            "expected_approval_status": sample.case.expected_approval_status,
            "approval_status": response.get("approval_status"),
            "expected_decision_status": sample.case.expected_decision_status,
            "decision_status": decision.get("decision_status")
            if isinstance(decision, dict)
            else None,
            "expected_summary_status": sample.case.expected_summary_status,
            "summary_status": executive_summary.get("summary_status")
            if isinstance(executive_summary, dict)
            else None,
            "expected_error_detail": sample.case.expected_error_detail,
            "actual_error_detail": response.get("detail"),
        }
        cases.append(
            DeepEvalPreparedCase(
                case_id=f"{sample.case.ask_mode}::{sample.case.id}",
                category=sample.case.scenario,
                scope="response",
                surface=sample.case.ask_mode,
                dataset_identifier=dataset_identifier,
                input_text=sample.case.question,
                actual_output=_string_or_none(response.get("answer")),
                expected_output=None,
                context=retrieval_context,
                retrieval_context=retrieval_context,
                metadata=metadata,
                source_error=(
                    None if sample.status_code == 200 else _string_or_none(response.get("detail"))
                ),
            )
        )
    return cases


def prepare_agent_workflow_cases(
    run: AgentEvaluationRun,
    *,
    dataset_identifier: str,
) -> list[DeepEvalPreparedCase]:
    cases: list[DeepEvalPreparedCase] = []
    for sample in run.samples:
        observation = sample.observation
        actual_output = None
        retrieval_context: tuple[str, ...] = ()
        metadata: dict[str, object] = {
            "source_case_id": sample.case.id,
            "expected_intent": sample.case.expected_intent,
            "expected_required_agents": list(sample.case.expected_required_agents),
            "expected_decision_status": sample.case.expected_decision_status,
            "expected_recommendation": sample.case.expected_recommendation,
            "expected_summary_status": sample.case.expected_summary_status,
            "expected_approval_status": sample.case.expected_approval_status,
            "expected_min_citations": sample.case.expected_min_citations,
            "expected_failure_mode": sample.case.expected_failure_mode,
            "notes": sample.case.notes,
        }
        if sample.state is not None:
            actual_output = _resolve_state_answer(sample.state)
            retrieval_context = _state_citation_quotes(sample.state)
        if observation is not None:
            metadata.update(
                {
                    "intent": observation.intent,
                    "required_agents": list(observation.required_agents),
                    "trace_completeness": observation.trace_completeness,
                    "citation_count": observation.citation_count,
                    "decision_status": observation.decision_status,
                    "approval_status": observation.approval_status,
                    "summary_status": observation.summary_status,
                    "final_recommendation": observation.final_recommendation,
                }
            )
        if sample.metrics is not None:
            metadata.update(
                {
                    "routing_accuracy": sample.metrics.routing_accuracy,
                    "citation_coverage": sample.metrics.citation_coverage,
                    "workflow_success": sample.metrics.workflow_success,
                }
            )
        cases.append(
            DeepEvalPreparedCase(
                case_id=f"agent_workflow::{sample.case.id}",
                category=sample.case.category,
                scope="workflow",
                surface="agent_workflow",
                dataset_identifier=dataset_identifier,
                input_text=sample.case.question,
                actual_output=actual_output,
                expected_output=sample.case.expected_recommendation,
                context=retrieval_context,
                retrieval_context=retrieval_context,
                metadata=metadata,
                source_error=sample.error,
            )
        )
    return cases


def build_deepeval_dataset(
    cases: list[DeepEvalPreparedCase],
    *,
    bindings: DeepEvalBindings,
    name: str,
) -> Any:
    dataset = bindings.EvaluationDataset(
        goldens=[build_golden(case, bindings=bindings) for case in cases],
        confident_api_key=None,
    )
    for case in cases:
        dataset.add_test_case(build_llm_test_case(case, bindings=bindings))
    if hasattr(dataset, "name"):
        dataset.name = name
    return dataset


def build_golden(
    case: DeepEvalPreparedCase,
    *,
    bindings: DeepEvalBindings,
) -> Any:
    _validate_case(case)
    return bindings.Golden(
        input=case.input_text,
        actual_output=case.actual_output,
        expected_output=case.expected_output,
        context=list(case.context) or None,
        retrieval_context=list(case.retrieval_context) or None,
        additional_metadata=_metadata_payload(case),
        comments=case.source_error,
        name=case.case_id,
        custom_column_key_values=_custom_columns(case),
    )


def build_llm_test_case(
    case: DeepEvalPreparedCase,
    *,
    bindings: DeepEvalBindings,
) -> Any:
    _validate_case(case)
    return bindings.LLMTestCase(
        input=case.input_text,
        actual_output=case.actual_output,
        expected_output=case.expected_output,
        context=list(case.context) or None,
        retrieval_context=list(case.retrieval_context) or None,
        metadata=_metadata_payload(case),
        comments=case.source_error,
        name=case.case_id,
        tags=[case.scope, case.surface, case.category],
        custom_column_key_values=_custom_columns(case),
    )


def import_deepeval_bindings() -> DeepEvalBindings:
    from deepeval import __version__, assert_test, evaluate
    from deepeval.dataset import EvaluationDataset, Golden
    from deepeval.evaluate import AsyncConfig, CacheConfig, DisplayConfig, ErrorConfig
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
    )
    from deepeval.test_case import LLMTestCase

    return DeepEvalBindings(
        version=__version__,
        EvaluationDataset=EvaluationDataset,
        Golden=Golden,
        LLMTestCase=LLMTestCase,
        evaluate=evaluate,
        assert_test=assert_test,
        AsyncConfig=AsyncConfig,
        CacheConfig=CacheConfig,
        DisplayConfig=DisplayConfig,
        ErrorConfig=ErrorConfig,
        metric_factories={
            "answer_relevancy": AnswerRelevancyMetric,
            "faithfulness": FaithfulnessMetric,
            "hallucination": HallucinationMetric,
            "contextual_relevancy": ContextualRelevancyMetric,
        },
    )


def _validate_case(case: DeepEvalPreparedCase) -> None:
    if not case.case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    if not case.category.strip():
        raise ValueError("category must be a non-empty string")
    if not case.input_text.strip():
        raise ValueError("input_text must be a non-empty string")


def _metadata_payload(case: DeepEvalPreparedCase) -> dict[str, object]:
    return {
        **case.metadata,
        "case_id": case.case_id,
        "category": case.category,
        "scope": case.scope,
        "surface": case.surface,
        "dataset_identifier": case.dataset_identifier,
    }


def _custom_columns(case: DeepEvalPreparedCase) -> dict[str, str]:
    return {
        "case_id": case.case_id,
        "category": case.category,
        "scope": case.scope,
        "surface": case.surface,
    }


def _resolve_state_answer(state: dict[str, object]) -> str | None:
    executive_summary = state.get("executive_summary", {})
    if isinstance(executive_summary, dict):
        summary = _string_or_none(executive_summary.get("summary"))
        if summary is not None:
            return summary
    decision = state.get("decision", {})
    if isinstance(decision, dict):
        rationale = _string_or_none(decision.get("rationale"))
        if rationale is not None:
            return rationale
    analysis = state.get("experiment_analysis", {})
    if isinstance(analysis, dict):
        return _string_or_none(analysis.get("summary"))
    return None


def _state_citation_quotes(state: dict[str, object]) -> tuple[str, ...]:
    collected: list[str] = []
    sections = [
        state.get("citations", []),
        state.get("experiment_analysis", {}).get("evidence_citations", []),
        state.get("business_impact", {}).get("evidence_citations", []),
        state.get("risk_assessment", {}).get("evidence_citations", []),
        state.get("decision", {}).get("evidence_citations", []),
        state.get("executive_summary", {}).get("evidence_citations", []),
    ]
    for section in sections:
        if not isinstance(section, list):
            continue
        for citation in section:
            if not isinstance(citation, dict):
                continue
            quote = str(citation.get("quote", "")).strip()
            if quote and quote not in collected:
                collected.append(quote)
    return tuple(collected)


def _string_or_none(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
