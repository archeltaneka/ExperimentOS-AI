from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.evals.policy.adapters import load_source
from packages.evals.policy.config import load_quality_policy
from packages.evals.policy.evaluator import PolicyEvaluator
from packages.evals.policy.models import (
    MetricThreshold,
    PolicySource,
    QualityPolicy,
    SeverityLevel,
)
from packages.evals.run_statistical_baseline import _policy_rule_evidence
from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
from packages.evals.statistical.models import CheckStatus, StatisticalCheck
from packages.evals.statistical.reporting import statistical_baseline_to_json


def _write_report(root: Path, **updates: object) -> Path:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    dataset = dataset.model_copy(
        update={"cases": tuple(c for c in dataset.cases if c.advanced is None)}
    )
    report = StatisticalBaselineEvaluator().evaluate(dataset)
    payload = json.loads(statistical_baseline_to_json(report))
    payload.update(updates)
    path = root / "phase4" / "statistical_baseline.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _policy(*metrics: MetricThreshold) -> QualityPolicy:
    return QualityPolicy(
        version="test-statistical-policy",
        sources={
            "statistics": PolicySource(
                source_id="statistics",
                path=Path("phase4/statistical_baseline.json"),
                format="statistical_baseline_json",
            )
        },
        metrics=metrics,
    )


def _metric(
    metric_id: str,
    *,
    value: float | int | str = 0,
    severity: SeverityLevel = "fail",
    required: bool = True,
) -> MetricThreshold:
    return MetricThreshold(
        metric_id=metric_id,
        source="statistics",
        category="Statistical Reliability",
        operator="eq",
        value=value,
        severity=severity,
        required=required,
    )


def test_statistical_adapter_exposes_structured_aggregate_metrics(tmp_path: Path) -> None:
    _write_report(tmp_path)
    source = PolicySource(
        source_id="statistics",
        path=Path("phase4/statistical_baseline.json"),
        format="statistical_baseline_json",
    )

    loaded = load_source(source, tmp_path)

    assert loaded is not None
    assert loaded.metrics["statistics.overall_status"].value == "pass"
    assert loaded.metrics["statistics.dataset_size"].value == 92
    assert loaded.metrics["statistics.cases_invalid"].value == 21
    assert loaded.metrics["statistics.cases_abstained"].value == 21
    assert loaded.metrics["statistics.failures.uncertainty"].value == 0
    assert loaded.metrics["statistics.failures.identification"].value == 0
    assert loaded.metrics["statistics.failures.estimand"].value == 0
    assert loaded.metrics["statistics.failures.provenance"].value == 0
    assert loaded.metrics["statistics.failures.heterogeneity_safety"].value == 0
    assert loaded.metrics["statistics.failures.determinism"].value == 0


def test_statistical_adapter_counts_heterogeneity_safety_failures(tmp_path: Path) -> None:
    path = _write_report(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["case_results"][0]["checks"].append(
        {
            "check_id": "direct_heterogeneity_evidence",
            "rule_id": "statistics.hte.direct_evidence",
            "dimension": "heterogeneity_safety",
            "status": "fail",
            "message": "Direct heterogeneity evidence is missing.",
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    source = PolicySource(
        source_id="statistics",
        path=Path("phase4/statistical_baseline.json"),
        format="statistical_baseline_json",
    )

    loaded = load_source(source, tmp_path)

    assert loaded is not None
    assert loaded.metrics["statistics.failures.heterogeneity_safety"].value == 1


def test_statistical_adapter_rejects_fractional_count_fields(tmp_path: Path) -> None:
    _write_report(tmp_path, cases_failed=0.9)
    source = PolicySource(
        source_id="statistics",
        path=Path("phase4/statistical_baseline.json"),
        format="statistical_baseline_json",
    )

    with pytest.raises(ValueError, match="cases_failed.*non-negative integer"):
        load_source(source, tmp_path)


def test_statistical_policy_passes_expected_invalid_and_abstained_cases(tmp_path: Path) -> None:
    _write_report(tmp_path)
    policy = _policy(
        _metric("statistics.overall_status", value="pass"),
        _metric("statistics.cases_invalid", value=21),
        _metric("statistics.cases_abstained", value=21),
        _metric("statistics.cases_failed"),
    )

    result = PolicyEvaluator(policy=policy, report_dir=tmp_path).evaluate()

    assert result.overall_status == "pass"
    assert not result.violations


def test_statistical_policy_classifies_blocking_and_advisory_outcomes(
    tmp_path: Path,
) -> None:
    path = _write_report(tmp_path)
    payload = json.loads(path.read_text())
    payload["case_results"][0]["checks"][0]["status"] = "fail"
    path.write_text(json.dumps(payload))
    policy = _policy(
        _metric("statistics.cases_failed"),
        _metric("statistics.cases_advisory", severity="warning"),
    )

    result = PolicyEvaluator(policy=policy, report_dir=tmp_path).evaluate()

    assert result.overall_status == "fail"
    assert result.violations[0].metric_id == "statistics.cases_failed"
    assert result.warnings[0].metric_id == "statistics.cases_advisory"


def test_statistical_policy_preserves_optional_missing_source_as_skipped(
    tmp_path: Path,
) -> None:
    policy = _policy(
        _metric("statistics.cases_failed", required=False),
    )

    result = PolicyEvaluator(policy=policy, report_dir=tmp_path).evaluate()

    assert result.overall_status == "skipped"
    assert result.skipped_metrics[0].metric_id == "statistics.cases_failed"
    assert result.skipped_metrics[0].observed_value is None


def test_central_policy_adds_statistical_rules_without_changing_phase3_rules() -> None:
    policy = load_quality_policy(Path("config/evaluation/quality_policy.yaml"))
    metrics = {metric.metric_id: metric for metric in policy.metrics}

    assert policy.sources["statistics"].format == "statistical_baseline_json"
    assert metrics["statistics.failures.reference_accuracy"].severity == "critical"
    assert metrics["statistics.failures.uncertainty"].severity == "critical"
    assert metrics["statistics.failures.identification"].severity == "critical"
    assert metrics["statistics.failures.estimand"].severity == "critical"
    assert metrics["statistics.failures.provenance"].severity == "critical"
    assert metrics["statistics.failures.heterogeneity_safety"].severity == "critical"
    assert metrics["statistics.minimum_cases_per_capability"].severity == "warning"
    assert metrics["rag.retrieval_success_rate"].value == 1.0
    assert metrics["rag.retrieval_success_rate"].severity == "fail"


def test_policy_rule_evidence_prefers_supporting_diagnostic_codes() -> None:
    report = StatisticalBaselineEvaluator().evaluate(
        load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    )
    target = next(
        case
        for case in report.case_results
        if case.case_id == "identification-post-treatment-adjustment"
    )
    failed_check = StatisticalCheck(
        check_id="post_treatment_adjustment",
        rule_id="statistics.identification.post_treatment_adjustment",
        dimension="identification",
        status=CheckStatus.FAIL,
        expected="absent",
        actual="present",
        message="Post-treatment adjustment was accepted.",
    )
    changed = target.model_copy(
        update={
            "checks": (*target.checks, failed_check),
            "diagnostic_codes": ("adjustment.post_treatment",),
        }
    )
    mutated = report.model_copy(
        update={
            "case_results": tuple(
                changed if case.case_id == target.case_id else case for case in report.case_results
            )
        }
    )

    assert _policy_rule_evidence("statistics.failures.identification", mutated) == (
        "identification-post-treatment-adjustment:adjustment.post_treatment",
        "identification-post-treatment-adjustment:statistics.identification.post_treatment_adjustment",
    )
