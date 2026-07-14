from __future__ import annotations

from dataclasses import dataclass

from packages.evals.dataset import EvaluationQuestion
from packages.qa.question_answering_service import QAResponse


@dataclass(frozen=True)
class SampleMetrics:
    retrieval_latency_ms: float
    llm_latency_ms: float
    citation_coverage: float
    retrieval_success: bool
    average_similarity: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class EvaluationSummary:
    question_count: int
    retrieval_success_rate: float
    average_citation_coverage: float
    average_retrieval_latency_ms: float
    average_llm_latency_ms: float
    average_similarity: float
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @classmethod
    def from_samples(cls, samples: list[SampleMetrics]) -> EvaluationSummary:
        if not samples:
            return cls(
                question_count=0,
                retrieval_success_rate=0.0,
                average_citation_coverage=0.0,
                average_retrieval_latency_ms=0.0,
                average_llm_latency_ms=0.0,
                average_similarity=0.0,
                total_input_tokens=0,
                total_output_tokens=0,
                estimated_cost_usd=0.0,
            )

        count = len(samples)
        return cls(
            question_count=count,
            retrieval_success_rate=sum(1 for sample in samples if sample.retrieval_success) / count,
            average_citation_coverage=sum(sample.citation_coverage for sample in samples) / count,
            average_retrieval_latency_ms=sum(sample.retrieval_latency_ms for sample in samples)
            / count,
            average_llm_latency_ms=sum(sample.llm_latency_ms for sample in samples) / count,
            average_similarity=sum(sample.average_similarity for sample in samples) / count,
            total_input_tokens=sum(sample.input_tokens for sample in samples),
            total_output_tokens=sum(sample.output_tokens for sample in samples),
            estimated_cost_usd=sum(sample.estimated_cost_usd for sample in samples),
        )


def calculate_sample_metrics(
    question: EvaluationQuestion,
    response: QAResponse,
    *,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
) -> SampleMetrics:
    expected_documents = set(question.expected_documents)
    cited_documents = {citation.document for citation in response.citations}
    citation_coverage = (
        len(expected_documents & cited_documents) / len(expected_documents)
        if expected_documents
        else 0.0
    )
    retrieved_text = " ".join(chunk.chunk_text for chunk in response.retrieved_chunks).lower()
    keyword_hit = any(keyword.lower() in retrieved_text for keyword in question.expected_keywords)
    retrieval_success = response.retrieval_metrics.retrieved_chunks > 0 and (
        citation_coverage > 0.0 or keyword_hit
    )
    input_cost = response.llm_metrics.input_tokens / 1000.0 * input_cost_per_1k_tokens
    output_cost = response.llm_metrics.output_tokens / 1000.0 * output_cost_per_1k_tokens

    return SampleMetrics(
        retrieval_latency_ms=(
            response.retrieval_metrics.embedding_time_ms
            + response.retrieval_metrics.vector_search_time_ms
        ),
        llm_latency_ms=response.llm_metrics.latency_ms,
        citation_coverage=citation_coverage,
        retrieval_success=retrieval_success,
        average_similarity=response.retrieval_metrics.average_similarity,
        input_tokens=response.llm_metrics.input_tokens,
        output_tokens=response.llm_metrics.output_tokens,
        estimated_cost_usd=input_cost + output_cost,
    )
