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


def test_ci_workflow_generates_reports_without_granting_push_runs_comment_permissions() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "id: quality_gate" in workflow
    assert "id: ci_report" in workflow
    assert "packages.evals.cli ci-report build" in workflow
    assert '--base-ref "${{ github.base_ref }}"' in workflow
    assert '--head-ref "${{ github.head_ref }}"' in workflow
    assert "Restore AI quality gate result" in workflow
    assert "gate_exit_code" in workflow
    assert "report_exit_code" in workflow
    assert "pr-quality-comment:" in workflow
    assert "github.event_name == 'pull_request'" in workflow
    assert "pull-requests: write" in workflow
    assert "pull_request_target" not in workflow


def test_pr_reporting_documentation_covers_local_preview_and_fork_safety() -> None:
    document = Path("docs/phase3/pr_evaluation_reports.md").read_text(encoding="utf-8")

    assert "ci-report build" in document
    assert "fork" in document.lower()
    assert "pull_request_target" in document
    assert "<!-- experimentos-ai-quality-report -->" in document
