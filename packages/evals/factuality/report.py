from __future__ import annotations

import json

from packages.evals.factuality.models import FactualityReport


def render_factuality_report(report: FactualityReport) -> str:
    lines = [
        "# Factuality Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Generated at: {report.generated_at}",
        f"- Target: {report.target}",
        f"- Mode: {report.mode}",
        f"- Dataset identifiers: {', '.join(report.dataset_identifiers) or 'none'}",
        f"- Judge provider/model: {report.judge_provider} / {report.judge_model or 'none'}",
        f"- Checks executed: {', '.join(report.checks_executed) or 'none'}",
        f"- Checks skipped: {', '.join(report.checks_skipped) or 'none'}",
        f"- Overall policy result: {report.policy_result.status}",
        "",
        "## Findings By Category",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    for category, count in sorted(report.findings_by_category.items()):
        lines.append(f"| {category} | {count} |")

    lines.extend(
        [
            "",
            "## Findings By Severity",
            "",
            "| Severity | Count |",
            "| --- | ---: |",
        ]
    )
    for severity, count in sorted(report.findings_by_severity.items()):
        lines.append(f"| {severity} | {count} |")

    lines.extend(
        [
            "",
            "## Case Outcomes",
            "",
            (
                "| Case | Surface | Category | Citation Coverage | Unparsed Claims | "
                "Findings | Prompt |"
            ),
            "| --- | --- | --- | ---: | --- | ---: | --- |",
        ]
    )
    for result in report.case_results:
        prompt = (
            f"{result.prompt_id}@{result.prompt_version}"
            if result.prompt_id and result.prompt_version
            else ""
        )
        lines.append(
            f"| {result.case_id} | {result.surface} | {result.category} | "
            f"{result.citation_coverage:.2f} | "
            f"{'yes' if result.unparsed_claims else 'no'} | "
            f"{len(result.failed_findings)} | {prompt} |"
        )

    lines.extend(["", "## Finding Details", ""])
    details = report.to_dict().get("findings_detail", [])
    if not details:
        lines.append("No failed findings were recorded.")
    else:
        for index, finding in enumerate(details, start=1):
            lines.extend(
                [
                    f"### Finding {index}",
                    "",
                    f"- Case: {finding['case_id']}",
                    f"- Surface: {finding['surface']}",
                    f"- Category: {finding['category']}",
                    f"- Severity: {finding['severity']}",
                    f"- Detector: {finding['detector']}",
                    f"- Exact Flagged Claim: {finding['exact_flagged_claim']}",
                    f"- Normalized Claim: {finding['normalized_claim']}",
                    (
                        "- Expected Evidence: "
                        + (_join_items(finding["expected_evidence"]) or "none")
                    ),
                    (
                        "- Available Evidence: "
                        + (_join_items(finding["available_evidence"]) or "none")
                    ),
                    "- Source IDs: " + (_join_items(finding["source_ids"]) or "none"),
                    (
                        "- Structured Field IDs: "
                        + (_join_items(finding["structured_field_ids"]) or "none")
                    ),
                    f"- Explanation: {finding['explanation']}",
                    f"- Classification: {finding['classification']}",
                    f"- Remediation Status: {finding['remediation_status']}",
                    "",
                ]
            )

    lines.extend(["## Policy Reasons", ""])
    if not report.policy_result.reasons:
        lines.append("No policy failures or warnings were recorded.")
    else:
        for reason in report.policy_result.reasons:
            lines.append(f"- {reason}")

    lines.extend(["", "## Judge Metrics", ""])
    if not report.judge_metrics:
        lines.append("No judge metrics were requested.")
    else:
        lines.append("| Framework | Metric | Case | Score | Status | Reason |")
        lines.append("| --- | --- | --- | ---: | --- | --- |")
        for metric in report.judge_metrics:
            status = "skipped" if metric.skipped else ("passed" if metric.passed else "failed")
            score = "" if metric.score is None else f"{metric.score:.3f}"
            lines.append(
                f"| {metric.framework} | {metric.metric_name} | {metric.case_id} | "
                f"{score} | {status} | {metric.reason or ''} |"
            )

    lines.extend(["", "## Limitations", ""])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")

    return "\n".join(lines) + "\n"


def factuality_report_to_json(report: FactualityReport) -> str:
    return json.dumps(report.to_dict(), indent=2) + "\n"


def _join_items(values: object) -> str:
    if not isinstance(values, list):
        return ""
    return " | ".join(str(value) for value in values if str(value).strip())
