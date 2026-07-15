from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from pathlib import Path

from packages.evals.agent_dataset import (
    DEFAULT_AGENT_DATASET_PATH,
    load_agent_evaluation_dataset,
)
from packages.evals.dataset import DEFAULT_DATASET_PATH, load_evaluation_dataset
from packages.evals.dataset_manifest import build_dataset_manifest
from packages.evals.phase3_verification.inventory import build_capability_inventory
from packages.evals.phase3_verification.models import (
    CommandResult,
    FinalReliabilityReview,
    ReviewFinding,
    VerificationCommand,
    VerificationMode,
)
from packages.evals.phase3_verification.reporting import write_final_review
from packages.evals.phase3_verification.validation import (
    VerificationError,
    derive_recommendation,
    extract_factuality_invariants,
    load_json_object,
    validate_final_review_files,
    validate_required_reports,
)

_OUTPUT_TAIL_LIMIT = 8_000
_PROMPT_EXPERIMENT_ID = "rag-answer-abstention-v1-v2"
_FINAL_JSON_NAME = "final_reliability_review.json"
_FINAL_MARKDOWN_NAME = "final_reliability_review.md"
_SAFE_ENVIRONMENT = {
    "ASK_MODE": "agent_workflow",
    "EMBEDDING_PROVIDER": "fake",
    "LLM_PROVIDER": "mock",
    "RAGAS_JUDGE_LLM_PROVIDER": "none",
    "RAGAS_JUDGE_EMBEDDING_PROVIDER": "none",
    "DEEPEVAL_JUDGE_PROVIDER": "none",
    "EXPERIMENTOS_LANGSMITH_ENABLED": "false",
    "LANGSMITH_TRACING": "false",
    "EXPERIMENTOS_PHOENIX_ENABLED": "false",
    "EXPERIMENTOS_OTEL_ENABLED": "false",
    "EXPERIMENTOS_OTEL_EXPORTER_TYPE": "none",
    "PROMPT_EXPERIMENTS_ENABLED": "false",
    "OPENAI_API_KEY": "",
    "GEMINI_API_KEY": "",
    "LANGCHAIN_API_KEY": "",
    "LANGSMITH_API_KEY": "",
    "EXPERIMENTOS_PHOENIX_API_KEY": "",
    "LANGSMITH_ENDPOINT": "",
    "EXPERIMENTOS_PHOENIX_ENDPOINT": "",
    "EXPERIMENTOS_OTEL_EXPORTER_ENDPOINT": "",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "",
    "PYTHONHASHSEED": "0",
}
_SAFE_SOURCE_VALUES = {
    "ASK_MODE": {"", "agent_workflow"},
    "EMBEDDING_PROVIDER": {"", "fake"},
    "LLM_PROVIDER": {"", "mock"},
    "RAGAS_JUDGE_LLM_PROVIDER": {"", "none"},
    "RAGAS_JUDGE_EMBEDDING_PROVIDER": {"", "none"},
    "DEEPEVAL_JUDGE_PROVIDER": {"", "none"},
    "EXPERIMENTOS_LANGSMITH_ENABLED": {"", "false", "0", "no"},
    "LANGSMITH_TRACING": {"", "false", "0", "no"},
    "EXPERIMENTOS_PHOENIX_ENABLED": {"", "false", "0", "no"},
    "EXPERIMENTOS_OTEL_ENABLED": {"", "false", "0", "no"},
    "EXPERIMENTOS_OTEL_EXPORTER_TYPE": {"", "none"},
    "PROMPT_EXPERIMENTS_ENABLED": {"", "false", "0", "no"},
}


def build_verification_environment(source: Mapping[str, str]) -> dict[str, str]:
    for variable, safe_values in _SAFE_SOURCE_VALUES.items():
        value = source.get(variable, "").strip().lower()
        if value not in safe_values:
            raise ValueError(
                f"{variable}={source.get(variable)!r} conflicts with offline verification safety."
            )
    environment = dict(source)
    environment.update(_SAFE_ENVIRONMENT)
    return environment


