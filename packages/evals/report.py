from __future__ import annotations

from collections import defaultdict

from packages.evals.evaluator import EvaluationRun, EvaluationSampleResult


def render_evaluation_report(run: EvaluationRun) -> str:
    summary = run.summary
    lines = [
        "# Evaluation Harness Report",
        "",
        "## Providers",
        "",
        f"- Embedding provider: {run.embedding_provider or 'unknown'}",
        f"- Embedding model: {run.embedding_model or 'unknown'}",
        f"- LLM provider: {run.llm_provider or 'unknown'}",
        f"- LLM model: {run.llm_model or 'unknown'}",
        "",
        "## Summary",
        "",
        f"- Questions evaluated: {summary.question_count}",
        f"- Retrieval success rate: {_percent(summary.retrieval_success_rate)}",
        f"- Average citation coverage: {_percent(summary.average_citation_coverage)}",
        f"- Average retrieval latency: {summary.average_retrieval_latency_ms:.1f} ms",
        f"- Average LLM latency: {summary.average_llm_latency_ms:.1f} ms",
        f"- Average similarity: {summary.average_similarity:.3f}",
        f"- Token usage: {summary.total_tokens} total "
        f"({summary.total_input_tokens} input, {summary.total_output_tokens} output)",
        f"- Estimated cost: ${summary.estimated_cost_usd:.6f}",
        "",
        "## Category Coverage",
        "",
        "| Category | Questions | Retrieval Success | Avg Citation Coverage |",
        "| --- | ---: | ---: | ---: |",
    ]
    for category, samples in sorted(_samples_by_category(run.samples).items()):
        metric_samples = [sample.metrics for sample in samples if sample.metrics is not None]
        if metric_samples:
            success_rate = sum(1 for metric in metric_samples if metric.retrieval_success) / len(
                metric_samples
            )
            coverage = sum(metric.citation_coverage for metric in metric_samples) / len(
                metric_samples
            )
        else:
            success_rate = 0.0
            coverage = 0.0
        lines.append(
            f"| {category} | {len(samples)} | {_percent(success_rate)} | {_percent(coverage)} |"
        )

    lines.extend(
        [
            "",
            "## Sample Results",
            "",
            "| ID | Experiment | Category | Prompt | Retrieval | Citation Coverage | "
            "Avg Similarity | Error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for sample in run.samples:
        prompt_label = _prompt_label(sample)
        if sample.metrics is None:
            lines.append(
                f"| {sample.question.id} | {sample.question.experiment_id} | "
                f"{sample.question.category} | {prompt_label} | no | 0.0% | 0.000 | "
                f"{sample.error or ''} |"
            )
            continue
        lines.append(
            f"| {sample.question.id} | {sample.question.experiment_id} | "
            f"{sample.question.category} | {prompt_label} | "
            f"{_yes_no(sample.metrics.retrieval_success)} | "
            f"{_percent(sample.metrics.citation_coverage)} | "
            f"{sample.metrics.average_similarity:.3f} | {sample.error or ''} |"
        )

    low_performing = _low_performing_samples(run.samples)
    lines.extend(
        [
            "",
            "## Follow-Up Candidates",
            "",
        ]
    )
    if not low_performing:
        lines.append("No questions fell below the current retrieval or citation thresholds.")
    else:
        for sample in low_performing:
            lines.append(f"- `{sample.question.id}`: {sample.question.question}")

    return "\n".join(lines) + "\n"


def _samples_by_category(
    samples: list[EvaluationSampleResult],
) -> dict[str, list[EvaluationSampleResult]]:
    grouped: dict[str, list[EvaluationSampleResult]] = defaultdict(list)
    for sample in samples:
        grouped[sample.question.category].append(sample)
    return dict(grouped)


def _low_performing_samples(samples: list[EvaluationSampleResult]) -> list[EvaluationSampleResult]:
    low_performing: list[EvaluationSampleResult] = []
    for sample in samples:
        if sample.metrics is None:
            low_performing.append(sample)
        elif not sample.metrics.retrieval_success or sample.metrics.citation_coverage < 1.0:
            low_performing.append(sample)
    return low_performing


def _percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _prompt_label(sample: EvaluationSampleResult) -> str:
    if sample.prompt_id is None or sample.prompt_version is None:
        return ""
    return f"{sample.prompt_id}@{sample.prompt_version}"
