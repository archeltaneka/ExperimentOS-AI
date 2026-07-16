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
        ".superpowers/sdd/task-1-report.md",
        "docs/superpowers/plans/task.md",
        "docs/superpowers/specs/task.md",
        "data/synthetic/experiments/exp-001/metadata.json",
    ]
    tracked_paths = [
        "data/eval/qa_dataset.json",
        "data/eval/agent_dataset.json",
        "data/eval/ci_smoke_dataset.json",
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


def test_repository_docs_explain_reports_vs_artifacts() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    development = Path("docs/development.md").read_text(encoding="utf-8")
    dataset = Path("docs/dataset.md").read_text(encoding="utf-8")
    hygiene = Path("docs/repository_hygiene.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())

    assert "Use `artifacts/local/...` for routine local verification output." in normalized_readme
    assert (
        "Use `reports/` only when intentionally refreshing curated baseline/reference artifacts "
        "that belong in git."
    ) in normalized_readme
    assert "reports/                    Generated local evaluation reports" not in readme
    assert "artifacts/local" in readme
    assert "artifacts/local" in development
    assert "artifacts/local" in dataset
    assert "--output reports/phase3/baseline_report.md" in readme
    assert "--output reports/phase3/baseline_report.md" in development
    assert "--output reports/phase3/baseline_report.md" in dataset
    assert "`reports/`" in hygiene
    assert "`artifacts/`" in hygiene
    assert "`data/eval/`" in hygiene


def test_ruff_import_classification_keeps_migrations_stable_across_ci_environments() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    env = Path("migrations/env.py").read_text(encoding="utf-8")
    initial = Path("migrations/versions/20260703_0001_initial_schema.py").read_text(
        encoding="utf-8"
    )
    content = Path("migrations/versions/20260704_0002_add_document_content.py").read_text(
        encoding="utf-8"
    )

    assert 'known-third-party = ["alembic", "pgvector", "sqlalchemy"]' in pyproject
    assert "from alembic import context\nfrom sqlalchemy import engine_from_config, pool" in env
    assert "import sqlalchemy as sa\nfrom alembic import op\nfrom sqlalchemy.dialects" in initial
    assert "import sqlalchemy as sa\nfrom alembic import op" in content


def test_env_example_uses_explicit_offline_provider_defaults() -> None:
    example = Path(".env.example").read_text(encoding="utf-8")

    assert "EMBEDDING_PROVIDER=fake" in example
    assert "LLM_PROVIDER=mock" in example
    assert "EMBEDDING_PROVIDER=auto" not in example
    assert "LLM_PROVIDER=auto" not in example


def test_duplicate_httpx2_dependency_is_absent() -> None:
    project = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"httpx2' not in project


def test_phase3_closeout_docs_describe_strict_and_diagnostic_modes() -> None:
    closeout = Path("docs/phase3/phase3_closeout.md").read_text(encoding="utf-8")

    assert "uv run python scripts/verify_phase3.py" in closeout
    assert "--offline-only" in closeout
    assert "non-closeout diagnostic" in closeout.lower()
    assert "production-oriented portfolio system" in closeout
    assert "not proof of production deployment at scale" in closeout


def test_phase3_docs_do_not_retain_known_closeout_drift() -> None:
    baseline = Path("docs/phase3/reliability_baseline.md").read_text(encoding="utf-8")
    factuality = Path("docs/phase3/factuality_and_hallucination.md").read_text(encoding="utf-8")
    pr_reports = Path("docs/phase3/pr_evaluation_reports.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "CI enforcement is not implemented" not in baseline
    assert "no CI quality gate consumes the experiment recommendation yet" not in baseline
    assert "not connected to production blocking or CI gates" not in factuality
    assert "packages.evals.cli ci-report" not in pr_reports
    assert "Phoenix and\nOpenTelemetry are still out of scope" not in readme


def test_branch_protection_docs_keep_pr_reporting_informational() -> None:
    docs = Path("docs/phase3/github_actions.md").read_text(encoding="utf-8")

    assert "AI quality gate" in docs
    assert "PR reporting" in docs
    assert "not required" in docs
    for check in ("format", "lint", "unit", "integration-db", "ai-quality-gate"):
        assert f"`{check}`" in docs
