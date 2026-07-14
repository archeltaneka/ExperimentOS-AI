from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from packages.evals.agent_dataset import DEFAULT_AGENT_DATASET_PATH, load_agent_evaluation_dataset
from packages.evals.ci_quality_gate import (
    CiEnvironmentFingerprint,
    CommandResult,
    GateResult,
    build_artifact_manifest,
    render_github_job_summary,
    validate_ci_environment,
    validate_policy_invariants,
    write_gate_result,
)
from packages.evals.dataset import load_evaluation_dataset
from packages.evals.policy.config import load_quality_policy
from packages.evals.prompt_experiments.loader import load_prompt_experiment_definition
from packages.evals.prompt_experiments.validation import validate_prompt_experiment_definition
from packages.evals.run_quality_policy import (
    QUALITY_POLICY_FAILURE_EXIT_CODE,
    QUALITY_POLICY_INFRASTRUCTURE_EXIT_CODE,
)

DEFAULT_POLICY_PATH = Path("config/evaluation/quality_policy.yaml")
DEFAULT_ARTIFACT_ROOT = Path("artifacts/ci/ai-quality")
DEFAULT_SEED_EXPERIMENT_DIR = Path("tests/fixtures/ci/exp-001-payment-recommendation")
DEFAULT_PROMPT_EXPERIMENT = "rag-answer-abstention-v1-v2"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 600

REQUIRED_REPORT_PATHS = (
    Path("evaluation.md"),
    Path("evaluation.json"),
    Path("agent_evaluation.md"),
    Path("agent_evaluation.json"),
    Path("agent_e2e_evaluation.md"),
    Path("agent_e2e_evaluation.json"),
    Path("phase3/prompt_regression.md"),
    Path("phase3/prompt_regression.json"),
    Path("phase3/factuality_report.md"),
    Path("phase3/factuality_report.json"),
    Path("phase3/ragas_report.md"),
    Path("phase3/ragas_report.json"),
    Path("phase3/deepeval_report.md"),
    Path("phase3/deepeval_report.json"),
    Path("phase3/quality_policy.md"),
    Path("phase3/quality_policy.json"),
    Path("phase3/ci_environment.json"),
    Path("phase3/ai_quality_gate.json"),
    Path("phase3/github_summary.md"),
)
OPTIONAL_REPORT_PATHS = (
    Path(f"phase3/prompt_experiments/{DEFAULT_PROMPT_EXPERIMENT}.md"),
    Path(f"phase3/prompt_experiments/{DEFAULT_PROMPT_EXPERIMENT}.json"),
)


