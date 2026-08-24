from __future__ import annotations

from pathlib import Path


def test_did_documentation_states_supported_design_and_limitations() -> None:
    documentation = Path("docs/phase4/difference_in_differences.md").read_text(encoding="utf-8")
    required_statements = (
        "ATT_DiD",
        "not just a before/after comparison",
        "parallel trends is an assumption",
        "does not prove parallel trends",
        "staggered adoption is unsupported",
        "No event-study implementation exists",
        "No workflow integration exists",
        "cluster-robust",
        "complete two-period panel",
    )

    for statement in required_statements:
        assert statement in documentation
