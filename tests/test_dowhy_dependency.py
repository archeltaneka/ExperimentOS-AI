from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.dowhy import dependency
from packages.experiments.analysis.causal.dowhy.dependency import AdapterError


def test_python_312_is_incompatible_before_import(monkeypatch) -> None:
    monkeypatch.setattr(dependency.metadata, "version", lambda name: "0.14")
    monkeypatch.setattr(dependency, "python_version", lambda: "3.12.14")
    monkeypatch.setattr(
        dependency.importlib,
        "import_module",
        lambda name: pytest.fail("DoWhy must not import on Python 3.12"),
    )
    with pytest.raises(AdapterError) as captured:
        dependency.load_dowhy()
    assert captured.value.code == "INCOMPATIBLE_DEPENDENCY_RUNTIME"
