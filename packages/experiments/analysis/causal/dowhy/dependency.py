"""Lazy optional DoWhy runtime boundary."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from importlib import metadata
from platform import python_version
from typing import Any

from packaging.requirements import Requirement
from packaging.version import Version

from .models import DoWhyFailureCode


class AdapterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DoWhyBackend:
    CausalModel: Any
    version: str


def load_dowhy() -> DoWhyBackend:
    try:
        installed = metadata.version("dowhy")
    except metadata.PackageNotFoundError:
        raise AdapterError(
            DoWhyFailureCode.OPTIONAL_DEPENDENCY_UNAVAILABLE,
            "Optional DoWhy is not installed.",
        ) from None
    except Exception:
        raise AdapterError(
            DoWhyFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
            "The installed DoWhy runtime could not be validated.",
        ) from None

    try:
        runtime = Version(python_version())
        if runtime.release[:2] != (3, 13):
            raise AdapterError(
                DoWhyFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
                "The verified DoWhy adapter runtime is Python 3.13 only.",
            )
        if Version(installed) != Version("0.14"):
            raise AdapterError(
                DoWhyFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
                "The verified adapter requires DoWhy 0.14.",
            )
        for raw in metadata.requires("dowhy") or ():
            requirement = Requirement(raw)
            if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
                continue
            if Version(metadata.version(requirement.name)) not in requirement.specifier:
                raise AdapterError(
                    DoWhyFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
                    "Installed dependencies do not satisfy the DoWhy runtime contract.",
                )
        module = importlib.import_module("dowhy")
        return DoWhyBackend(CausalModel=module.CausalModel, version=installed)
    except AdapterError:
        raise
    except Exception:
        raise AdapterError(
            DoWhyFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
            "The installed DoWhy runtime is incompatible or could not be imported.",
        ) from None
