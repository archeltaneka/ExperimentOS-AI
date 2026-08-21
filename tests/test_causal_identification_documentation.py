from __future__ import annotations

from pathlib import Path


def test_causal_identification_documentation_records_required_boundaries() -> None:
    documentation = Path("docs/phase4/causal_identification_contracts.md").read_text(
        encoding="utf-8"
    )
    required = (
        "Identification vs estimation",
        "Estimands",
        "Variable roles",
        "Measurement timing",
        "Adjustment sets",
        "Causal graph",
        "Assumptions",
        "Identification statuses",
        "Evidence limitations",
        "Post-treatment leakage",
        "ATE",
        "ATT",
        "Difference-in-Differences",
        "Heterogeneous effects",
        "Third-party independence",
        "Limitations",
        "Identified does not mean causality proven.",
        "No causal effects are computed",
        "No propensity scores are fit",
        "No graph discovery is performed",
        "No DoWhy or EconML dependency is introduced",
    )
    for text in required:
        assert text in documentation