def discover_synthetic_fixtures(
    root: Path,
    expected_ids: Collection[str],
) -> tuple[Path, ...]:
    if not root.is_dir():
        raise ValueError(
            f"synthetic fixture directory is missing: {root}. "
            "Run `uv run python scripts/generate_synthetic_experiments.py` only when safe."
        )
    expected = set(expected_ids)
    discovered = {path.name: path for path in root.iterdir() if path.is_dir()}
    missing = sorted(expected - set(discovered))
    extra = sorted(set(discovered) - expected)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected: {', '.join(extra)}")
        raise ValueError(
            "synthetic fixture inventory does not match QA dataset (" + "; ".join(details) + ")"
        )
    return tuple(discovered[experiment_id] for experiment_id in sorted(expected))


def run_command(
    command: VerificationCommand,
    *,
    env: Mapping[str, str],
    cwd: Path,
) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command.argv),
            cwd=cwd,
            env=dict(env),
            text=True,
            capture_output=True,
            timeout=command.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command_id=command.command_id,
            argv=command.argv,
            status="timeout",
            exit_code=None,
            duration_seconds=round(time.monotonic() - started, 3),
            stdout_tail=_tail(exc.stdout),
            stderr_tail=_tail(exc.stderr),
            report_paths=command.report_paths,
        )
    return CommandResult(
        command_id=command.command_id,
        argv=command.argv,
        status="pass" if completed.returncode == 0 else "fail",
        exit_code=completed.returncode,
        duration_seconds=round(time.monotonic() - started, 3),
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
        report_paths=command.report_paths,
    )


def run_phase3_verification(
    *,
    mode: VerificationMode,
    artifact_root: Path,
    report_root: Path,
    repository_root: Path,
    source_environment: Mapping[str, str] | None = None,
) -> FinalReliabilityReview:
    source = dict(os.environ if source_environment is None else source_environment)
    artifact_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    for path in (
        artifact_root / "diagnostic/prompt_experiments",
        artifact_root / "quality_gate/phase3/prompt_experiments",
        artifact_root / "ci",
    ):
        path.mkdir(parents=True, exist_ok=True)

    try:
        environment = build_verification_environment(source)
    except ValueError as exc:
        return _write_configuration_failure(
            mode=mode,
            artifact_root=artifact_root,
            report_root=report_root,
            message=str(exc),
        )
    if mode == "strict" and not source.get("DATABASE_URL", "").strip():
        return _write_configuration_failure(
            mode=mode,
            artifact_root=artifact_root,
            report_root=report_root,
            message=(
                "DATABASE_URL is required for strict closeout. "
                "Run `docker compose up -d postgres`, "
                "then in PowerShell set `$env:DATABASE_URL = "
                '"postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"`.'
            ),
        )

    try:
        commands = build_verification_commands(mode, artifact_root=artifact_root)
    except (OSError, ValueError) as exc:
        return _write_configuration_failure(
            mode=mode,
            artifact_root=artifact_root,
            report_root=report_root,
            message=f"verification input validation failed: {exc}",
        )

    results: list[CommandResult] = []
    database_failed = False
    quality_gate_failed = False
    for command in commands:
        if command.command_id.startswith("database.") and database_failed:
            result = _skipped_result(command, "blocked by an earlier database stage failure")
        elif command.command_id in {"tests.database", "quality_gate.full"} and database_failed:
            result = _skipped_result(command, "blocked by an earlier database stage failure")
        elif command.command_id.startswith("ci_report.") and quality_gate_failed:
            result = _skipped_result(command, "blocked by the authoritative quality gate failure")
        else:
            result = run_command(command, env=environment, cwd=repository_root)
        results.append(result)
        if command.command_id.startswith("database.") and result.status != "pass":
            database_failed = True
        if command.command_id == "tests.database" and result.status != "pass":
            database_failed = True
        if command.command_id == "quality_gate.full" and result.status != "pass":
            quality_gate_failed = True

    policy_payload: dict[str, object] = {"overall_status": "pass"}
    factuality_invariants: dict[str, int] = {}
    validation_errors: list[str] = []
    if mode == "strict":
        try:
            payloads = validate_required_reports(artifact_root)
            policy_payload = payloads["quality_gate/phase3/quality_policy.json"]
            factuality_invariants = extract_factuality_invariants(
                payloads["quality_gate/phase3/factuality_report.json"]
            )
        except VerificationError as exc:
            validation_errors.append(str(exc))
    else:
        factuality_path = artifact_root / "diagnostic/factuality_report.json"
        try:
            factuality_invariants = extract_factuality_invariants(load_json_object(factuality_path))
            _validate_declared_command_reports(results)
        except VerificationError as exc:
            validation_errors.append(str(exc))

    if validation_errors:
        results.append(
            _synthetic_result(
                "reports.required",
                status="fail",
                exit_code=2,
                stderr="; ".join(validation_errors),
            )
        )
    recommendation = derive_recommendation(
        mode=mode,
        command_results=tuple(results),
        policy_payload=policy_payload,
        factuality_invariants=factuality_invariants,
        unresolved_critical_findings=0,
    )
    review = _build_review(
        mode=mode,
        command_results=tuple(results),
        recommendation=recommendation,
        overall_status="fail" if recommendation == "not_ready" else "pass",
        policy_payload=policy_payload,
        factuality_invariants=factuality_invariants,
        validation_errors=tuple(validation_errors),
    )
    _write_and_validate_review(review, report_root)
    return review


