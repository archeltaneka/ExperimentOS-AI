from __future__ import annotations

import argparse

from packages.evals.run_ci_report import main as ci_report_main
from packages.evals.run_factuality import main as factuality_main
from packages.evals.run_prompt_experiment import main as prompt_experiment_main
from packages.evals.run_quality_policy import main as quality_policy_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ExperimentOS evaluation CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    factuality = subparsers.add_parser(
        "factuality",
        help="Run deterministic and optional judge-based factuality checks.",
    )
    factuality.add_argument("args", nargs=argparse.REMAINDER)
    prompt_experiment = subparsers.add_parser(
        "prompt-experiment",
        help="Validate, assign, run, and report prompt experiments.",
    )
    prompt_experiment.add_argument("args", nargs=argparse.REMAINDER)
    quality_policy = subparsers.add_parser(
        "quality-policy",
        help="Aggregate existing evaluation reports into the centralized quality policy.",
    )
    quality_policy.add_argument("args", nargs=argparse.REMAINDER)
    ci_report = subparsers.add_parser(
        "ci-report",
        help="Build and render CI evaluation reports from existing structured artifacts.",
    )
    ci_report.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(argv)
    if parsed.command == "factuality":
        return factuality_main(parsed.args)
    if parsed.command == "prompt-experiment":
        return prompt_experiment_main(parsed.args)
    if parsed.command == "quality-policy":
        return quality_policy_main(parsed.args)
    if parsed.command == "ci-report":
        return ci_report_main(parsed.args)
    parser.error(f"unknown command: {parsed.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
