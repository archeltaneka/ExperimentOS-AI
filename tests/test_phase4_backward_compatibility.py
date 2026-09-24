"""Real old surfaces and existing final-gate orchestration remain compatible."""

from pathlib import Path
from types import SimpleNamespace


def test_compatibility_matrix_executes_old_surfaces_and_labels_external_checks():
    from packages.evals.statistical.workflow.compatibility import evaluate_compatibility

    results = {r.surface: r for r in evaluate_compatibility()}
    for surface in (
        "legacy_rag_api",
        "agent_workflow",
        "old_ask_api",
        "prompts",
        "phase3_policy",
        "factuality",
    ):
        assert results[surface].status == "pass", results[surface]
        assert results[surface].evidence_ids
    for surface in ("database", "langsmith", "phoenix"):
        assert results[surface].status == "skipped"
        assert results[surface].reason


def test_existing_ai_gate_runs_phase4_before_final_policy():
    from scripts import run_ai_quality_gate as gate

    commands = gate._build_commands(gate.parse_args([]))
    names = [c.name for c in commands]
    assert names.index("phase4_statistical_baseline") < names.index("quality_policy")
    assert gate._status_from_result("phase4_statistical_baseline", 1)[0] == "quality_fail"
    for name in (
        "statistical_baseline.json",
        "statistical_baseline.md",
        "quality_policy.json",
        "github_summary.md",
    ):
        assert Path("phase4") / name in gate.REQUIRED_REPORT_PATHS


def test_phase4_quality_failure_still_runs_final_policy(monkeypatch):
    from scripts import run_ai_quality_gate as gate

    commands = (
        gate.EvaluationCommand("phase4_statistical_baseline", ("phase4",), 1),
        gate.EvaluationCommand("quality_policy", ("policy",), 1),
    )
    seen = []
    monkeypatch.setattr(gate, "_build_commands", lambda args: commands)

    def run(argv, **kwargs):
        seen.append(argv[0])
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(gate.subprocess, "run", run)
    _, code, _ = gate._run_commands(gate.parse_args([]))
    assert seen == ["phase4", "policy"]
    assert code == 1


def test_existing_ci_report_does_not_hide_workflow_failure(tmp_path):
    import json

    from packages.evals.ci_reporting.aggregator import _statistical_suite

    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {
                "overall_status": "pass",
                "workflow": [
                    {
                        "family": "business",
                        "checks": {"integrity": {"status": "fail"}},
                    }
                ],
            }
        )
    )
    suite = _statistical_suite(path)
    assert suite.status == "fail"
    assert dict(suite.key_metrics)["Business impact"] == "fail"


def test_existing_ci_jobs_use_complete_and_optional_scopes():
    import shlex

    import yaml

    jobs = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())["jobs"]
    optional = [
        shlex.split(s["run"])
        for s in jobs["advanced-causal-optional"]["steps"]
        if "statistical-baseline" in s.get("run", "")
    ][0]
    assert optional[optional.index("--scope") + 1] == "optional-adapters"
    summary = next(
        s
        for s in jobs["offline-eval-smoke"]["steps"]
        if s.get("name") == "Publish Phase 4 statistical summary"
    )
    assert "always()" in summary["if"]
    assert "github_summary.md" in summary["run"]
    assert all(
        not arg.startswith(("analysis.failures.", "statistics.failures.")) for arg in optional
    )
