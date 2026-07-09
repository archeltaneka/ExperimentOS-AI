from __future__ import annotations

from packages.evals.agent_e2e import AgentE2ERun

KNOWN_LIMITATIONS = (
    "The E2E evaluator uses deterministic fake workflow and legacy QA backends rather than the "
    "live database-backed retrieval path.",
    "Assertions are structural and intentionally avoid exact prose matching.",
    "Failure-path coverage validates structured API surfacing, not downstream recovery behavior.",
)

PHASE3_NEXT_STEPS = (
    "Add causal inference once the Phase 2 contract is stable.",
    "Add LLM-as-judge only after deterministic regression coverage is mature.",
    "Expand database-backed integrated evaluation beyond fake workflow fixtures.",
)


def render_agent_e2e_report(run: AgentE2ERun) -> str:
    summary = run.summary
    lines = [
        "# Agent Workflow E2E Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Total test/eval cases: {summary.sample_count}",
        f"- Pass/fail summary: {summary.pass_count} passed, {summary.fail_count} failed",
        f"- Default agent workflow coverage: {_percent(summary.default_agent_workflow_coverage)}",
        f"- Legacy fallback coverage: {_percent(summary.legacy_fallback_coverage)}",
        f"- Intent accuracy: {_percent(summary.intent_accuracy)}",
        f"- Required agent routing accuracy: {_percent(summary.routing_accuracy)}",
        f"- Citation coverage: {_percent(summary.citation_coverage)}",
        f"- Decision coverage: {_percent(summary.decision_coverage)}",
        f"- Executive summary coverage: {_percent(summary.executive_summary_coverage)}",
        f"- Approval status coverage: {_percent(summary.approval_status_coverage)}",
        f"- Average workflow latency: {summary.average_latency_ms:.1f} ms",
        "",
        "## Case Results",
        "",
        "| Case | Mode | Status | Intent | Pass | Failures |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for sample in run.samples:
        lines.append(
            f"| {sample.case.id} | {sample.case.ask_mode} | {sample.status_code} | "
            f"{sample.response_json.get('intent', '')} | "
            f"{'yes' if sample.passed else 'no'} | "
            f"{'; '.join(sample.failure_reasons)} |"
        )

    lines.extend(["", "## Known Limitations", ""])
    for limitation in KNOWN_LIMITATIONS:
        lines.append(f"- {limitation}")

    lines.extend(["", "## Phase 3 Next Steps", ""])
    for step in PHASE3_NEXT_STEPS:
        lines.append(f"- {step}")

    return "\n".join(lines) + "\n"


def _percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"
