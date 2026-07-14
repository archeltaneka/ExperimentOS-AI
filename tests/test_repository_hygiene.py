from __future__ import annotations

import subprocess
from pathlib import Path


def test_gitignore_tracks_eval_inputs_and_ignores_runtime_outputs() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    ignored_paths = [
        "artifacts/run.json",
        "reports/evaluation.json",
        "reports/agent_evaluation.json",
        "reports/agent_e2e_evaluation.json",
        "docs/superpowers/plans/task.md",
        "docs/superpowers/specs/task.md",
        "data/synthetic/experiments/exp-001/metadata.json",
    ]
    tracked_paths = [
        "data/eval/qa_dataset.json",
        "data/eval/agent_dataset.json",
    ]

    for path in ignored_paths:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", path],
            cwd=repository_root,
            check=False,
        )
        assert result.returncode == 0, f"Expected {path} to be ignored"

    for path in tracked_paths:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", path],
            cwd=repository_root,
            check=False,
        )
        assert result.returncode != 0, f"Expected {path} not to be ignored"
