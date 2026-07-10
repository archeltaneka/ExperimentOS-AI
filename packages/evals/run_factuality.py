from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.evals.agent_dataset import DEFAULT_AGENT_DATASET_PATH
from packages.evals.dataset import DEFAULT_DATASET_PATH
from packages.evals.factuality.models import FactualityPolicy
from packages.evals.factuality.report import factuality_report_to_json, render_factuality_report
from packages.evals.factuality.runner import build_factuality_report as build_runner_report
from packages.evals.run import build_evaluation_run as build_legacy_rag_run
from packages.evals.run import parse_args as parse_legacy_rag_args
from packages.evals.run import resolve_runtime_options as resolve_legacy_rag_runtime_options
from packages.evals.run_agent import build_evaluation_run as build_agent_run
from packages.evals.run_agent import parse_args as parse_agent_args
from packages.ingestion.load_experiment import run_async
from packages.observability.factory import resolve_observability_provider

DEFAULT_MARKDOWN_REPORT_PATH = Path("reports/phase3/factuality_report.md")
DEFAULT_JSON_REPORT_PATH = Path("reports/phase3/factuality_report.json")
DEFAULT_POLICY_PATH = Path("config/evaluation/factuality.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic and optional judge-based factuality checks."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the repository-owned QA evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--agent-dataset",
        type=Path,
        default=DEFAULT_AGENT_DATASET_PATH,
        help="Path to the deterministic agent workflow dataset JSON file.",
    )
    parser.add_argument(
        "--target",
        choices=("legacy_rag", "agent_workflow", "all"),
        default="all",
        help="Evaluation target to execute.",
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "judge"),
        default="offline",
        help="Offline mode runs deterministic checks only.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT_PATH,
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_REPORT_PATH,
        help="JSON report output path.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Optional directory where the Markdown and JSON reports should be written.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
        help="Path to the factuality policy configuration JSON file.",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Optional single case identifier to evaluate.",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Optional case category to filter.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved chunks.")
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "fake", "openai", "gemini", "huggingface", "ollama"),
        default=None,
        help="Embedding provider used by legacy_rag.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model name used by legacy_rag.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=("mock", "openai", "gemini", "ollama"),
        default=None,
        help="LLM provider used by legacy_rag.",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model name used by legacy_rag.",
    )
    parser.add_argument(
        "--judge-provider",
        choices=("none", "openai", "gemini"),
        default="none",
        help="Explicit judge provider for judge mode.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Explicit judge model for judge mode.",
    )
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="Return a non-zero exit code when the policy result is fail.",
    )
    return parser.parse_args(argv)


def build_factuality_report_from_args(args: argparse.Namespace):
    observability_provider = resolve_observability_provider()
    root_span = observability_provider.start_root_span(
        "evaluation.factuality",
        trace_id=f"evaluation.factuality:{args.target}",
        inputs={"target": args.target, "mode": args.mode},
        metadata={"surface": "evaluation.factuality"},
        tags=("evaluation", "factuality"),
    )
    with root_span.activate():
        return _build_factuality_report_from_args(args, observability_provider)


def _build_factuality_report_from_args(args: argparse.Namespace, observability_provider):
    legacy_run = None
    agent_run = None
    if args.target in {"legacy_rag", "all"}:
        legacy_args = resolve_legacy_rag_runtime_options(
            parse_legacy_rag_args(
                [
                    "--dataset",
                    str(args.dataset),
                    "--output",
                    str(args.output),
                    "--top-k",
                    str(args.top_k),
                    *(
                        ["--embedding-provider", args.embedding_provider]
                        if args.embedding_provider is not None
                        else []
                    ),
                    *(["--embedding-model", args.embedding_model] if args.embedding_model else []),
                    *(["--llm-provider", args.llm_provider] if args.llm_provider else []),
                    *(["--llm-model", args.llm_model] if args.llm_model else []),
                ]
            )
        )
        legacy_run = run_async(build_legacy_rag_run(legacy_args))
    if args.target in {"agent_workflow", "all"}:
        agent_args = parse_agent_args(
            [
                "--dataset",
                str(args.agent_dataset),
                "--output",
                str(args.output),
            ]
        )
        agent_run = build_agent_run(agent_args)
    report = _build_runner_report(args, legacy_run, agent_run)
    current_span = observability_provider.current_span()
    if current_span is not None:
        current_span.add_metadata(
            {
                "target": args.target,
                "mode": args.mode,
                "dataset": str(args.dataset),
                "agent_dataset": str(args.agent_dataset),
            }
        )
        current_span.finish(
            outputs={
                "status": report.policy_result.status,
                "case_count": len(report.case_results),
            }
        )
    return report


def build_factuality_report(args: argparse.Namespace):
    return build_factuality_report_from_args(args)


def _build_runner_report(args: argparse.Namespace, legacy_run, agent_run):
    return build_runner_report(
        target=args.target,
        mode=args.mode,
        legacy_run=legacy_run,
        agent_run=agent_run,
        dataset_identifier=str(args.dataset),
        agent_dataset_identifier=str(args.agent_dataset),
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        policy=_load_policy(args.policy),
        case_id=args.case_id,
        category=args.category,
    )


def write_factuality_reports(args: argparse.Namespace):
    if args.report_dir is not None:
        args.output = args.report_dir / DEFAULT_MARKDOWN_REPORT_PATH.name
        args.json_output = args.report_dir / DEFAULT_JSON_REPORT_PATH.name
    report = build_factuality_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_factuality_report(report), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(factuality_report_to_json(report), encoding="utf-8")
    return report


def _load_policy(path: Path) -> FactualityPolicy:
    if not path.is_file():
        return FactualityPolicy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("factuality policy must be a JSON object")
    return FactualityPolicy(
        critical_violations_allowed=int(payload.get("critical_violations_allowed", 0) or 0),
        unsupported_numerical_claims_allowed=int(
            payload.get("unsupported_numerical_claims_allowed", 0) or 0
        ),
        fabricated_financial_claims_allowed=int(
            payload.get("fabricated_financial_claims_allowed", 0) or 0
        ),
        fabricated_statistical_claims_allowed=int(
            payload.get("fabricated_statistical_claims_allowed", 0) or 0
        ),
        required_citation_coverage_minimum=float(
            payload.get("required_citation_coverage_minimum", 1.0) or 1.0
        ),
        max_unresolved_medium_severity_findings=int(
            payload.get("max_unresolved_medium_severity_findings", 0) or 0
        ),
        judge_metric_thresholds={
            str(key): float(value)
            for key, value in dict(payload.get("judge_metric_thresholds", {})).items()
        },
    )


def main(argv: list[str] | None = None, *, args: argparse.Namespace | None = None) -> int:
    parsed_args = args or parse_args(argv)
    report = write_factuality_reports(parsed_args)
    print(f"Wrote factuality report to {parsed_args.output}")
    print(report.policy_result.status)
    if parsed_args.fail_on_violation and report.policy_result.status == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