def build_verification_commands(
    mode: VerificationMode,
    *,
    artifact_root: Path,
) -> tuple[VerificationCommand, ...]:
    commands = list(_common_commands(artifact_root))
    if mode == "offline_only":
        commands.extend(_offline_diagnostic_commands(artifact_root))
        return tuple(commands)

    questions = load_evaluation_dataset(DEFAULT_DATASET_PATH)
    fixtures = discover_synthetic_fixtures(
        Path("data/synthetic/experiments"),
        {question.experiment_id for question in questions},
    )
    commands.append(
        _command(
            "database.migrate",
            "uv",
            "run",
            "alembic",
            "upgrade",
            "head",
            strict_only=True,
        )
    )
    for pass_number in (1, 2):
        for fixture in fixtures:
            commands.append(
                _command(
                    f"database.ingest.{pass_number}.{fixture.name}",
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "packages.ingestion.load_experiment",
                    "--experiment-dir",
                    str(fixture),
                    "--embedding-provider",
                    "fake",
                    strict_only=True,
                )
            )
    commands.extend(_strict_commands(artifact_root))
    return tuple(commands)


def _common_commands(_artifact_root: Path) -> tuple[VerificationCommand, ...]:
    focused_tests = (
        "tests/test_phase3_dataset_integrity.py",
        "tests/test_phase3_architecture.py",
        "tests/test_env_config.py",
        "tests/test_api_health.py",
        "tests/test_api_ask.py",
        "tests/test_agent_workflow.py",
        "tests/test_evaluation_harness.py",
        "tests/test_agent_evaluation.py",
        "tests/test_agent_e2e_evaluation.py",
        "tests/test_ragas_evaluation.py",
        "tests/test_deepeval_evaluation.py",
        "tests/test_prompt_registry.py",
        "tests/test_prompt_registry_cli.py",
        "tests/test_prompt_regression.py",
        "tests/test_prompt_experiment_validation.py",
        "tests/test_prompt_experiment_runner.py",
        "tests/test_prompt_experiment_cli.py",
        "tests/test_factuality.py",
        "tests/test_quality_policy.py",
        "tests/test_observability_config.py",
        "tests/test_observability_cli.py",
        "tests/test_observability_langsmith.py",
        "tests/test_observability_phoenix.py",
        "tests/test_observability_opentelemetry.py",
        "tests/test_observability_composite.py",
        "tests/test_observability_redaction.py",
        "tests/test_observability_integration.py",
        "tests/test_ci_quality_gate.py",
        "tests/test_ci_reporting.py",
        "tests/test_github_actions_ci.py",
        "tests/test_repository_hygiene.py",
        "tests/test_phase3_verification.py",
    )
    return (
        _command("config.lock", "uv", "lock", "--check"),
        _command("format.check", "uv", "run", "ruff", "format", "--check", "."),
        _command("lint", "uv", "run", "ruff", "check", "."),
        _command(
            "prompt.registry.validate",
            "uv",
            "run",
            "python",
            "-m",
            "packages.llm.prompt_registry_cli",
            "validate",
        ),
        _command(
            "prompt.experiment.validate",
            "uv",
            "run",
            "python",
            "-m",
            "packages.evals.run_prompt_experiment",
            "validate",
            "--experiment",
            _PROMPT_EXPERIMENT_ID,
        ),
        _command(
            "observability.status",
            "uv",
            "run",
            "python",
            "-m",
            "packages.observability.cli",
            "status",
            "--provider",
            "all",
        ),
        _command(
            "observability.validate",
            "uv",
            "run",
            "python",
            "-m",
            "packages.observability.cli",
            "validate",
            "--provider",
            "all",
        ),
        *tuple(
            _command(
                f"observability.dry_run.{provider}",
                "uv",
                "run",
                "python",
                "-m",
                "packages.observability.cli",
                "dry-run",
                "--provider",
                provider,
            )
            for provider in ("langsmith", "phoenix", "opentelemetry")
        ),
        _command("tests.focused", "uv", "run", "pytest", "-q", *focused_tests, timeout=600),
    )


