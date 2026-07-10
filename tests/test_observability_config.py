from __future__ import annotations

import importlib

import pytest


def test_load_observability_settings_defaults_to_disabled(monkeypatch) -> None:
    from packages.observability.models import load_observability_settings

    monkeypatch.delenv("EXPERIMENTOS_LANGSMITH_ENABLED", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    settings = load_observability_settings()

    assert settings.enabled is False
    assert settings.project is None
    assert settings.sampling_rate == 0.0
    assert settings.trace_inputs is False
    assert settings.trace_outputs is False
    assert settings.redact_sensitive_data is True


def test_resolve_provider_returns_noop_when_disabled(monkeypatch) -> None:
    from packages.observability.factory import resolve_observability_provider
    from packages.observability.noop import NoOpObservabilityProvider

    monkeypatch.delenv("EXPERIMENTOS_LANGSMITH_ENABLED", raising=False)

    provider = resolve_observability_provider()

    assert isinstance(provider, NoOpObservabilityProvider)


def test_resolve_provider_raises_when_enabled_without_optional_dependency(monkeypatch) -> None:
    from packages.observability.factory import (
        ObservabilityConfigurationError,
        resolve_observability_provider,
    )

    monkeypatch.setenv("EXPERIMENTOS_LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "experimentos-test")

    original_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name.startswith("langsmith"):
            raise ModuleNotFoundError("No module named 'langsmith'")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(ObservabilityConfigurationError, match="langsmith"):
        resolve_observability_provider()


def test_observability_cli_validate_reports_disabled_configuration(capsys, monkeypatch) -> None:
    from packages.observability.cli import main

    monkeypatch.delenv("EXPERIMENTOS_LANGSMITH_ENABLED", raising=False)

    exit_code = main(["validate"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "disabled" in captured.out.lower()


def test_observability_cli_smoke_test_requires_explicit_enablement(
    capsys, monkeypatch, tmp_path
) -> None:
    from packages.observability.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EXPERIMENTOS_LANGSMITH_ENABLED", raising=False)

    exit_code = main(["smoke-test"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "enable" in captured.out.lower()

