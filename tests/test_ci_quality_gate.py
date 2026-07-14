from __future__ import annotations

import json
from pathlib import Path

import pytest


def _ci_env(**overrides: str) -> dict[str, str]:
    env = {
        "ASK_MODE": "agent_workflow",
        "EMBEDDING_PROVIDER": "fake",
        "LLM_PROVIDER": "mock",
        "PROMPT_EXPERIMENTS_ENABLED": "false",
        "EXPERIMENTOS_LANGSMITH_ENABLED": "false",
        "EXPERIMENTOS_PHOENIX_ENABLED": "false",
        "EXPERIMENTOS_OTEL_ENABLED": "false",
        "LANGSMITH_TRACING": "false",
        "OPENAI_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "RAGAS_JUDGE_LLM_PROVIDER": "none",
        "RAGAS_JUDGE_EMBEDDING_PROVIDER": "none",
        "DEEPEVAL_JUDGE_PROVIDER": "none",
        "DATABASE_URL": "postgresql+psycopg://ci:ci@localhost:5433/experimentos_ci",
    }
    env.update(overrides)
    return env


def test_validate_ci_environment_accepts_offline_defaults() -> None:
    from packages.evals.ci_quality_gate import validate_ci_environment

    fingerprint = validate_ci_environment(_ci_env())

    assert fingerprint.ask_mode == "agent_workflow"
    assert fingerprint.embedding_provider == "fake"
    assert fingerprint.llm_provider == "mock"
    assert fingerprint.external_judges_enabled is False
    assert fingerprint.live_provider_configured is False
    assert fingerprint.observability_export_enabled is False


def test_validate_ci_environment_rejects_live_provider_configuration() -> None:
    from packages.evals.ci_quality_gate import validate_ci_environment

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        validate_ci_environment(_ci_env(OPENAI_API_KEY="sk-test"))


def test_validate_ci_environment_rejects_non_fake_embedding_provider() -> None:
    from packages.evals.ci_quality_gate import validate_ci_environment

    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER"):
        validate_ci_environment(_ci_env(EMBEDDING_PROVIDER="openai"))


def test_validate_ci_environment_rejects_external_judge_provider() -> None:
    from packages.evals.ci_quality_gate import validate_ci_environment

    with pytest.raises(ValueError, match="DEEPEVAL_JUDGE_PROVIDER"):
        validate_ci_environment(_ci_env(DEEPEVAL_JUDGE_PROVIDER="openai"))


def test_validate_policy_invariants_enforces_zero_tolerance_rules() -> None:
    from packages.evals.ci_quality_gate import validate_policy_invariants
    from packages.evals.policy.config import load_quality_policy

    policy = load_quality_policy(Path("config/evaluation/quality_policy.yaml"))

    validate_policy_invariants(policy)


def test_validate_policy_invariants_rejects_weakened_critical_threshold(tmp_path: Path) -> None:
    from packages.evals.ci_quality_gate import validate_policy_invariants
    from packages.evals.policy.config import load_quality_policy

    policy_path = tmp_path / "quality_policy.yaml"
    policy_path.write_text(
        Path("config/evaluation/quality_policy.yaml")
        .read_text(encoding="utf-8")
        .replace(
            "metric_id: factuality.findings.fabricated_revenue_or_roi",
            "metric_id: factuality.findings.fabricated_revenue_or_roi",
        )
        .replace("value: 0\n    severity: critical", "value: 1\n    severity: critical", 1),
        encoding="utf-8",
    )
    policy = load_quality_policy(policy_path)

    with pytest.raises(ValueError, match="fabricated_revenue_or_roi"):
        validate_policy_invariants(policy)


