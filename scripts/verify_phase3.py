from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from packages.evals.phase3_verification.runner import run_phase3_verification


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic Phase 3 end-to-end reliability closeout "
            "(strict mode by default)."
        )
    )
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help=(
            "Run a non-closeout diagnostic that skips PostgreSQL-dependent checks; "
            "this mode can never recommend ready_to_close."
        ),
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/phase3/verification"),
    )
    parser.add_argument("--report-root", type=Path, default=Path("reports/phase3"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mode = "offline_only" if args.offline_only else "strict"
    if args.offline_only:
        print("Phase 3 NON-CLOSEOUT DIAGNOSTIC (offline-only)")
    else:
        print("Phase 3 strict closeout verification")
    review = run_phase3_verification(
        mode=mode,
        artifact_root=args.artifact_root,
        report_root=args.report_root,
        repository_root=Path.cwd(),
    )
    for result in review.commands:
        exit_code = "none" if result.exit_code is None else str(result.exit_code)
        print(
            f"[{result.status}] {result.command_id}: "
            f"exit={exit_code} duration={result.duration_seconds:.3f}s"
        )
    print(f"Policy version: {review.policy_version or 'not available'}")
    print(f"Dataset versions: {review.dataset_versions}")
    print(f"Providers: {review.provider_configuration}")
    print(f"Recommendation: {review.recommendation}")
    return 0 if review.overall_status == "pass" and review.recommendation != "not_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
