"""Dependency state classification for optional advanced causal adapters."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from packages.experiments.analysis.causal.dowhy import dependency as dowhy_dependency
from packages.experiments.analysis.causal.econml import dependency as econml_dependency

DependencyModule = ModuleType


@pytest.mark.parametrize(
    ("dependency", "package_name", "load", "unsupported_python"),
    [
        (econml_dependency, "econml", econml_dependency.load_econml, "3.15.0"),
        (dowhy_dependency, "dowhy", dowhy_dependency.load_dowhy, "3.12.14"),
    ],
)
def test_missing_top_level_package_is_unavailable_even_on_unsupported_python(
    monkeypatch: pytest.MonkeyPatch,
    dependency: DependencyModule,
    package_name: str,
    load: Callable[[], object],
    unsupported_python: str,
) -> None:
    def missing(name: str) -> str:
        assert name == package_name
        raise dependency.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(dependency, "python_version", lambda: unsupported_python)
    monkeypatch.setattr(dependency.metadata, "version", missing)

    with pytest.raises(dependency.AdapterError) as captured:
        load()

    assert captured.value.code == "OPTIONAL_DEPENDENCY_UNAVAILABLE"


@pytest.mark.parametrize(
    ("dependency", "package_name", "package_version", "load"),
    [
        (econml_dependency, "econml", "0.17.0", econml_dependency.load_econml),
        (dowhy_dependency, "dowhy", "0.14", dowhy_dependency.load_dowhy),
    ],
)
def test_installed_package_with_broken_import_is_incompatible_without_secret_text(
    monkeypatch: pytest.MonkeyPatch,
    dependency: DependencyModule,
    package_name: str,
    package_version: str,
    load: Callable[[], object],
) -> None:
    secret = "customer_id=7391 private outcome=41.5"

    monkeypatch.setattr(dependency, "python_version", lambda: "3.13.7")
    monkeypatch.setattr(dependency.metadata, "version", lambda name: package_version)
    monkeypatch.setattr(dependency.metadata, "requires", lambda name: ())
    monkeypatch.setattr(
        dependency.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError(secret)),
    )

    with pytest.raises(dependency.AdapterError) as captured:
        load()

    assert captured.value.code == "INCOMPATIBLE_DEPENDENCY_RUNTIME"
    assert secret not in str(captured.value)
    assert package_name.lower() in str(captured.value).lower()


@pytest.mark.parametrize(
    ("dependency", "package_name", "package_version", "load"),
    [
        (econml_dependency, "econml", "0.17.0", econml_dependency.load_econml),
        (dowhy_dependency, "dowhy", "0.14", dowhy_dependency.load_dowhy),
    ],
)
def test_missing_transitive_dependency_is_incompatible_not_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    dependency: DependencyModule,
    package_name: str,
    package_version: str,
    load: Callable[[], object],
) -> None:
    def version(name: str) -> str:
        if name == package_name:
            return package_version
        raise dependency.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(dependency, "python_version", lambda: "3.13.7")
    monkeypatch.setattr(dependency.metadata, "version", version)
    monkeypatch.setattr(dependency.metadata, "requires", lambda name: ["missing-runtime>=1"])
    monkeypatch.setattr(
        dependency.importlib,
        "import_module",
        lambda name: pytest.fail("broken dependency closure must prevent import"),
    )

    with pytest.raises(dependency.AdapterError) as captured:
        load()

    assert captured.value.code == "INCOMPATIBLE_DEPENDENCY_RUNTIME"
