"""Private lazy optional imports and installed-runtime compatibility checks."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from importlib import metadata
from platform import python_version
from types import ModuleType

from packaging.requirements import Requirement
from packaging.version import Version

from ..advanced.models import AdvancedFailureCode


class AdapterError(ValueError):
    """Owned diagnostic context; never includes third-party exception messages."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EconMLBackend:
    dml: ModuleType
    dr: ModuleType
    inference: ModuleType
    version: str


def load_econml() -> EconMLBackend:
    """Check installation metadata before importing optional compiled implementations."""
    try:
        installed = metadata.version("econml")
    except metadata.PackageNotFoundError:
        raise AdapterError(
            AdvancedFailureCode.OPTIONAL_DEPENDENCY_UNAVAILABLE,
            "Optional EconML is not installed.",
        ) from None
    except Exception:
        raise AdapterError(
            AdvancedFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
            "The installed EconML runtime could not be validated.",
        ) from None

    try:
        runtime = Version(python_version())
        if runtime.release[:2] not in ((3, 12), (3, 13), (3, 14)):
            raise AdapterError(
                AdvancedFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
                "This adapter supports Python 3.12 through 3.14 only.",
            )
        if Version(installed) != Version("0.17.0"):
            raise AdapterError(
                AdvancedFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
                "This adapter requires the verified EconML 0.17.0 implementation.",
            )
        for raw in metadata.requires("econml") or ():
            requirement = Requirement(raw)
            if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
                continue
            if Version(metadata.version(requirement.name)) not in requirement.specifier:
                raise AdapterError(
                    AdvancedFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
                    "Installed EconML dependency versions do not satisfy its runtime contract.",
                )
        return EconMLBackend(
            dml=importlib.import_module("econml.dml"),
            dr=importlib.import_module("econml.dr"),
            inference=importlib.import_module("econml.inference"),
            version=installed,
        )
    except AdapterError:
        raise
    except Exception:
        raise AdapterError(
            AdvancedFailureCode.INCOMPATIBLE_DEPENDENCY_RUNTIME,
            "The installed EconML runtime is incompatible or could not be imported.",
        ) from None