@dataclass(frozen=True)
class EvaluationCommand:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the DB-backed offline AI quality gate and enforce the centralized policy."
    )
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--dataset", type=Path, default=Path("data/eval/ci_smoke_dataset.json"))
    parser.add_argument("--agent-dataset", type=Path, default=DEFAULT_AGENT_DATASET_PATH)
    parser.add_argument("--seed-experiment-dir", type=Path, default=DEFAULT_SEED_EXPERIMENT_DIR)
    parser.add_argument("--prompt-experiment", default=DEFAULT_PROMPT_EXPERIMENT)
    parser.add_argument("--artifact-name", default="ai-quality-gate-local")
    parser.add_argument(
        "--command-timeout-seconds",
        type=int,
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--policy-changed",
        choices=("true", "false"),
        default="false",
        help="Flag the summary when the policy file changed in this revision.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_root = args.artifact_root
    phase3_dir = artifact_root / "phase3"
    phase3_dir.mkdir(parents=True, exist_ok=True)

    gate_result_path = phase3_dir / "ai_quality_gate.json"
    summary_path = phase3_dir / "github_summary.md"
    manifest_path = phase3_dir / "artifact_manifest.json"
    fingerprint_path = phase3_dir / "ci_environment.json"
    command_results: list[CommandResult] = []

    try:
        fingerprint = validate_ci_environment(os.environ)
        fingerprint_path.write_text(
            json.dumps(asdict(fingerprint), indent=2) + "\n",
            encoding="utf-8",
        )
        policy = load_quality_policy(args.policy)
        validate_policy_invariants(policy)
        _validate_inputs(args)
        failed_command, exit_code, command_results = _run_commands(args)
        status, message = _status_from_result(failed_command, exit_code)
    except Exception as exc:
        fingerprint = _fallback_fingerprint()
        status = "infrastructure_fail"
        message = str(exc)
        exit_code = QUALITY_POLICY_INFRASTRUCTURE_EXIT_CODE

    manifest = build_artifact_manifest(
        artifact_root,
        required_paths=tuple(
            path
            for path in REQUIRED_REPORT_PATHS
            if path not in {Path("phase3/ai_quality_gate.json"), Path("phase3/github_summary.md")}
        ),
        optional_paths=OPTIONAL_REPORT_PATHS,
    )
    provisional_gate_result = GateResult(
        status=status,
        message=message,
        artifact_name=args.artifact_name,
        fingerprint=fingerprint,
        manifest=manifest,
        command_results=tuple(command_results),
    )
    write_gate_result(gate_result_path, provisional_gate_result)

    policy_payload = _load_json_if_exists(phase3_dir / "quality_policy.json")
    summary = render_github_job_summary(
        policy_payload,
        fingerprint=fingerprint,
        manifest=manifest,
        artifact_name=args.artifact_name,
        policy_changed=args.policy_changed == "true",
        infrastructure_error=message if status == "infrastructure_fail" else None,
    )
    summary_path.write_text(summary, encoding="utf-8")
    manifest = build_artifact_manifest(
        artifact_root,
        required_paths=REQUIRED_REPORT_PATHS,
        optional_paths=OPTIONAL_REPORT_PATHS,
    )
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2) + "\n", encoding="utf-8")
    gate_result = GateResult(
        status=status,
        message=message,
        artifact_name=args.artifact_name,
        fingerprint=fingerprint,
        manifest=manifest,
        command_results=tuple(command_results),
    )
    write_gate_result(gate_result_path, gate_result)
    summary = render_github_job_summary(
        policy_payload,
        fingerprint=fingerprint,
        manifest=manifest,
        artifact_name=args.artifact_name,
        policy_changed=args.policy_changed == "true",
        infrastructure_error=message if status == "infrastructure_fail" else None,
    )
    summary_path.write_text(summary, encoding="utf-8")
    print(summary)
    return exit_code


def _validate_inputs(args: argparse.Namespace) -> None:
    questions = load_evaluation_dataset(args.dataset)
    load_agent_evaluation_dataset(args.agent_dataset)
    definition = load_prompt_experiment_definition(args.prompt_experiment)
    validate_prompt_experiment_definition(definition)
    if not questions:
        raise ValueError(f"no evaluation questions found in {args.dataset}")
    if not args.seed_experiment_dir.is_dir():
        raise ValueError(f"seed experiment directory not found: {args.seed_experiment_dir}")


def _run_commands(args: argparse.Namespace) -> tuple[str | None, int, list[CommandResult]]:
    repo_root = Path(__file__).resolve().parent.parent
    commands = _build_commands(args)
    results: list[CommandResult] = []
    for command in commands:
        print(f"Running {command.name}: {' '.join(command.argv)}")
        completed = subprocess.run(
            command.argv,
            cwd=repo_root,
            timeout=command.timeout_seconds,
            check=False,
        )
        results.append(
            CommandResult(
                name=command.name,
                command=" ".join(command.argv),
                exit_code=completed.returncode,
            )
        )
        if completed.returncode != 0:
            return command.name, completed.returncode, results
    return None, 0, results


