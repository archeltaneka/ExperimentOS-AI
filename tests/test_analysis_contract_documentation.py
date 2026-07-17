from __future__ import annotations

import importlib
import inspect
from enum import Enum
from pathlib import Path

from packages.experiments import analysis
from packages.experiments.analysis import ContractModel

ANALYSIS_PACKAGE = Path("packages/experiments/analysis")


def _is_public_runtime_contract(value: object) -> bool:
    return inspect.isclass(value) and (issubclass(value, ContractModel) or issubclass(value, Enum))


def test_every_public_analysis_module_has_a_useful_docstring() -> None:
    missing = []
    for path in sorted(ANALYSIS_PACKAGE.glob("*.py")):
        module_name = f"packages.experiments.analysis.{path.stem}"
        module = importlib.import_module(module_name)
        if not inspect.getdoc(module):
            missing.append(module_name)

    assert not missing, f"public analysis modules without docstrings: {missing}"


def test_every_exported_analysis_model_and_enum_has_a_useful_docstring() -> None:
    missing = []
    for name in analysis.__all__:
        value = getattr(analysis, name)
        if (
            _is_public_runtime_contract(value)
            and value.__module__.startswith("packages.experiments.analysis")
            and not (value.__doc__ and value.__doc__.strip())
        ):
            missing.append(name)

    assert not missing, f"public analysis contracts without docstrings: {missing}"