def _offline_diagnostic_commands(artifact_root: Path) -> tuple[VerificationCommand, ...]:
    report_dir = artifact_root / "diagnostic"
    return (
        _command(
            "evaluation.prompt_regression",
            "uv",
            "run",
            "python",
            "-m",
            "packages.evals.run_prompt_regression",
            "--prompt-id",
            "rag.answer",
            "--baseline-version",
            "1",
            "--candidate-version",
            "1",
            "--offline",
            "--dataset",
            DEFAULT_DATASET_PATH.as_posix(),
            "--embedding-provider",
            "fake",
            "--llm-provider",
            "mock",
            "--output",
            str(report_dir / "prompt_regression.md"),
            "--json-output",
            str(report_dir / "prompt_regression.json"),
            reports=(
                str(report_dir / "prompt_regression.md"),
                str(report_dir / "prompt_regression.json"),
            ),
        ),
        _command(
            "evaluation.factuality",
            "uv",
            "run",
            "python",
            "-m",
            "packages.evals.run_factuality",
            "--target",
            "agent_workflow",
            "--mode",
            "offline",
            "--judge-provider",
            "none",
            "--report-dir",
            str(report_dir),
            reports=(
                str(report_dir / "factuality_report.md"),
                str(report_dir / "factuality_report.json"),
            ),
        ),
        _command(
            "prompt.experiment.sample",
            "uv",
            "run",
            "python",
            "-m",
            "packages.evals.run_prompt_experiment",
            "run",
            "--experiment",
            _PROMPT_EXPERIMENT_ID,
            "--mode",
            "offline",
            "--dataset",
            DEFAULT_DATASET_PATH.as_posix(),
            "--report-dir",
            str(report_dir / "prompt_experiments"),
            reports=(
                str(report_dir / f"prompt_experiments/{_PROMPT_EXPERIMENT_ID}.md"),
                str(report_dir / f"prompt_experiments/{_PROMPT_EXPERIMENT_ID}.json"),
            ),
        ),
    )


