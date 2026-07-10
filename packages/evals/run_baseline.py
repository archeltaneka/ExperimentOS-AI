from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from packages.evals.agent_dataset import DEFAULT_AGENT_DATASET_PATH
from packages.evals.agent_e2e_report import render_agent_e2e_report
from packages.evals.agent_report import render_agent_evaluation_report
from packages.evals.baseline import (
    build_phase3_baseline_report,
    render_phase3_baseline_report,
)
from packages.evals.dataset import DEFAULT_DATASET_PATH
from packages.evals.factuality.report import factuality_report_to_json, render_factuality_report
from packages.evals.factuality.runner import (
    build_factuality_report as build_factuality_runner_report,
)
from packages.evals.report import render_evaluation_report
from packages.evals.run import build_evaluation_run as build_qa_evaluation_run
from packages.evals.run import parse_args as parse_qa_args
from packages.evals.run_agent import build_evaluation_run as build_agent_evaluation_run
from packages.evals.run_agent import parse_args as parse_agent_args
from packages.evals.run_agent_e2e import build_evaluation_run as build_agent_e2e_evaluation_run
from packages.evals.run_agent_e2e import parse_args as parse_agent_e2e_args
from packages.evals.run_factuality import (
    DEFAULT_JSON_REPORT_PATH as FACTUALITY_JSON_REPORT_PATH,
)
from packages.evals.run_factuality import (
    DEFAULT_MARKDOWN_REPORT_PATH as FACTUALITY_REPORT_PATH,
)
from packages.evals.run_factuality import (
    parse_args as parse_factuality_args,
)
from packages.ingestion.load_experiment import run_async

DEFAULT_BASELINE_REPORT_PATH = Path("reports/phase3/baseline_report.md")
DEFAULT_RAG_REPORT_PATH = Path("reports/evaluation.md")
DEFAULT_AGENT_REPORT_PATH = Path("reports/agent_evaluation.md")
DEFAULT_AGENT_E2E_REPORT_PATH = Path("reports/agent_e2e_evaluation.md")
DEFAULT_FACTUALITY_REPORT_PATH = FACTUALITY_REPORT_PATH
DEFAULT_FACTUALITY_JSON_REPORT_PATH = FACTUALITY_JSON_REPORT_PATH


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase 3 reliability baseline over existing local evaluation flows."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_BASELINE_REPORT_PATH,
        help="Path where the aggregate Phase 3 baseline Markdown report should be written.",
    )
    parser.add_argument(
        "--rag-output",
        type=Path,
        default=DEFAULT_RAG_REPORT_PATH,
        help="Path where the RAG evaluation report should be written.",
    )
    parser.add_argument(
        "--agent-output",
        type=Path,
        default=DEFAULT_AGENT_REPORT_PATH,
        help="Path where the agent workflow evaluation report should be written.",
    )
    parser.add_argument(
        "--agent-e2e-output",
        type=Path,
        default=DEFAULT_AGENT_E2E_REPORT_PATH,
        help="Path where the agent workflow E2E evaluation report should be written.",
    )
    parser.add_argument(
        "--factuality-output",
        type=Path,
        default=DEFAULT_FACTUALITY_REPORT_PATH,
        help="Path where the factuality evaluation report should be written.",
    )
    parser.add_argument(
        "--factuality-json-output",
        type=Path,
        default=DEFAULT_FACTUALITY_JSON_REPORT_PATH,
        help="Path where the factuality evaluation JSON report should be written.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the QA evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--agent-dataset",
        type=Path,
        default=DEFAULT_AGENT_DATASET_PATH,
        help="Path to the agent evaluation dataset JSON file.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve.")
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "fake", "openai", "gemini", "huggingface", "ollama"),
        default=None,
        help="Embedding provider for the QA baseline evaluation.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model name for the QA baseline evaluation.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=("mock", "openai", "gemini", "ollama"),
        default=None,
        help="LLM provider for the QA baseline evaluation.",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model name for the QA baseline evaluation.",
    )
    return parser.parse_args(argv)


