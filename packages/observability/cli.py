from __future__ import annotations

import argparse
import importlib
import json
from urllib.parse import urlparse

from packages.observability.factory import (
    ObservabilityConfigurationError,
    resolve_observability_provider,
)
from packages.observability.models import (
    ObservabilitySettings,
    OpenTelemetrySettings,
    ProviderSettings,
    load_observability_settings,
)
from packages.observability.redaction import redact_payload

ProviderName = str
_PROVIDERS = ("all", "langsmith", "phoenix", "opentelemetry")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observability diagnostics.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("status", "validate", "dry-run", "smoke-test"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument(
            "--provider",
            choices=_PROVIDERS,
            default="all",
            help="Provider to inspect. Defaults to all configured sinks.",
        )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_observability_settings()

    if args.command == "status":
        print(_status_message(settings, provider=args.provider))
        return 0
    if args.command == "validate":
        return _run_validate(settings, provider=args.provider)
    if args.command == "dry-run":
        return _run_dry_run(settings, provider=args.provider)
    if args.command == "smoke-test":
        return _run_smoke_test(settings, provider=args.provider)
    return 1


def _run_validate(settings: ObservabilitySettings, *, provider: ProviderName) -> int:
    selected = _select_settings(settings, provider=provider)
    enabled = _enabled_provider_names(selected, provider=provider)
    if not enabled:
        print(_disabled_validation_message(provider))
        return 0
    try:
        _validate_selected_settings(selected, provider=provider)
    except ObservabilityConfigurationError as exc:
        print(str(exc))
        return 1
    print(f"{_provider_label(provider)} configuration is valid.")
    return 0


def _run_dry_run(settings: ObservabilitySettings, *, provider: ProviderName) -> int:
    selected = _select_settings(settings, provider=provider)
    enabled = _enabled_provider_names(selected, provider=provider)
    if enabled:
        try:
            _validate_selected_settings(selected, provider=provider)
        except ObservabilityConfigurationError as exc:
            print(str(exc))
            return 1

    sections: list[str] = [
        "Observability dry-run",
        "source_of_truth=ExperimentOS internal traces/metrics/reports",
    ]
    for provider_name, provider_settings in _iter_selected_provider_settings(
        selected,
        provider=provider,
    ):
        payloads = _dry_run_payloads(provider_settings)
        sections.extend(
            [
                (
                    f"{provider_name}: enabled={provider_settings.enabled} "
                    f"available={_dependency_available(provider_name)} "
                    f"endpoint_type={_endpoint_type(provider_name, provider_settings.endpoint)} "
                    f"project={_project_name(provider_name, provider_settings)} "
                    f"sampling_rate={provider_settings.sampling_rate:.2f} "
                    f"redaction={provider_settings.redact_sensitive_data}"
                ),
                (
                    f"{provider_name}: instrumentation="
                    f"{_instrumentation_status(provider_name)}"
                ),
                f"{provider_name}: input={json.dumps(payloads['input'], sort_keys=True)}",
                f"{provider_name}: output={json.dumps(payloads['output'], sort_keys=True)}",
            ]
        )
    print("\n".join(sections))
    return 0


def _run_smoke_test(settings: ObservabilitySettings, *, provider: ProviderName) -> int:
    selected = _select_settings(settings, provider=provider)
    enabled = _enabled_provider_names(selected, provider=provider)
    if not enabled:
        print(f"Enable {_provider_label(provider)} tracing explicitly before running a smoke test.")
        return 1
    try:
        _validate_selected_settings(selected, provider=provider)
        resolved_provider = resolve_observability_provider(selected)
    except ObservabilityConfigurationError as exc:
        print(str(exc))
        return 1

    root = resolved_provider.start_root_span(
        "observability_smoke_test",
        trace_id="observability-smoke-test",
        inputs={"check": "status"},
        metadata={
            "surface": "cli",
            "execution_mode": "diagnostic",
            "provider_scope": provider,
        },
        tags=("smoke-test", provider),
    )
    root.finish(outputs={"status": "ok"})
    flushed = resolved_provider.force_flush()
    resolved_provider.shutdown()
    print(
        f"Smoke test emitted an observability trace for {_provider_label(provider)}. "
        f"force_flush={flushed}"
    )
    return 0


def _disabled_validation_message(provider: ProviderName) -> str:
    if provider == "all":
        return (
            "All external observability sinks are disabled. "
            "Configuration is valid for local default use."
        )
    return (
        f"{_provider_label(provider)} tracing is disabled. "
        "Configuration is valid for local default use."
    )


def _select_settings(
    settings: ObservabilitySettings,
    *,
    provider: ProviderName,
) -> ObservabilitySettings:
    if provider == "langsmith":
        return ObservabilitySettings(langsmith=settings.langsmith)
    if provider == "phoenix":
        return ObservabilitySettings(phoenix=settings.phoenix)
    if provider == "opentelemetry":
        return ObservabilitySettings(otel=settings.otel)
    return settings


def _iter_selected_provider_settings(
    settings: ObservabilitySettings,
    *,
    provider: ProviderName,
) -> list[tuple[str, ProviderSettings]]:
    if provider == "langsmith":
        return [("langsmith", settings.langsmith)]
    if provider == "phoenix":
        return [("phoenix", settings.phoenix)]
    if provider == "opentelemetry":
        return [("opentelemetry", settings.otel)]
    return [
        ("langsmith", settings.langsmith),
        ("opentelemetry", settings.otel),
        ("phoenix", settings.phoenix),
    ]


def _enabled_provider_names(
    settings: ObservabilitySettings,
    *,
    provider: ProviderName,
) -> list[str]:
    return [
        provider_name
        for provider_name, provider_settings in _iter_selected_provider_settings(
            settings,
            provider=provider,
        )
        if provider_settings.enabled
    ]


def _validate_selected_settings(settings: ObservabilitySettings, *, provider: ProviderName) -> None:
    errors: list[str] = []
    for provider_name, provider_settings in _iter_selected_provider_settings(
        settings,
        provider=provider,
    ):
        if not provider_settings.enabled:
            continue
        errors.extend(provider_settings.validate())
        _require_provider_dependency(provider_name)
    if errors:
        raise ObservabilityConfigurationError(" ".join(errors))


def _require_provider_dependency(provider_name: str) -> None:
    module_names = {
        "langsmith": ("langsmith", "langsmith.run_trees"),
        "opentelemetry": (
            "opentelemetry.trace",
            "opentelemetry.sdk.trace",
            "opentelemetry.sdk.metrics",
        ),
        "phoenix": ("phoenix.otel", "opentelemetry.trace"),
    }[provider_name]
    try:
        for module_name in module_names:
            importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ObservabilityConfigurationError(
            f"{_provider_label(provider_name)} tracing is enabled but the optional "
            "dependencies are not installed."
        ) from exc


def _dependency_available(provider_name: str) -> bool:
    module_names = {
        "langsmith": ("langsmith", "langsmith.run_trees"),
        "opentelemetry": (
            "opentelemetry.trace",
            "opentelemetry.sdk.trace",
            "opentelemetry.sdk.metrics",
        ),
        "phoenix": ("phoenix.otel", "opentelemetry.trace"),
    }[provider_name]
    try:
        for module_name in module_names:
            importlib.import_module(module_name)
    except ModuleNotFoundError:
        return False
    return True


def _endpoint_type(provider_name: str, endpoint: str | None) -> str:
    if provider_name == "langsmith" and not endpoint:
        return "managed-default"
    if not endpoint:
        return "unset"
    parsed = urlparse(endpoint)
    hostname = (parsed.hostname or "").lower()
    if hostname in {"127.0.0.1", "localhost", "0.0.0.0"}:
        return "local"
    if provider_name == "phoenix" and "arize" in hostname:
        return "phoenix-cloud"
    return "remote"


def _project_name(provider_name: str, settings: ProviderSettings) -> str:
    if provider_name == "opentelemetry" and isinstance(settings, OpenTelemetrySettings):
        return settings.service_name
    project = getattr(settings, "project", None)
    if project:
        return str(project)
    return "<unset>" if provider_name == "langsmith" else "experimentos-local"


def _provider_label(provider: ProviderName) -> str:
    if provider == "all":
        return "All selected observability sinks"
    if provider == "langsmith":
        return "LangSmith"
    if provider == "opentelemetry":
        return "OpenTelemetry"
    return "Phoenix"


def _instrumentation_status(provider_name: str) -> str:
    if provider_name == "opentelemetry":
        return "manual ExperimentOS spans plus optional FastAPI transport spans"
    if provider_name == "phoenix":
        return "manual ExperimentOS spans only; auto-instrumentation disabled"
    return "manual ExperimentOS spans only"


def _dry_run_payloads(settings: ProviderSettings) -> dict[str, object]:
    sample_inputs = redact_payload(
        {
            "question": "Should we roll out the payment recommendation experiment?",
            "prompt": "private prompt body",
            "retrieved_chunks": [
                {"chunk_text": "private evidence", "document_id": "doc-1"},
                {"chunk_text": "private evidence 2", "document_id": "doc-2"},
            ],
            "authorization": "Bearer secret",
            "request_id": "req-dry-run",
        },
        settings=settings,
    )
    sample_outputs = redact_payload(
        {
            "answer": "private answer body",
            "status": "completed",
            "citation_count": 2,
        },
        settings=settings,
        is_output=True,
    )
    return {
        "input": sample_inputs,
        "output": sample_outputs,
    }


def _status_message(settings: ObservabilitySettings, *, provider: ProviderName) -> str:
    lines = [
        "Observability status",
        "source_of_truth=ExperimentOS internal traces/metrics/reports",
    ]
    for provider_name, provider_settings in _iter_selected_provider_settings(
        settings,
        provider=provider,
    ):
        detail_lines = [
            (
                f"{provider_name}: enabled={provider_settings.enabled} "
                f"available={_dependency_available(provider_name)} "
                f"endpoint_type={_endpoint_type(provider_name, provider_settings.endpoint)} "
                f"project={_project_name(provider_name, provider_settings)} "
                f"environment={provider_settings.environment} "
                f"sampling_rate={provider_settings.sampling_rate:.2f}"
            ),
            (
                f"{provider_name}: trace_inputs={provider_settings.trace_inputs} "
                f"trace_outputs={provider_settings.trace_outputs} "
                f"redaction={provider_settings.redact_sensitive_data} "
                f"instrumentation={_instrumentation_status(provider_name)}"
            ),
        ]
        if provider_name == "opentelemetry" and isinstance(
            provider_settings, OpenTelemetrySettings
        ):
            detail_lines.extend(
                [
                    (
                        f"{provider_name}: service_name={provider_settings.service_name} "
                        f"service_version={provider_settings.service_version} "
                        f"exporter_type={provider_settings.exporter_type} "
                        f"protocol={provider_settings.protocol}"
                    ),
                    (
                        f"{provider_name}: trace_enabled={provider_settings.trace_enabled} "
                        f"metrics_enabled={provider_settings.metrics_enabled} "
                        f"propagation={provider_settings.propagation_enabled} "
                        f"batch_export={provider_settings.batch_export}"
                    ),
                    (
                        f"{provider_name}: processor_type="
                        f"{'BatchSpanProcessor' if provider_settings.batch_export else 'SimpleSpanProcessor'} "  # noqa: E501
                        f"metric_reader_type={_metric_reader_type(provider_settings)} "
                        f"init_state={_otel_init_state(provider_settings)}"
                    ),
                ]
            )
        lines.extend(detail_lines)
    return "\n".join(lines)


def _metric_reader_type(settings: OpenTelemetrySettings) -> str:
    exporter_type = settings.exporter_type
    if exporter_type == "in_memory":
        return "InMemoryMetricReader"
    if exporter_type in {"otlp", "otlp_http", "console"}:
        return "PeriodicExportingMetricReader"
    return "none"


def _otel_init_state(settings: OpenTelemetrySettings) -> str:
    if not settings.enabled:
        return "disabled"
    if (
        settings.exporter_type == "none"
        and not settings.trace_enabled
        and not settings.metrics_enabled
    ):
        return "invalid"
    return "configured"


if __name__ == "__main__":
    raise SystemExit(main())
