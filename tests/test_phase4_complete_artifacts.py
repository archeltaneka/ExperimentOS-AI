"""Rendering is derived, deterministic, and recursively safe."""


def test_render_twice_is_identical_and_workflow_is_private(tmp_path):
    from packages.evals.run_statistical_baseline import parse_args, run_statistical_baseline
    from packages.evals.statistical.reporting import (
        render_phase4_job_summary,
        render_statistical_baseline_markdown,
    )
    from packages.evals.statistical.workflow.telemetry import privacy_violations

    report = run_statistical_baseline(
        parse_args(
            [
                "--json-output",
                str(tmp_path / "statistical_baseline.json"),
                "--output",
                str(tmp_path / "statistical_baseline.md"),
            ]
        )
    )
    assert render_phase4_job_summary(report) == render_phase4_job_summary(report)
    assert render_statistical_baseline_markdown(report) == render_statistical_baseline_markdown(
        report
    )
    assert not privacy_violations(report.model_dump(mode="json"))
    assert "Database" in render_phase4_job_summary(report)
