from pathlib import Path


def test_dowhy_documentation_states_required_causal_limits() -> None:
    text = Path("docs/phase4/dowhy_adapters.md").read_text(encoding="utf-8").lower()
    for statement in (
        "supplied assumptions, not learned truth",
        "conditional on the supplied graph",
        "does not prove causal validity",
        "specific perturbation",
        "does not replace experimentos causal contracts",
        "automated causal discovery is not supported",
    ):
        assert statement in text