def _strict_commands(artifact_root: Path) -> tuple[VerificationCommand, ...]:
    quality_root = artifact_root / "quality_gate"
    ci_root = artifact_root / "ci"
    database_tests = (
        "tests/test_alembic_config.py",
        "tests/test_db_models.py",
        "tests/test_ingestion_load_experiment.py",
        "tests/test_retrieval_service.py",
        "tests/test_retrieval_agent.py",
        "tests/test_api_ask_db_integration.py",
    )
    return (
        _command(
            "tests.full",
            "uv",
            "run",
            "pytest",
            "-q",
            timeout=1200,
            strict_only=True,
        ),
        _command(
            "tests.database",
            "uv",
            "run",
            "pytest",
            "-q",
            *database_tests,
            timeout=600,
            strict_only=True,
        ),
        _command(
            "quality_gate.full",
            "uv",
            "run",
            "python",
            "scripts/run_ai_quality_gate.py",
            "--artifact-root",
            str(quality_root),
            "--dataset",
            DEFAULT_DATASET_PATH.as_posix(),
            "--agent-dataset",
            "data/eval/agent_dataset.json",
            timeout=1800,
            strict_only=True,
        ),
        _command(
            "ci_report.build",
            "uv",
            "run",
            "python",
            "-m",
            "packages.evals.run_ci_report",
            "build",
            "--report-dir",
            str(quality_root),
            "--quality-policy-report",
            str(quality_root / "phase3/quality_policy.json"),
            "--output",
            str(ci_root / "pr_quality_report.json"),
            "--format",
            "all",
            "--strict",
            strict_only=True,
        ),
        _command(
            "ci_report.render",
            "uv",
            "run",
            "python",
            "-m",
            "packages.evals.run_ci_report",
            "render",
            "--input",
            str(ci_root / "pr_quality_report.json"),
            "--format",
            "pr-comment",
            "--output",
            str(ci_root / "pr_comment.md"),
            strict_only=True,
        ),
        _command(
            "ci_report.validate",
            "uv",
            "run",
            "python",
            "-m",
            "packages.evals.run_ci_report",
            "validate",
            "--input",
            str(ci_root / "pr_quality_report.json"),
            strict_only=True,
        ),
    )


def _command(
    command_id: str,
    *argv: str,
    timeout: int = 300,
    reports: tuple[str, ...] = (),
    strict_only: bool = False,
) -> VerificationCommand:
    return VerificationCommand(
        command_id=command_id,
        argv=tuple(argv),
        required=True,
        timeout_seconds=timeout,
        report_paths=reports,
        strict_only=strict_only,
    )


def _tail(value: str | bytes | None) -> str:
    if value is None:
        return ""
    text = value.decode(errors="replace") if isinstance(value, bytes) else value
    return text[-_OUTPUT_TAIL_LIMIT:]


def _write_configuration_failure(
    *,
    mode: VerificationMode,
    artifact_root: Path,
    report_root: Path,
    message: str,
) -> FinalReliabilityReview:
    result = _synthetic_result(
        "configuration.database_url" if "DATABASE_URL" in message else "configuration.safety",
        status="fail",
        exit_code=2,
        stderr=message,
    )
    review = _build_review(
        mode=mode,
        command_results=(result,),
        recommendation="not_ready",
        overall_status="fail",
        policy_payload={},
        factuality_invariants={},
        validation_errors=(message,),
    )
    _write_and_validate_review(review, report_root)
    return review


