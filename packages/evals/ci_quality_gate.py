from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from packages.evals.policy.models import MetricThreshold, QualityPolicy


@dataclass(frozen=True)
class CiEnvironmentFingerprint:
    ask_mode: str
    embedding_provider: str
    llm_provider: str
    prompt_experiments_enabled: bool
    external_judges_enabled: bool
    live_provider_configured: bool
    observability_export_enabled: bool
    ragas_judge_llm_provider: str = "none"
    ragas_judge_embedding_provider: str = "none"
    deepeval_judge_provider: str = "none"
    openai_api_key_present: bool = False
    google_api_key_present: bool = False
    database_url_present: bool = False


@dataclass(frozen=True)
class ArtifactRecord:
    relative_path: str
    present: bool


@dataclass(frozen=True)
class ArtifactManifest:
    artifact_root: str
    required_reports: tuple[ArtifactRecord, ...]
    optional_reports: tuple[ArtifactRecord, ...]


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: str
    exit_code: int


GateStatus = Literal["pass", "quality_fail", "infrastructure_fail"]


@dataclass(frozen=True)
class GateResult:
    status: GateStatus
    message: str
    artifact_name: str
    fingerprint: CiEnvironmentFingerprint
    manifest: ArtifactManifest
    command_results: tuple[CommandResult, ...] = field(default_factory=tuple)


def validate_ci_environment(
    env: Mapping[str, str],
    *,
    require_database: bool = True,
) -> CiEnvironmentFingerprint:
    ask_mode = env.get("ASK_MODE", "").strip()
    if ask_mode != "agent_workflow":
        raise ValueError("ASK_MODE must remain `agent_workflow` for the CI quality gate.")

    embedding_provider = env.get("EMBEDDING_PROVIDER", "").strip().lower()
    if embedding_provider != "fake":
        raise ValueError("EMBEDDING_PROVIDER must remain `fake` for deterministic CI.")

    llm_provider = env.get("LLM_PROVIDER", "").strip().lower()
    if llm_provider != "mock":
        raise ValueError("LLM_PROVIDER must remain `mock` for deterministic CI.")

    prompt_experiments_enabled = _env_bool(env.get("PROMPT_EXPERIMENTS_ENABLED", "false"))
    if prompt_experiments_enabled:
        raise ValueError("PROMPT_EXPERIMENTS_ENABLED must remain false in CI.")

    ragas_judge_llm_provider = env.get("RAGAS_JUDGE_LLM_PROVIDER", "none").strip().lower()
    if ragas_judge_llm_provider not in {"", "none", "mock"}:
        raise ValueError(
            "RAGAS_JUDGE_LLM_PROVIDER must remain `none` or `mock` for offline CI."
        )

    ragas_judge_embedding_provider = env.get(
        "RAGAS_JUDGE_EMBEDDING_PROVIDER",
        "none",
    ).strip().lower()
    if ragas_judge_embedding_provider not in {"", "none", "fake"}:
        raise ValueError(
            "RAGAS_JUDGE_EMBEDDING_PROVIDER must remain `none` or `fake` for offline CI."
        )

    deepeval_judge_provider = env.get("DEEPEVAL_JUDGE_PROVIDER", "none").strip().lower()
    if deepeval_judge_provider not in {"", "none"}:
        raise ValueError("DEEPEVAL_JUDGE_PROVIDER must remain `none` for offline CI.")

    openai_api_key_present = bool(env.get("OPENAI_API_KEY", "").strip())
    if openai_api_key_present:
        raise ValueError("OPENAI_API_KEY must be empty so no live provider can be selected.")

    google_api_key_present = bool(env.get("GOOGLE_API_KEY", "").strip())
    if google_api_key_present:
        raise ValueError("GOOGLE_API_KEY must be empty so no live provider can be selected.")

    observability_export_enabled = _observability_export_enabled(env)
    if observability_export_enabled:
        raise ValueError(
            "EXPERIMENTOS observability exporters must remain disabled for the CI quality gate."
        )

    database_url_present = bool(env.get("DATABASE_URL", "").strip())
    if require_database and not database_url_present:
        raise ValueError("DATABASE_URL is required for the DB-backed CI quality gate.")

    external_judges_enabled = any(
        provider not in safe_values
        for provider, safe_values in (
            (ragas_judge_llm_provider, {"", "none", "mock"}),
            (ragas_judge_embedding_provider, {"", "none", "fake"}),
            (deepeval_judge_provider, {"", "none"}),
        )
    )
    live_provider_configured = (
        openai_api_key_present
        or google_api_key_present
        or embedding_provider != "fake"
        or llm_provider != "mock"
        or external_judges_enabled
    )

    return CiEnvironmentFingerprint(
        ask_mode=ask_mode,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        prompt_experiments_enabled=prompt_experiments_enabled,
        external_judges_enabled=external_judges_enabled,
        live_provider_configured=live_provider_configured,
        observability_export_enabled=observability_export_enabled,
        ragas_judge_llm_provider=ragas_judge_llm_provider or "none",
        ragas_judge_embedding_provider=ragas_judge_embedding_provider or "none",
        deepeval_judge_provider=deepeval_judge_provider or "none",
        openai_api_key_present=openai_api_key_present,
        google_api_key_present=google_api_key_present,
        database_url_present=database_url_present,
    )