def _build_commands(args: argparse.Namespace) -> tuple[EvaluationCommand, ...]:
    phase3_dir = args.artifact_root / "phase3"
    python = sys.executable
    timeout = args.command_timeout_seconds
    return (
        EvaluationCommand(
            name="seed_integration_fixture",
            argv=(
                python,
                "-m",
                "packages.ingestion.load_experiment",
                "--experiment-dir",
                str(args.seed_experiment_dir),
                "--embedding-provider",
                "fake",
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="validate_prompt_registry",
            argv=(python, "-m", "packages.llm.prompt_registry_cli", "validate"),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="validate_prompt_experiment",
            argv=(
                python,
                "-m",
                "packages.evals.run_prompt_experiment",
                "validate",
                "--experiment",
                args.prompt_experiment,
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="custom_rag_evaluation",
            argv=(
                python,
                "-m",
                "packages.evals.run",
                "--dataset",
                str(args.dataset),
                "--output",
                str(args.artifact_root / "evaluation.md"),
                "--json-output",
                str(args.artifact_root / "evaluation.json"),
                "--embedding-provider",
                "fake",
                "--llm-provider",
                "mock",
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="custom_agent_evaluation",
            argv=(
                python,
                "-m",
                "packages.evals.run_agent",
                "--dataset",
                str(args.agent_dataset),
                "--output",
                str(args.artifact_root / "agent_evaluation.md"),
                "--json-output",
                str(args.artifact_root / "agent_evaluation.json"),
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="end_to_end_evaluation",
            argv=(
                python,
                "-m",
                "packages.evals.run_agent_e2e",
                "--output",
                str(args.artifact_root / "agent_e2e_evaluation.md"),
                "--json-output",
                str(args.artifact_root / "agent_e2e_evaluation.json"),
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="prompt_regression",
            argv=(
                python,
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
                str(args.dataset),
                "--embedding-provider",
                "fake",
                "--llm-provider",
                "mock",
                "--output",
                str(phase3_dir / "prompt_regression.md"),
                "--json-output",
                str(phase3_dir / "prompt_regression.json"),
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="factuality",
            argv=(
                python,
                "-m",
                "packages.evals.run_factuality",
                "--dataset",
                str(args.dataset),
                "--agent-dataset",
                str(args.agent_dataset),
                "--target",
                "all",
                "--mode",
                "offline",
                "--embedding-provider",
                "fake",
                "--llm-provider",
                "mock",
                "--output",
                str(phase3_dir / "factuality_report.md"),
                "--json-output",
                str(phase3_dir / "factuality_report.json"),
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="prompt_experiment_sample",
            argv=(
                python,
                "-m",
                "packages.evals.run_prompt_experiment",
                "run",
                "--experiment",
                args.prompt_experiment,
                "--mode",
                "offline",
                "--dataset",
                str(args.dataset),
                "--report-dir",
                str(phase3_dir / "prompt_experiments"),
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="ragas_offline",
            argv=(
                python,
                "-m",
                "packages.evals.run_ragas",
                "--dataset",
                str(args.dataset),
                "--output",
                str(phase3_dir / "ragas_report.md"),
                "--json-output",
                str(phase3_dir / "ragas_report.json"),
                "--embedding-provider",
                "fake",
                "--llm-provider",
                "mock",
                "--judge-llm-provider",
                "none",
                "--judge-embedding-provider",
                "none",
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="deepeval_offline",
            argv=(
                python,
                "-m",
                "packages.evals.run_deepeval",
                "--mode",
                "offline",
                "--dataset",
                str(args.dataset),
                "--agent-dataset",
                str(args.agent_dataset),
                "--output",
                str(phase3_dir / "deepeval_report.md"),
                "--json-output",
                str(phase3_dir / "deepeval_report.json"),
                "--embedding-provider",
                "fake",
                "--llm-provider",
                "mock",
                "--judge-provider",
                "none",
            ),
            timeout_seconds=timeout,
        ),
        EvaluationCommand(
            name="quality_policy",
            argv=(
                python,
                "-m",
                "packages.evals.run_quality_policy",
                "--policy",
                str(args.policy),
                "--report-dir",
                str(args.artifact_root),
                "--output",
                str(phase3_dir / "quality_policy.md"),
                "--json-output",
                str(phase3_dir / "quality_policy.json"),
            ),
            timeout_seconds=timeout,
        ),
    )


def _status_from_result(command_name: str | None, exit_code: int) -> tuple[str, str]:
    if exit_code == 0:
        return "pass", "All required evaluation suites satisfied the centralized quality policy."
    if command_name == "quality_policy" and exit_code == QUALITY_POLICY_FAILURE_EXIT_CODE:
        return "quality_fail", "Blocking quality policy violations were detected."
    if exit_code == QUALITY_POLICY_INFRASTRUCTURE_EXIT_CODE:
        return "infrastructure_fail", "The quality policy evaluation encountered an internal error."
    if command_name is None:
        return "infrastructure_fail", "The AI quality gate exited unexpectedly."
    return (
        "infrastructure_fail",
        f"The `{command_name}` command exited with status {exit_code}.",
    )


def _fallback_fingerprint() -> CiEnvironmentFingerprint:
    return CiEnvironmentFingerprint(
        ask_mode=os.environ.get("ASK_MODE", ""),
        embedding_provider=os.environ.get("EMBEDDING_PROVIDER", ""),
        llm_provider=os.environ.get("LLM_PROVIDER", ""),
        prompt_experiments_enabled=False,
        external_judges_enabled=False,
        live_provider_configured=False,
        observability_export_enabled=False,
    )


def _load_json_if_exists(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
