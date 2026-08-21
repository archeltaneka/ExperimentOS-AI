from __future__ import annotations

import inspect
from pathlib import Path

from packages.experiments.analysis import causal


def test_public_causal_contracts_are_experimentos_owned() -> None:
    public_classes = [
        value
        for name in causal.__all__
        if inspect.isclass(value := getattr(causal, name))
    ]
    assert public_classes
    assert all(
        item.__module__.startswith("packages.experiments.analysis")
        for item in public_classes
    )


def test_public_causal_package_has_no_vendor_or_graph_library_coupling() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in Path("packages/experiments/analysis/causal").glob("*.py")
    )
    assert "import econml" not in source
    assert "import dowhy" not in source
    assert "import networkx" not in source
    assert "statsmodels" not in source
