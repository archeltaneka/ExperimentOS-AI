"""Optional imports cannot break core or escape the adapter boundary."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_table
from tests.econml_fixtures import assert_owned_graph, dr_execution, linear_rows
from tests.hte_fixtures import effect_rows, hte_table


@pytest.mark.parametrize("hte", [False, True])
@pytest.mark.parametrize("exception", [ModuleNotFoundError, ImportError, OSError])
def test_optional_import_failures_return_explicit_owned_unavailable_state(
    monkeypatch, hte: bool, exception: type[Exception]
) -> None:
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, EconMLHTEAdapter

    original = importlib.import_module

    def blocked(name: str, *args, **kwargs):
        if name == "econml" or name.startswith("econml."):
            raise exception("sensitive row payload must not escape")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", blocked)
    adapter = (
        EconMLHTEAdapter()
        if hte
        else EconMLDMLAdapter(
            constant_effect_assumption=True,
        )
    )
    execution = dr_execution() if hte else dml_execution()
    table = hte_table(effect_rows()) if hte else dml_table(linear_rows())
    result = adapter.analyze(execution, table, provenance=provenance())
    reason = result.abstention_reason
    code = reason if isinstance(reason, str) else reason.code
    assert code == "OPTIONAL_DEPENDENCY_UNAVAILABLE"
    assert result.status.value == "abstained"
    assert "sensitive row" not in result.model_dump_json()
    assert_owned_graph(result)


def test_incompatible_econml_version_is_explicit(monkeypatch) -> None:
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, dependency

    original = dependency.metadata.version
    monkeypatch.setattr(
        dependency.metadata,
        "version",
        lambda name: "0.16.0" if name == "econml" else original(name),
    )
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(dml_execution(), dml_table(linear_rows()), provenance=provenance())
    assert result.abstention_reason.code == "INCOMPATIBLE_DEPENDENCY_RUNTIME"
    assert result.point_estimate is None


def test_future_interpreter_is_unsupported_without_narrowing_core(monkeypatch) -> None:
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, dependency

    monkeypatch.setattr(dependency, "python_version", lambda: "3.15.0")
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(dml_execution(), dml_table(linear_rows()), provenance=provenance())
    assert result.abstention_reason.code == "INCOMPATIBLE_DEPENDENCY_RUNTIME"


def test_core_and_all_baseline_imports_and_runs_work_when_econml_imports_are_blocked() -> None:
    script = """
import importlib, builtins
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name == 'econml' or name.startswith('econml.'):
        raise ImportError('EconML deliberately absent')
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, EconMLHTEAdapter
from packages.experiments.analysis.causal.dml import DoubleMachineLearningEstimator
from packages.experiments.analysis.causal.hte import HeterogeneousEffectEstimator
for module in ('causal.ipw', 'causal.propensity', 'causal.did', 'randomized', 'apps.api.main'):
    importlib.import_module(module if module.startswith('apps.') else
        'packages.experiments.analysis.' + module)
from tests.dml_fixtures import dml_execution, dml_table
from tests.hte_fixtures import effect_rows, hte_execution, hte_table
from tests.econml_fixtures import linear_rows
from tests.causal_identification_fixtures import provenance
assert DoubleMachineLearningEstimator().analyze(dml_execution(fold_count=4, seed=812),
    dml_table(linear_rows()), provenance=provenance()).status.value == 'completed'
assert HeterogeneousEffectEstimator().analyze(hte_execution(fold_count=4),
    hte_table(effect_rows()), provenance=provenance()).status.value == 'completed'
"""
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_incompatible_direct_dependency_is_explicit_before_import(monkeypatch):
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, dependency

    monkeypatch.setattr(
        dependency.metadata, "version", lambda name: "0.17.0" if name == "econml" else "1.10.0"
    )
    monkeypatch.setattr(dependency.metadata, "requires", lambda name: ["scikit-learn>=1.6,<1.10"])
    monkeypatch.setattr(
        dependency.importlib,
        "import_module",
        lambda name: pytest.fail("incompatible runtime imported"),
    )
    result = EconMLDMLAdapter(constant_effect_assumption=True).analyze(
        dml_execution(), dml_table(linear_rows()), provenance=provenance()
    )
    assert result.abstention_reason.code == "INCOMPATIBLE_DEPENDENCY_RUNTIME"
