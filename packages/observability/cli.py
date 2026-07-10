from __future__ import annotations

import argparse

from packages.observability.factory import (
    ObservabilityConfigurationError,
    resolve_observability_provider,
)
from packages.observability.models import load_observability_settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observability diagnostics.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("validate")
    smoke = subparsers.add_parser("smoke-test")
    smoke.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_observability_settings()
    if args.command == "status":
        print(_status_message(settings))
        return 0
    if args.command == "validate":
        if not settings.enabled:
            print("LangSmith tracing is disabled. Configuration is valid for local default use.")
            return 0
        try:
            resolve_observability_provider(settings)
        except ObservabilityConfigurationError as exc:
            print(str(exc))
            return 1
        print("LangSmith tracing configuration is valid.")
        return 0
    if args.command == "smoke-test":
        if args.dry_run:
            print("Dry-run smoke test: payload construction validated locally; no trace emitted.")
            return 0
        if not settings.enabled:
            print("Enable LangSmith tracing explicitly before running a smoke test.")
            return 1
        try:
            provider = resolve_observability_provider(settings)
        except ObservabilityConfigurationError as exc:
            print(str(exc))
            return 1
        root = provider.start_root_span(
            "observability_smoke_test",
            trace_id="smoke-test",
            inputs={"check": "status"},
            metadata={"surface": "cli"},
            tags=("smoke-test",),
        )
        root.finish(outputs={"status": "ok"})
        print("Smoke test emitted an observability trace.")
        return 0
    return 1


def _status_message(settings) -> str:
    status = "enabled" if settings.enabled else "disabled"
    project = settings.project or "<unset>"
    return (
        f"LangSmith tracing is {status}. "
        f"project={project} sampling_rate={settings.sampling_rate:.2f} "
        f"trace_inputs={settings.trace_inputs} trace_outputs={settings.trace_outputs}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
