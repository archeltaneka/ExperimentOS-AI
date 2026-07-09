from __future__ import annotations

import argparse
from pathlib import Path

from packages.evals.agent_e2e import AgentE2EEvaluator, build_default_agent_e2e_cases
from packages.evals.agent_e2e_report import render_agent_e2e_report

DEFAULT_AGENT_E2E_REPORT_PATH = Path("reports/agent_e2e_evaluation.md")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic /ask API end-to-end evaluation harness."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_AGENT_E2E_REPORT_PATH,
        help="Path where the agent E2E Markdown report should be written.",
    )
    return parser.parse_args(argv)


def run_evaluation(args: argparse.Namespace) -> str:
    result = build_evaluation_run(args)
    report = render_agent_e2e_report(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


def build_evaluation_run(args: argparse.Namespace):
    evaluator = AgentE2EEvaluator(cases=build_default_agent_e2e_cases())
    return evaluator.evaluate()


def main() -> None:
    args = parse_args()
    report = run_evaluation(args)
    print(f"Wrote agent E2E evaluation report to {args.output}")
    print(report.splitlines()[0])


if __name__ == "__main__":
    main()
