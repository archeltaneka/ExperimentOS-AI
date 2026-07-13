from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_base_reports(report_dir: Path) -> None:
    (report_dir / "phase3").mkdir(parents=True, exist_ok=True)
    (report_dir / "evaluation.md").write_text(
        "\n".join(
            [
                "# Evaluation Harness Report",
                "",
                "## Summary",
                "",
                "- Questions evaluated: 62",
                "- Retrieval success rate: 100.0%",
                "- Average citation coverage: 100.0%",
                "- Average retrieval latency: 50.9 ms",
                "- Average LLM latency: 0.0 ms",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "agent_evaluation.md").write_text(
        "\n".join(
            [
                "# Agent Workflow Evaluation Report",
                "",
                "## Summary",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                "| Samples evaluated | 8 |",
                "| Pass count | 8 |",
                "| Fail count | 0 |",
                "| Workflow success rate | 100.0% |",
                "| Average workflow latency | 2.7 ms |",
                "| Average trace completeness | 100.0% |",
                "| Planner intent accuracy | 100.0% |",
                "| Required agent routing accuracy | 100.0% |",
                "| Citation coverage | 100.0% |",
                "| Decision recommendation coverage | 100.0% |",
                "",
                "## Tool Usage",
                "",
                "- Total tool calls: 25",
                "- Total tool failures: 0",
                "- Average tool calls per sample: 3.12",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "agent_e2e_evaluation.md").write_text(
        "\n".join(
            [
                "# Agent Workflow E2E Evaluation Report",
                "",
                "## Summary",
                "",
                "- Total test/eval cases: 11",
                "- Pass/fail summary: 11 passed, 0 failed",
                "- Default agent workflow coverage: 100.0%",
                "- Legacy fallback coverage: 100.0%",
                "- Intent accuracy: 100.0%",
                "- Required agent routing accuracy: 100.0%",
                "- Citation coverage: 100.0%",
                "- Decision coverage: 100.0%",
                "- Executive summary coverage: 100.0%",
                "- Approval status coverage: 100.0%",
                "- Average workflow latency: 8.8 ms",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "phase3" / "ragas_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-10T00:00:00Z",
                "metric_results": [
                    {
                        "name": "id_based_context_precision",
                        "status": "computed",
                        "average_score": 1.0,
                        "reason": None,
                    },
                    {
                        "name": "id_based_context_recall",
                        "status": "computed",
                        "average_score": 1.0,
                        "reason": None,
                    },
                    {
                        "name": "answer_relevancy",
                        "status": "skipped",
                        "average_score": None,
                        "reason": "judge llm provider `none` does not enable RAGAS judge metrics",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "phase3" / "deepeval_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-10T00:00:00Z",
                "evaluation_mode": "offline",
                "metric_results": [
                    {
                        "metric_name": "routing_accuracy",
                        "score": 1.0,
                        "threshold": 1.0,
                        "passed": True,
                        "skipped": False,
                        "skip_reason": None,
                        "error": None,
                    },
                    {
                        "metric_name": "trace_completeness",
                        "score": 1.0,
                        "threshold": 1.0,
                        "passed": True,
                        "skipped": False,
                        "skip_reason": None,
                        "error": None,
                    },
                    {
                        "metric_name": "answer_relevancy",
                        "score": None,
                        "threshold": 0.5,
                        "passed": None,
                        "skipped": True,
                        "skip_reason": (
                            "Judge metrics are disabled in offline mode to avoid implicit "
                            "live provider calls."
                        ),
                        "error": None,
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "phase3" / "prompt_regression.json").write_text(
        json.dumps(
            {
                "prompt_id": "rag.answer",
                "summary": {
                    "cases_run": 63,
                    "regressions": 0,
                    "improvements": 0,
                    "unchanged": 63,
                    "failures": 0,
                    "skipped": 0,
                    "passed": True,
                },
                "metrics": [
                    {
                        "name": "prompt_rendering_success",
                        "baseline": 1.0,
                        "candidate": 1.0,
                        "delta": 0.0,
                        "regressions": 0,
                        "improvements": 0,
                    },
                    {
                        "name": "legacy_fallback_compatibility",
                        "baseline": 1.0,
                        "candidate": 1.0,
                        "delta": 0.0,
                        "regressions": 0,
                        "improvements": 0,
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "phase3" / "factuality_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-10T00:00:00Z",
                "target": "all",
                "mode": "offline",
                "policy_result": {
                    "status": "pass",
                    "reasons": [],
                    "finding_counts": {},
                    "severity_counts": {},
                },
                "findings_by_category": {
                    "fabricated_revenue_or_roi": 0,
                    "fabricated_statistical_significance": 0,
                    "citation_missing": 0,
                    "citation_does_not_support_claim": 0,
                    "answer_generated_when_abstention_was_expected": 0,
                },
                "findings_by_severity": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                },
                "case_status_counts": {
                    "pass": 10,
                    "warning": 0,
                    "fail": 0,
                    "skipped": 0,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_policy(path: Path, body: str) -> Path:
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def _base_policy_yaml() -> str:
    return """
version: "2026-07-13"
sources:
  rag:
    path: evaluation.md
    format: rag_markdown
  agent:
    path: agent_evaluation.md
    format: agent_markdown
  agent_e2e:
    path: agent_e2e_evaluation.md
    format: agent_e2e_markdown
  ragas:
    path: phase3/ragas_report.json
    format: ragas_json
  deepeval:
    path: phase3/deepeval_report.json
    format: deepeval_json
  prompt_regression:
    path: phase3/prompt_regression.json
    format: prompt_regression_json
  factuality:
    path: phase3/factuality_report.json
    format: factuality_json
metrics:
  - metric_id: rag.retrieval_success_rate
    source: rag
    category: Retrieval
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: rag.average_citation_coverage
    source: rag
    category: Retrieval
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: agent.routing_accuracy
    source: agent
    category: Workflow
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: agent.trace_completeness
    source: agent
    category: Workflow
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: agent_e2e.default_agent_workflow_coverage
    source: agent_e2e
    category: Workflow
    operator: gte
    value: 1.0
    severity: critical
    required: true
  - metric_id: agent_e2e.legacy_fallback_coverage
    source: agent_e2e
    category: Workflow
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: ragas.id_based_context_precision
    source: ragas
    category: Retrieval
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: ragas.answer_relevancy
    source: ragas
    category: Answer Quality
    operator: gte
    value: 0.5
    severity: warning
    required: false
  - metric_id: deepeval.routing_accuracy.average_score
    source: deepeval
    category: Workflow
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: deepeval.answer_relevancy.average_score
    source: deepeval
    category: Answer Quality
    operator: gte
    value: 0.5
    severity: warning
    required: false
  - metric_id: prompt_regression.summary.pass_rate
    source: prompt_regression
    category: Prompt
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: prompt_regression.metric.prompt_rendering_success.candidate
    source: prompt_regression
    category: Prompt
    operator: gte
    value: 1.0
    severity: fail
    required: true
  - metric_id: factuality.findings.fabricated_revenue_or_roi
    source: factuality
    category: Factuality
    operator: lte
    value: 0
    severity: critical
    required: true
  - metric_id: factuality.findings.answer_generated_when_abstention_was_expected
    source: factuality
    category: Factuality
    operator: lte
    value: 0
    severity: fail
    required: true
  - metric_id: rag.average_retrieval_latency_ms
    source: rag
    category: Reliability
    operator: lte
    value: 3000
    severity: warning
    required: true
"""


def test_load_quality_policy_parses_yaml_and_threshold_fields(tmp_path: Path) -> None:
    from packages.evals.policy.config import load_quality_policy

    policy_path = _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())

    policy = load_quality_policy(policy_path)

    assert policy.version == "2026-07-13"
    assert policy.sources["rag"].format == "rag_markdown"
    assert any(metric.metric_id == "rag.retrieval_success_rate" for metric in policy.metrics)
    optional_metric = next(metric for metric in policy.metrics if metric.required is False)
    assert optional_metric.metric_id == "ragas.answer_relevancy"
    assert optional_metric.severity == "warning"


def test_load_quality_policy_rejects_invalid_threshold_operator(tmp_path: Path) -> None:
    from packages.evals.policy.config import load_quality_policy

    policy_path = _write_policy(
        tmp_path / "quality_policy.yaml",
        """
version: "2026-07-13"
sources:
  rag:
    path: evaluation.md
    format: rag_markdown
metrics:
  - metric_id: rag.retrieval_success_rate
    source: rag
    category: Retrieval
    operator: between
    value: 1.0
    severity: fail
    required: true
""",
    )

    with pytest.raises(ValueError, match="operator"):
        load_quality_policy(policy_path)


def test_quality_policy_evaluator_passes_and_tracks_skipped_optional_metrics(
    tmp_path: Path,
) -> None:
    from packages.evals.policy.config import load_quality_policy
    from packages.evals.policy.evaluator import PolicyEvaluator

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    policy = load_quality_policy(
        _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())
    )

    result = PolicyEvaluator(policy=policy, report_dir=report_dir).evaluate()

    assert result.overall_status == "pass"
    assert result.category_results["Retrieval"].status == "pass"
    assert result.category_results["Workflow"].status == "pass"
    assert result.category_results["Prompt"].status == "pass"
    skipped_ids = {metric.metric_id for metric in result.skipped_metrics}
    assert "ragas.answer_relevancy" in skipped_ids
    assert "deepeval.answer_relevancy.average_score" in skipped_ids


def test_quality_policy_evaluator_warns_for_warning_only_thresholds(tmp_path: Path) -> None:
    from packages.evals.policy.config import load_quality_policy
    from packages.evals.policy.evaluator import PolicyEvaluator

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    policy = load_quality_policy(
        _write_policy(
            tmp_path / "quality_policy.yaml",
            _base_policy_yaml().replace("value: 3000", "value: 10"),
        )
    )

    result = PolicyEvaluator(policy=policy, report_dir=report_dir).evaluate()

    assert result.overall_status == "warning"
    assert result.category_results["Reliability"].status == "warning"
    assert any(
        violation.metric_id == "rag.average_retrieval_latency_ms" for violation in result.warnings
    )


def test_quality_policy_evaluator_fails_for_critical_metric_violations(tmp_path: Path) -> None:
    from packages.evals.policy.config import load_quality_policy
    from packages.evals.policy.evaluator import PolicyEvaluator

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    payload = json.loads(
        (report_dir / "phase3" / "factuality_report.json").read_text(encoding="utf-8")
    )
    payload["policy_result"]["status"] = "fail"
    payload["findings_by_category"]["fabricated_revenue_or_roi"] = 1
    (report_dir / "phase3" / "factuality_report.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    policy = load_quality_policy(
        _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())
    )

    result = PolicyEvaluator(policy=policy, report_dir=report_dir).evaluate()

    assert result.overall_status == "fail"
    assert result.category_results["Factuality"].status == "fail"
    critical_ids = {
        violation.metric_id for violation in result.violations if violation.severity == "critical"
    }
    assert "factuality.findings.fabricated_revenue_or_roi" in critical_ids


def test_quality_policy_evaluator_marks_missing_required_report_as_failure(tmp_path: Path) -> None:
    from packages.evals.policy.config import load_quality_policy
    from packages.evals.policy.evaluator import PolicyEvaluator

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    (report_dir / "phase3" / "deepeval_report.json").unlink()
    policy = load_quality_policy(
        _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())
    )

    result = PolicyEvaluator(policy=policy, report_dir=report_dir).evaluate()

    assert result.overall_status == "fail"
    assert any(
        violation.metric_id == "deepeval.routing_accuracy.average_score"
        and "missing source report" in violation.message.lower()
        for violation in result.violations
    )


def test_quality_policy_evaluator_fails_loudly_on_malformed_report(tmp_path: Path) -> None:
    from packages.evals.policy.config import load_quality_policy
    from packages.evals.policy.evaluator import PolicyEvaluator

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    (report_dir / "phase3" / "ragas_report.json").write_text("{not-json}\n", encoding="utf-8")
    policy = load_quality_policy(
        _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())
    )

    with pytest.raises(ValueError, match="ragas"):
        PolicyEvaluator(policy=policy, report_dir=report_dir).evaluate()


def test_quality_policy_evaluator_treats_missing_factuality_count_keys_as_zero(
    tmp_path: Path,
) -> None:
    from packages.evals.policy.config import load_quality_policy
    from packages.evals.policy.evaluator import PolicyEvaluator

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    payload = json.loads(
        (report_dir / "phase3" / "factuality_report.json").read_text(encoding="utf-8")
    )
    payload["findings_by_category"] = {
        "answer_generated_when_abstention_was_expected": 0,
    }
    (report_dir / "phase3" / "factuality_report.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    policy = load_quality_policy(
        _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())
    )

    result = PolicyEvaluator(policy=policy, report_dir=report_dir).evaluate()

    assert result.overall_status == "pass"
    assert not any(
        violation.metric_id == "factuality.findings.fabricated_revenue_or_roi"
        for violation in result.violations
    )


def test_quality_policy_renderers_include_status_thresholds_and_violations(tmp_path: Path) -> None:
    from packages.evals.policy.config import load_quality_policy
    from packages.evals.policy.evaluator import PolicyEvaluator
    from packages.evals.policy.report import (
        quality_policy_report_to_json,
        render_quality_policy_report,
    )

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    payload = json.loads(
        (report_dir / "phase3" / "factuality_report.json").read_text(encoding="utf-8")
    )
    payload["policy_result"]["status"] = "fail"
    payload["findings_by_category"]["answer_generated_when_abstention_was_expected"] = 2
    (report_dir / "phase3" / "factuality_report.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    policy = load_quality_policy(
        _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())
    )
    result = PolicyEvaluator(policy=policy, report_dir=report_dir).evaluate()

    markdown = render_quality_policy_report(result)
    json_payload = json.loads(quality_policy_report_to_json(result))

    assert "# Phase 3 Quality Policy Report" in markdown
    assert "answer_generated_when_abstention_was_expected" in markdown
    assert json_payload["overall_status"] == "fail"
    assert json_payload["policy_version"] == "2026-07-13"


def test_quality_policy_cli_writes_reports_and_enforces_exit_modes(
    tmp_path: Path,
) -> None:
    from packages.evals.run_quality_policy import main, parse_args

    report_dir = tmp_path / "reports"
    _write_base_reports(report_dir)
    payload = json.loads(
        (report_dir / "phase3" / "factuality_report.json").read_text(encoding="utf-8")
    )
    payload["policy_result"]["status"] = "fail"
    payload["findings_by_category"]["answer_generated_when_abstention_was_expected"] = 1
    (report_dir / "phase3" / "factuality_report.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    policy_path = _write_policy(tmp_path / "quality_policy.yaml", _base_policy_yaml())

    args = parse_args(
        [
            "--policy",
            str(policy_path),
            "--report-dir",
            str(report_dir),
        ]
    )
    exit_code = main(args=args)

    assert exit_code == 1
    assert (report_dir / "phase3" / "quality_policy.md").is_file()
    assert (report_dir / "phase3" / "quality_policy.json").is_file()

    strict_args = parse_args(
        [
            "--policy",
            str(policy_path),
            "--report-dir",
            str(report_dir),
            "--warn-only",
        ]
    )
    assert main(args=strict_args) == 0