async def run_phase3_baseline(args: argparse.Namespace) -> str:
    qa_args = parse_qa_args(
        [
            "--dataset",
            str(args.dataset),
            "--output",
            str(args.rag_output),
            "--top-k",
            str(args.top_k),
            *(
                ["--embedding-provider", args.embedding_provider]
                if args.embedding_provider is not None
                else []
            ),
            *(["--embedding-model", args.embedding_model] if args.embedding_model else []),
            *(["--llm-provider", args.llm_provider] if args.llm_provider is not None else []),
            *(["--llm-model", args.llm_model] if args.llm_model else []),
        ]
    )
    agent_args = parse_agent_args(
        [
            "--dataset",
            str(args.agent_dataset),
            "--output",
            str(args.agent_output),
        ]
    )
    agent_e2e_args = parse_agent_e2e_args(
        [
            "--output",
            str(args.agent_e2e_output),
        ]
    )
    factuality_args = parse_factuality_args(
        [
            "--dataset",
            str(args.dataset),
            "--agent-dataset",
            str(args.agent_dataset),
            "--target",
            "all",
            "--mode",
            "offline",
            "--output",
            str(args.factuality_output),
            "--json-output",
            str(args.factuality_json_output),
            "--top-k",
            str(args.top_k),
            *(
                ["--embedding-provider", args.embedding_provider]
                if args.embedding_provider is not None
                else []
            ),
            *(["--embedding-model", args.embedding_model] if args.embedding_model else []),
            *(["--llm-provider", args.llm_provider] if args.llm_provider is not None else []),
            *(["--llm-model", args.llm_model] if args.llm_model else []),
        ]
    )

    qa_run = await _build_qa_run(qa_args)
    qa_report = render_evaluation_report(qa_run)
    _write_report(args.rag_output, qa_report)

    agent_run = _build_agent_run(agent_args)
    agent_report = render_agent_evaluation_report(agent_run)
    _write_report(args.agent_output, agent_report)

    agent_e2e_run = _build_agent_e2e_run(agent_e2e_args)
    agent_e2e_report = render_agent_e2e_report(agent_e2e_run)
    _write_report(args.agent_e2e_output, agent_e2e_report)
    factuality_run = _build_factuality_run(factuality_args, qa_run, agent_run)
    factuality_report = render_factuality_report(factuality_run)
    _write_report(args.factuality_output, factuality_report)
    _write_report(args.factuality_json_output, factuality_report_to_json(factuality_run))

    qa_command = _qa_command(qa_args)
    agent_command = _agent_command(agent_args)
    agent_e2e_command = _agent_e2e_command(agent_e2e_args)
    factuality_command = _factuality_command(factuality_args)
    baseline = build_phase3_baseline_report(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        qa_run=qa_run,
        qa_command=qa_command,
        qa_dataset=str(qa_args.dataset),
        qa_report_path=str(args.rag_output),
        agent_run=agent_run,
        agent_command=agent_command,
        agent_dataset=str(agent_args.dataset),
        agent_report_path=str(args.agent_output),
        agent_e2e_run=agent_e2e_run,
        agent_e2e_command=agent_e2e_command,
        agent_e2e_report_path=str(args.agent_e2e_output),
        factuality_report=factuality_run,
        factuality_command=factuality_command,
        factuality_report_path=str(args.factuality_output),
    )
    report = render_phase3_baseline_report(baseline)
    _write_report(args.output, report)
    return report


async def _build_qa_run(args: argparse.Namespace):
    return await build_qa_evaluation_run(args)


def _build_agent_run(args: argparse.Namespace):
    return build_agent_evaluation_run(args)


def _build_agent_e2e_run(args: argparse.Namespace):
    return build_agent_e2e_evaluation_run(args)


def _build_factuality_run(args: argparse.Namespace, qa_run, agent_run):
    return build_factuality_runner_report(
        target=args.target,
        mode=args.mode,
        legacy_run=qa_run,
        agent_run=agent_run,
        dataset_identifier=str(args.dataset),
        agent_dataset_identifier=str(args.agent_dataset),
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        case_id=args.case_id,
        category=args.category,
    )


def _write_report(path: Path, report: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def _qa_command(args: argparse.Namespace) -> str:
    parts = [
        "uv run python -m packages.evals.run",
        f"--dataset {args.dataset}",
        f"--output {args.output}",
        f"--top-k {args.top_k}",
    ]
    if args.embedding_provider is not None:
        parts.append(f"--embedding-provider {args.embedding_provider}")
    if args.embedding_model:
        parts.append(f"--embedding-model {args.embedding_model}")
    if args.llm_provider is not None:
        parts.append(f"--llm-provider {args.llm_provider}")
    if args.llm_model:
        parts.append(f"--llm-model {args.llm_model}")
    return " ".join(parts)


def _agent_command(args: argparse.Namespace) -> str:
    return (
        "uv run python -m packages.evals.run_agent "
        f"--dataset {args.dataset} --output {args.output}"
    )


def _agent_e2e_command(args: argparse.Namespace) -> str:
    return f"uv run python -m packages.evals.run_agent_e2e --output {args.output}"


def _factuality_command(args: argparse.Namespace) -> str:
    parts = [
        "uv run python -m packages.evals.run_factuality",
        f"--dataset {args.dataset}",
        f"--agent-dataset {args.agent_dataset}",
        f"--target {args.target}",
        f"--mode {args.mode}",
        f"--output {args.output}",
        f"--json-output {args.json_output}",
        f"--top-k {args.top_k}",
    ]
    if args.embedding_provider is not None:
        parts.append(f"--embedding-provider {args.embedding_provider}")
    if args.embedding_model:
        parts.append(f"--embedding-model {args.embedding_model}")
    if args.llm_provider is not None:
        parts.append(f"--llm-provider {args.llm_provider}")
    if args.llm_model:
        parts.append(f"--llm-model {args.llm_model}")
    return " ".join(parts)


def main() -> None:
    args = parse_args()
    report = run_async(run_phase3_baseline(args))
    print(f"Wrote Phase 3 baseline report to {args.output}")
    print(report.splitlines()[0])


if __name__ == "__main__":
    main()
