"""Documentation guardrails for the deliberately bounded DML design."""

from __future__ import annotations

from pathlib import Path


def test_dml_documentation_states_identification_and_scope_limits() -> None:
    documentation = Path("docs/phase4/double_machine_learning.md").read_text(encoding="utf-8")

    for required in (
        "DML does not remove unmeasured confounding",
        "Same-fold fitting and scoring is forbidden",
        "Good predictive performance does not prove",
        "Severe overlap failures abstain",
        "no IV-DML",
        "continuous or multiple treatment",
        "EconML",
        "DoWhy",
        "no epsilon is added",
    ):
        assert required in documentation
