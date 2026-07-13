from __future__ import annotations

import json
from dataclasses import asdict

from packages.evals.prompt_experiments.models import PromptExperimentReport


def render_prompt_experiment_report(report: PromptExperimentReport) -> str:
    return render_prompt_experiment_report_payload(asdict(report))


def render_prompt_experiment_report_payload(payload: dict[str, object]) -> str:
    variants = dict(payload.get("variants", {}))
    treatment_versions = tuple(payload.get("treatment_versions", ()))
    recommendation = dict(payload.get("recommendation", {}))
    lines = [
        "# Prompt Experiment Report",
        "",
        f"- Experiment ID: {payload.get('experiment_id', '')}",
        f"- Prompt ID: {payload.get('prompt_id', '')}",
        f"- Control version: {payload.get('control_version', '')}",
        f"- Treatment versions: {', '.join(str(value) for value in treatment_versions)}",
        f"- Dataset: {payload.get('dataset_id', '')}",
        f"- Assignment strategy: {payload.get('assignment_strategy', '')}",
        f"- Recommendation: {recommendation.get('outcome', '')}",
        (
            "- Production traffic involved: yes"
            if bool(payload.get("production_traffic_involved"))
            else "- Production traffic involved: no"
        ),
        "",
        "## Variants",
        "",
        (
            "| Variant | Prompt Version | Sample Size | Factuality Pass Rate | "
            "Citation Coverage | Regression Pass Rate |"
        ),
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for variant, result in variants.items():
        result_mapping = dict(result)
        metrics = dict(result_mapping.get("metrics", {}))
        lines.append(
            f"| {variant} | {result_mapping.get('prompt_version', '')} | "
            f"{int(result_mapping.get('sample_size', 0) or 0)} | "
            f"{float(metrics.get('factuality_pass_rate', 0.0) or 0.0):.3f} | "
            f"{float(metrics.get('citation_coverage', 0.0) or 0.0):.3f} | "
            f"{float(metrics.get('regression_pass_rate', 0.0) or 0.0):.3f} |"
        )

    lines.extend(["", "## Recommendation", ""])
    for reason in recommendation.get("reasons", ()):
        lines.append(f"- {reason}")

    lines.extend(["", "## Limitations", ""])
    for limitation in payload.get("limitations", ()):
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"


def prompt_experiment_report_to_json(report: PromptExperimentReport) -> str:
    return json.dumps(asdict(report), indent=2)
