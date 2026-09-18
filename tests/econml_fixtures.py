"""Independent adapter references and owned request construction."""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping, Sequence
from datetime import datetime

import pytest
from pydantic import BaseModel

requires_econml = pytest.mark.skipif(
    importlib.util.find_spec("econml") is None, reason="optional EconML environment required"
)


from packages.evals.statistical.advanced.references.econml import (  # noqa: F401, E402
    dr_execution,
    linear_rows,
)


def assert_owned_graph(value: object) -> None:
    """Reject hidden third-party objects, arrays, and exceptions recursively."""
    if isinstance(value, BaseModel):
        assert type(value).__module__.startswith("packages.experiments.analysis")
        for name in type(value).model_fields:
            assert_owned_graph(getattr(value, name))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            assert isinstance(key, str)
            assert_owned_graph(item)
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for item in value:
            assert_owned_graph(item)
    else:
        assert value is None or isinstance(value, str | int | float | bool | datetime)
