from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from packages.evals.ci_quality_gate import validate_ci_environment


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that the AI quality gate environment is deterministic and offline."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path where the CI environment fingerprint JSON should be written.",
    )
    parser.add_argument(
        "--no-database",
        action="store_true",
        help="Skip the DATABASE_URL requirement.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        fingerprint = validate_ci_environment(
            os.environ,
            require_database=not args.no_database,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(fingerprint), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote CI environment fingerprint to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
