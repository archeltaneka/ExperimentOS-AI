from __future__ import annotations

from pathlib import Path


def test_ci_workflow_declares_two_tier_jobs_and_offline_defaults() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow

    for job_name in (
        "format:",
        "lint:",
        "validate:",
        "unit:",
        "offline-eval-smoke:",
        "integration-db:",
    ):
        assert job_name in workflow

    assert "pgvector/pgvector:pg16" in workflow
    assert "ASK_MODE: agent_workflow" in workflow
    assert "EMBEDDING_PROVIDER: fake" in workflow
    assert "LLM_PROVIDER: mock" in workflow
    assert "PROMPT_EXPERIMENTS_ENABLED:" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "docker compose" not in workflow.lower()
