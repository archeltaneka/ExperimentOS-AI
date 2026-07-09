from __future__ import annotations

from packages.agents.observability import PHASE2_WORKFLOW_NODES
from packages.evals.agent_evaluator import AgentEvaluationRun


def render_agent_evaluation_report(run: AgentEvaluationRun) -> str:
    summary = run.summary
    lines = [
        "# Agent Workflow Evaluation Report",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Samples evaluated | {summary.sample_count} |",
        f"| Pass count | {summary.pass_count} |",
        f"| Fail count | {summary.fail_count} |",
        f"| Workflow success rate | {_percent(summary.workflow_success_rate)} |",
        f"| Average workflow latency | {summary.average_workflow_latency_ms:.1f} ms |",
        f"| Average trace completeness | {_percent(summary.average_trace_completeness)} |",
        f"| Planner intent accuracy | {_percent(summary.planner_intent_accuracy)} |",
        f"| Required agent routing accuracy | {_percent(summary.routing_accuracy)} |",
        f"| Citation coverage | {_percent(summary.citation_coverage)} |",
        f"| Decision recommendation coverage | {_percent(summary.recommendation_coverage)} |",
        "",
        "## Per-Agent Latency",
        "",
        "| Agent | Avg Latency (ms) |",
        "| --- | ---: |",
    ]
    for node in PHASE2_WORKFLOW_NODES:
        lines.append(f"| {node} | {summary.per_agent_latency_ms.get(node, 0.0):.1f} |")

    lines.extend(
        [
            "",
            "## Status Distribution",
            "",
            "| Decision Status | Count |",
            "| --- | ---: |",
        ]
    )
    for status, count in sorted(summary.decision_status_distribution.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "| Approval Status | Count |",
            "| --- | ---: |",
        ]
    )
    for status, count in sorted(summary.approval_status_distribution.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## Tool Usage",
            "",
            f"- Total tool calls: {summary.total_tool_calls}",
            f"- Total tool failures: {summary.total_tool_failures}",
            f"- Average tool calls per sample: {summary.average_tool_calls:.2f}",
            "",
            "## Sample Results",
            "",
            "| ID | Intent | Routing | Citations | Recommendation | Workflow | Pass | Error |",
            "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for sample in run.samples:
        if sample.metrics is None or sample.observation is None:
            lines.append(
                f"| {sample.case.id} | {sample.case.expected_intent} | 0.0% | 0.0% | "
                f"n/a | failed | no | {sample.error or ''} |"
            )
            continue
        lines.append(
            f"| {sample.case.id} | {sample.observation.intent} | "
            f"{_percent(sample.metrics.routing_accuracy)} | "
            f"{_percent(sample.metrics.citation_coverage)} | "
            f"{sample.observation.final_recommendation} | "
            f"{'success' if sample.metrics.workflow_success else 'failure'} | "
            f"{'yes' if sample.metrics.passed else 'no'} | "
            f"{sample.error or ''} |"
        )

    lines.extend(["", "## Failure Cases", ""])
    if not summary.failure_cases:
        lines.append("No failure cases were recorded.")
    else:
        for case_id in summary.failure_cases:
            lines.append(f"- `{case_id}`")

    return "\n".join(lines) + "\n"


def _percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"