def test_build_artifact_manifest_tracks_required_and_optional_reports(tmp_path: Path) -> None:
    from packages.evals.ci_quality_gate import build_artifact_manifest

    artifact_root = tmp_path / "artifacts"
    (artifact_root / "evaluation.md").parent.mkdir(parents=True, exist_ok=True)
    (artifact_root / "evaluation.md").write_text("# ok\n", encoding="utf-8")
    (artifact_root / "phase3" / "quality_policy.json").parent.mkdir(parents=True, exist_ok=True)
    (artifact_root / "phase3" / "quality_policy.json").write_text("{}\n", encoding="utf-8")

    manifest = build_artifact_manifest(
        artifact_root,
        required_paths=(
            Path("evaluation.md"),
            Path("phase3/quality_policy.json"),
            Path("agent_evaluation.md"),
        ),
        optional_paths=(
            Path("phase3/prompt_experiments/rag-answer-abstention-v1-v2.json"),
        ),
    )

    required = {artifact.relative_path: artifact.present for artifact in manifest.required_reports}
    optional = {artifact.relative_path: artifact.present for artifact in manifest.optional_reports}
    assert required["evaluation.md"] is True
    assert required["phase3/quality_policy.json"] is True
    assert required["agent_evaluation.md"] is False
    assert optional["phase3/prompt_experiments/rag-answer-abstention-v1-v2.json"] is False


def test_render_github_job_summary_includes_gate_status_details_and_artifact_name() -> None:
    from packages.evals.ci_quality_gate import (
        ArtifactManifest,
        ArtifactRecord,
        render_github_job_summary,
        validate_ci_environment,
    )

    fingerprint = validate_ci_environment(_ci_env())
    policy_payload = {
        "policy_version": "2026-07-14",
        "overall_status": "fail",
        "category_results": {
            "Workflow": {"status": "fail"},
            "Factuality": {"status": "pass"},
        },
        "violations": [
            {
                "metric_id": "agent_e2e.default_agent_workflow_coverage",
                "severity": "critical",
                "message": "Observed value `0.0` did not satisfy `gte 1.0`.",
            }
        ],
        "warnings": [
            {
                "metric_id": "rag.average_retrieval_latency_ms",
                "severity": "warning",
                "message": "Observed value `42` did not satisfy `lte 10`.",
            }
        ],
        "skipped_metrics": [
            {
                "metric_id": "deepeval.answer_relevancy.average_score",
                "message": "Judge metrics are disabled in offline mode.",
            }
        ],
    }
    manifest = ArtifactManifest(
        artifact_root="artifacts/ci/ai-quality",
        required_reports=(
            ArtifactRecord(relative_path="evaluation.md", present=True),
            ArtifactRecord(relative_path="agent_evaluation.md", present=True),
        ),
        optional_reports=(
            ArtifactRecord(
                relative_path="phase3/prompt_experiments/rag-answer-abstention-v1-v2.json",
                present=False,
            ),
        ),
    )

    summary = render_github_job_summary(
        policy_payload,
        fingerprint=fingerprint,
        manifest=manifest,
        artifact_name="ai-quality-gate-1234",
        policy_changed=True,
    )

    assert "Overall quality status: fail" in summary
    assert "Policy version: `2026-07-14`" in summary
    assert "Workflow: fail" in summary
    assert "agent_e2e.default_agent_workflow_coverage" in summary
    assert "deepeval.answer_relevancy.average_score" in summary
    assert "Artifact bundle: `ai-quality-gate-1234`" in summary
    assert "External judges used: no" in summary
    assert "Live providers called: no" in summary
    assert "Quality policy file changed in this revision." in summary


def test_ci_quality_gate_result_json_round_trips(tmp_path: Path) -> None:
    from packages.evals.ci_quality_gate import (
        ArtifactManifest,
        ArtifactRecord,
        CiEnvironmentFingerprint,
        GateResult,
        write_gate_result,
    )

    result = GateResult(
        status="quality_fail",
        message="Blocking policy violations were detected.",
        artifact_name="ai-quality-gate-1234",
        fingerprint=CiEnvironmentFingerprint(
            ask_mode="agent_workflow",
            embedding_provider="fake",
            llm_provider="mock",
            prompt_experiments_enabled=False,
            external_judges_enabled=False,
            live_provider_configured=False,
            observability_export_enabled=False,
        ),
        manifest=ArtifactManifest(
            artifact_root="artifacts/ci/ai-quality",
            required_reports=(ArtifactRecord(relative_path="evaluation.md", present=True),),
            optional_reports=(),
        ),
        command_results=(),
    )

    output = tmp_path / "gate_result.json"
    write_gate_result(output, result)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "quality_fail"
    assert payload["artifact_name"] == "ai-quality-gate-1234"
    assert payload["fingerprint"]["embedding_provider"] == "fake"