def validate_policy_invariants(policy: QualityPolicy) -> None:
    required_invariants = {
        "factuality.findings.fabricated_revenue_or_roi": ("lte", 0, "critical"),
        "factuality.findings.fabricated_statistical_significance": ("lte", 0, "critical"),
        "factuality.findings.contradiction_with_structured_experiment_data": (
            "lte",
            0,
            "critical",
        ),
    }
    metric_map = {metric.metric_id: metric for metric in policy.metrics}
    for metric_id, (operator, value, severity) in required_invariants.items():
        metric = metric_map.get(metric_id)
        if metric is None:
            raise ValueError(f"Critical invariant `{metric_id}` is missing from the policy.")
        _assert_invariant(metric, operator=operator, value=value, severity=severity)


def build_artifact_manifest(
    artifact_root: Path,
    *,
    required_paths: Sequence[Path],
    optional_paths: Sequence[Path],
) -> ArtifactManifest:
    return ArtifactManifest(
        artifact_root=str(artifact_root).replace("\\", "/"),
        required_reports=tuple(_artifact_record(artifact_root, path) for path in required_paths),
        optional_reports=tuple(_artifact_record(artifact_root, path) for path in optional_paths),
    )


def render_github_job_summary(
    policy_payload: Mapping[str, object],
    *,
    fingerprint: CiEnvironmentFingerprint,
    manifest: ArtifactManifest,
    artifact_name: str,
    policy_changed: bool = False,
    infrastructure_error: str | None = None,
) -> str:
    overall_status = str(policy_payload.get("overall_status", "unknown"))
    policy_version = str(policy_payload.get("policy_version", "unknown"))
    category_results = _mapping(policy_payload.get("category_results"))
    violations = _list(policy_payload.get("violations"))
    warnings = _list(policy_payload.get("warnings"))
    skipped_metrics = _list(policy_payload.get("skipped_metrics"))

    lines = [
        "# AI Quality Gate Summary",
        "",
        f"- Overall quality status: {overall_status}",
        f"- Policy version: `{policy_version}`",
        f"- Artifact bundle: `{artifact_name}`",
        f"- External judges used: {_yes_no(fingerprint.external_judges_enabled)}",
        f"- Live providers called: {_yes_no(fingerprint.live_provider_configured)}",
        f"- Observability exports enabled: {_yes_no(fingerprint.observability_export_enabled)}",
    ]
    if policy_changed:
        lines.append("- Quality policy file changed in this revision.")
    if infrastructure_error:
        lines.append(f"- Infrastructure failure: {infrastructure_error}")

    lines.extend(["", "## Category Status", ""])
    if category_results:
        for category, payload in category_results.items():
            status = "unknown"
            if isinstance(payload, Mapping):
                status = str(payload.get("status", "unknown"))
            lines.append(f"- {category}: {status}")
    else:
        lines.append("- No category results were available.")

    lines.extend(["", "## Required Suites", ""])
    for artifact in manifest.required_reports:
        lines.append(
            f"- `{artifact.relative_path}`: {'present' if artifact.present else 'missing'}"
        )

    lines.extend(["", "## Critical Violations", ""])
    critical_violations = [
        violation for violation in violations if _mapping(violation).get("severity") == "critical"
    ]
    if critical_violations:
        for violation in critical_violations:
            payload = _mapping(violation)
            lines.append(
                f"- `{payload.get('metric_id', 'unknown')}`: {payload.get('message', 'no details')}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Warnings", ""])
    if warnings:
        for warning in warnings:
            payload = _mapping(warning)
            lines.append(
                f"- `{payload.get('metric_id', 'unknown')}`: {payload.get('message', 'no details')}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Skipped Optional Metrics", ""])
    if skipped_metrics:
        for metric in skipped_metrics:
            payload = _mapping(metric)
            lines.append(
                f"- `{payload.get('metric_id', 'unknown')}`: {payload.get('message', 'no details')}"
            )
    else:
        lines.append("- None.")

    return "\n".join(lines) + "\n"


def write_gate_result(path: Path, result: GateResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")


def _artifact_record(artifact_root: Path, path: Path) -> ArtifactRecord:
    return ArtifactRecord(
        relative_path=path.as_posix(),
        present=(artifact_root / path).is_file(),
    )


def _assert_invariant(
    metric: MetricThreshold,
    *,
    operator: str,
    value: int,
    severity: str,
) -> None:
    if metric.operator != operator:
        raise ValueError(
            f"Critical invariant `{metric.metric_id}` must use operator `{operator}`."
        )
    if metric.value != value:
        raise ValueError(f"Critical invariant `{metric.metric_id}` must keep value `{value}`.")
    if metric.severity != severity:
        raise ValueError(
            f"Critical invariant `{metric.metric_id}` must keep severity `{severity}`."
        )
    if metric.required is not True:
        raise ValueError(f"Critical invariant `{metric.metric_id}` must remain required.")


def _env_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _observability_export_enabled(env: Mapping[str, str]) -> bool:
    return any(
        (
            _env_bool(env.get("EXPERIMENTOS_LANGSMITH_ENABLED", "false")),
            _env_bool(env.get("LANGSMITH_TRACING", "false")),
            _env_bool(env.get("EXPERIMENTOS_PHOENIX_ENABLED", "false")),
            _env_bool(env.get("EXPERIMENTOS_OTEL_ENABLED", "false")),
            env.get("EXPERIMENTOS_OTEL_EXPORTER_TYPE", "").strip().lower()
            not in {"", "none"},
        )
    )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []
