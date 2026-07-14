from __future__ import annotations

from pathlib import Path


def test_ci_workflow_declares_ai_quality_gate_and_offline_defaults() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "concurrency:" in workflow
    assert "cancel-in-progress: true" in workflow

    for job_name in (
        "format:",
        "lint:",
        "validate:",
        "unit:",
        "offline-eval-smoke:",
        "integration-db:",
        "ai-quality-gate:",
    ):
        assert job_name in workflow

    assert "pgvector/pgvector:pg16" in workflow
    assert "ASK_MODE: agent_workflow" in workflow
    assert "EMBEDDING_PROVIDER: fake" in workflow
    assert "LLM_PROVIDER: mock" in workflow
    assert "RAGAS_JUDGE_LLM_PROVIDER: none" in workflow
    assert "RAGAS_JUDGE_EMBEDDING_PROVIDER: none" in workflow
    assert "DEEPEVAL_JUDGE_PROVIDER: none" in workflow
    assert "PROMPT_EXPERIMENTS_ENABLED:" in workflow
    assert "--target agent_workflow" in workflow
    assert "tests/fixtures/ci/exp-001-payment-recommendation" in workflow
    assert "tests/test_ci_quality_gate.py" in workflow
    assert "tests/test_repository_hygiene.py" in workflow
    assert "tests/test_ragas_evaluation.py" in workflow
    assert "--policy-changed ${{ steps.policy_changes.outputs.changed || 'false' }}" in workflow
    assert "data/synthetic/experiments/exp-001-payment-recommendation" not in workflow
    assert "actions/upload-artifact@" in workflow
    assert "if: ${{ always() }}" in workflow
    assert "timeout-minutes:" in workflow
    assert "docker compose" not in workflow.lower()
