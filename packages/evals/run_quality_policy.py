from __future__ import annotations

import argparse
from pathlib import Path

from packages.evals.policy.config import load_quality_policy
from packages.evals.policy.evaluator import PolicyEvaluator
from packages.evals.policy.report import quality_policy_report_to_json, render_quality_policy_report

DEFAULT_POLICY_PATH = Path("config/evaluation/quality_policy.yaml")
DEFAULT_REPORT_DIR = Path("reports")
DEFAULT_MARKDOWN_REPORT_PATH = Path("reports/phase3/quality_policy.md")
DEFAULT_JSON_REPORT_PATH = Path("reports/phase3/quality_policy.json")
QUALITY_POLICY_FAILURE_EXIT_CODE = 1
QUALITY_POLICY_INFRASTRUCTURE_EXIT_CODE = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the centralized Phase 3 quality policy from existing report artifacts."
        )
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
        help="Path to the quality policy YAML file.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Directory containing the evaluation reports consumed by the policy.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT_PATH,
        help="Markdown quality policy report output path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_REPORT_PATH,
        help="JSON quality policy report output path.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Alias for --warning-policy fail.",
    )
    parser.add_argument(
        "--warning-policy",
        choices=("allow", "fail"),
        default="allow",
        help="Whether warning-only policy outcomes should return a non-zero exit code.",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Always return success while preserving the report status.",
    )
    return parser.parse_args(argv)


def evaluate_quality_policy(args: argparse.Namespace):
    policy = load_quality_policy(args.policy)
    return PolicyEvaluator(policy=policy, report_dir=args.report_dir).evaluate()


def write_quality_policy_reports(args: argparse.Namespace):
    if args.output == DEFAULT_MARKDOWN_REPORT_PATH:
        args.output = args.report_dir / "phase3" / DEFAULT_MARKDOWN_REPORT_PATH.name
    if args.json_output == DEFAULT_JSON_REPORT_PATH:
        args.json_output = args.report_dir / "phase3" / DEFAULT_JSON_REPORT_PATH.name

    result = evaluate_quality_policy(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_quality_policy_report(result), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(quality_policy_report_to_json(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None, *, args: argparse.Namespace | None = None) -> int:
    parsed_args = args or parse_args(argv)
    try:
        result = write_quality_policy_reports(parsed_args)
    except Exception as exc:
        print(f"Quality policy evaluation error: {exc}")
        return QUALITY_POLICY_INFRASTRUCTURE_EXIT_CODE
    print(f"Wrote quality policy report to {parsed_args.output}")
    print(result.overall_status)
    if parsed_args.warn_only:
        return 0
    if result.overall_status == "fail":
        return QUALITY_POLICY_FAILURE_EXIT_CODE
    if result.overall_status == "warning" and _fail_on_warning(parsed_args):
        return QUALITY_POLICY_FAILURE_EXIT_CODE
    return 0


def _fail_on_warning(args: argparse.Namespace) -> bool:
    return bool(args.strict or args.warning_policy == "fail")


if __name__ == "__main__":
    raise SystemExit(main())
