"""Canonical presentation of typed evidence. No estimation or inferred business inputs."""

from .results import AnalysisResultEnvelope


def render_analysis(envelope: AnalysisResultEnvelope) -> str:
    lines = [f"Method: {envelope.method or 'not selected'}. Status: {envelope.status}."]
    if envelope.abstention is not None:
        lines.append(
            f"Analysis withheld ({envelope.abstention.code}): {envelope.abstention.message}"
        )
    if envelope.failure is not None:
        lines.append(f"Analysis unavailable ({envelope.failure.code}).")
    if envelope.evidence is not None:
        # The family discriminator preserves applicable uncertainty semantics;
        # native labels/units, assumptions and diagnostics are not reinterpreted.
        lines.extend(
            [
                "Validated evidence, uncertainty, assumptions and diagnostics:",
                envelope.evidence.model_dump_json(indent=2),
            ]
        )
    if envelope.business_impact is not None:
        lines.extend(
            [
                "Business scenario: explicit operational inputs and derived impact "
                "(separate from statistical evidence):",
                envelope.business_impact.model_dump_json(indent=2),
            ]
        )
    lines.append(
        "This evidence does not authorize rollout; "
        "product readiness and human review remain separate."
    )
    lines.append("Structured artifacts: " + ", ".join(a.artifact_id for a in envelope.artifacts))
    return "\n\n".join(lines)
