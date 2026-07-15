from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_report_inputs(
    root: Path,
    *,
    policy_status: str = "pass",
    gate_status: str = "pass",
    missing_required: bool = False,
    optional_present: bool = True,
) -> None:
    phase3 = root / "phase3"
    _write_json(
        phase3 / "quality_policy.json",
        {
            "policy_version": "2026-07-13",
            "overall_status": policy_status,
            "category_results": {
                "Retrieval": {"name": "Retrieval", "status": policy_status, "metrics": []},
                "Factuality": {"name": "Factuality", "status": "pass", "metrics": []},
            },
            "metrics_evaluated": [
                {
                    "metric_id": "rag.average_citation_coverage",
                    "category": "Retrieval",
                    "observed_value": 1.0,
                    "threshold_value": 1.0,
                    "operator": "gte",
                    "status": policy_status,
                }
            ],
            "violations": [
                {
                    "metric_id": "factuality.findings.fabricated_revenue_or_roi",
                    "category": "Factuality",
                    "severity": "critical",
                    "status": "fail",
                    "message": "Observed value 1 did not satisfy lte 0.",
                    "source_path": "phase3/factuality_report.json",
                    "observed_value": 1,
                    "threshold_value": 0,
                }
            ]
            if policy_status == "fail"
            else [],
            "warnings": [],
            "skipped_metrics": [
                {
                    "metric_id": "ragas.answer_relevancy",
                    "category": "Answer Quality",
                    "message": "Judge metrics are disabled in offline mode.",
                }
            ],
        },
    )
    _write_json(
        phase3 / "ai_quality_gate.json",
        {
            "status": gate_status,
            "message": "gate result",
            "artifact_name": "ai-quality-gate-123",
            "fingerprint": {
                "ask_mode": "agent_workflow",
                "embedding_provider": "fake",
                "llm_provider": "mock",
                "external_judges_enabled": False,
                "live_provider_configured": False,
                "observability_export_enabled": False,
            },
            "command_results": [],
        },
    )
    required = [{"relative_path": "evaluation.json", "present": not missing_required}]
    optional = [
        {
            "relative_path": "phase3/prompt_experiments/example.json",
            "present": optional_present,
        }
    ]
    _write_json(
        phase3 / "artifact_manifest.json",
        {"artifact_root": str(root), "required_reports": required, "optional_reports": optional},
    )
    _write_json(
        root / "evaluation.json",
        {
            "summary": {
                "question_count": 2,
                "retrieval_success_rate": 1.0,
                "average_citation_coverage": 1.0,
                "average_retrieval_latency_ms": 12.0,
            },
            "dataset_version": "ci-v1",
        },
    )


def test_ci_quality_report_serializes_without_github_objects() -> None:
    from packages.evals.ci_reporting.models import CiQualityReport, ReportStatus

    payload = CiQualityReport.minimal(ReportStatus.FAIL, "2026-07-13").to_dict()

    assert payload["overall_status"] == "fail"
    assert "github" not in payload


def test_aggregator_copies_policy_failure_and_critical_finding(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import ReportMetadata

    _write_report_inputs(tmp_path, policy_status="fail", gate_status="quality_fail")

    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
    )

    assert report.overall_status == "fail"
    assert (
        report.critical_violations[0].metric_id == "factuality.findings.fabricated_revenue_or_roi"
    )
    assert report.execution.external_judge_used is False
    assert report.execution.live_provider_used is False
    assert report.skipped_metrics[0].metric_id == "ragas.answer_relevancy"


def test_aggregator_marks_missing_required_report_as_infrastructure_error(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import ReportMetadata

    _write_report_inputs(tmp_path, missing_required=True)

    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
    )

    assert report.overall_status == "infrastructure_error"
    assert report.failure_type == "missing_required_report"


def test_aggregator_keeps_missing_optional_report_visible(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import ReportMetadata

    _write_report_inputs(tmp_path, optional_present=False)

    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
    )

    assert report.overall_status == "pass"
    assert report.suites[-1].status == "skipped"


def test_pr_comment_has_marker_escapes_markdown_and_announces_truncation(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import RenderLimits, ReportMetadata
    from packages.evals.ci_reporting.renderer import render_pr_comment

    _write_report_inputs(tmp_path, policy_status="fail", gate_status="quality_fail")
    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
    )
    report = report.with_warnings(("unsafe | content", "second warning"))

    comment = render_pr_comment(report, limits=RenderLimits(max_warnings=1, max_characters=4000))

    assert "<!-- experimentos-ai-quality-report -->" in comment
    assert "unsafe \\| content" in comment
    assert "1 additional warning omitted" in comment


def test_renderer_does_not_announce_negative_omissions(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import ReportMetadata
    from packages.evals.ci_reporting.renderer import render_job_summary

    _write_report_inputs(tmp_path, policy_status="fail", gate_status="quality_fail")
    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
    )

    assert "additional critical finding omitted" not in render_job_summary(report)


def test_aggregator_marks_malformed_policy_report_as_infrastructure_error(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import ReportMetadata

    _write_report_inputs(tmp_path)
    (tmp_path / "phase3" / "quality_policy.json").write_text("{", encoding="utf-8")

    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
    )

    assert report.overall_status == "infrastructure_error"
    assert report.failure_type == "malformed_report"


def test_ci_report_cli_builds_json_and_comment_preview(tmp_path: Path, capsys) -> None:
    from packages.evals.run_ci_report import main

    _write_report_inputs(tmp_path)
    output = tmp_path / "phase3" / "pr_quality_report.json"

    assert main(["build", "--report-dir", str(tmp_path), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["overall_status"] == "pass"
    assert main(["render", "--input", str(output), "--format", "pr-comment"]) == 0
    assert "<!-- experimentos-ai-quality-report -->" in capsys.readouterr().out


def test_aggregator_reports_trusted_metric_delta_only_for_matching_versions(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import ReportMetadata

    _write_report_inputs(tmp_path)
    baseline = tmp_path / "baseline.json"
    _write_json(
        baseline,
        {
            "policy_version": "2026-07-13",
            "dataset_version": "ci-v1",
            "metrics": {"rag.average_citation_coverage": 0.8},
        },
    )

    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
        baseline_report=baseline,
    )

    delta = report.metric_deltas[0]
    assert delta.baseline_value == 0.8
    assert delta.absolute_delta == 0.19999999999999996
    assert delta.status == "pass"


def test_aggregator_suppresses_delta_for_dataset_version_mismatch(tmp_path: Path) -> None:
    from packages.evals.ci_reporting.aggregator import build_ci_quality_report
    from packages.evals.ci_reporting.models import ReportMetadata

    _write_report_inputs(tmp_path)
    baseline = tmp_path / "baseline.json"
    _write_json(
        baseline,
        {
            "policy_version": "2026-07-13",
            "dataset_version": "other-dataset",
            "metrics": {"rag.average_citation_coverage": 0.8},
        },
    )

    report = build_ci_quality_report(
        tmp_path,
        metadata=ReportMetadata(commit_sha="abc123", execution_mode="agent_workflow"),
        baseline_report=baseline,
    )

    assert report.metric_deltas[0].status == "unavailable"
