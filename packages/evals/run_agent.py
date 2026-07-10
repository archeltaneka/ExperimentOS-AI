from __future__ import annotations

import argparse
from pathlib import Path

from packages.evals.agent_dataset import (
    DEFAULT_AGENT_DATASET_PATH,
    load_agent_evaluation_dataset,
)
from packages.evals.agent_evaluator import (
    AgentWorkflowEvaluator,
    build_default_agent_workflow_service,
)
from packages.evals.agent_report import render_agent_evaluation_report
from packages.observability.factory import resolve_observability_provider

DEFAULT_AGENT_REPORT_PATH = Path("reports/agent_evaluation.md")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic agent workflow evaluation harness."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_AGENT_DATASET_PATH,
        help="Path to the agent evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_AGENT_REPORT_PATH,
        help="Path where the agent evaluation Markdown report should be written.",
    )
    return parser.parse_args(argv)


def run_evaluation(args: argparse.Namespace) -> str:
    result = build_evaluation_run(args)
    report = render_agent_evaluation_report(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


def build_evaluation_run(args: argparse.Namespace):
    observability_provider = resolve_observability_provider()
    root_span = observability_provider.start_root_span(
        "evaluation.agent",
        trace_id=f"evaluation.agent:{args.dataset}",
        inputs={"dataset": str(args.dataset)},
        metadata={"surface": "evaluation.agent"},
        tags=("evaluation", "agent"),
    )
    with root_span.activate():
        return _build_evaluation_run(args, observability_provider)


def _build_evaluation_run(args: argparse.Namespace, observability_provider):
    cases = load_agent_evaluation_dataset(args.dataset)
    evaluator = AgentWorkflowEvaluator(
        workflow_service=build_default_agent_workflow_service(observability_provider),
        cases=cases,
    )
    result = evaluator.evaluate()
    current_span = observability_provider.current_span()
    if current_span is not None:
        current_span.add_metadata(
            {
                "sample_count": result.summary.sample_count,
                "workflow_success_rate": result.summary.workflow_success_rate,
                "surface": "evaluation.agent",
            }
        )
        current_span.finish(
            outputs={
                "status": "completed",
                "sample_count": result.summary.sample_count,
                "fail_count": result.summary.fail_count,
            }
        )
    return result


def main() -> None:
    args = parse_args()
    report = run_evaluation(args)
    print(f"Wrote agent evaluation report to {args.output}")
    print(report.splitlines()[0])


if __name__ == "__main__":
    main()
