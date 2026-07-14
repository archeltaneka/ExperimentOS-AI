from __future__ import annotations

from pathlib import Path


def test_gitignore_tracks_eval_inputs_and_ignores_runtime_outputs() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    required_rules = [
        "artifacts/",
        "reports/evaluation.json",
        "reports/agent_evaluation.json",
        "reports/agent_e2e_evaluation.json",
        "docs/superpowers/plans/",
        "docs/superpowers/specs/",
        "data/*",
        "!data/eval/",
        "!data/eval/qa_dataset.json",
        "!data/eval/agent_dataset.json",
    ]

    for rule in required_rules:
        assert rule in gitignore
