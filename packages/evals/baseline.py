from __future__ import annotations

from dataclasses import dataclass

from packages.evals.agent_e2e import AgentE2ERun
from packages.evals.agent_e2e_report import KNOWN_LIMITATIONS as E2E_KNOWN_LIMITATIONS
from packages.evals.agent_evaluator import AgentEvaluationRun
from packages.evals.evaluator import EvaluationRun

QA_MISSING_METRICS = (
    "factual grounding",
    "hallucination risk",
    "routing accuracy",
    "decision quality",
    "trace completeness",
    "regression stability",
)

QA_KNOWN_LIMITATIONS = (
    "The Phase 1 QA harness measures retrieval and citation behavior but does not score "
    "factual grounding directly.",
    "The QA harness uses the legacy_rag path rather than the default agent_workflow path.",
)

AGENT_MISSING_METRICS = (
    "factual grounding",
    "hallucination risk",
    "regression stability",
)

AGENT_KNOWN_LIMITATIONS = (
    "The agent workflow evaluator uses a deterministic in-process workflow service rather than "
    "the live FastAPI /ask route.",
    "The agent workflow evaluator measures structural workflow quality, not prose quality.",
)

E2E_MISSING_METRICS = (
    "database-backed retrieval quality",
    "factual grounding",
    "hallucination risk",
    "regression stability",
)

BASELINE_KNOWN_GAPS = (
    "No threshold policy exists yet for turning these metrics into CI gates.",
    "No direct hallucination or factuality score is computed yet.",
    "No external tracing or observability export is enabled yet.",
)

BASELINE_NEXT_WORK = (
    (
        "Add deterministic factual grounding and unsupported-claim checks on top of "
        "the expanded datasets."
    ),
    "Define category-specific threshold policies before introducing CI quality gates.",
    (
        "Add report-level regression diffs so future baseline runs can compare changed "
        "failure cases directly."
    ),
)


@dataclass(frozen=True)
class Phase3BaselineSection:
    name: str
    command: str
    dataset: str | None
    report_path: str
    status: str
    status_reason: str
    key_metrics: tuple[tuple[str, str], ...]
    missing_metrics: tuple[str, ...]
    known_limitations: tuple[str, ...]


@dataclass(frozen=True)
class Phase3BaselineReport:
    generated_at: str
    overall_status: str
    sections: list[Phase3BaselineSection]
    known_gaps: tuple[str, ...]
    next_recommended_work: tuple[str, ...]


def build_phase3_baseline_report(
    *,
    generated_at: str,
    qa_run: EvaluationRun,
    qa_command: str,
    qa_dataset: str,
    qa_report_path: str,
    agent_run: AgentEvaluationRun,
    agent_command: str,
    agent_dataset: str,
    agent_report_path: str,
    agent_e2e_run: AgentE2ERun,
    agent_e2e_command: str,
    agent_e2e_report_path: str,
) -> Phase3BaselineReport:
    sections = [
        _build_qa_section(
            run=qa_run,
            command=qa_command,
            dataset=qa_dataset,
            report_path=qa_report_path,
        ),
        _build_agent_section(
            run=agent_run,
            command=agent_command,
            dataset=agent_dataset,
            report_path=agent_report_path,
        ),
        _build_agent_e2e_section(
            run=agent_e2e_run,
            command=agent_e2e_command,
            report_path=agent_e2e_report_path,
        ),
    ]
    overall_status = "pass" if all(section.status == "pass" for section in sections) else "fail"
    return Phase3BaselineReport(
        generated_at=generated_at,
        overall_status=overall_status,
        sections=sections,
        known_gaps=BASELINE_KNOWN_GAPS,
        next_recommended_work=BASELINE_NEXT_WORK,
    )


