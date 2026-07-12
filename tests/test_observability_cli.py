from __future__ import annotations

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import (
    ObservabilitySettings,
    OpenTelemetrySettings,
    PhoenixSettings,
)


class _LifecycleProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(PhoenixSettings(enabled=True, endpoint="http://127.0.0.1:6006"))
        self.flush_calls = 0
        self.shutdown_calls = 0

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        return None

    def force_flush(self) -> bool:
        self.flush_calls += 1
        return True

    def shutdown(self) -> bool:
        self.shutdown_calls += 1
        return True


def test_cli_status_reports_phoenix_manual_span_mode(capsys, monkeypatch) -> None:
    from packages.observability import cli

    settings = ObservabilitySettings(
        phoenix=PhoenixSettings(
            enabled=True,
            endpoint="http://127.0.0.1:6006/v1/traces",
            project="experimentos-local",
            sampling_rate=0.5,
        )
    )
    monkeypatch.setattr(cli, "load_observability_settings", lambda: settings)
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: object())

    assert cli.main(["status", "--provider", "phoenix"]) == 0

    output = capsys.readouterr().out
    assert "phoenix: enabled=True" in output
    assert "endpoint_type=local" in output
    assert "sampling_rate=0.50" in output
    assert "manual ExperimentOS spans only; auto-instrumentation disabled" in output


def test_cli_validate_accepts_disabled_phoenix_configuration(capsys, monkeypatch) -> None:
    from packages.observability import cli

    monkeypatch.setattr(
        cli,
        "load_observability_settings",
        lambda: ObservabilitySettings(phoenix=PhoenixSettings(enabled=False)),
    )

    assert cli.main(["validate", "--provider", "phoenix"]) == 0

    assert "Phoenix tracing is disabled" in capsys.readouterr().out


def test_cli_validate_reports_missing_phoenix_dependencies(capsys, monkeypatch) -> None:
    from packages.observability import cli

    settings = ObservabilitySettings(
        phoenix=PhoenixSettings(
            enabled=True,
            endpoint="http://127.0.0.1:6006/v1/traces",
            project="experimentos-local",
        )
    )
    monkeypatch.setattr(cli, "load_observability_settings", lambda: settings)

    def failing_import(name: str):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(cli.importlib, "import_module", failing_import)

    assert cli.main(["validate", "--provider", "phoenix"]) == 1

    assert "Phoenix tracing is enabled but the optional dependencies are not installed." in (
        capsys.readouterr().out
    )


def test_cli_dry_run_redacts_sensitive_payloads_without_network_calls(
    capsys,
    monkeypatch,
) -> None:
    from packages.observability import cli

    settings = ObservabilitySettings(
        phoenix=PhoenixSettings(
            enabled=True,
            endpoint="http://127.0.0.1:6006/v1/traces",
            project="experimentos-local",
        )
    )
    monkeypatch.setattr(cli, "load_observability_settings", lambda: settings)
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: object())

    assert cli.main(["dry-run", "--provider", "phoenix"]) == 0

    output = capsys.readouterr().out
    assert '"authorization": "<redacted>"' in output
    assert '"prompt": "<omitted>"' in output
    assert '"retrieved_chunks": "<omitted>"' in output
    assert '"answer": "<omitted>"' in output


def test_cli_smoke_test_requires_explicit_enablement(capsys, monkeypatch) -> None:
    from packages.observability import cli

    monkeypatch.setattr(
        cli,
        "load_observability_settings",
        lambda: ObservabilitySettings(phoenix=PhoenixSettings(enabled=False)),
    )

    assert cli.main(["smoke-test", "--provider", "phoenix"]) == 1

    assert "Enable Phoenix tracing explicitly before running a smoke test." in (
        capsys.readouterr().out
    )


def test_cli_smoke_test_uses_selected_provider_and_flushes(capsys, monkeypatch) -> None:
    from packages.observability import cli

    settings = ObservabilitySettings(
        phoenix=PhoenixSettings(
            enabled=True,
            endpoint="http://127.0.0.1:6006/v1/traces",
            project="experimentos-local",
        )
    )
    provider = _LifecycleProvider()
    monkeypatch.setattr(cli, "load_observability_settings", lambda: settings)
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(cli, "resolve_observability_provider", lambda _settings: provider)

    assert cli.main(["smoke-test", "--provider", "phoenix"]) == 0

    output = capsys.readouterr().out
    assert "Smoke test emitted an observability trace for Phoenix." in output
    assert provider.flush_calls == 1
    assert provider.shutdown_calls == 1


def test_cli_status_reports_opentelemetry_runtime_details(capsys, monkeypatch) -> None:
    from packages.observability import cli

    settings = ObservabilitySettings(
        otel=OpenTelemetrySettings(
            enabled=True,
            exporter_type="otlp_http",
            endpoint="http://127.0.0.1:4318/v1/traces",
            service_name="experimentos-ai",
            service_version="0.1.0",
            trace_enabled=True,
            metrics_enabled=True,
            propagation_enabled=True,
            sampling_rate=0.5,
        )
    )
    monkeypatch.setattr(cli, "load_observability_settings", lambda: settings)
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: object())

    assert cli.main(["status", "--provider", "opentelemetry"]) == 0

    output = capsys.readouterr().out
    assert "opentelemetry: enabled=True" in output
    assert "service_name=experimentos-ai" in output
    assert "exporter_type=otlp_http" in output
    assert "endpoint_type=local" in output
    assert "trace_enabled=True" in output
    assert "metrics_enabled=True" in output
    assert "propagation=True" in output


def test_cli_dry_run_for_opentelemetry_redacts_sensitive_payloads(capsys, monkeypatch) -> None:
    from packages.observability import cli

    settings = ObservabilitySettings(
        otel=OpenTelemetrySettings(
            enabled=True,
            exporter_type="console",
            trace_enabled=True,
            metrics_enabled=True,
            service_name="experimentos-ai",
        )
    )
    monkeypatch.setattr(cli, "load_observability_settings", lambda: settings)
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: object())

    assert cli.main(["dry-run", "--provider", "opentelemetry"]) == 0

    output = capsys.readouterr().out
    assert "source_of_truth=ExperimentOS internal traces/metrics/reports" in output
    assert '"authorization": "<redacted>"' in output
    assert '"prompt": "<omitted>"' in output
    assert '"retrieved_chunks": "<omitted>"' in output