def _build_review(
    *,
    mode: VerificationMode,
    command_results: tuple[CommandResult, ...],
    recommendation: str,
    overall_status: str,
    policy_payload: Mapping[str, object],
    factuality_invariants: dict[str, int],
    validation_errors: tuple[str, ...],
) -> FinalReliabilityReview:
    qa_questions = load_evaluation_dataset(DEFAULT_DATASET_PATH)
    agent_cases = load_agent_evaluation_dataset(DEFAULT_AGENT_DATASET_PATH)
    qa_manifest = build_dataset_manifest(
        DEFAULT_DATASET_PATH,
        dataset_id="qa.golden",
        case_count=len(qa_questions),
    )
    agent_manifest = build_dataset_manifest(
        DEFAULT_AGENT_DATASET_PATH,
        dataset_id="agent.golden",
        case_count=len(agent_cases),
    )
    focused_passed = any(
        result.command_id == "tests.focused" and result.status == "pass"
        for result in command_results
    )
    compatibility_status = "pass" if focused_passed else "not_verified"
    policy_version = policy_payload.get("policy_version", "")
    limitations = [
        "Live OpenAI, LangSmith, Phoenix, and OTLP services are outside default verification.",
        "Dry-runs and in-memory exporters establish integration behavior, not production scale.",
        "Judge metrics are optional and skipped values are never interpreted as zero.",
    ]
    if mode == "offline_only":
        limitations.insert(
            0,
            "Offline-only mode is diagnostic and is not milestone closeout evidence.",
        )
    if validation_errors:
        limitations.append("Required evidence validation failed; see command diagnostics.")
    return FinalReliabilityReview(
        schema_version="phase3-final-review-v1",
        generated_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        mode=mode,
        closeout_eligible=mode == "strict",
        recommendation=recommendation,  # type: ignore[arg-type]
        overall_status=overall_status,  # type: ignore[arg-type]
        commands=command_results,
        capability_inventory=build_capability_inventory(),
        findings=_review_findings(),
        dataset_versions={
            qa_manifest.dataset_id: qa_manifest.version,
            agent_manifest.dataset_id: agent_manifest.version,
        },
        policy_version=str(policy_version),
        provider_configuration={
            "ask_mode": "agent_workflow",
            "embedding": "fake",
            "llm": "mock",
            "judges": "none",
            "external_observability_exports": "disabled",
            "prompt_experiments": "disabled",
        },
        factuality_invariants=factuality_invariants,
        compatibility={
            "ask_mode_default": "agent_workflow",
            "legacy_rag": compatibility_status,
            "post_ask_contract": compatibility_status,
            "deterministic_agents": compatibility_status,
            "third_party_run_ids_public": "absent" if focused_passed else "not_verified",
        },
        limitations=tuple(limitations),
        unresolved_risks=(
            "Live vendor connectivity and production load behavior require "
            "deployment-specific validation.",
        ),
        section_summaries=_section_summaries(
            mode=mode,
            command_results=command_results,
            policy_payload=policy_payload,
            validation_errors=validation_errors,
        ),
    )


def _review_findings() -> tuple[ReviewFinding, ...]:
    return (
        ReviewFinding(
            finding_id="P3-001",
            area="evaluation",
            severity="critical",
            status="fixed",
            summary="Evaluation reports lacked immutable dataset provenance.",
            evidence=("packages/evals/dataset_manifest.py",),
        ),
        ReviewFinding(
            finding_id="P3-002",
            area="configuration",
            severity="critical",
            status="fixed",
            summary="Missing provider settings could implicitly select live providers.",
            evidence=("apps/api/main.py", ".env.example"),
        ),
        ReviewFinding(
            finding_id="P3-003",
            area="evaluation",
            severity="critical",
            status="fixed",
            summary="The central policy omitted fabricated experiment-result zero tolerance.",
            evidence=("config/evaluation/quality_policy.yaml",),
        ),
        ReviewFinding(
            finding_id="P3-004",
            area="ci",
            severity="critical",
            status="fixed",
            summary="The quality-gate job could mask failed prerequisite jobs.",
            evidence=(".github/workflows/ci.yml",),
        ),
        ReviewFinding(
            finding_id="P3-005",
            area="security",
            severity="warning",
            status="fixed",
            summary="Several write-capable GitHub Actions were tag-pinned instead of SHA-pinned.",
            evidence=(".github/workflows/ci.yml",),
        ),
        ReviewFinding(
            finding_id="P3-006",
            area="reliability",
            severity="critical",
            status="fixed",
            summary=(
                "No repository-owned strict Phase 3 closeout command or report contract existed."
            ),
            evidence=("scripts/verify_phase3.py",),
        ),
        ReviewFinding(
            finding_id="P3-007",
            area="configuration",
            severity="critical",
            status="fixed",
            summary="Dotenv loading silently overrode explicit CI and verification settings.",
            evidence=("packages/config/env.py", "tests/test_env_config.py"),
        ),
        ReviewFinding(
            finding_id="P3-008",
            area="dependencies",
            severity="warning",
            status="fixed",
            summary="RAGAS 0.4.3 metric namespace changes made the installed adapter unavailable.",
            evidence=("packages/evals/ragas_adapter.py", "tests/test_ragas_evaluation.py"),
        ),
        ReviewFinding(
            finding_id="P3-009",
            area="dependencies",
            severity="warning",
            status="fixed",
            summary="The development group included an unused duplicate httpx2 distribution.",
            evidence=("pyproject.toml", "uv.lock"),
        ),
        ReviewFinding(
            finding_id="P3-010",
            area="documentation",
            severity="warning",
            status="fixed",
            summary="Phase 3 guides retained stale commands, scope, and CI-enforcement claims.",
            evidence=("docs/phase3/phase3_closeout.md",),
        ),
    )


