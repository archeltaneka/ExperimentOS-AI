from __future__ import annotations

import subprocess
import time
from collections.abc import Collection, Mapping
from pathlib import Path

from packages.evals.dataset import DEFAULT_DATASET_PATH, load_evaluation_dataset
from packages.evals.phase3_verification.models import (
    CommandResult,
    VerificationCommand,
    VerificationMode,
)

_OUTPUT_TAIL_LIMIT = 8_000
_PROMPT_EXPERIMENT_ID = "rag-answer-abstention-v1-v2"
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