def render_phase3_baseline_report(report: Phase3BaselineReport) -> str:
    lines = [
        "# Phase 3 Reliability Baseline Report",
        "",
        f"- Generated at: {report.generated_at}",
        f"- Overall status: {report.overall_status}",
        "",
        "## Evaluation Status",
        "",
        "| Evaluation | Status | Reason | Dataset | Report |",
        "| --- | --- | --- | --- | --- |",
    ]
    for section in report.sections:
        lines.append(
            f"| {section.name} | {section.status} | {section.status_reason} | "
            f"{section.dataset or 'n/a'} | `{section.report_path}` |"
        )

    lines.extend(["", "## Commands Run", ""])
    for section in report.sections:
        lines.append(f"- `{section.command}`")

    for section in report.sections:
        lines.extend(
            [
                "",
                f"## {section.name}",
                "",
                f"- Status: {section.status}",
                f"- Reason: {section.status_reason}",
                f"- Dataset: {section.dataset or 'n/a'}",
                f"- Report path: `{section.report_path}`",
                "",
                "### Key Metrics",
                "",
            ]
        )
        for label, value in section.key_metrics:
            lines.append(f"- {label}: {value}")

        lines.extend(["", "### Missing Metrics", ""])
        for metric in section.missing_metrics:
            lines.append(f"- {metric}")

        lines.extend(["", "### Known Limitations", ""])
        for limitation in section.known_limitations:
            lines.append(f"- {limitation}")

    lines.extend(["", "## Known Gaps", ""])
    for gap in report.known_gaps:
        lines.append(f"- {gap}")

    lines.extend(["", "## Next Recommended Reliability Work", ""])
    for step in report.next_recommended_work:
        lines.append(f"- {step}")

    return "\n".join(lines) + "\n"


def _build_qa_section(
    *,
    run: EvaluationRun,
    command: str,
    dataset: str,
    report_path: str,
) -> Phase3BaselineSection:
    summary = run.summary
    sample_errors = [sample.error for sample in run.samples if sample.error]
    status = "pass" if not sample_errors else "fail"
    status_reason = (
        "completed without sample errors"
        if not sample_errors
        else f"{len(sample_errors)} sample errors"
    )
    return Phase3BaselineSection(
        name="RAG Evaluation",
        command=command,
        dataset=dataset,
        report_path=report_path,
        status=status,
        status_reason=status_reason,
        key_metrics=(
            ("Questions evaluated", str(summary.question_count)),
            ("Retrieval success rate", _percent(summary.retrieval_success_rate)),
            ("Average citation coverage", _percent(summary.average_citation_coverage)),
            ("Average retrieval latency", f"{summary.average_retrieval_latency_ms:.1f} ms"),
            ("Average LLM latency", f"{summary.average_llm_latency_ms:.1f} ms"),
        ),
        missing_metrics=QA_MISSING_METRICS,
        known_limitations=QA_KNOWN_LIMITATIONS,
    )


def _build_agent_section(
    *,
    run: AgentEvaluationRun,
    command: str,
    dataset: str,
    report_path: str,
) -> Phase3BaselineSection:
    summary = run.summary
    status = "pass" if summary.fail_count == 0 else "fail"
    status_reason = (
        "all deterministic workflow cases passed"
        if summary.fail_count == 0
        else f"{summary.fail_count} workflow cases failed"
    )
    return Phase3BaselineSection(
        name="Agent Workflow Evaluation",
        command=command,
        dataset=dataset,
        report_path=report_path,
        status=status,
        status_reason=status_reason,
        key_metrics=(
            ("Samples evaluated", str(summary.sample_count)),
            ("Pass/fail summary", f"{summary.pass_count} passed, {summary.fail_count} failed"),
            ("Workflow success rate", _percent(summary.workflow_success_rate)),
            ("Routing accuracy", _percent(summary.routing_accuracy)),
            ("Trace completeness", _percent(summary.average_trace_completeness)),
        ),
        missing_metrics=AGENT_MISSING_METRICS,
        known_limitations=AGENT_KNOWN_LIMITATIONS,
    )


def _build_agent_e2e_section(
    *,
    run: AgentE2ERun,
    command: str,
    report_path: str,
) -> Phase3BaselineSection:
    summary = run.summary
    status = "pass" if summary.fail_count == 0 else "fail"
    status_reason = (
        "all deterministic API cases passed"
        if summary.fail_count == 0
        else f"{summary.fail_count} API cases failed"
    )
    return Phase3BaselineSection(
        name="Agent Workflow E2E Evaluation",
        command=command,
        dataset=None,
        report_path=report_path,
        status=status,
        status_reason=status_reason,
        key_metrics=(
            ("Total test/eval cases", str(summary.sample_count)),
            ("Pass/fail summary", f"{summary.pass_count} passed, {summary.fail_count} failed"),
            ("Default agent workflow coverage", _percent(summary.default_agent_workflow_coverage)),
            ("Legacy fallback coverage", _percent(summary.legacy_fallback_coverage)),
            ("Approval status coverage", _percent(summary.approval_status_coverage)),
        ),
        missing_metrics=E2E_MISSING_METRICS,
        known_limitations=E2E_KNOWN_LIMITATIONS,
    )


def _percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"