def _section_summaries(
    *,
    mode: VerificationMode,
    command_results: tuple[CommandResult, ...],
    policy_payload: Mapping[str, object],
    validation_errors: tuple[str, ...],
) -> dict[str, str]:
    passed = sum(result.status == "pass" for result in command_results)
    failed = sum(result.status != "pass" for result in command_results)
    strict_label = "strict closeout" if mode == "strict" else "non-closeout diagnostic"
    return {
        "files_changed": "See the feature branch diff linked to GitHub issue #68.",
        "architecture": (
            "ExperimentOS models remain authoritative; external evaluation and observability "
            "integrations remain adapters or optional sinks."
        ),
        "security": (
            "External network access is test-blocked, secrets are redacted, and live providers "
            "and exports are disabled in verification."
        ),
        "tests": (
            f"{passed} command stages passed and {failed} did not pass in {strict_label} mode."
        ),
        "database": (
            "Alembic, deterministic repeated ingestion, retrieval, API, and workflow database "
            "tests are required in strict mode."
        ),
        "evaluations": (
            "Repository-owned evaluation reports are consumed through the centralized "
            "quality policy."
        ),
        "quality_policy": (
            f"Authoritative policy status: {policy_payload.get('overall_status', 'not available')}."
        ),
        "observability": (
            "NoOp, optional sink dry-runs, composite isolation, redaction, and OpenTelemetry "
            "in-memory exporters are covered without network calls."
        ),
        "ci": (
            "Prerequisite exit codes, strict policy failure, always-uploaded artifacts, and "
            "informational PR reporting are verified."
        ),
        "documentation": "Commands, defaults, limits, and branch-protection guidance are reviewed.",
        "phase4": (
            "Prioritize deployment-specific load validation and operational alerting only after "
            "Phase 3 closeout; do not infer production scale from this review."
        ),
        "validation": (
            "; ".join(validation_errors) if validation_errors else "all required evidence valid"
        ),
    }


def _validate_declared_command_reports(results: list[CommandResult]) -> None:
    missing = [
        path
        for result in results
        if result.status == "pass"
        for value in result.report_paths
        if not (path := Path(value)).is_file()
    ]
    if missing:
        raise VerificationError(
            "missing required report: " + ", ".join(path.as_posix() for path in missing)
        )
    for result in results:
        for value in result.report_paths:
            path = Path(value)
            if path.suffix == ".json":
                load_json_object(path)


def _write_and_validate_review(review: FinalReliabilityReview, report_root: Path) -> None:
    markdown_path = report_root / _FINAL_MARKDOWN_NAME
    json_path = report_root / _FINAL_JSON_NAME
    write_final_review(review, markdown_path=markdown_path, json_path=json_path)
    validate_final_review_files(json_path, markdown_path)


def _skipped_result(command: VerificationCommand, reason: str) -> CommandResult:
    return CommandResult(
        command_id=command.command_id,
        argv=command.argv,
        status="skipped",
        exit_code=None,
        duration_seconds=0.0,
        stdout_tail="",
        stderr_tail=reason,
        report_paths=command.report_paths,
    )


def _synthetic_result(
    command_id: str,
    *,
    status: str,
    exit_code: int | None,
    stderr: str,
) -> CommandResult:
    return CommandResult(
        command_id=command_id,
        argv=(),
        status=status,  # type: ignore[arg-type]
        exit_code=exit_code,
        duration_seconds=0.0,
        stdout_tail="",
        stderr_tail=stderr,
        report_paths=(),
    )
