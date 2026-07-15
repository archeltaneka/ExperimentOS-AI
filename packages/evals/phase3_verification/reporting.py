from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from packages.evals.phase3_verification.models import FinalReliabilityReview, ReviewFinding

_ASSIGNED_SECRET = re.compile(
    r"(?i)\b(?:OPENAI_API_KEY|GEMINI_API_KEY|LANGSMITH_API_KEY|"
    r"EXPERIMENTOS_PHOENIX_API_KEY|DATABASE_URL|TOKEN|PASSWORD|SECRET)"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_TOKEN = re.compile(
    r"(?:\bsk-[A-Za-z0-9_-]{12,}|\bghp_[A-Za-z0-9]{12,}|\bgithub_pat_[A-Za-z0-9_]{12,})"
)
_JSON_PROMPT = re.compile(r'(?i)("(?:prompt|system_prompt|user_prompt)"\s*:\s*)"(?:\\.|[^"\\])*"')
_JSON_RETRIEVED_CHUNKS = re.compile(
    r'(?is)("(?:retrieved_chunks|document_chunks)"\s*:\s*)\[[^\]]*\]'
)


def final_review_to_dict(review: FinalReliabilityReview) -> dict[str, object]:
    payload = asdict(review)
    redacted = _redact_structure(payload)
    if not isinstance(redacted, dict):
        raise TypeError("final reliability review must serialize to an object")
    return redacted


def render_final_review_markdown(review: FinalReliabilityReview) -> str:
    payload = final_review_to_dict(review)
    lines = [
        "# Phase 3 Final Reliability Review",
        "",
        f"- Schema: `{review.schema_version}`",
        f"- Generated: `{review.generated_at_utc}`",
        f"- Mode: `{review.mode}`",
        f"- Closeout eligible: `{'yes' if review.closeout_eligible else 'no'}`",
        f"- Overall status: `{review.overall_status}`",
        (
            "- Scope: production-oriented portfolio system; "
            "not proof of production deployment at scale."
        ),
        "",
        "## Files Changed",
        "",
        _summary(review, "files_changed", "Recorded in the issue branch Git diff."),
        "",
        "## Capability Inventory",
        "",
        (
            "| Capability | Implementation | Configuration | CLI | Tests | Reports | Docs | "
            "Optional dependencies | Default | External requirement | Limitations |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in review.capability_inventory:
        lines.append(
            "| "
            + " | ".join(
                (
                    _cell(f"{item.capability_id}: {item.name}"),
                    _items(item.implementation_locations),
                    _items(item.configuration),
                    _items(item.cli_commands),
                    _items(item.tests),
                    _items(item.generated_reports),
                    _items(item.documentation),
                    _items(item.optional_dependencies),
                    _cell(item.default_state),
                    _cell(item.external_service_requirement),
                    _items(item.known_limitations),
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Architecture Review",
            "",
            _summary(review, "architecture", "No architecture summary was recorded."),
            "",
            "### Architectural Inconsistencies Found",
            "",
            _finding_lines(review.findings, status="open", area="architecture"),
            "",
            "## Defects Fixed",
            "",
            _finding_lines(review.findings, status="fixed"),
            "",
            "## Configuration and Security Findings",
            "",
            _summary(review, "security", "Configuration and security checks are command-backed."),
            "",
            _finding_lines(review.findings, areas={"configuration", "security", "privacy"}),
            "",
            "## Commands Run",
            "",
            "| Command | Status | Exit | Duration (s) | Expected reports |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for command in payload["commands"]:
        if not isinstance(command, dict):
            continue
        argv = command.get("argv", ())
        rendered_argv = (
            " ".join(str(value) for value in argv) if isinstance(argv, list | tuple) else ""
        )
        report_paths = command.get("report_paths", ())
        rendered_reports = (
            "<br>".join(_cell(str(value)) for value in report_paths)
            if isinstance(report_paths, list | tuple) and report_paths
            else "none"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    _cell(f"{command.get('command_id')}: {rendered_argv}"),
                    _cell(str(command.get("status"))),
                    _cell(str(command.get("exit_code"))),
                    _cell(str(command.get("duration_seconds"))),
                    rendered_reports,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Test Results",
            "",
            _summary(review, "tests", "See the command table for focused and full test evidence."),
            "",
            "## Database Verification",
            "",
            _summary(review, "database", "See strict database command evidence."),
            "",
            "## Evaluation Results",
            "",
            _summary(review, "evaluations", "See authoritative quality-gate reports."),
            "",
            "### Dataset Versions",
            "",
            _mapping_table(review.dataset_versions, "Dataset", "Version"),
            "",
            "## Factuality Invariants",
            "",
            _mapping_table(review.factuality_invariants, "Invariant", "Findings"),
            "",
            "## Quality Policy",
            "",
            f"- Policy version: `{_cell(review.policy_version)}`",
            f"- {_summary(review, 'quality_policy', 'See the authoritative policy report.')}",
            "",
            "## Observability",
            "",
            _summary(
                review,
                "observability",
                "See status, validation, dry-run, and in-memory tests.",
            ),
            "",
            "## CI and PR Reporting",
            "",
            _summary(review, "ci", "CI orchestration and PR reporting were validated locally."),
            "",
            "## API Compatibility",
            "",
            _mapping_table(review.compatibility, "Contract", "Status"),
            "",
            "## Documentation Changes",
            "",
            _summary(
                review,
                "documentation",
                "Documentation was reviewed against working commands.",
            ),
            "",
            "## Known Limitations",
            "",
            _bullets(review.limitations),
            "",
            "## Unresolved Risks",
            "",
            _bullets(review.unresolved_risks),
            "",
            "## Recommended Phase 4 Direction",
            "",
            _summary(
                review,
                "phase4",
                "Address documented deferred work without expanding Phase 3.",
            ),
            "",
            "## Milestone Recommendation",
            "",
            f"`{review.recommendation}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_final_review(
    review: FinalReliabilityReview,
    *,
    markdown_path: Path,
    json_path: Path,
) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(final_review_to_dict(review), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_final_review_markdown(review), encoding="utf-8")


def _redact_structure(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _redact_structure(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_redact_structure(item) for item in value)
    if isinstance(value, list):
        return [_redact_structure(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    redacted = _ASSIGNED_SECRET.sub("[REDACTED]", value)
    redacted = _BEARER_TOKEN.sub("Bearer [REDACTED]", redacted)
    redacted = _SECRET_TOKEN.sub("[REDACTED]", redacted)
    redacted = _JSON_PROMPT.sub(r'\1"[REDACTED]"', redacted)
    return _JSON_RETRIEVED_CHUNKS.sub(r"\1[\"[REDACTED]\"]", redacted)


def _summary(review: FinalReliabilityReview, key: str, fallback: str) -> str:
    return _redact_text(review.section_summaries.get(key, fallback))


def _items(values: tuple[str, ...]) -> str:
    return "<br>".join(_cell(value) for value in values) if values else "none"


def _cell(value: str) -> str:
    return _redact_text(value).replace("|", "\\|").replace("\n", " ")


def _bullets(values: tuple[str, ...]) -> str:
    if not values:
        return "- None recorded."
    return "\n".join(f"- {_redact_text(value)}" for value in values)


def _mapping_table(values: dict[str, object], key_heading: str, value_heading: str) -> str:
    lines = [f"| {key_heading} | {value_heading} |", "| --- | --- |"]
    for key, value in sorted(values.items()):
        lines.append(f"| {_cell(str(key))} | {_cell(str(value))} |")
    return "\n".join(lines)


def _finding_lines(
    findings: tuple[ReviewFinding, ...],
    *,
    status: str | None = None,
    area: str | None = None,
    areas: set[str] | None = None,
) -> str:
    selected = [
        finding
        for finding in findings
        if (status is None or finding.status == status)
        and (area is None or finding.area == area)
        and (areas is None or finding.area in areas)
    ]
    if not selected:
        return "- None recorded."
    return "\n".join(
        f"- `{finding.finding_id}` [{finding.severity}/{finding.status}] "
        f"{_redact_text(finding.summary)}"
        for finding in selected
    )
