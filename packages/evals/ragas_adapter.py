from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any

from packages.evals.evaluator import EvaluationRun

DEFAULT_RAGAS_METRICS = (
    "id_based_context_precision",
    "id_based_context_recall",
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevancy",
)


@dataclass(frozen=True)
class RagasMetricSpec:
    name: str
    requires_judge_llm: bool = False
    requires_judge_embeddings: bool = False
    description: str = ""


SUPPORTED_RAGAS_METRICS = {
    "id_based_context_precision": RagasMetricSpec(
        name="id_based_context_precision",
        description="Offline-safe context precision using retrieved and expected document IDs.",
    ),
    "id_based_context_recall": RagasMetricSpec(
        name="id_based_context_recall",
        description="Offline-safe context recall using retrieved and expected document IDs.",
    ),
    "context_precision": RagasMetricSpec(
        name="context_precision",
        requires_judge_llm=True,
        description=(
            "Judge-LLM context precision using the retrieved contexts and reference answer."
        ),
    ),
    "context_recall": RagasMetricSpec(
        name="context_recall",
        requires_judge_llm=True,
        description="Judge-LLM context recall using the retrieved contexts and reference answer.",
    ),
    "faithfulness": RagasMetricSpec(
        name="faithfulness",
        requires_judge_llm=True,
        description="Judge-LLM faithfulness between the answer and retrieved contexts.",
    ),
    "answer_relevancy": RagasMetricSpec(
        name="answer_relevancy",
        requires_judge_llm=True,
        requires_judge_embeddings=True,
        description="Judge-LLM and embedding based answer relevancy.",
    ),
}


@dataclass(frozen=True)
class RagasEvaluationSample:
    question_id: str
    experiment_id: str
    category: str
    difficulty: str
    user_input: str
    response: str
    reference: str
    retrieved_contexts: tuple[str, ...]
    retrieved_context_ids: tuple[str, ...]
    reference_context_ids: tuple[str, ...]
    notes: str | None = None


@dataclass(frozen=True)
class RagasExcludedSample:
    question_id: str
    experiment_id: str
    category: str
    reason: str


@dataclass(frozen=True)
class PreparedRagasDataset:
    samples: tuple[RagasEvaluationSample, ...]
    excluded_samples: tuple[RagasExcludedSample, ...]


@dataclass(frozen=True)
class RagasBindings:
    version: str
    EvaluationDataset: type[Any]
    SingleTurnSample: type[Any]
    RunConfig: type[Any]
    evaluate: Any
    llm_factory: Any
    embedding_factory: Any
    metric_factories: dict[str, Any]
    shimmed_vertexai: bool = False


def prepare_ragas_dataset(run: EvaluationRun) -> PreparedRagasDataset:
    included: list[RagasEvaluationSample] = []
    excluded: list[RagasExcludedSample] = []
    for sample in run.samples:
        if sample.error is not None:
            excluded.append(
                RagasExcludedSample(
                    question_id=sample.question.id,
                    experiment_id=sample.question.experiment_id,
                    category=sample.question.category,
                    reason=sample.error,
                )
            )
            continue
        included.append(
            RagasEvaluationSample(
                question_id=sample.question.id,
                experiment_id=sample.question.experiment_id,
                category=sample.question.category,
                difficulty=sample.question.difficulty,
                user_input=sample.question.question,
                response=sample.answer,
                reference=sample.question.reference_answer,
                retrieved_contexts=sample.retrieved_contexts,
                retrieved_context_ids=sample.retrieved_documents,
                reference_context_ids=sample.question.expected_documents,
                notes=sample.question.notes,
            )
        )
    return PreparedRagasDataset(
        samples=tuple(included),
        excluded_samples=tuple(excluded),
    )


def build_ragas_dataset(
    prepared: PreparedRagasDataset,
    bindings: RagasBindings,
) -> Any:
    ragas_samples = [
        bindings.SingleTurnSample(
            user_input=sample.user_input,
            response=sample.response,
            reference=sample.reference,
            retrieved_contexts=list(sample.retrieved_contexts),
            retrieved_context_ids=list(sample.retrieved_context_ids),
            reference_context_ids=list(sample.reference_context_ids),
        )
        for sample in prepared.samples
    ]
    return bindings.EvaluationDataset(
        samples=ragas_samples,
        name="experimentos-phase3-ragas",
    )


def build_ragas_metric(name: str, bindings: RagasBindings) -> Any:
    if name not in bindings.metric_factories:
        raise ValueError(f"unsupported ragas metric: {name}")
    return bindings.metric_factories[name]()


def get_ragas_metric_spec(name: str) -> RagasMetricSpec:
    try:
        return SUPPORTED_RAGAS_METRICS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_RAGAS_METRICS))
        raise ValueError(
            f"unsupported ragas metric {name!r}; expected one of: {supported}"
        ) from exc


def import_ragas_bindings() -> RagasBindings:
    shimmed_vertexai = _install_vertexai_import_shim()

    from ragas import EvaluationDataset, SingleTurnSample, __version__, evaluate
    from ragas.embeddings import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        ContextPrecision,
        ContextRecall,
        Faithfulness,
        IDBasedContextPrecision,
        IDBasedContextRecall,
        ResponseRelevancy,
    )
    from ragas.run_config import RunConfig

    return RagasBindings(
        version=__version__,
        EvaluationDataset=EvaluationDataset,
        SingleTurnSample=SingleTurnSample,
        RunConfig=RunConfig,
        evaluate=evaluate,
        llm_factory=llm_factory,
        embedding_factory=embedding_factory,
        metric_factories={
            "id_based_context_precision": IDBasedContextPrecision,
            "id_based_context_recall": IDBasedContextRecall,
            "context_precision": ContextPrecision,
            "context_recall": ContextRecall,
            "faithfulness": Faithfulness,
            "answer_relevancy": ResponseRelevancy,
        },
        shimmed_vertexai=shimmed_vertexai,
    )


def _install_vertexai_import_shim() -> bool:
    try:
        import langchain_community.chat_models.vertexai  # noqa: F401
    except ModuleNotFoundError as exc:
        if exc.name != "langchain_community.chat_models.vertexai":
            raise
        module = types.ModuleType("langchain_community.chat_models.vertexai")

        class ChatVertexAI:  # pragma: no cover - compatibility shim only
            pass

        module.ChatVertexAI = ChatVertexAI
        sys.modules["langchain_community.chat_models.vertexai"] = module
        return True
    return False
